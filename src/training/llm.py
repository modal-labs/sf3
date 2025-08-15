import os
import sys
import warnings
from pathlib import Path

import modal
import modal.experimental

from ..llm import LLMServer
from ..llm import app as llm_app
from ..utils import (
    CHARACTER_TO_ID,
    HEALTH_MAX,
    GameInfo,
    PlayerState,
    create_messages,
    gb,
    get_available_instructions_for_character,
    minutes,
    parse_move,
    seed,
    # region,
)
from ..yolo import YOLOServer
from ..yolo import app as yolo_app

# Modal setup

app = modal.App("sf3-llm-train").include(llm_app).include(yolo_app)

# diambra engine
engine_app = modal.App.lookup("sf3-engine-train", create_if_missing=True)
engine_image = (
    modal.experimental.raw_registry_image("docker.io/diambra/engine:v2.2.4")
    .env(
        {
            "HOME": "/tmp",
        }
    )
    .entrypoint([])
    # since sandbox is created in app, files will be in Modal container, not locally
    # so we need to add them to the web app image as well
    .add_local_file(
        "/root/sfiii3n.zip",
        "/opt/diambraArena/roms/sfiii3n.zip",
    )
    .add_local_file(
        "/root/credentials",
        "/tmp/.diambra/credentials",
    )
)

# training
local_engine_dir = Path(__file__).parent.parent.parent / "assets" / "engine"
remote_train_script_path = "/root/trl_train.py"
train_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .uv_pip_install(
        "accelerate==1.10.0",
        "datasets==3.6.0",
        "diambra==0.0.20",
        "diambra-arena==2.2.7",
        "flashinfer-python==0.2.6.post1",
        "huggingface_hub[hf_transfer]==0.34.4",
        "matplotlib==3.10.5",
        "openai==1.99.9",
        "torch==2.7.1",
        "trl==0.21.0",
        "wandb==0.21.0",
        extra_index_url="https://download.pytorch.org/whl/cu128",
        extra_options="--index-strategy unsafe-best-match",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
    )
    # engine
    .add_local_file(
        local_engine_dir / "sfiii3n.zip",
        "/root/sfiii3n.zip",
    )
    .add_local_file(
        local_engine_dir / "credentials",
        "/root/credentials",
    )
    # training
    .add_local_file(
        Path(__file__).parent / "trl_train.py",
        remote_train_script_path,
    )
)

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sf3-vllm-cache", create_if_missing=True)
cache_path = Path("/cache")
cache_volume = modal.Volume.from_name("sf3-llm-train-cache", create_if_missing=True)

# helper fns


async def create_llm(ckpt_path: str = ""):
    try:
        print("Creating LLM...")
        llm = LLMServer(ckpt_path=ckpt_path)
        await llm.boot.remote.aio()
        print("LLM created")
        return llm
    except Exception as e:
        print(f"Couldn't create LLM: {e}", file=sys.stderr)
        return None


async def create_yolo():
    try:
        print("Creating YOLO...")
        yolo = YOLOServer()
        await yolo.boot.remote.aio()
        print("YOLO created")
        return yolo
    except Exception as e:
        print(f"Couldn't create YOLO: {e}", file=sys.stderr)
        return None


async def create_sandbox():
    try:
        print("Creating sandbox...")
        engine_port = 50051
        sandbox = modal.Sandbox.create(
            "/bin/diambraEngineServer",
            app=engine_app,
            image=engine_image,
            timeout=2 * 60 * minutes,
            unencrypted_ports=[engine_port],
            verbose=True,
        )
        tunnels = sandbox.tunnels()
        tunnel = tunnels[engine_port]
        host, port = tunnel.tcp_socket
        os.environ["DIAMBRA_ENVS"] = f"{host}:{port}"
        print(f"Created sandbox {sandbox.object_id} at {host}:{port}")
        return sandbox
    except Exception as e:
        print(f"Couldn't create sandbox: {e}", file=sys.stderr)
        return None


