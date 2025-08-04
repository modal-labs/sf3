from pathlib import Path

import modal
import modal.experimental

from ..llm import LLMServer
from ..llm import app as llm_app
from ..utils import (
    CHARACTER_MAPPING,
    CHARACTER_TO_ID,
    GameInfo,
    PlayerState,
    create_messages,
    local_assets_dir,
    minutes,
)
from ..yolo import YOLOServer
from ..yolo import app as yolo_app
from .engine import create_environment, create_sandbox

# Modal setup

app = modal.App("sf3-llm-train").include(llm_app).include(yolo_app)

local_engine_dir = local_assets_dir / "engine"
local_train_dir = Path(__file__).parent
local_src_dir = Path(__file__).parent.parent

remote_rm_path = "/root/rm.py"
remote_reward_path = "/root/reward.py"
remote_engine_path = "/root/engine.py"
remote_utils_path = "/root/src/utils.py"


def fix_opencv():
    import opencv_fixer

    opencv_fixer.AutoFix()


verl_image = (
    modal.Image.from_registry("verlai/verl:app-verl0.5-vllm0.9.1-mcore0.12.2-te2.2")
    .apt_install("git")
    .run_commands("git clone https://github.com/volcengine/verl /root/verl")
    .run_commands("cd /root/verl && uv pip install --system -e '.[vllm]'")
    .uv_pip_install(
        "opencv-fixer==0.2.5",
        "diambra-arena==2.2.7",
        "diambra==0.0.20",
        "psutil==7.0.0",
        "huggingface_hub[hf_transfer]==0.33.4",
        "aiohttp==3.12.15",
    )
    .run_function(fix_opencv)
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "VLLM_USE_V1": "1",
        }
    )
    # sppo
    .add_local_dir(local_src_dir / "sppo", "/root/sppo")
    .add_local_file(local_train_dir / "reward.py", remote_reward_path)
    .add_local_file(local_train_dir / "engine.py", remote_engine_path)
    .add_local_file(local_src_dir / "utils.py", remote_utils_path)
    # engine
    .add_local_file(
        local_engine_dir / "sfiii3n.zip",
        "/root/sfiii3n.zip",
    )
    .add_local_file(
        local_engine_dir / "credentials",
        "/root/credentials",
    )
)

cache_path = Path("/cache")
cache_volume = modal.Volume.from_name(f"{app.name}-cache", create_if_missing=True)

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)

vllm_cache_vol = modal.Volume.from_name("sf3-vllm-cache", create_if_missing=True)


MODEL_NAME = "Qwen/Qwen3-0.6B"


# data

training_character = "Chun-Li"
training_super_art = 1

frozen_characters = list(CHARACTER_MAPPING.values())


async def create_yolo():
    print("Creating YOLO...")
    yolo = YOLOServer()
    await yolo.boot.remote.aio()
    print("YOLO created")
    return yolo


async def create_llm():
    print("Creating LLM...")
    llm = LLMServer()
    await llm.boot.remote.aio()
    print("LLM created")
    return llm


