import asyncio
import base64
import os
import shutil
import sys
import warnings
from io import BytesIO
from pathlib import Path

import modal
import modal.exception

from ..env import EnvironmentConfig
from ..env import create_environment as create_local_environment
from ..serve.qwen35_35ba3b_fp8 import Qwen35Server
from ..serve.qwen35_35ba3b_fp8 import app as llm_app
from ..utils import (
    HEALTH_MAX,
    GameInfo,
    PlayerState,
    _exec_subprocess,
    create_messages,
    get_available_instructions_for_character,
    minutes,
    parse_move,
)

# Modal setup

app = modal.App("sf3-llm-train").include(llm_app)

# training
local_engine_dir = Path(__file__).parent.parent.parent / "assets" / "engine"

flash_attn_release = (
    "https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/"
    "flash_attn-2.8.3+cu12torch2.7cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
)
transformers_version = "5.3.0"
torch_version = "2.7.1"
torchvision_version = "0.22.1"
torchaudio_version = "2.7.1"

TRAIN_REPO_PATH = Path("/LLaMA-Factory")
train_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "git")
    .env(
        {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "XDG_RUNTIME_DIR": "/tmp",
            "DISABLE_VERSION_CHECK": "1",
        }
    )
    .uv_pip_install(
        "accelerate==1.10.0",
        "datasets==3.6.0",
        f"torch=={torch_version}",
        f"torchvision=={torchvision_version}",
        f"torchaudio=={torchaudio_version}",
        flash_attn_release,
        "huggingface_hub[hf_transfer]==0.34.4",
        "matplotlib==3.10.5",
        "MAMEToolkit==1.1.0",
        "numpy==2.3.1",
        "opencv-python==4.11.0.86",
        # "openai==1.99.9",
        "pillow==12.0.0",
        "wandb==0.21.0",
        extra_index_url="https://download.pytorch.org/whl/cu128",
        extra_options="--index-strategy unsafe-best-match",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
    )
    # training
    .run_commands(
        [
            f"git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git {TRAIN_REPO_PATH}",
            f"cd {TRAIN_REPO_PATH} && uv pip install --system --compile-bytecode -e .",
            f"uv pip install --system --compile-bytecode 'transformers=={transformers_version}'",
        ]
    )
    # engine
    .add_local_file(
        local_engine_dir / "sfiii3n.zip",
        "/root/sfiii3n.zip",
    )
)

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sf3-vllm-cache", create_if_missing=True)
cache_path = Path("/cache")
cache_volume = modal.Volume.from_name("sf3-llm-train-cache", create_if_missing=True)

env_create_timeout = 60
episode_timeout = 10 * minutes
dataset_create_timeout = 20 * minutes
train_timeout = 24 * 60 * minutes
eval_timeout = 20 * minutes

dataset_flush_every = 4
max_dataset_attempts = 3
max_train_attempts = 3

# helper fns


def is_modal_timeout_error(exc: BaseException) -> bool:
    seen = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, modal.exception.FunctionTimeoutError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


async def create_llm(ckpt_path: str):
    try:
        print("Creating LLM...")
        llm = Qwen35Server(ckpt_path=ckpt_path)
        await llm.boot.remote.aio()
        print("LLM created")
        return llm
    except Exception as e:
        print(f"Couldn't create LLM: {e}", file=sys.stderr)
        return None


# dataset

# reduce problem difficulty
character = "Ryu"
outfit = 1
super_art = 1

# increase move variety
recent_move_limit = 8
opponent_pool_size_per_round = 4

# td-lambda returns
n_move_returns = 32  # roughly length of round
gamma = 0.99

