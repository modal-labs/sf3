import time
import uuid
import warnings
from math import ceil

import modal
from modal_training_gym import (
    MultimodalDataset,
    Qwen3_VL_8B,
    TrainConfig,
)
from modal_training_gym.common import hf_secrets
from modal_training_gym.common.checkpoint import (
    Checkpoint,
    CheckpointType,
    list_checkpoints,
)
from modal_training_gym.common.wandb import WandbConfig
from modal_training_gym.train_recipes.slime_recipe import Qwen3_VL_8b_Recipe

from src.serve import MODELS, POLICY_MODEL_KEY, qwen3_vl_8b
from src.utils import MAX_CPU_DIFFICULTY, MAX_TOKENS

from .rollout import (
    OPPONENT_SERVER_APP_NAME,
    build_rollout_image,
    parse_opponent,
    sf3_generate,
    sf3_group_reward_post_process,
    sf3_rm,
)

APP_NAME = "sf3-train"
app = modal.App(APP_NAME)

WANDB_PROJECT = "sf3-train-qwen3-vl-8b"
WANDB_ENTITY = "andrewhinh"

BASE_OPPONENT = f"model:{POLICY_MODEL_KEY}"
POOL_SIZE = 3
FIXED_OPPONENTS = (
    "model:ministral3_14b",
    "model:gemma4_31b",
    "model:qwen35_9b",
    *(f"cpu:{level}" for level in range(1, MAX_CPU_DIFFICULTY + 1)),
)
# Round N samples uniformly from the POOL_SIZE-wide ladder window opening at rung N, so
# each rung is fought for POOL_SIZE rounds. Fixed rungs climb in difficulty behind pairs
# of self-play rungs (None) replaying completed rounds 1, 2, 3, ... in order; rung N is
# first fought in round N - 2, so its checkpoint exists by then. The ladder is self-play
# past its last rung, which keeps that rung in the pool for all POOL_SIZE rounds.
OPPONENT_LADDER: tuple[str | None, ...] = (
    "random",
    "random",
    "random",
    BASE_OPPONENT,
    *(rung for fixed in FIXED_OPPONENTS for rung in (None, None, fixed)),
)
ANCHOR_OPPONENT = next(rung for rung in reversed(OPPONENT_LADDER) if rung is not None)


def ladder_rung(index: int) -> str | None:
    return OPPONENT_LADDER[index] if index < len(OPPONENT_LADDER) else None


def self_play_round(index: int) -> int:
    replayed = sum(rung is None for rung in OPPONENT_LADDER[:index])
    return 1 + replayed + max(0, index - len(OPPONENT_LADDER))


def opponent_pool(round_idx: int, prior_checkpoints: dict[int, str]) -> list[str]:
    pool = []
    for index in range(round_idx, round_idx + POOL_SIZE):
        rung = ladder_rung(index)
        if rung is not None:
            pool.append(rung)
            continue
        # the scheduled round, else the newest checkpoint before it, else untrained weights
        earlier = [done for done in prior_checkpoints if done <= self_play_round(index)]
        pool.append(
            f"ckpt:{prior_checkpoints[max(earlier)]}" if earlier else BASE_OPPONENT
        )
    selves = [
        slot
        for slot, entry in enumerate(pool)
        if entry.startswith("ckpt:") or entry == BASE_OPPONENT
    ]
    if prior_checkpoints and selves:
        newest = f"ckpt:{prior_checkpoints[max(prior_checkpoints)]}"
        if newest not in pool:
            pool[selves[0]] = newest
    if all(entry.startswith("ckpt:") for entry in pool):
        pool[-1] = ANCHOR_OPPONENT
    return pool


def latest_hf_export(training_run_id: str) -> Checkpoint:
    exports = [
        entry
        for entry in list_checkpoints(training_run_id)
        if entry.checkpoint_type is CheckpointType.hf
    ]
    if not exports:
        raise RuntimeError(f"training run {training_run_id} saved no HF export")
    export = max(exports, key=lambda entry: entry.name)
    gym_location = (export.checkpoints_volume_name, export.checkpoints_mount_path)
    serve_location = (qwen3_vl_8b.CHECKPOINTS_VOLUME, qwen3_vl_8b.CHECKPOINTS_MOUNT)
    if gym_location != serve_location:
        raise RuntimeError(
            f"gym saved checkpoints to {gym_location} but serve mounts {serve_location}"
        )
    return export