@app.function(
    image=verl_image,
    volumes={cache_path: cache_volume},
    timeout=60 * minutes,
)
async def run_rl_episode(
    idx: int,
    character: str,
    super_art: int,
    difficulty: int,
    split: str,
    save_video: bool = False,
):
    import asyncio

    from tqdm import tqdm

    ## init

    characters = [training_character, character]
    super_arts = [training_super_art, super_art]

    yolo, llm = await asyncio.gather(create_yolo(), create_llm())

    sandbox = create_sandbox()
    env = create_environment(difficulty, characters, super_arts)
    if env is None:
        sandbox.terminate()
        return []
    observation, info = env.reset()

    step_idx = 0
    step_info = []
    video_info = []

    print("Running episode...")
    pbar = tqdm(desc="step_idx", unit="step")
    while True:
        obs_p1 = observation["P1"]
        obs_p2 = observation["P2"]

        boxes, class_ids = await yolo.detect_characters.remote.aio(
            [CHARACTER_TO_ID[training_character], CHARACTER_TO_ID[character]],
            observation["frame"],
        )

        game_info = GameInfo(
            stage=observation["stage"][0],
            timer=observation["timer"][0],
            boxes=boxes,
            class_ids=class_ids,
        )

        p1_side = obs_p1["side"]

        player1 = PlayerState(
            character=training_character,
            super_art=super_arts[0],
            wins=obs_p1["wins"][0],
            side=p1_side,
            stunned=obs_p1["stunned"],
            stun_bar=obs_p1["stun_bar"][0],
            health=obs_p1["health"][0],
            super_count=obs_p1["super_count"][0],
            super_bar=obs_p1["super_bar"][0],
        )

        player2 = PlayerState(
            character=character,
            super_art=super_arts[1],
            wins=obs_p2["wins"][0],
            side=obs_p2["side"],
            stunned=obs_p2["stunned"],
            stun_bar=obs_p2["stun_bar"][0],
            health=obs_p2["health"][0],
            super_count=obs_p2["super_count"][0],
            super_bar=obs_p2["super_bar"][0],
        )

        training_messages = create_messages(game_info, player2, player1)
        frozen_messages = create_messages(game_info, player1, player2)

        training_moves = await llm.chat.remote.aio(
            training_messages,
            training_character,
            super_arts[0],
            obs_p1["super_count"][0],
            p1_side,
        )
        frozen_moves = await llm.chat.remote.aio(
            frozen_messages,
            character,
            super_arts[1],
            obs_p2["super_count"][0],
            obs_p2["side"],
        )

        if len(training_moves) > len(frozen_moves):
            frozen_moves = frozen_moves + [0] * (
                len(training_moves) - len(frozen_moves)
            )
        elif len(frozen_moves) > len(training_moves):
            training_moves = training_moves + [0] * (
                len(frozen_moves) - len(training_moves)
            )

        for training_move, frozen_move in zip(training_moves, frozen_moves):
            (
                observation,
                reward,
                terminated,
                truncated,
                info,
            ) = env.step(
                {
                    "agent_0": training_move,
                    "agent_1": frozen_move,
                }
            )

            if save_video:
                boxes, class_ids = await yolo.detect_characters.remote.aio(
                    [CHARACTER_TO_ID[training_character], CHARACTER_TO_ID[character]],
                    observation["frame"],
                )

                video_info.append(
                    {
                        "frame": observation["frame"],
                        "boxes": boxes,
                        "class_ids": class_ids,
                    }
                )

        step_info.append(
            {
                "training_messages": training_messages,
                "super_count": player1.super_count,
                "side": p1_side,
            }
        )

        if terminated or truncated:
            break

        step_idx += 1
        pbar.update(1)

    pbar.close()
    print("Episode finished.")

    if save_video:
        import cv2

        print("Saving video...")

        out_path = cache_path / f"{split}_{idx}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        scale_factor = 3  # 384x224 -> 1152x672
        orig_height, orig_width = video_info[0]["frame"].shape[:2]
        up_height, up_width = orig_height * scale_factor, orig_width * scale_factor

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(
            str(out_path), fourcc, 60.0, (up_width, up_height)
        )

        for frame_data in video_info:
            frame = cv2.cvtColor(frame_data["frame"], cv2.COLOR_RGB2BGR)
            boxes = frame_data["boxes"]
            class_ids = frame_data["class_ids"]

            # upscale frame
            frame = cv2.resize(
                frame, (up_width, up_height), interpolation=cv2.INTER_LINEAR
            )

            for box, class_id in zip(boxes, class_ids):
                if class_id == -1:
                    continue

                x1, y1, x2, y2 = [int(coord * scale_factor) for coord in box]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                character_name = CHARACTER_MAPPING[class_id]
                cv2.putText(
                    frame,
                    character_name,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5 * scale_factor,
                    (0, 255, 0),
                    2,
                )

            video_writer.write(frame)

        video_writer.release()

        print(f"Saved video to {out_path}")

    print("Cleaning up...")
    try:
        env.close()
    except Exception as e:
        print(f"Warning: closing environment failed: {e}")
    print("Done.")

    return [
        {
            "data_source": f"{split}_{idx}",
            "prompt": step["training_messages"],
            "ability": "fighting_game",
            "reward_model": {"style": "rule", "ground_truth": ""},
            "extra_info": {
                "messages": step["training_messages"],
                "character": characters[0],
                "super_art": super_arts[0],
                "super_count": step["super_count"],
                "side": step["side"],
            },
        }
        for idx, step in enumerate(step_info)
    ]


@app.function(
    image=verl_image, volumes={cache_path: cache_volume}, timeout=60 * minutes
)
async def create_dataset(
    split: str,
    n_samples: int | None = None,
    n_videos: int | None = None,
):
    import asyncio
    import itertools
    import random

    from datasets import Dataset

    player2_super_arts = list(range(1, 3 + 1))
    player2_difficulties = list(range(1, 8 + 1))
    combinations = list(
        itertools.product(frozen_characters, player2_super_arts, player2_difficulties)
    )
    if n_samples is not None and n_samples < len(combinations):
        combinations = random.sample(combinations, n_samples)

    if n_videos is not None and n_videos < len(combinations):
        idxs = random.sample(range(len(combinations)), n_videos)
    elif n_videos is not None:
        idxs = range(len(combinations))

    data = [
        item
        for sublist in await asyncio.gather(
            *[
                run_rl_episode.remote.aio(
                    idx, *combination, split, save_video=idx in idxs
                )
                for idx, combination in enumerate(combinations)
            ]
        )
        if sublist
        for item in sublist
    ]
    ds = Dataset.from_list(data)
    out_path = cache_path / f"{split}.parquet"
    ds.to_parquet(str(out_path))
    return f"Saved {len(ds)} samples to {out_path}"