def create_environment(
    characters: list[str],
    outfits: list[int],
    super_arts: list[int],
):
    import diambra.arena as arena
    from diambra.arena import EnvironmentSettingsMultiAgent, Roles, SpaceTypes

    print("Creating diambra environment...")
    settings = EnvironmentSettingsMultiAgent(
        step_ratio=6,
        role=(Roles.P1, Roles.P2),
        render_mode="rgb_array",
        splash_screen=False,
        grpc_timeout=15,
        action_space=(SpaceTypes.DISCRETE, SpaceTypes.DISCRETE),
        characters=characters,
        outfits=outfits,
        super_art=super_arts,
    )
    try:
        env = arena.make("sfiii3n", settings)
    except Exception as e:
        print(f"Couldn't create diambra environment: {e}", file=sys.stderr)
        return None
    print("diambra environment created successfully!")
    return env


# dataset

# reduce variance
character = "Ken"
outfit = 1
super_art = 1

# increase move var
recent_move_limit = 20
max_steps_without_reward = 64
opponent_pool_size_per_round = 3

# TD-lambda returns
n_move_returns = 16
gamma = 0.99

# misc
n_videos_per_round = 1


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    # region=region,
    timeout=2 * 60 * minutes,
)
async def run_episode_data(
    idx: int,
    split: str,
    run_name: str,
    project_name: str,
    save_video: bool,
    round_idx: int,
    current_ckpt_path: str = "",
    opponent_ckpt_paths: list[str] | None = None,
):
    import asyncio
    import random

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

    tasks = [create_sandbox(), create_yolo()]

    # first round: just use random moves to "bootstrap" the model
    if round_idx == 0:
        tasks.append(asyncio.to_thread(lambda: None))
    else:
        tasks.append(create_llm(current_ckpt_path))

    if selected_opponent_path:
        tasks.append(create_llm(selected_opponent_path))
    else:
        tasks.append(asyncio.to_thread(lambda: None))

    sandbox, yolo, current_llm, prior_llm = await asyncio.gather(*tasks)

    if sandbox is None:
        return []
    if yolo is None:
        sandbox.terminate()
        return []
    if round_idx > 0 and current_llm is None:
        sandbox.terminate()
        return []
    if selected_opponent_path and prior_llm is None:
        sandbox.terminate()
        return []

    try:
        env = await asyncio.wait_for(
            asyncio.to_thread(
                create_environment,
                characters,
                outfits,
                super_arts,
            ),
            timeout=15,
        )
    except asyncio.TimeoutError:
        print("Timeout while creating environment", file=sys.stderr)
        sandbox.terminate()
        return []
    if env is None:
        sandbox.terminate()
        return []

    # init episode

    try:
        observation, info = env.reset()
    except Exception as e:
        print(f"env.reset() failed: {e}", file=sys.stderr)
        sandbox.terminate()
        return []

    step_idx = 0
    steps_without_reward = 0

    p1_recent_moves = []
    p2_recent_moves = []
    step_data = []
    frames = []

    # run episode

    print("Running episode...")
    pbar = tqdm(desc="step_idx", unit="step")
    while True:
        # get info for prompt
        obs_p1 = observation["P1"]
        obs_p2 = observation["P2"]
        boxes, class_ids = await yolo.detect_characters.remote.aio(
            [CHARACTER_TO_ID[character], CHARACTER_TO_ID[character]],
            observation["frame"],
        )
        game_info = GameInfo(
            timer=observation["timer"][0],
            boxes=boxes,
            class_ids=class_ids,
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

        # run current policy
        p1_messages = create_messages(game_info, player2, player1, p1_recent_moves)
        if round_idx == 0:
            available_moves = get_available_instructions_for_character(
                character, super_arts[0], obs_p1["super_count"][0]
            )
            p1_move_name = random.choice(available_moves)
            p1_buttons = parse_move(character, p1_move_name, p1_side)
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
                )
            except Exception as e:
                print(f"current_llm.chat failed: {e}", file=sys.stderr)
                sandbox.terminate()
                return []

        # run opponent policy
        p2_messages = create_messages(game_info, player1, player2, p2_recent_moves)
        if prior_llm is None:
            available_moves = get_available_instructions_for_character(
                character, super_arts[1], obs_p2["super_count"][0]
            )
            p2_move_name = random.choice(available_moves)
            p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])
        else:
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
                sandbox.terminate()
                return []

            total_reward += reward

            if save_video:
                boxes, class_ids = await yolo.detect_characters.remote.aio(
                    [CHARACTER_TO_ID[character], CHARACTER_TO_ID[character]],
                    observation["frame"],
                )
                frames.append(observation["frame"])

        p1_recent_moves.append(p1_move_name)
        if len(p1_recent_moves) > recent_move_limit:
            p1_recent_moves.pop(0)
        p2_recent_moves.append(p2_move_name)
        if len(p2_recent_moves) > recent_move_limit:
            p2_recent_moves.pop(0)

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

    # calculate TD-lambda returns

    dataset = []

    # https://docs.diambra.ai/envs/#reward-function
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
    p1_messages = [step["p1"]["messages"] for step in step_data]
    p1_responses = [step["p1"]["responses"] for step in step_data]
    p1_rewards = [step["p1"]["reward"] for step in step_data]
    p2_messages = [step["p2"]["messages"] for step in step_data]
    p2_responses = [step["p2"]["responses"] for step in step_data]
    timers = [step["timer"] for step in step_data]
    p1_healths = [step["p1"]["health"] for step in step_data]
    p2_healths = [step["p2"]["health"] for step in step_data]

    for i in range(num_steps):
        n_steps = min(n_move_returns, num_steps - i)
        ret = sum(p1_rewards[i + j] * (gamma**j) for j in range(n_steps))

        threshold = 0.5  # make sure we have a clear signal
        if ret > threshold:
            dataset.append(
                {
                    "prompt": p1_messages[i],
                    "completion": p1_responses[i],
                    "label": True,
                }
            )
            dataset.append(
                {
                    "prompt": p2_messages[i],
                    "completion": p2_responses[i],
                    "label": False,
                }
            )
        elif ret < -threshold:
            dataset.append(
                {
                    "prompt": p1_messages[i],
                    "completion": p1_responses[i],
                    "label": False,
                }
            )
            dataset.append(
                {
                    "prompt": p2_messages[i],
                    "completion": p2_responses[i],
                    "label": True,
                }
            )
        elif abs(ret) <= threshold:
            w = compute_weight(timers[i], p1_healths[i], p2_healths[i])
            if w > 5.0:  # require clear advantage
                dataset.append(
                    {
                        "prompt": p1_messages[i],
                        "completion": p1_responses[i],
                        "label": True,
                    }
                )
                dataset.append(
                    {
                        "prompt": p2_messages[i],
                        "completion": p2_responses[i],
                        "label": False,
                    }
                )
            elif w < -5.0:  # require clear disadvantage
                dataset.append(
                    {
                        "prompt": p1_messages[i],
                        "completion": p1_responses[i],
                        "label": False,
                    }
                )
                dataset.append(
                    {
                        "prompt": p2_messages[i],
                        "completion": p2_responses[i],
                        "label": True,
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

    print("Cleaning up...")
    try:
        env.close()
    except Exception as e:
        warnings.warn(f"Couldn't close environment: {e}")
    sandbox.terminate()
    print("Done.")

    return dataset


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    # region=region,
    timeout=2 * 60 * minutes,
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

    cache_volume.reload()

    video_idxs = range(n_episodes)
    if n_videos_per_round < n_episodes:
        video_idxs = random.sample(range(n_episodes), n_videos_per_round)

    data = []
    async for sublist in run_episode_data.starmap.aio(
        [
            (
                idx,
                split,
                run_name,
                project_name,
                idx in video_idxs,
                round_idx,
                current_ckpt_path,
                opponent_ckpt_paths,
            )
            for idx in range(n_episodes)
        ]
    ):
        data.extend(sublist)

    if len(data) == 0:
        raise Exception("No data collected")

    ds = Dataset.from_list(data)
    out_path = cache_path / project_name / run_name / f"{split}.parquet"
    ds.to_parquet(str(out_path))
    return f"Saved {len(ds)} samples to {out_path}"


# training

model_name = "Qwen/Qwen3-8B"  # "Qwen/Qwen3-8B-Base"

# increase beta + lr over rounds to encourage more exploitation
start_beta = 0.01  # 0.1
end_beta = 0.1  # 1
start_lr = 5e-7
end_lr = 1e-6  # 5e-6

# resources
n_gpu = 8
gpu = f"h200:{n_gpu}"
cpu = n_gpu * 4
memory = n_gpu * 8 * gb


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
)
def get_round_status(round_idx: int, max_steps: int):
    import time

    cache_volume.reload()

    project_name = f"{app.name}-{model_name.split('/')[-1].lower()}"
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
    has_train_ds = train_file.exists()
    has_val_ds = val_file.exists()

    # check if training is complete

    latest_ckpt = ""
    final_ckpt = ""
    can_resume = False
    training_complete = False
    if run_dir.is_dir():
        checkpoints = [
            p
            for p in run_dir.iterdir()
            if p.is_dir() and p.name.startswith("checkpoint-")
        ]
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
            if target.exists():
                final_ckpt = str(target)
                training_complete = True

    # check if evaluation is complete

    baseline_eval_results = run_dir / "eval_results_baseline.json"
    baseline_eval_viz = run_dir / "match_history_baseline.png"
    has_baseline_eval = baseline_eval_results.exists() and baseline_eval_viz.exists()
    final_eval_results = run_dir / "eval_results.json"
    final_eval_viz = run_dir / "match_history.png"
    has_final_eval = final_eval_results.exists() and final_eval_viz.exists()

    return {
        "project_name": project_name,
        "run_name": run_name,
        "has_baseline_eval": has_baseline_eval,
        "has_train_ds": has_train_ds,
        "has_val_ds": has_val_ds,
        "latest_checkpoint": latest_ckpt,
        "final_checkpoint": final_ckpt,
        "training_complete": training_complete,
        "can_resume": can_resume,
        "has_final_eval": has_final_eval,
    }


@app.function(
    image=train_image,
    gpu=gpu,
    cpu=cpu,
    memory=memory,
    volumes={
        cache_path: cache_volume,
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=[modal.Secret.from_name("ajhinh-wandb-secret")],
    timeout=24 * 60 * minutes,
)
def train_model(
    run_name: str,
    project_name: str,
    max_steps: int,
    beta: float,
    lr: float,
    current_ckpt_path: str = "",
    resume: bool = False,
):
    import os
    import subprocess

    os.environ["WANDB_PROJECT"] = project_name

    cache_volume.reload()

    cmd = [
        "accelerate",
        "launch",
        f"--num_processes={str(n_gpu)}",
        "--mixed_precision=bf16",
        remote_train_script_path,
        "--run_name",
        run_name,
        "--train_file",
        str(cache_path / project_name / run_name / "train.parquet"),
        "--eval_file",
        str(cache_path / project_name / run_name / "val.parquet"),
        "--model_name_or_path",
        current_ckpt_path or model_name,
        "--save_dir",
        str(cache_path / project_name / run_name),
        "--max_steps",
        str(max_steps),
        "--beta",
        str(beta),
        "--lr",
        str(lr),
        "--seed",
        str(seed),
    ]

    if resume:
        cmd.append("--resume")

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Accelerate training failed with code {result.returncode}")

    save_path = cache_path / project_name / run_name / f"checkpoint-{max_steps}"
    return str(save_path)


# evaluation


async def create_openai_client():
    from openai import OpenAI

    return OpenAI()


opponent = "gpt-5"
reasoning = {"effort": "minimal"}
text = {"verbosity": "low"}

k_factor = 16.0
initial_rating = 1200.0


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    # region=region,
    secrets=[modal.Secret.from_name("openai-secret")],
    timeout=2 * 60 * minutes,
)
async def run_episode_eval(
    idx: int,
    run_name: str,
    project_name: str,
    save_video: bool,
    current_ckpt_path: str = "",
):
    import asyncio

    from tqdm import tqdm

    ## init bg processes

    characters = [character, character]
    outfits = [outfit, outfit]
    super_arts = [super_art, super_art]

    tasks = [
        create_sandbox(),
        create_yolo(),
        create_llm(current_ckpt_path),
        create_openai_client(),
    ]
    sandbox, yolo, trained_llm, openai_client = await asyncio.gather(*tasks)

    if sandbox is None:
        return None
    if yolo is None:
        sandbox.terminate()
        return None
    if trained_llm is None:
        sandbox.terminate()
        return None

    try:
        env = await asyncio.wait_for(
            asyncio.to_thread(
                create_environment,
                characters,
                outfits,
                super_arts,
            ),
            timeout=15,
        )
    except asyncio.TimeoutError:
        print("Timeout while creating environment", file=sys.stderr)
        sandbox.terminate()
        return None
    if env is None:
        sandbox.terminate()
        return None

    # init episode

    try:
        observation, info = env.reset()
    except Exception as e:
        print(f"env.reset() failed: {e}", file=sys.stderr)
        sandbox.terminate()
        return None

    step_idx = 0

    winner = None
    p1_recent_moves = []
    p2_recent_moves = []
    frames = []

    # run episode

    print("Running episode...")
    pbar = tqdm(desc="step_idx", unit="step")
    while True:
        # get info for prompt
        obs_p1 = observation["P1"]
        obs_p2 = observation["P2"]
        boxes, class_ids = await yolo.detect_characters.remote.aio(
            [CHARACTER_TO_ID[character], CHARACTER_TO_ID[character]],
            observation["frame"],
        )
        game_info = GameInfo(
            timer=observation["timer"][0],
            boxes=boxes,
            class_ids=class_ids,
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

        # run trained policy
        p1_messages = create_messages(game_info, player2, player1, p1_recent_moves)
        try:
            (
                p1_buttons,
                p1_move_name,
            ) = await trained_llm.chat.remote.aio(
                p1_messages,
                character,
                super_arts[0],
                obs_p1["super_count"][0],
                p1_side,
            )
        except Exception as e:
            print(f"trained_llm.chat failed: {e}", file=sys.stderr)
            sandbox.terminate()
            return None

        # run opponent policy
        p2_messages = create_messages(game_info, player1, player2, p2_recent_moves)
        try:
            response = openai_client.responses.create(
                model=opponent,
                input=p2_messages,
                reasoning=reasoning,
                text=text,
            )
            p2_move_name = response.output_text
            p2_buttons = parse_move(character, p2_move_name, obs_p2["side"])
            if p2_buttons is None:
                raise Exception(f"Invalid move from OpenAI: {p2_move_name}")
        except Exception as e:
            print(f"openai_client.responses.create failed: {e}", file=sys.stderr)
            sandbox.terminate()
            return None

        # pad shorter move sequence to match longer one
        if len(p1_buttons) > len(p2_buttons):
            p2_buttons = p2_buttons + [0] * (len(p1_buttons) - len(p2_buttons))
        elif len(p2_buttons) > len(p1_buttons):
            p1_buttons = p1_buttons + [0] * (len(p2_buttons) - len(p1_buttons))

        # step env
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
                sandbox.terminate()
                return None

            if save_video:
                boxes, class_ids = await yolo.detect_characters.remote.aio(
                    [CHARACTER_TO_ID[character], CHARACTER_TO_ID[character]],
                    observation["frame"],
                )
                frames.append(observation["frame"])

        p1_recent_moves.append(p1_move_name)
        if len(p1_recent_moves) > recent_move_limit:
            p1_recent_moves.pop(0)
        p2_recent_moves.append(p2_move_name)
        if len(p2_recent_moves) > recent_move_limit:
            p2_recent_moves.pop(0)

        if terminated or truncated:
            break

        step_idx += 1
        pbar.update(1)

    pbar.close()
    print("Episode finished.")

    # misc

    if save_video and len(frames) > 0:
        import cv2

        print("Saving video...")

        out_path = cache_path / project_name / run_name / f"eval_{idx}.mp4"
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

    print("Cleaning up...")
    try:
        env.close()
    except Exception as e:
        warnings.warn(f"Couldn't close environment: {e}")
    sandbox.terminate()
    print("Done.")

    p1_wins = observation["P1"]["wins"][0]
    p2_wins = observation["P2"]["wins"][0]
    if p1_wins > p2_wins:
        winner = current_ckpt_path or "pretrained"
    elif p2_wins > p1_wins:
        winner = opponent
    else:
        winner = None
    return winner


def calculate_elo_scores(
    models: list,
    match_results: list,
):
    from collections import defaultdict

    ratings = defaultdict(lambda: initial_rating)
    match_history = []
    elo_over_time = {model: [initial_rating] for model in models}

    for match_idx, result in enumerate(match_results):
        if result is not None:
            winner = result
            loser = [m for m in models if m != winner][0]

            r_winner = ratings[winner]
            r_loser = ratings[loser]

            e_winner = 1 / (1 + 10 ** ((r_loser - r_winner) / 400))
            e_loser = 1 / (1 + 10 ** ((r_winner - r_loser) / 400))

            ratings[winner] = r_winner + k_factor * (1 - e_winner)
            ratings[loser] = r_loser + k_factor * (0 - e_loser)

            match_history.append(
                {
                    "match_num": match_idx + 1,
                    "type": "win",
                    "winner": winner,
                    "loser": loser,
                    "winner_elo_before": r_winner,
                    "winner_elo_after": ratings[winner],
                    "loser_elo_before": r_loser,
                    "loser_elo_after": ratings[loser],
                }
            )
        else:
            r1 = ratings[models[0]]
            r2 = ratings[models[1]]

            e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
            e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))

            ratings[models[0]] = r1 + k_factor * (0.5 - e1)
            ratings[models[1]] = r2 + k_factor * (0.5 - e2)

            match_history.append(
                {
                    "match_num": match_idx + 1,
                    "type": "draw",
                    "player1": models[0],
                    "player2": models[1],
                    "player1_elo_before": r1,
                    "player1_elo_after": ratings[models[0]],
                    "player2_elo_before": r2,
                    "player2_elo_after": ratings[models[1]],
                }
            )

        for model in models:
            elo_over_time[model].append(ratings[model])

    return dict(ratings), match_history, elo_over_time