@app.local_entrypoint()
def main(
    n_rounds: int = 100,
    num_rollout: int = 20,
    # 4 prompts × 8 fights = 32 concurrent fights, matching serve/qwen3_vl_8b max_num_seqs
    rollout_batch_size: int = 4,
    n_samples_per_prompt: int = 8,
    start_round: int = 0,
    prior_hf: str = "",
):
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}-{uuid.uuid4().hex[:8]}"
    print(f"run_id: {run_id}", flush=True)

    rungs = list(dict.fromkeys(rung for rung in OPPONENT_LADDER if rung is not None))
    for opponent in rungs:
        parse_opponent(opponent)

    rounds = range(start_round, n_rounds)
    scheduled = {
        rung
        for round_idx in rounds
        for rung in map(ladder_rung, range(round_idx, round_idx + POOL_SIZE))
        if rung is not None
    }
    unseen = [rung for rung in rungs if rung not in scheduled]
    if unseen:
        warnings.warn(
            f"rounds {start_round}-{n_rounds - 1} skip the ladder rungs {unseen}; "
            f"the full climb spans rounds 0-{len(OPPONENT_LADDER) - 1}",
            stacklevel=2,
        )

    opponent_app = modal.App(OPPONENT_SERVER_APP_NAME)
    models = {
        detail for kind, detail in map(parse_opponent, scheduled) if kind == "model"
    }
    for key in {POLICY_MODEL_KEY, *models}:
        opponent_app.include(MODELS[key].app)
    opponent_app.deploy()

    checkpoint = None
    prior_checkpoints: dict[int, str] = {}
    if prior_hf:
        checkpoint = Checkpoint(
            checkpoint_type=CheckpointType.hf,
            name=prior_hf.rstrip("/").rsplit("/", 1)[-1],
            path=prior_hf,
            timestamp=time.time(),
            training_run_id="",
        )
        prior_checkpoints[start_round - 1] = prior_hf
    for round_idx in rounds:
        pool = opponent_pool(round_idx, prior_checkpoints)

        result = TrainConfig(
            model=Qwen3_VL_8B(),
            checkpoint=checkpoint,
            dataset=MultimodalDataset(
                # placeholder to size the live rollout batch size
                rows=[
                    {
                        "prompt": "Generate a fresh live SF3 trajectory.",
                        "media": [],
                        "label": str(work_slot),
                    }
                    for work_slot in range(rollout_batch_size)
                ],
                dataset_id=f"{run_id}-r{round_idx}",
                modality="image",
                always_prepare=True,
                apply_chat_template=False,
            ),
            recipe=Qwen3_VL_8b_Recipe(
                custom_generate_function=sf3_generate,
                custom_rm_function=sf3_rm,
                custom_reward_post_process_function=sf3_group_reward_post_process,
                dynamic_sampling_filter_path="src.train.rollout.sf3_valid_group",
                image_overlay=build_rollout_image,
                train_function_kwargs={"secrets": list(hf_secrets())},
                extra_config={
                    **(Qwen3_VL_8b_Recipe().extra_config or {}),
                    "custom_megatron_init_path": "src.train.rollout.megatron_init",
                    "sf3_opponent_pool": pool,
                    "sf3_round": round_idx,
                    # Megatron requires global_batch_size % (mbs * dp) == 0, and
                    # dp = 8 GPUs / TP 2 = 4, so mbs must divide gbs // dp (32 // 4 = 8),
                    # move (~300 tok) * 8 = ~2400 tok < max_tokens_per_gpu=9,216
                    "micro_batch_size": 8,
                },
                num_rollout=num_rollout,
                rollout_batch_size=rollout_batch_size,
                n_samples_per_prompt=n_samples_per_prompt,
                global_batch_size=rollout_batch_size * n_samples_per_prompt,
                rollout_max_response_len=MAX_TOKENS,
                sglang_mem_fraction_static=0.8,
                save_interval=ceil(num_rollout / 2),
                eval_interval=None,
                wandb=WandbConfig(
                    project=WANDB_PROJECT,
                    entity=WANDB_ENTITY,
                    group=f"{run_id}-r{round_idx}",
                    disable_random_suffix=False,
                ),
            ),
        ).train()

        checkpoint = latest_hf_export(result.training_run_id)
        prior_checkpoints[round_idx] = checkpoint.path
        print(f"round {round_idx} vs {pool}: {checkpoint.path}", flush=True)
