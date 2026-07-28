from __future__ import annotations

import asyncio
import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from copy import copy
from dataclasses import dataclass
from enum import Enum
from math import ceil, sqrt, tanh
from typing import Any

import modal

from src.env import EnvironmentConfig, create_environment
from src.serve import MODELS, POLICY_MODEL_KEY
from src.utils import (
    CHARACTER_MAPPING,
    HEALTH_MAX,
    MAX_CPU_DIFFICULTY,
    MAX_TOKENS,
    FrameEncoder,
    create_gameplay_image,
    create_messages,
    generate_move,
    get_available_instructions_for_character,
    move_regex,
    player_state,
    resolve_move_with_fallback,
)

ROSTER = tuple(CHARACTER_MAPPING.values())
OUTFIT = SUPER_ART = 1
OPPONENT_SERVER_APP_NAME = "sf3-fight-workers"
FRAME_KEY = "sf3_frame"

GROUP_DROP_TOLERANCE = 2.0
MIN_GROUP_DROPS_IN_A_ROW = 4
IMAGE_PAD = "<|image_pad|>"

_groups_dropped_in_a_row = 0
_opponent_servers: dict[str, Any] = {}
_image_tokens_by_frame_size: dict[tuple[int, int], int] = {}


class TokenContractError(RuntimeError):
    pass


class OpponentSpecError(ValueError):
    pass


def parse_opponent(opponent: str) -> tuple[str, str]:
    kind, _, detail = opponent.partition(":")
    playable = {
        "random": not detail,
        "model": detail in MODELS,
        "ckpt": bool(detail),
        "cpu": detail.isdigit() and 1 <= int(detail) <= MAX_CPU_DIFFICULTY,
    }.get(kind, False)
    if not playable:
        raise OpponentSpecError(f"unplayable opponent {opponent!r}")
    return kind, detail


def opponent_server(opponent: str):
    kind, detail = parse_opponent(opponent)
    if kind not in {"model", "ckpt"}:
        return None
    server = _opponent_servers.get(opponent)
    if server is None:
        spec = MODELS[detail if kind == "model" else POLICY_MODEL_KEY]
        ckpt_path = spec.version["model"] if kind == "model" else detail
        server = modal.Cls.from_name(OPPONENT_SERVER_APP_NAME, spec.server.__name__)(
            ckpt_path=ckpt_path
        )
        _opponent_servers[opponent] = server
    return server


def group_matchup(
    pool: list[str], round_idx: int, group_index: int
) -> tuple[str, list[str]]:
    rng = random.Random(f"{round_idx}:{group_index}")
    return rng.choice(pool), rng.sample(ROSTER, 2)


def prompt_token_ids(
    tokenizer, processor, prompt_text: str, frame: str, frame_size: tuple[int, int]
) -> list[int]:
    count = _image_tokens_by_frame_size.get(frame_size)
    if count is None:
        from qwen_vl_utils import process_vision_info

        images, _videos = process_vision_info([
            {"role": "user", "content": [{"type": "image", "image": frame}]}
        ])
        processed = processor(text=prompt_text, images=images, return_tensors="pt")
        token_ids = [int(token) for token in processed["input_ids"][0].tolist()]
        pad_id = tokenizer.convert_tokens_to_ids(IMAGE_PAD)
        _image_tokens_by_frame_size[frame_size] = token_ids.count(pad_id)
        return token_ids
    expanded = prompt_text.replace(IMAGE_PAD, IMAGE_PAD * count, 1)
    return tokenizer(expanded, add_special_tokens=False)["input_ids"]


class EndReason(str, Enum):
    WON = "won"
    LOST = "lost"
    FAILED = "failed"

    @property
    def trains(self) -> bool:
        return self is not EndReason.FAILED


@dataclass(frozen=True)
class FightResult:
    end_reason: EndReason
    health_return: float
    stages_cleared: int


def build_rollout_image(image: modal.Image) -> modal.Image:
    return create_gameplay_image(
        base_image=image,
        extra_python_packages=("qwen-vl-utils==0.0.14",),
        copy=True,
        add_python_source=True,
    )


def _step_buttons(env, buttons: list[int], opponent_buttons: list[int]):
    total_reward = 0.0
    stages_cleared = 0

    for button in buttons:
        observation, reward, terminated, _truncated, info = env.step({
            "agent_0": button,
            "agent_1": opponent_buttons.pop(0) if opponent_buttons else 0,
        })
        total_reward += float(reward)
        if info.get("stage_done"):
            stages_cleared += 1
        if terminated:
            winner = EndReason.WON if info.get("winner") == "P1" else EndReason.LOST
            return observation, total_reward, stages_cleared, False, winner
        if info.get("round_done"):
            return observation, total_reward, stages_cleared, True, None
    return observation, total_reward, stages_cleared, False, None