def create_elo_prog_viz(
    models: list,
    match_results: list,
    save_path: str = None,
):
    import matplotlib.pyplot as plt

    elo_scores, match_history, elo_over_time = calculate_elo_scores(
        models, match_results
    )

    fig, ax = plt.subplots(figsize=(12, 6))

    for model in models:
        elo_trajectory = elo_over_time[model]
        label = model.split("/")[-1] if "/" in model else model
        ax.plot(
            range(len(elo_trajectory)),
            elo_trajectory,
            marker="o",
            markersize=2,
            label=label,
        )
    ax.axhline(y=initial_rating, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Match Number")
    ax.set_ylabel("ELO Rating")
    ax.set_title("ELO Progression")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Match history visualization saved to {save_path}")

    return elo_scores


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    # region=region,
    timeout=2 * 60 * minutes,
)
async def evaluate_model(
    run_name: str,
    project_name: str,
    n_episodes: int,
    current_ckpt_path: str = "",
    eval_suffix: str = "",
):
    import json
    import random

    video_idxs = range(n_episodes)
    if n_videos_per_round < n_episodes:
        video_idxs = random.sample(range(n_episodes), n_videos_per_round)

    data = []
    async for winner in run_episode_eval.starmap.aio(
        [
            (
                idx,
                run_name,
                project_name,
                idx in video_idxs,
                current_ckpt_path,
            )
            for idx in range(n_episodes)
        ]
    ):
        data.append(winner)

    if len(data) == 0:
        raise Exception("No data collected")

    if not current_ckpt_path:
        current_ckpt_path = "pretrained"

    models = [current_ckpt_path, opponent]

    viz_path = cache_path / project_name / run_name / f"match_history{eval_suffix}.png"
    elo_scores = create_elo_prog_viz(models, data, save_path=str(viz_path))

    eval_results_path = (
        cache_path / project_name / run_name / f"eval_results{eval_suffix}.json"
    )
    with open(eval_results_path, "w") as f:
        json.dump(
            {
                "trained_elo": elo_scores[current_ckpt_path],
                "opponent_elo": elo_scores[opponent],
                "trained_win_rate": sum(1 for r in data if r == current_ckpt_path)
                / len(data),
                "opponent_win_rate": sum(1 for r in data if r == opponent) / len(data),
                "draw_rate": sum(1 for r in data if r is None) / len(data),
            },
            f,
        )