# misc
n_videos_per_round = 1
max_steps_without_reward = 128


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    # region=region,
    timeout=episode_timeout,
    nonpreemptible=True,
)
async def run_episode_data(
    idx: int,
    split: str,
    run_name: str,
    project_name: str,
    round_idx: int,
    save_video: bool,
    current_ckpt_path: str = "",
    opponent_ckpt_paths: list[str] | None = None,
):
    import random
    from collections import deque

    from PIL import Image
    from tqdm import tqdm

    ## init bg processes

    characters = [character, character]
    outfits = [outfit, outfit]
    super_arts = [super_art, super_art]

    if opponent_ckpt_paths is None:
        opponent_ckpt_paths = []
    selected_opponent_path = None
    if len(opponent_ckpt_paths) > 0:
        selected_opponent_path = random.choice(opponent_ckpt_paths)

    tasks = []

    # first round: just use random moves to "bootstrap" the model
    if round_idx == 0:
        tasks.append(asyncio.to_thread(lambda: None))
    else:
        tasks.append(create_llm(current_ckpt_path))

    if selected_opponent_path:
        tasks.append(create_llm(selected_opponent_path))
    else:
        tasks.append(asyncio.to_thread(lambda: None))

    current_llm, prior_llm = await asyncio.gather(*tasks)
    if round_idx > 0 and current_llm is None:
        return []
    if selected_opponent_path and prior_llm is None:
        return []

    env_config = EnvironmentConfig(
        characters=tuple(characters),
        outfits=tuple(outfits),
        super_arts=tuple(super_arts),
        step_ratio=6,
        render_mode="rgb_array",
        roms_path="/root",
    )
    try:
        env = await asyncio.wait_for(
            asyncio.to_thread(create_local_environment, env_config),
            timeout=env_create_timeout,
        )
    except asyncio.TimeoutError:
        print("Timeout while creating environment", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Couldn't create local environment: {e}", file=sys.stderr)
        return []

    # init episode

    try:
        observation, info = env.reset()
    except Exception as e:
        print(f"env.reset() failed: {e}", file=sys.stderr)
        return []

    step_idx = 0
    steps_without_reward = 0

    prev_game_info = None
    prev_player1_state = None
    prev_player2_state = None
    p1_recent_moves = deque(maxlen=recent_move_limit)
    p2_recent_moves = deque(maxlen=recent_move_limit)
    step_data = []
    frames = []
    frame_starts = []

    # run episode

    print("Running episode...")
    pbar = tqdm(desc="step_idx", unit="step")
    while True:
        # get info for prompt
        obs_p1 = observation["P1"]
        obs_p2 = observation["P2"]
        game_info = GameInfo(
            timer=observation["timer"][0],
        )
        p1_side = obs_p1["side"]
        player1 = PlayerState(
            character=character,
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

        buffer = BytesIO()
        Image.fromarray(observation["frame"]).save(buffer, format="PNG")
        frame_data = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"

        # run current policy
        p1_messages, p1_available_moves = create_messages(
            game_info,
            player2,
            player1,
            prev_game_info,
            prev_player2_state,
            prev_player1_state,
            p1_recent_moves,
            frames=[frame_data],
        )

        # run opponent policy
        p2_messages, p2_available_moves = create_messages(
            game_info,
            player1,
            player2,
            prev_game_info,
            prev_player1_state,
            prev_player2_state,
            p2_recent_moves,
            frames=[frame_data],
        )

        if round_idx > 0 and prior_llm is not None:
            p1_result, p2_result = await asyncio.gather(
                current_llm.chat.remote.aio(
                    p1_messages,
                    character,
                    super_arts[0],
                    obs_p1["super_count"][0],
                    p1_side,
                    p1_available_moves,
                ),
                prior_llm.chat.remote.aio(
                    p2_messages,
                    character,
                    super_arts[1],
                    obs_p2["super_count"][0],
                    obs_p2["side"],
                    p2_available_moves,
                ),
                return_exceptions=True,
            )
            if isinstance(p1_result, Exception):
                print(f"current_llm.chat failed: {p1_result}", file=sys.stderr)
                return []
            p1_buttons, p1_move_name = p1_result
            if isinstance(p2_result, Exception):
                print(f"prior_llm.chat (opponent) failed: {p2_result}", file=sys.stderr)
                available_moves = get_available_instructions_for_character(
                    character, super_arts[1], obs_p2["super_count"][0]
                )
                p2_move_name = random.choice(available_moves)
                p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])
            else:
                p2_buttons, p2_move_name = p2_result
        elif round_idx == 0:
            p1_move_name = random.choice(p1_available_moves)
            p1_buttons = parse_move(character, p1_move_name, p1_side)
            p2_move_name = random.choice(p2_available_moves)
            p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])
        elif prior_llm is None:
            try:
                (
                    p1_buttons,
                    p1_move_name,
                ) = await current_llm.chat.remote.aio(
                    p1_messages,
                    character,
                    super_arts[0],
                    obs_p1["super_count"][0],
                    p1_side,
                    p1_available_moves,
                )
            except Exception as e:
                print(f"current_llm.chat failed: {e}", file=sys.stderr)
                return []
            p2_move_name = random.choice(p2_available_moves)
            p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])
        else:
            try:
                (
                    p1_buttons,
                    p1_move_name,
                ) = await current_llm.chat.remote.aio(
                    p1_messages,
                    character,
                    super_arts[0],
                    obs_p1["super_count"][0],
                    p1_side,
                    p1_available_moves,
                )
            except Exception as e:
                print(f"current_llm.chat failed: {e}", file=sys.stderr)
                return []
            try:
                (
                    p2_buttons,
                    p2_move_name,
                ) = await prior_llm.chat.remote.aio(
                    p2_messages,
                    character,
                    super_arts[1],
                    obs_p2["super_count"][0],
                    obs_p2["side"],
                    p2_available_moves,
                )
            except Exception as e:
                print(f"prior_llm.chat (opponent) failed: {e}", file=sys.stderr)
                available_moves = get_available_instructions_for_character(
                    character, super_arts[1], obs_p2["super_count"][0]
                )
                p2_move_name = random.choice(available_moves)
                p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])

        # pad shorter move sequence to match longer one
        if len(p1_buttons) > len(p2_buttons):
            p2_buttons = p2_buttons + [0] * (len(p1_buttons) - len(p2_buttons))
        elif len(p2_buttons) > len(p1_buttons):
            p1_buttons = p1_buttons + [0] * (len(p2_buttons) - len(p1_buttons))

        # step env
        current_timer = observation["timer"][0]
        p1_health_before = obs_p1["health"][0]
        p2_health_before = obs_p2["health"][0]

        total_reward = 0
        frame_starts.append(len(frames))
        for p1_button, p2_button in zip(p1_buttons, p2_buttons):
            try:
                (
                    observation,
                    reward,
                    terminated,
                    truncated,
                    info,
                ) = env.step(
                    {
                        "agent_0": p1_button,
                        "agent_1": p2_button,
                    }
                )
            except Exception as e:
                print(f"env.step() failed for step {step_idx}: {e}", file=sys.stderr)
                return []

            total_reward += reward

            frames.append(observation["frame"])

        p1_recent_moves.append(p1_move_name)
        p2_recent_moves.append(p2_move_name)

        prev_game_info = game_info
        prev_player1_state = player1
        prev_player2_state = player2

        step_data.append(
            {
                "p1": {
                    "messages": p1_messages,
                    "responses": [
                        {
                            "role": "assistant",
                            "content": p1_move_name,
                        }
                    ],
                    "reward": total_reward,
                    "health": p1_health_before,
                },
                "p2": {
                    "messages": p2_messages,
                    "responses": [
                        {
                            "role": "assistant",
                            "content": p2_move_name,
                        }
                    ],
                    "health": p2_health_before,
                },
                "timer": current_timer,
                "frame": frames[frame_starts[-1]],
            }
        )

        if total_reward == 0:
            steps_without_reward += 1
            if steps_without_reward >= max_steps_without_reward:
                warnings.warn(
                    f"Terminating episode early: {steps_without_reward} steps without reward"
                )
                break
        else:
            steps_without_reward = 0

        if terminated or truncated:
            break

        step_idx += 1
        pbar.update(1)

    pbar.close()
    print("Episode finished.")

    # calculate td-lambda returns

    dataset = []

    # map health difference and timer to reward in range [-20, 20]
    # at extreme health advantage (p1=160, p2=0) and high urgency (timer=0): 25 (capped at 20)
    # at extreme health disadvantage (p1=0, p2=160) and any timer: -20
    # at equal health (p1=160, p2=160) and no urgency (timer=100): 0
    # at equal health (p1=160, p2=160) and high urgency (timer=0): negative (time pressure penalty)
    def compute_weight(timer_value: int, p1_h: int, p2_h: int) -> float:
        health_diff = (float(p2_h) - float(p1_h)) / float(HEALTH_MAX)  # [-1, 1]
        time_urgency = (100.0 - float(timer_value)) / 100.0  # [0, 1]

        health_reward = health_diff * 20.0  # [-20, 20]
        if health_diff <= 0:
            time_penalty = time_urgency * 10.0 * (1.0 - abs(health_diff))  # [0, 10]
            weight = health_reward - time_penalty  # [-30, 20]
        else:
            time_boost = time_urgency * 5.0 * health_diff  # [0, 5]
            weight = health_reward + time_boost  # [-20, 25]

        return max(-20.0, min(20.0, weight))  # [-20, 20]

    num_steps = len(step_data)
    p1_msgs_list = [step["p1"]["messages"] for step in step_data]
    p1_rsp_list = [step["p1"]["responses"] for step in step_data]
    p1_healths = [step["p1"]["health"] for step in step_data]
    p1_rewards = [step["p1"]["reward"] for step in step_data]
    p2_msgs_list = [step["p2"]["messages"] for step in step_data]
    p2_rsp_list = [step["p2"]["responses"] for step in step_data]
    p2_healths = [step["p2"]["health"] for step in step_data]
    timers = [step["timer"] for step in step_data]
    ds_frames = [step["frame"] for step in step_data]

    def parse_messages(
        msgs_list: list[list[dict]], rsp_list: list[str]
    ) -> list[list[dict]]:
        for msgs, rsp in zip(msgs_list, rsp_list):
            msgs[1]["content"] = "<image>" + msgs[-1]["content"][-1]["text"]  # user
            msgs.extend(rsp)
        return msgs_list

    p1_msgs_list = parse_messages(p1_msgs_list, p1_rsp_list)
    p2_msgs_list = parse_messages(p2_msgs_list, p2_rsp_list)

    for i in range(num_steps):
        n_steps = min(n_move_returns, num_steps - i)
        ret = sum(p1_rewards[i + j] * (gamma**j) for j in range(n_steps))

        threshold = 0.5  # make sure we have a clear signal
        pil_image = Image.fromarray(ds_frames[i]).convert("RGB")

        image_dir = cache_path / project_name / run_name / "images" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{i}.png"
        pil_image.save(image_path)

        if ret > threshold:
            dataset.append(
                {
                    "messages": p1_msgs_list[i],
                    "label": True,
                    "images": [str(image_path)],
                }
            )
            dataset.append(
                {
                    "messages": p2_msgs_list[i],
                    "label": False,
                    "images": [str(image_path)],
                }
            )
        elif ret < -threshold:
            dataset.append(
                {
                    "messages": p1_msgs_list[i],
                    "label": False,
                    "images": [str(image_path)],
                }
            )
            dataset.append(
                {
                    "messages": p2_msgs_list[i],
                    "label": True,
                    "images": [str(image_path)],
                }
            )
        elif abs(ret) <= threshold:
            w = compute_weight(timers[i], p1_healths[i], p2_healths[i])
            if w > 5.0:  # require clear advantage
                dataset.append(
                    {
                        "messages": p1_msgs_list[i],
                        "label": True,
                        "images": [str(image_path)],
                    }
                )
                dataset.append(
                    {
                        "messages": p2_msgs_list[i],
                        "label": False,
                        "images": [str(image_path)],
                    }
                )
            elif w < -5.0:  # require clear disadvantage
                dataset.append(
                    {
                        "messages": p1_msgs_list[i],
                        "label": False,
                        "images": [str(image_path)],
                    }
                )
                dataset.append(
                    {
                        "messages": p2_msgs_list[i],
                        "label": True,
                        "images": [str(image_path)],
                    }
                )

    # misc

    if save_video and len(frames) > 0:
        import cv2

        print("Saving video...")

        out_path = cache_path / project_name / run_name / f"{split}_{idx}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        scale_factor = 3  # 384x224 -> 1152x672
        orig_height, orig_width = frames[0].shape[:2]
        up_height, up_width = orig_height * scale_factor, orig_width * scale_factor

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(
            str(out_path),
            fourcc,
            60.0,
            (up_width, up_height),  # 60 fps
        )

        for frame in frames:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = cv2.resize(
                frame, (up_width, up_height), interpolation=cv2.INTER_LINEAR
            )
            video_writer.write(frame)

        video_writer.release()
        print(f"Saved video to {out_path}")

    await cache_volume.commit.aio()

    print("Cleaning up...")
    try:
        env.close()
    except Exception as e:
        warnings.warn(f"Couldn't close environment: {e}")
    print("Done.")

    return dataset


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    # region=region,
    timeout=dataset_create_timeout,
    nonpreemptible=True,
)
async def create_dataset(
    split: str,
    run_name: str,
    project_name: str,
    n_episodes: int,
    round_idx: int,
    current_ckpt_path: str = "",
    opponent_ckpt_paths: list[str] | None = None,
):
    import random

    from datasets import Dataset

    await cache_volume.reload.aio()

    video_idxs = range(n_episodes)
    if n_videos_per_round < n_episodes:
        video_idxs = random.sample(range(n_episodes), n_videos_per_round)

    out_path = cache_path / project_name / run_name / f"{split}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return f"Dataset already exists at {out_path}"

    data = []
    completed_episodes = 0

    try:
        async for sublist in run_episode_data.starmap.aio(
            [
                (
                    idx,
                    split,
                    run_name,
                    project_name,
                    round_idx,
                    idx in video_idxs,
                    current_ckpt_path,
                    opponent_ckpt_paths,
                )
                for idx in range(n_episodes)
            ],
            return_exceptions=True,
            wrap_returned_exceptions=False,
        ):
            completed_episodes += 1
            if isinstance(sublist, Exception):
                print(
                    f"run_episode_data failed for {run_name=} {split=}: {sublist}",
                    file=sys.stderr,
                )
                continue
            data.extend(sublist)
            if completed_episodes % dataset_flush_every == 0:
                Dataset.from_list(data).to_parquet(str(out_path))
                await cache_volume.commit.aio()
    except Exception as exc:
        if not is_modal_timeout_error(exc):
            raise
        print(
            f"run_episode_data timed out for {run_name=} {split=}; keeping partial dataset",
            file=sys.stderr,
        )

    if len(data) == 0:
        raise Exception("No data collected")

    Dataset.from_list(data).to_parquet(str(out_path))
    await cache_volume.commit.aio()
    return f"Saved {len(data)} samples to {out_path}"