async def _play_fight(
    opponent: str,
    characters: list[str],
    session_id: str,
    on_observation,
) -> FightResult:
    kind, detail = parse_opponent(opponent)
    server = opponent_server(opponent)
    rng = random.Random(f"{session_id}:bot")
    policy_character, opponent_character = characters
    p1_identity = {
        "character": policy_character,
        "outfit": OUTFIT,
        "superArt": SUPER_ART,
    }
    env = await asyncio.to_thread(
        create_environment,
        EnvironmentConfig(
            characters=(policy_character, opponent_character),
            outfits=(OUTFIT, OUTFIT),
            super_arts=(SUPER_ART, SUPER_ART),
            step_ratio=6,
            render_mode="rgb_array",
            roms_path="/root",
            vs_cpu=kind == "cpu",
            cpu_difficulty=int(detail) if kind == "cpu" else 1,
        ),
    )
    health_return = 0.0
    stages_cleared = 0
    frame_encoder = FrameEncoder()
    opponent_buttons: list[int] = []
    try:
        observation, _info = await asyncio.to_thread(env.reset)
        while True:
            pixels = observation.get("frame")
            if pixels is None:
                raise ValueError("fight observation missing frame")
            frame_size = (pixels.shape[1], pixels.shape[0])
            frame = frame_encoder.data_url(pixels)
            player1 = player_state(observation, p1_identity, "P1")
            player2 = player_state(observation, env.read_player_identity("P2"), "P2")
            messages, available = create_messages(player2, player1, [frame])

            async def next_opponent_buttons() -> list[int]:
                if opponent_buttons:
                    return opponent_buttons
                if server is not None:
                    buttons, _ = await generate_move(
                        server.chat.remote.aio, player2, player1, frame
                    )
                    return buttons
                if kind == "cpu":
                    # the emulator drives P2 itself at cpu_difficulty
                    return []
                buttons, _ = resolve_move_with_fallback(
                    player2.character,
                    rng.choice(
                        get_available_instructions_for_character(
                            player2.character, player2.super_art, player2.super_count
                        )
                    ),
                    player2.side,
                )
                return buttons

            try:
                async with asyncio.TaskGroup() as group:
                    policy = group.create_task(
                        on_observation(frame, frame_size, messages, available)
                    )
                    bot = group.create_task(next_opponent_buttons())
            except BaseExceptionGroup as error:
                contract = error.subgroup(TokenContractError)
                raise (contract or error).exceptions[0] from error
            buttons, _ = resolve_move_with_fallback(
                policy_character, policy.result(), player1.side
            )
            opponent_buttons = bot.result()

            (
                observation,
                reward,
                clears,
                round_done,
                end_reason,
            ) = await asyncio.to_thread(_step_buttons, env, buttons, opponent_buttons)
            health_return += reward
            stages_cleared += clears
            if round_done:
                opponent_buttons.clear()
            if end_reason is not None:
                cleared = stages_cleared + (1 if end_reason is EndReason.WON else 0)
                return FightResult(end_reason, health_return, cleared)
    finally:
        with suppress(Exception):
            await asyncio.to_thread(env.close)