@app.local_entrypoint()
async def local(
    # scale
    n_rounds: int = 10,
    n_train_episodes_per_round: int = 90,  # ~30k samples
    n_val_episodes_per_round: int = 10,
    # training
    max_steps: int = 1000,  # bs = 32
    # evaluation
    n_eval_episodes: int = 100,
):
    import asyncio

    current_ckpt_path = ""
    all_prior_models = []

    for round_idx in range(n_rounds):
        status = get_round_status.remote(round_idx, max_steps)
        project_name = status["project_name"]
        run_name = status["run_name"]

        if (
            status["training_complete"]
            and status["final_checkpoint"]
            and status["has_final_eval"]
        ):
            if current_ckpt_path:
                all_prior_models.append(current_ckpt_path)
            current_ckpt_path = status["final_checkpoint"]
            continue

        ckpt_to_use = "" if round_idx == 0 else current_ckpt_path

        if round_idx == 0 and not status["has_baseline_eval"]:
            await evaluate_model.remote.aio(
                run_name,
                project_name,
                n_eval_episodes,
                ckpt_to_use,
                "_baseline",
            )

        if not (status["has_train_ds"] and status["has_val_ds"]):
            if round_idx == 0:  # only random moves for bootstrapping
                opponent_pool = []
            elif round_idx == 1:  # self-play against round 0 model + random
                opponent_pool = [current_ckpt_path] if current_ckpt_path else []
            else:  # mix of recent models for diverse opponents
                recent_models = all_prior_models[-opponent_pool_size_per_round:]
                opponent_pool = recent_models + [None] if recent_models else [None]

            await asyncio.gather(
                create_dataset.remote.aio(
                    "train",
                    run_name,
                    project_name,
                    n_train_episodes_per_round,
                    round_idx,
                    ckpt_to_use,
                    opponent_pool,
                ),
                create_dataset.remote.aio(
                    "val",
                    run_name,
                    project_name,
                    n_val_episodes_per_round,
                    round_idx,
                    ckpt_to_use,
                    opponent_pool,
                ),
            )

        status = get_round_status.remote(round_idx, max_steps)

        if not status["training_complete"]:
            progress = round_idx / max(1, n_rounds - 1)
            beta = start_beta + (end_beta - start_beta) * progress
            lr = start_lr + (end_lr - start_lr) * progress

            new_ckpt_path = train_model.remote(
                run_name,
                project_name,
                max_steps,
                beta,
                lr,
                ckpt_to_use,
                status["can_resume"],
            )
            if current_ckpt_path:
                all_prior_models.append(current_ckpt_path)
            current_ckpt_path = new_ckpt_path
        else:
            if current_ckpt_path:
                all_prior_models.append(current_ckpt_path)
            current_ckpt_path = status["final_checkpoint"]

        if not status["has_final_eval"]:
            await evaluate_model.remote.aio(
                run_name,
                project_name,
                n_eval_episodes,
                current_ckpt_path,
            )