# training

model_name = "Qwen/Qwen3.5-35B-A3B"

# resources
# n_nodes = 1
n_gpu = 4  # n_proc_per_node
gpu = f"h200:{n_gpu}"

# batch size: https://huggingface.co/docs/trl/main/en/kto_trainer#batch-size-recommendations
global_bs = 32  # to limit noise in training
bs_per_device = 4
grad_accum_steps = global_bs // (n_gpu * bs_per_device)

# beta/lr: https://huggingface.co/docs/trl/main/en/kto_trainer#learning-rate-recommendations
lr_scheduler_type = "cosine"
warmup_ratio = 0.1
start_beta = 0.1
end_beta = 1
start_lr = 5e-7
end_lr = 1e-6


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
)
async def get_round_status(round_idx: int, max_steps: int, project_name: str):
    import time

    await cache_volume.reload.aio()

    base_path = cache_path / project_name
    prefix = f"{round_idx}-"

    run_dirs = []
    if base_path.exists():
        for path in base_path.iterdir():
            if path.is_dir() and path.name.startswith(prefix):
                run_dirs.append(path)
    if run_dirs:
        run_dirs.sort(key=lambda p: p.stat().st_mtime)
        run_dir = run_dirs[-1]
        run_name = run_dir.name
    else:
        run_name = f"{round_idx}-{time.strftime('%Y%m%d_%H%M%S')}"
        run_dir = base_path / run_name

    # check if dataset exists

    train_file = run_dir / "train.parquet"
    val_file = run_dir / "val.parquet"

    # check if training is complete

    latest_ckpt = ""
    final_ckpt = ""
    can_resume = False
    training_complete = False
    if run_dir.is_dir():
        lora_dir = run_dir / "lora"
        checkpoints = (
            [
                p
                for p in lora_dir.iterdir()
                if p.is_dir() and p.name.startswith("checkpoint-")
            ]
            if lora_dir.is_dir()
            else []
        )
        if checkpoints:
            checkpoints.sort(
                key=lambda p: (
                    int(p.name.split("checkpoint-")[-1]),
                    p.stat().st_mtime,
                )
            )
            latest_ckpt = str(checkpoints[-1])
            can_resume = True
        target = run_dir / f"checkpoint-{max_steps}"
        if (target / "config.json").is_file():
            final_ckpt = str(target)
            training_complete = True

    # check if evaluation is complete

    baseline_eval_results = base_path / "eval_results_baseline.json"
    baseline_eval_viz = base_path / "match_history_baseline.png"

    final_eval_results = base_path / "eval_results_final.json"
    final_eval_viz = base_path / "match_history_final.png"

    return {
        "project_name": project_name,
        "run_name": run_name,
        "has_baseline_eval": baseline_eval_results.exists()
        and baseline_eval_viz.exists(),
        "has_train_ds": train_file.exists(),
        "has_val_ds": val_file.exists(),
        "latest_checkpoint": latest_ckpt,
        "final_checkpoint": final_ckpt,
        "training_complete": training_complete,
        "can_resume": can_resume,
        "has_final_eval": final_eval_results.exists() and final_eval_viz.exists(),
    }