def _align_samples(args, samples: list) -> list:
    def arg(name: str) -> int:
        return int(getattr(args, name, 1) or 1)

    parallel = (
        arg("tensor_model_parallel_size")
        * arg("pipeline_model_parallel_size")
        * arg("context_parallel_size")
    )
    dp = max(1, (arg("actor_num_nodes") * arg("actor_num_gpus_per_node")) // parallel)
    mb_group = (
        arg("microbatch_group_size_per_vp_stage")
        if arg("virtual_pipeline_model_parallel_size") > 1
        else 1
    )
    align = max(1, dp * arg("micro_batch_size") * mb_group)
    remainder = len(samples) % align
    if not remainder:
        return samples
    padded = list(samples)
    for _ in range(align - remainder):
        filler = copy(samples[-1])
        filler.loss_mask = [0] * filler.response_length
        padded.append(filler)
    return padded


async def sf3_generate(args, sample, sampling_params):
    from slime.rollout.sglang_rollout import GenerateState
    from slime.utils.http_utils import post
    from slime.utils.types import Sample

    state = GenerateState(args)
    url = f"http://{args.sglang_router_ip}:{args.sglang_router_port}/generate"
    template_kwargs = getattr(args, "apply_chat_template_kwargs", None)
    if isinstance(template_kwargs, str):
        template_kwargs = json.loads(template_kwargs)
    template_kwargs = template_kwargs or {"enable_thinking": False}

    rollout_id = int(sample.index)
    round_idx = int(getattr(args, "sf3_round", 0) or 0)
    session_id = f"{round_idx}:{sample.group_index}:{rollout_id}"
    opponent, characters = group_matchup(
        list(getattr(args, "sf3_opponent_pool", None) or ["random"]),
        round_idx,
        sample.group_index,
    )
    policy_samples: list[Sample] = []

    async def on_observation(
        frame: str,
        frame_size: tuple[int, int],
        messages: list,
        available_moves: list[str],
    ):
        prompt_text = state.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            **template_kwargs,
        )
        prompt_ids = prompt_token_ids(
            state.tokenizer, state.processor, prompt_text, frame, frame_size
        )
        output = await post(
            url,
            {
                "text": prompt_text,
                "image_data": [frame],
                "sampling_params": {
                    **sampling_params,
                    "max_new_tokens": MAX_TOKENS,
                    "regex": move_regex(available_moves),
                },
                "return_logprob": True,
            },
        )

        meta_info = output["meta_info"]
        finish_reason = meta_info.get("finish_reason") or {}
        finish_type = (
            finish_reason.get("type")
            if isinstance(finish_reason, dict)
            else str(finish_reason)
        )
        if finish_type == "abort":
            raise RuntimeError("SGLang aborted the action request")

        if meta_info.get("prompt_tokens") != len(prompt_ids):
            raise TokenContractError(
                f"SGLang counted {meta_info.get('prompt_tokens')!r} prompt "
                f"tokens but the local processor produced {len(prompt_ids)}"
            )
        logprobs = meta_info.get("output_token_logprobs")
        if not logprobs:
            raise RuntimeError("SGLang returned no output_token_logprobs for an action")
        truncated = finish_type == "length"
        move_sample = copy(sample)
        move_sample.rollout_id = rollout_id
        move_sample.prompt = prompt_text
        move_sample.tokens = prompt_ids + [item[1] for item in logprobs]
        move_sample.response = output["text"]
        move_sample.response_length = len(logprobs)
        move_sample.reward = None
        move_sample.loss_mask = [1] * len(logprobs)
        move_sample.rollout_log_probs = [float(item[0]) for item in logprobs]
        move_sample.status = (
            Sample.Status.TRUNCATED if truncated else Sample.Status.COMPLETED
        )
        move_sample.multimodal_inputs = None
        move_sample.multimodal_train_inputs = {FRAME_KEY: frame}
        policy_samples.append(move_sample)

        move = output["text"].strip()
        if truncated or move not in available_moves:
            return "No-Move"
        return move

    try:
        result = await _play_fight(opponent, characters, session_id, on_observation)
    except (TokenContractError, OpponentSpecError):
        raise
    except Exception:
        result = FightResult(EndReason.FAILED, 0.0, 0)

    if not result.end_reason.trains or not policy_samples:
        sample.rollout_id = rollout_id
        sample.status = Sample.Status.ABORTED
        sample.metadata = {
            **sample.metadata,
            "sf3": {"end_reason": result.end_reason.value, "opponent": opponent},
        }
        return [sample]

    meta = {
        "end_reason": result.end_reason.value,
        "opponent": opponent,
        "characters": characters,
        "health_return": result.health_return,
        "stages_cleared": result.stages_cleared,
        "reward": result.stages_cleared + 0.5 * tanh(result.health_return / HEALTH_MAX),
        "moves": len(policy_samples),
    }
    for policy_sample in policy_samples:
        policy_sample.metadata = {**policy_sample.metadata, "sf3": dict(meta)}
    return _align_samples(args, policy_samples)


def _frame_vision_inputs(image_processor, frame: str) -> dict:
    from qwen_vl_utils import process_vision_info

    images, _videos = process_vision_info([
        {"role": "user", "content": [{"type": "image", "image": frame}]}
    ])
    return image_processor(images=images, return_tensors="pt")