# training

n_gpus = 4

reward_function_name = "compute_reward"


@app.function(
    image=verl_image,
    gpu=f"h200:{n_gpus}",
    cpu=64,
    volumes={
        cache_path: cache_volume,
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=[modal.Secret.from_name("ajhinh-wandb-secret")],
    timeout=24 * 60 * minutes,
)
def train_model(*arglist) -> None:
    import subprocess
    import time

    cache_volume.reload()

    # Parameters taken from:
    # https://github.com/modal-labs/modal-examples/pull/1245/files
    # https://qwen.readthedocs.io/en/latest/training/verl.html
    # https://verl.readthedocs.io/en/latest/examples/config.html
    # https://github.com/volcengine/verl/blob/main/recipe/sppo/run_qwen2.5-7b_rm.sh

    micro_batch_size_per_gpu = 4

    cmd = [
        "python",
        "-m",
        "sppo.main_sppo",
        # Algorithm configuration
        "algorithm.adv_estimator=null",
        "algorithm.use_kl_in_reward=False",
        # Data configuration
        f"data.train_files={cache_path / 'train.parquet'}",
        f"data.val_files={cache_path / 'val.parquet'}",
        "data.train_batch_size=64",  #  1024
        "data.max_prompt_length=1024",
        "data.max_response_length=512",
        "data.filter_overlong_prompts=True",
        "data.truncation='error'",
        "data.return_raw_chat=True",
        # Model configuration
        f"actor_rollout_ref.model.path={MODEL_NAME}",
        "actor_rollout_ref.model.use_remove_padding=True",
        "actor_rollout_ref.model.enable_gradient_checkpointing=True",
        # Actor configuration
        "actor_rollout_ref.actor.optim.lr=1e-6",
        "actor_rollout_ref.actor.optim.lr_warmup_steps=15",
        "actor_rollout_ref.actor.ppo_mini_batch_size=16",  # 256
        f"actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu={micro_batch_size_per_gpu}",
        "actor_rollout_ref.actor.use_kl_loss=False",
        "actor_rollout_ref.actor.fsdp_config.param_offload=False",
        "actor_rollout_ref.actor.fsdp_config.optimizer_offload=False",
        "actor_rollout_ref.actor.checkpoint.save_contents='model,optimizer,extra,hf_model'",
        # Rollout configuration
        "actor_rollout_ref.rollout.name=vllm",
        "actor_rollout_ref.rollout.tensor_model_parallel_size=1",
        f"actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu={micro_batch_size_per_gpu}",
        "actor_rollout_ref.rollout.gpu_memory_utilization=0.7",  # https://verl.readthedocs.io/en/latest/perf/perf_tuning.html
        "actor_rollout_ref.rollout.max_num_batched_tokens=40960",
        "actor_rollout_ref.rollout.temperature=0.6",
        "actor_rollout_ref.rollout.top_p=0.95",
        "actor_rollout_ref.rollout.top_k=20",
        "actor_rollout_ref.rollout.val_kwargs.n=1",  # 2 will trigger validation, 1 will bypass
        # Trainer configuration
        "trainer.logger=['console', 'wandb']",
        f"trainer.project_name={app.name}-{MODEL_NAME.lower().split('/')[1]}",
        f"trainer.experiment_name=run_{time.strftime('%Y%m%d_%H%M%S')}",
        f"trainer.n_gpus_per_node={n_gpus}",
        "trainer.val_before_train=False",
        "trainer.nnodes=1",
        f"trainer.default_local_dir={cache_path}",
        "trainer.resume_mode=auto",
        # Parameters chosen to ensure easy automated testing. Remove if needed.
        "trainer.total_epochs=1",
        "trainer.total_training_steps=1",
        "trainer.save_freq=1",
        "trainer.test_freq=1",
        # Custom reward function configuration
        f"custom_reward_function.path={remote_reward_path}",
        f"custom_reward_function.name={reward_function_name}",
    ]
    if arglist:
        cmd.extend(arglist)

    subprocess.run(cmd, check=True)


@app.local_entrypoint()
async def local(
    prepare: bool = False,
    n_train_samples: int
    | None = 2,  # 18 characters * 3 super arts * 8 difficulties = 432
    n_train_videos: int | None = 1,
    n_val_samples: int | None = 2,  # 10% of train samples = 43
    n_val_videos: int | None = 1,
    train: bool = False,
):
    import asyncio

    if prepare:
        await asyncio.gather(
            create_dataset.remote.aio("train", n_train_samples, n_train_videos),
            create_dataset.remote.aio("val", n_val_samples, n_val_videos),
        )

    if train:
        train_model.remote()