@app.function(
    image=train_image,
    gpu=gpu,
    volumes={
        cache_path: cache_volume,
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=[modal.Secret.from_dotenv(Path(__file__).parent.parent.parent)],
    timeout=train_timeout,
    retries=modal.Retries(max_retries=1, initial_delay=0.0),
    single_use_containers=True,
)
# @modal.experimental.clustered(size=n_nodes)
async def train_model(
    run_name: str,
    project_name: str,
    max_steps: int,
    beta: float,
    lr: float,
    current_ckpt_path: str = "",
    resume: bool = False,
):
    import json

    import yaml

    await cache_volume.reload.aio()

    logging_steps = max(1, max_steps // 100)
    eval_steps = max(1, max_steps // 10)

    os.environ["WANDB_PROJECT"] = project_name
    os.environ["WANDB_RUN_NAME"] = run_name

    # cluster_info = modal.experimental.get_cluster_info()

    os.chdir(TRAIN_REPO_PATH)
    data_path = Path("data")
    save_dir = cache_path / project_name / run_name
    save_dir.mkdir(parents=True, exist_ok=True)
    lora_dir = save_dir / "lora"
    lora_dir.mkdir(parents=True, exist_ok=True)
    final_ckpt = save_dir / f"checkpoint-{max_steps}"
    final_ckpt_config = final_ckpt / "config.json"

    if final_ckpt_config.is_file():
        print(f"Final checkpoint already present at {final_ckpt}")
        return str(final_ckpt)
    if final_ckpt.exists():
        print(f"Removing incomplete export at {final_ckpt}")
        shutil.rmtree(final_ckpt)

    with open(str(data_path / "dataset_info.json"), "w") as f:
        json.dump(
            {
                f"kto_{split}": {
                    "file_name": str(
                        cache_path / project_name / run_name / f"{split}.parquet"
                    ),
                    "formatting": "sharegpt",
                    "columns": {
                        "messages": "messages",
                        "kto_tag": "label",
                        "images": "images",
                    },
                    "tags": {
                        "role_tag": "role",
                        "content_tag": "content",
                        "user_tag": "user",
                        "assistant_tag": "assistant",
                        "system_tag": "system",
                    },
                }
                for split in ["train", "val"]
            },
            f,
        )

    resume_path = None
    candidates = [
        d for d in lora_dir.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")
    ]
    if candidates:
        candidates.sort(
            key=lambda p: (
                int(p.name.split("checkpoint-")[-1]),
                p.stat().st_mtime,
            )
        )
        resume_path = str(candidates[-1])
        print(f"Resuming training from {resume_path}")
    elif resume:
        print("Resume requested, but no checkpoint found")

    train_yaml_path = str(data_path / "config.yaml")
    with open(train_yaml_path, "w") as f:
        yaml.dump(
            {
                # model
                "model_name_or_path": current_ckpt_path or model_name,
                "image_max_pixels": 262144,
                "trust_remote_code": True,
                "enable_thinking": False,
                # method
                "stage": "kto",
                "do_train": True,
                "finetuning_type": "lora",
                "lora_rank": 8,
                "lora_target": "all",
                "pref_beta": beta,
                # dataset
                "dataset": "kto_train",
                "template": "qwen3_5",
                "cutoff_len": 2048,
                "overwrite_cache": True,
                "preprocessing_num_workers": 16,
                "dataloader_num_workers": 4,
                # output
                "output_dir": str(lora_dir),
                "logging_steps": logging_steps,
                "save_strategy": "steps",
                "save_steps": max_steps,
                "plot_loss": True,
                "overwrite_output_dir": resume_path is None,
                "save_only_model": False,
                "include_effective_tokens_per_second": True,
                "report_to": "wandb",
                "run_name": run_name,
                # train
                "per_device_train_batch_size": bs_per_device,
                "gradient_accumulation_steps": grad_accum_steps,
                "learning_rate": lr,
                "lr_scheduler_type": lr_scheduler_type,
                "warmup_ratio": warmup_ratio,
                "max_steps": max_steps,
                "bf16": True,
                "ddp_timeout": 180000000,
                "resume_from_checkpoint": resume_path,
                # eval
                "eval_dataset": "kto_val",
                "per_device_eval_batch_size": bs_per_device,
                "eval_strategy": "steps",
                "eval_steps": eval_steps,
            },
            f,
        )

    export_yaml_path = str(data_path / "export.yaml")
    with open(export_yaml_path, "w") as f:
        yaml.dump(
            {
                # model
                "model_name_or_path": current_ckpt_path or model_name,
                "adapter_name_or_path": str(lora_dir),
                "template": "qwen3_5",
                "trust_remote_code": True,
                "enable_thinking": False,
                # export
                "export_dir": str(final_ckpt),
                "export_size": 5,
                "export_device": "cpu",
                "export_legacy_format": False,
            },
            f,
        )

    os.environ["FORCE_TORCHRUN"] = "1"
    os.environ["DISABLE_VERSION_CHECK"] = "1"
    # os.environ["NNODES"] = "1"
    # os.environ["NODE_RANK"] = "0"
    # os.environ["MASTER_ADDR"] = "127.0.0.1"
    # os.environ["MASTER_PORT"] = "1234"

    _exec_subprocess(["llamafactory-cli", "train", train_yaml_path])
    await cache_volume.commit.aio()
    _exec_subprocess(["llamafactory-cli", "export", export_yaml_path])
    if not final_ckpt_config.is_file():
        raise RuntimeError(f"Export incomplete: missing {final_ckpt_config}")
    await cache_volume.commit.aio()

    return str(final_ckpt)


# evaluation


# async def create_openai_client():
#     from openai import OpenAI
#
#     return OpenAI()
#
#
# opponent = "gpt-5.4-nano"
# reasoning = {"effort": "none"}
# text = {"verbosity": "low"}
#
# k_factor = 16.0
# initial_rating = 1200.0
#
#
# @app.function(
#     image=train_image,
#     volumes={cache_path: cache_volume},
#     # region=region,
#     secrets=[modal.Secret.from_dotenv(Path(__file__).parent.parent.parent)],
#     timeout=episode_timeout,
# )
# async def run_episode_eval(
#     idx: int,
#     project_name: str,
#     save_video: bool,
#     eval_suffix: str,
#     current_ckpt_path: str,
# ):
#     import asyncio
#     from collections import deque
#
#     from tqdm import tqdm
#
#     ## init bg processes
#
#     characters = [character, character]
#     outfits = [outfit, outfit]
#     super_arts = [super_art, super_art]
#
#     tasks = [
#         create_sandbox(),
#         create_llm(current_ckpt_path),
#         create_openai_client(),
#     ]
#     sandbox, trained_llm, openai_client = await asyncio.gather(*tasks)
#
#     if sandbox is None:
#         return None
#     if trained_llm is None:
#         await sandbox.terminate.aio()
#         return None
#
#     try:
#         env = await asyncio.wait_for(
#             asyncio.to_thread(
#                 create_environment,
#                 characters,
#                 outfits,
#                 super_arts,
#             ),
#             timeout=env_create_timeout,
#         )
#     except asyncio.TimeoutError:
#         print("Timeout while creating environment", file=sys.stderr)
#         await sandbox.terminate.aio()
#         return None
#     if env is None:
#         await sandbox.terminate.aio()
#         return None
#
#     # init episode
#
#     try:
#         observation, info = env.reset()
#     except Exception as e:
#         print(f"env.reset() failed: {e}", file=sys.stderr)
#         await sandbox.terminate.aio()
#         return None
#
#     step_idx = 0
#     steps_without_reward = 0
#     winner = None
#
#     prev_game_info = None
#     prev_player1_state = None
#     prev_player2_state = None
#     p1_recent_moves = deque(maxlen=recent_move_limit)
#     p2_recent_moves = deque(maxlen=recent_move_limit)
#     frames = []
#
#     # run episode
#
#     print("Running episode...")
#     pbar = tqdm(desc="step_idx", unit="step")
#     while True:
#         # get info for prompt
#         obs_p1 = observation["P1"]
#         obs_p2 = observation["P2"]
#         game_info = GameInfo(
#             timer=observation["timer"][0],
#         )
#         p1_side = obs_p1["side"]
#         player1 = PlayerState(
#             character=character,
#             super_art=super_arts[0],
#             wins=obs_p1["wins"][0],
#             side=p1_side,
#             stunned=obs_p1["stunned"],
#             stun_bar=obs_p1["stun_bar"][0],
#             health=obs_p1["health"][0],
#             super_count=obs_p1["super_count"][0],
#             super_bar=obs_p1["super_bar"][0],
#         )
#         player2 = PlayerState(
#             character=character,
#             super_art=super_arts[1],
#             wins=obs_p2["wins"][0],
#             side=obs_p2["side"],
#             stunned=obs_p2["stunned"],
#             stun_bar=obs_p2["stun_bar"][0],
#             health=obs_p2["health"][0],
#             super_count=obs_p2["super_count"][0],
#             super_bar=obs_p2["super_bar"][0],
#         )
#
#         # run trained policy
#         buffer = BytesIO()
#         Image.fromarray(observation["frame"]).save(buffer, format="PNG")
#         p1_messages, p1_available_moves = create_messages(
#             game_info,
#             player2,
#             player1,
#             prev_game_info,
#             prev_player2_state,
#             prev_player1_state,
#             p1_recent_moves,
#             frames=[f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode("utf-8")}"],
#         )
#         try:
#             (
#                 p1_buttons,
#                 p1_move_name,
#             ) = await trained_llm.chat.remote.aio(
#                 p1_messages,
#                 character,
#                 super_arts[0],
#                 obs_p1["super_count"][0],
#                 p1_side,
#                 p1_available_moves,
#             )
#         except Exception as e:
#             print(f"trained_llm.chat failed: {e}", file=sys.stderr)
#             await sandbox.terminate.aio()
#             return None
#
#         # run opponent policy
#         buffer = BytesIO()
#         Image.fromarray(observation["frame"]).save(buffer, format="PNG")
#         p2_messages, p2_available_moves = create_messages(
#             game_info,
#             player1,
#             player2,
#             prev_game_info,
#             prev_player1_state,
#             prev_player2_state,
#             p2_recent_moves,
#             frames=[f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode("utf-8")}"],
#         )
#         try:
#             response = openai_client.responses.create(
#                 model=opponent,
#                 input=p2_messages,
#                 reasoning=reasoning,
#                 text=text,
#             )
#             p2_move_name = response.output_text
#             p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])
#             if p2_buttons is None or p2_move_name not in p2_available_moves:
#                 raise Exception(f"Invalid move from OpenAI: {p2_move_name}")
#         except Exception as e:
#             print(f"openai_client.responses.create failed: {e}", file=sys.stderr)
#             await sandbox.terminate.aio()
#             return None
#
#         # pad shorter move sequence to match longer one
#         if len(p1_buttons) > len(p2_buttons):
#             p2_buttons = p2_buttons + [0] * (len(p1_buttons) - len(p2_buttons))
#         elif len(p2_buttons) > len(p1_buttons):
#             p1_buttons = p1_buttons + [0] * (len(p2_buttons) - len(p1_buttons))
#
#         # step env
#         total_reward = 0
#         for p1_button, p2_button in zip(p1_buttons, p2_buttons):
#             try:
#                 (
#                     observation,
#                     reward,
#                     terminated,
#                     truncated,
#                     info,
#                 ) = env.step(
#                     {
#                         "agent_0": p1_button,
#                         "agent_1": p2_button,
#                     }
#                 )
#             except Exception as e:
#                 print(f"env.step() failed for step {step_idx}: {e}", file=sys.stderr)
#                 await sandbox.terminate.aio()
#                 return None
#
#             total_reward += reward
#
#             if save_video:
#                 frames.append(observation["frame"])
#
#         p1_recent_moves.append(p1_move_name)
#         p2_recent_moves.append(p2_move_name)
#
#         prev_game_info = game_info
#         prev_player1_state = player1
#         prev_player2_state = player2
#
#         if total_reward == 0:
#             steps_without_reward += 1
#             if steps_without_reward >= max_steps_without_reward:
#                 warnings.warn(
#                     f"Terminating episode early: {steps_without_reward} steps without reward"
#                 )
#                 break
#         else:
#             steps_without_reward = 0
#
#         if terminated or truncated:
#             break
#
#         step_idx += 1
#         pbar.update(1)
#
#     pbar.close()
#     print("Episode finished.")
#
#     # misc
#
#     if save_video and len(frames) > 0:
#         import cv2
#
#         print("Saving video...")
#
#         out_path = cache_path / project_name / f"eval_{idx}{eval_suffix}.mp4"
#         out_path.parent.mkdir(parents=True, exist_ok=True)
#
#         scale_factor = 3  # 384x224 -> 1152x672
#         orig_height, orig_width = frames[0].shape[:2]
#         up_height, up_width = orig_height * scale_factor, orig_width * scale_factor
#
#         fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#         video_writer = cv2.VideoWriter(
#             str(out_path),
#             fourcc,
#             60.0,
#             (up_width, up_height),  # 60 fps
#         )
#
#         for frame in frames:
#             frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
#             frame = cv2.resize(
#                 frame, (up_width, up_height), interpolation=cv2.INTER_LINEAR
#             )
#             video_writer.write(frame)
#
#         video_writer.release()
#         print(f"Saved video to {out_path}")
#
#     print("Cleaning up...")
#     try:
#         env.close()
#     except Exception as e:
#         warnings.warn(f"Couldn't close environment: {e}")
#     await sandbox.terminate.aio()
#     print("Done.")
#
#     p1_wins = observation["P1"]["wins"][0]
#     p2_wins = observation["P2"]["wins"][0]
#     if p1_wins > p2_wins:
#         winner = current_ckpt_path
#     elif p2_wins > p1_wins:
#         winner = opponent
#     else:
#         winner = None
#     return winner
#
#
# def calculate_elo_scores(
#     models: list,
#     match_results: list,
# ):
#     from collections import defaultdict
#
#     ratings = defaultdict(lambda: initial_rating)
#     match_history = []
#     elo_over_time = {model: [initial_rating] for model in models}
#
#     for match_idx, result in enumerate(match_results):
#         if result is not None:
#             winner = result
#             loser = [m for m in models if m != winner][0]
#
#             r_winner = ratings[winner]
#             r_loser = ratings[loser]
#
#             e_winner = 1 / (1 + 10 ** ((r_loser - r_winner) / 400))
#             e_loser = 1 / (1 + 10 ** ((r_winner - r_loser) / 400))
#
#             ratings[winner] = r_winner + k_factor * (1 - e_winner)
#             ratings[loser] = r_loser + k_factor * (0 - e_loser)
#
#             match_history.append(
#                 {
#                     "match_num": match_idx + 1,
#                     "type": "win",
#                     "winner": winner,
#                     "loser": loser,
#                     "winner_elo_before": r_winner,
#                     "winner_elo_after": ratings[winner],
#                     "loser_elo_before": r_loser,
#                     "loser_elo_after": ratings[loser],
#                 }
#             )
#         else:
#             r1 = ratings[models[0]]
#             r2 = ratings[models[1]]
#
#             e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
#             e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
#
#             ratings[models[0]] = r1 + k_factor * (0.5 - e1)
#             ratings[models[1]] = r2 + k_factor * (0.5 - e2)
#
#             match_history.append(
#                 {
#                     "match_num": match_idx + 1,
#                     "type": "draw",
#                     "player1": models[0],
#                     "player2": models[1],
#                     "player1_elo_before": r1,
#                     "player1_elo_after": ratings[models[0]],
#                     "player2_elo_before": r2,
#                     "player2_elo_after": ratings[models[1]],
#                 }
#             )
#
#         for model in models:
#             elo_over_time[model].append(ratings[model])
#
#     return dict(ratings), match_history, elo_over_time
#
#
# def create_elo_prog_viz(
#     models: list,
#     match_results: list,
#     save_path: str = None,
# ):
#     import matplotlib.pyplot as plt
#
#     elo_scores, match_history, elo_over_time = calculate_elo_scores(
#         models, match_results
#     )
#
#     fig, ax = plt.subplots(figsize=(12, 6))
#
#     for model in models:
#         elo_trajectory = elo_over_time[model]
#         label = model.split("/")[-1] if "/" in model else model
#         ax.plot(
#             range(len(elo_trajectory)),
#             elo_trajectory,
#             marker="o",
#             markersize=2,
#             label=label,
#         )
#     ax.axhline(y=initial_rating, color="gray", linestyle="--", alpha=0.5)
#     ax.set_xlabel("Match Number")
#     ax.set_ylabel("ELO Rating")
#     ax.set_title("ELO Progression")
#     ax.legend()
#     ax.grid(True, alpha=0.3)
#
#     plt.tight_layout()
#     save_path = Path(save_path)
#     save_path.parent.mkdir(parents=True, exist_ok=True)
#     plt.savefig(save_path, dpi=150, bbox_inches="tight")
#     plt.close()
#
#     print(f"Match history visualization saved to {save_path}")
#
#     return elo_scores
#
#
# @app.function(
#     image=train_image,
#     volumes={cache_path: cache_volume},
#     # region=region,
#     timeout=eval_timeout,
# )
# async def evaluate_model(
#     project_name: str,
#     n_episodes: int,
#     eval_suffix: str,
#     current_ckpt_path: str,
# ):
#     import json
#     import random
#
#     video_idxs = range(n_episodes)
#     if n_videos_per_round < n_episodes:
#         video_idxs = random.sample(range(n_episodes), n_videos_per_round)
#
#     data = []
#     async for winner in run_episode_eval.starmap.aio(
#         [
#             (
#                 idx,
#                 project_name,
#                 idx in video_idxs,
#                 eval_suffix,
#                 current_ckpt_path,
#             )
#             for idx in range(n_episodes)
#         ]
#     ):
#         data.append(winner)
#
#     if len(data) == 0:
#         raise Exception("No data collected")
#
#     models = [current_ckpt_path, opponent]
#
#     viz_path = cache_path / project_name / f"match_history{eval_suffix}.png"
#     elo_scores = create_elo_prog_viz(models, data, save_path=str(viz_path))
#
#     eval_results_path = cache_path / project_name / f"eval_results{eval_suffix}.json"
#     with open(eval_results_path, "w") as f:
#         json.dump(
#             {
#                 "trained_elo": elo_scores[current_ckpt_path],
#                 "opponent_elo": elo_scores[opponent],
#                 "trained_win_rate": sum(1 for r in data if r == current_ckpt_path)
#                 / len(data),
#                 "opponent_win_rate": sum(1 for r in data if r == opponent) / len(data),
#                 "draw_rate": sum(1 for r in data if r is None) / len(data),
#             },
#             f,
#         )


@app.local_entrypoint()
async def local(
    # scale
    n_rounds: int = 10,
    n_train_episodes_per_round: int = 45,  # ~32k samples
    n_val_episodes_per_round: int = 5,
    # training
    max_steps: int = 1000,
    # evaluation
    n_eval_episodes: int = 20,
):
    project_name = f"{app.name}-{model_name.split('/')[-1].replace('.', '_').lower()}-{n_rounds}-{max_steps}"

    current_ckpt_path = ""
    all_prior_models = []

    # baseline evaluation

    status = await get_round_status.remote.aio(0, max_steps, project_name)
    # if not status["has_baseline_eval"]:
    #     await evaluate_model.remote.aio(
    #         project_name,
    #         n_eval_episodes,
    #         "_baseline",
    #         model_name,
    #     )

    # training loop

    for round_idx in range(n_rounds):
        status = await get_round_status.remote.aio(round_idx, max_steps, project_name)
        run_name = status["run_name"]

        if status["training_complete"] and status["final_checkpoint"]:
            if current_ckpt_path and (
                not all_prior_models or all_prior_models[-1] != current_ckpt_path
            ):
                all_prior_models.append(current_ckpt_path)
            current_ckpt_path = status["final_checkpoint"]
            continue

        ckpt_to_use = "" if round_idx == 0 else current_ckpt_path

        if not (status["has_train_ds"] and status["has_val_ds"]):
            if round_idx == 0:  # only random moves for bootstrapping
                opponent_pool = []
            elif round_idx == 1:  # self-play against round 0 model + random
                opponent_pool = [current_ckpt_path] if current_ckpt_path else []
            else:  # mix of recent models for diverse opponents
                recent_models = all_prior_models[-opponent_pool_size_per_round:]
                opponent_pool = recent_models + [None] if recent_models else [None]

            dataset_specs = []
            if not status["has_train_ds"]:
                dataset_specs.append(("train", n_train_episodes_per_round))
            if not status["has_val_ds"]:
                dataset_specs.append(("val", n_val_episodes_per_round))

            async def ensure_dataset_split(split: str, n_episodes: int):
                for attempt_idx in range(max_dataset_attempts):
                    status = await get_round_status.remote.aio(
                        round_idx, max_steps, project_name
                    )
                    split_is_ready = (
                        status["has_train_ds"]
                        if split == "train"
                        else status["has_val_ds"]
                    )
                    if split_is_ready:
                        return

                    try:
                        await create_dataset.remote.aio(
                            split,
                            run_name,
                            project_name,
                            n_episodes,
                            round_idx,
                            ckpt_to_use,
                            opponent_pool,
                        )
                        return
                    except Exception as exc:
                        if not is_modal_timeout_error(exc):
                            raise

                        status = await get_round_status.remote.aio(
                            round_idx, max_steps, project_name
                        )
                        split_is_ready = (
                            status["has_train_ds"]
                            if split == "train"
                            else status["has_val_ds"]
                        )
                        if split_is_ready:
                            print(
                                f"{split} dataset present after timeout for round {round_idx}; continuing"
                            )
                            return

                        if attempt_idx == max_dataset_attempts - 1:
                            raise

                        print(
                            f"{split} dataset timed out for round {round_idx}; retrying"
                        )

            if dataset_specs:
                await asyncio.gather(
                    *(
                        ensure_dataset_split(split, n_episodes)
                        for split, n_episodes in dataset_specs
                    )
                )

        status = await get_round_status.remote.aio(round_idx, max_steps, project_name)
        if not (status["has_train_ds"] and status["has_val_ds"]):
            raise RuntimeError(f"Missing dataset artifacts for round {round_idx}")

        if not status["training_complete"]:
            progress = round_idx / max(1, n_rounds - 1)
            beta = start_beta + (end_beta - start_beta) * progress
            lr = start_lr + (end_lr - start_lr) * progress

            new_ckpt_path = ""
            for attempt_idx in range(max_train_attempts):
                status = await get_round_status.remote.aio(
                    round_idx, max_steps, project_name
                )
                if status["training_complete"] and status["final_checkpoint"]:
                    new_ckpt_path = status["final_checkpoint"]
                    break

                try:
                    new_ckpt_path = await train_model.remote.aio(
                        run_name,
                        project_name,
                        max_steps,
                        beta,
                        lr,
                        ckpt_to_use,
                        status["can_resume"],
                    )
                    break
                except Exception as exc:
                    if not is_modal_timeout_error(exc):
                        raise

                    status = await get_round_status.remote.aio(
                        round_idx, max_steps, project_name
                    )
                    if status["training_complete"] and status["final_checkpoint"]:
                        print(
                            f"Final checkpoint present after timeout for round {round_idx}; continuing"
                        )
                        new_ckpt_path = status["final_checkpoint"]
                        break

                    if (
                        not status["can_resume"]
                        or attempt_idx == max_train_attempts - 1
                    ):
                        raise

                    print(
                        f"Training timed out for round {round_idx}; retrying from {status['latest_checkpoint']}"
                    )

            if current_ckpt_path and (
                not all_prior_models or all_prior_models[-1] != current_ckpt_path
            ):
                all_prior_models.append(current_ckpt_path)
            current_ckpt_path = new_ckpt_path
        else:
            if current_ckpt_path and (
                not all_prior_models or all_prior_models[-1] != current_ckpt_path
            ):
                all_prior_models.append(current_ckpt_path)
            current_ckpt_path = status["final_checkpoint"]

    # final evaluation

    # final_status = await get_round_status.remote.aio(n_rounds - 1, max_steps, project_name)
    # if not final_status["has_final_eval"]:
    #     await evaluate_model.remote.aio(
    #         project_name,
    #         n_eval_episodes,
    #         f"_{final_status['run_name']}",
    #         current_ckpt_path,
    #     )