def megatron_init(args) -> None:
    import torch
    from slime.backends.megatron_utils.data import DataIterator
    from slime.utils.processing_utils import load_processor

    # training-gym only learns its run id after launch, so the HF export path is resolved here
    args.save_hf = os.path.join(args.save, "iter_{rollout_id:07d}_hf")

    image_processor = load_processor(
        args.hf_checkpoint, trust_remote_code=True
    ).image_processor
    get_next = DataIterator.get_next
    ranks = max(1, int(getattr(args, "actor_num_gpus_per_node", 1) or 1))
    pool = ThreadPoolExecutor(max_workers=max(1, len(os.sched_getaffinity(0)) // ranks))

    def vision_inputs(entry):
        if not entry or FRAME_KEY not in entry:
            return None
        return _frame_vision_inputs(image_processor, entry[FRAME_KEY])

    def get_next_with_frames(self, keys):
        batch = get_next(self, keys)
        entries = batch.get("multimodal_train_inputs")
        if not entries:
            return batch
        device = torch.cuda.current_device()
        recomputed = list(entries)
        for index, processed in enumerate(pool.map(vision_inputs, entries)):
            if processed is not None:
                recomputed[index] = {
                    key: value.to(device=device, non_blocking=True)
                    for key, value in processed.items()
                }
        batch["multimodal_train_inputs"] = recomputed
        return batch

    DataIterator.get_next = get_next_with_frames


def sf3_valid_group(args, group) -> bool:
    global _groups_dropped_in_a_row

    def group_drop_reason(group) -> str | None:
        from slime.utils.types import Sample

        rewards = []
        for fight in group:
            samples = fight if isinstance(fight, list) else [fight]
            if not samples:
                return "a fight produced no samples"
            aborted = [
                item.metadata.get("sf3", {}).get("end_reason", "aborted")
                for item in samples
                if item.status == Sample.Status.ABORTED
            ]
            if aborted:
                return f"fight ended as {aborted[0]}"
            rewards.append(float(samples[0].metadata["sf3"]["reward"]))
        if len(rewards) < 2 or max(rewards) - min(rewards) <= 1e-6:
            return f"no reward variance across fights {rewards}"
        return None

    reason = group_drop_reason(group)
    if reason is None:
        _groups_dropped_in_a_row = 0
        return True

    _groups_dropped_in_a_row += 1
    group_size = max(1, int(getattr(args, "n_samples_per_prompt", 1) or 1))
    max_drops = max(MIN_GROUP_DROPS_IN_A_ROW, ceil(GROUP_DROP_TOLERANCE * group_size))
    if _groups_dropped_in_a_row >= max_drops:
        raise RuntimeError(
            f"{_groups_dropped_in_a_row} prompt groups dropped in a row without "
            f"an accepted rollout; last reason: {reason}"
        )
    return False


async def sf3_rm(args, sample, **kwargs) -> float | list[float]:
    if isinstance(sample, list):
        return [float(item.metadata["sf3"]["reward"]) for item in sample]
    return float(sample.metadata["sf3"]["reward"])


def sf3_group_reward_post_process(args, samples):
    scored = [item.reward is not None for item in samples]
    rewards = [
        float(item.get_reward_value(args)) if is_scored else 0.0
        for item, is_scored in zip(samples, scored, strict=True)
    ]
    estimator = getattr(args, "advantage_estimator", "grpo")
    if estimator not in {
        "grpo",
        "gspo",
        "cispo",
        "reinforce_plus_plus_baseline",
    } or not getattr(args, "rewards_normalization", True):
        return rewards, rewards

    keys = [(int(item.group_index), int(item.rollout_id)) for item in samples]
    fights: dict[tuple[int, int], float] = {}
    for key, reward, is_scored in zip(keys, rewards, scored, strict=True):
        if is_scored:
            fights.setdefault(key, reward)
    groups: dict[int, list[tuple[int, int]]] = {}
    for key in fights:
        groups.setdefault(key[0], []).append(key)

    use_std = estimator in {"grpo", "gspo", "cispo"} and getattr(
        args, "grpo_std_normalization", True
    )
    normalized: dict[tuple[int, int], float] = {}
    for group in groups.values():
        centered = [fights[key] for key in group]
        mean = sum(centered) / len(centered)
        centered = [value - mean for value in centered]
        if use_std and len(centered) > 1:
            variance = sum(value * value for value in centered) / (len(centered) - 1)
            centered = [value / (sqrt(variance) + 1e-6) for value in centered]
        normalized.update(zip(group, centered, strict=True))

    return rewards, [normalized.get(key, 0.0) for key in keys]
