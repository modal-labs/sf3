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
    get_available_instructions_for_character,
    local_assets_dir,
    minutes,
    parse_move,
    seed,
)
from ..yolo import YOLOServer
from ..yolo import app as yolo_app

# Modal setup
app = modal.App("sf3-llm-train").include(llm_app).include(yolo_app)

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

local_engine_dir = local_assets_dir / "engine"

train_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .uv_pip_install(
        "torch==2.7.1",
        "trl==0.21.0",
        "accelerate==1.8.1",
        "datasets==3.6.0",
        "flashinfer-python==0.2.6.post1",
        "diambra-arena==2.2.7",
        "diambra==0.0.20",
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
)

cache_path = Path("/cache")
cache_volume = modal.Volume.from_name(f"{app.name}-cache", create_if_missing=True)

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sf3-vllm-cache", create_if_missing=True)

MODEL_NAME = "Qwen/Qwen3-8B"


# data

character = "Chun-Li"
outfit = 1
super_art = 1


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
    print("Creating sandbox...")
    engine_port = 50051
    sandbox = modal.Sandbox.create(
        "/bin/diambraEngineServer",
        app=engine_app,
        image=engine_image,
        timeout=60 * minutes,
        unencrypted_ports=[engine_port],
        verbose=True,
    )
    tunnels = sandbox.tunnels()
    tunnel = tunnels[engine_port]
    host, port = tunnel.tcp_socket
    os.environ["DIAMBRA_ENVS"] = f"{host}:{port}"
    print(f"Created sandbox {sandbox.object_id} at {host}:{port}")
    return sandbox


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
        grpc_timeout=1 * minutes,
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


@app.function(
    image=train_image,
    volumes={cache_path: cache_volume},
    timeout=60 * minutes,
)
async def run_rl_episode(
    idx: int,
    split: str,
    run_name: str,
    n_move_returns: int,
    frozen_random_prob: float,
    save_video: bool,
    max_steps_without_reward: int,
    current_ckpt_path: str = "",
    prior_ckpt_path: str = "",
):
    import asyncio
    import random

    from tqdm import tqdm

    ## init

    characters = [character, character]
    outfits = [outfit, outfit]
    super_arts = [super_art, super_art]

    tasks = [create_yolo(), create_sandbox(), create_llm(current_ckpt_path)]

    if prior_ckpt_path:
        tasks.append(create_llm(prior_ckpt_path))
    else:
        tasks.append(asyncio.to_thread(lambda: None))

    yolo, sandbox, current_llm, prior_llm = await asyncio.gather(*tasks)

    if yolo is None:
        sandbox.terminate()
        return []

    if current_llm is None:
        sandbox.terminate()
        return []

    if prior_ckpt_path and prior_llm is None:
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
            timeout=1 * minutes,
        )
    except asyncio.TimeoutError:
        print("Timeout while creating environment", file=sys.stderr)
        sandbox.terminate()
        return []
    if env is None:
        sandbox.terminate()
        return []

    observation, info = env.reset()

    step_idx = 0
    steps_without_reward = 0

    # buffers for n-step returns
    step_rewards: list[float] = []
    step_prompts: list[list[dict[str, str]]] = []
    step_training_responses: list[list[dict[str, str]]] = []
    step_frozen_responses: list[list[dict[str, str]]] = []
    step_timer: list[int] = []
    step_p1_health: list[int] = []
    step_p2_health: list[int] = []

    step_data = []
    frames = []

    print("Running episode...")
    pbar = tqdm(desc="step_idx", unit="step")
    while True:
        obs_p1 = observation["P1"]
        obs_p2 = observation["P2"]

        boxes, class_ids = await yolo.detect_characters.remote.aio(
            [CHARACTER_TO_ID[character], CHARACTER_TO_ID[character]],
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

        training_messages = create_messages(game_info, player2, player1)
        try:
            training_buttons, training_move_name = await current_llm.chat.remote.aio(
                training_messages,
                character,
                super_arts[0],
                obs_p1["super_count"][0],
                p1_side,
                return_move_name=True,
            )
        except Exception as e:
            print(f"current_llm.chat failed: {e}", file=sys.stderr)
            available_moves = get_available_instructions_for_character(
                character, super_arts[0], obs_p1["super_count"][0]
            )
            training_move_name = random.choice(available_moves)
            training_buttons = parse_move(character, training_move_name, p1_side)

        if prior_llm is None:
            available_moves = get_available_instructions_for_character(
                character, super_arts[1], obs_p2["super_count"][0]
            )
            frozen_move_name = random.choice(available_moves)
            frozen_buttons = parse_move(character, frozen_move_name, obs_p2["side"])
        else:
            if random.random() < frozen_random_prob:
                available_moves = get_available_instructions_for_character(
                    character, super_arts[1], obs_p2["super_count"][0]
                )
                frozen_move_name = random.choice(available_moves)
                frozen_buttons = parse_move(character, frozen_move_name, obs_p2["side"])
            else:
                frozen_messages = create_messages(game_info, player1, player2)
                try:
                    frozen_buttons, frozen_move_name = await prior_llm.chat.remote.aio(
                        frozen_messages,
                        character,
                        super_arts[1],
                        obs_p2["super_count"][0],
                        obs_p2["side"],
                        return_move_name=True,
                    )
                except Exception as e:
                    print(f"prior_llm.chat failed: {e}", file=sys.stderr)
                    available_moves = get_available_instructions_for_character(
                        character, super_arts[1], obs_p2["super_count"][0]
                    )
                    frozen_move_name = random.choice(available_moves)
                    frozen_buttons = parse_move(
                        character, frozen_move_name, obs_p2["side"]
                    )

        if len(training_buttons) > len(frozen_buttons):
            frozen_buttons = frozen_buttons + [0] * (
                len(training_buttons) - len(frozen_buttons)
            )
        elif len(frozen_buttons) > len(training_buttons):
            training_buttons = training_buttons + [0] * (
                len(frozen_buttons) - len(training_buttons)
            )

        # record pre-step info for tie-breaking and weighting later
        current_timer = observation["timer"][0]
        p1_health_before = obs_p1["health"][0]
        p2_health_before = obs_p2["health"][0]

        move_set_reward = 0
        for training_button, frozen_button in zip(training_buttons, frozen_buttons):
            try:
                (
                    observation,
                    reward,
                    terminated,
                    truncated,
                    info,
                ) = env.step(
                    {
                        "agent_0": training_button,
                        "agent_1": frozen_button,
                    }
                )
            except Exception as e:
                print(f"env.step() failed for step {step_idx}: {e}", file=sys.stderr)
                continue

            move_set_reward += reward

            if save_video:
                boxes, class_ids = await yolo.detect_characters.remote.aio(
                    [CHARACTER_TO_ID[character], CHARACTER_TO_ID[character]],
                    observation["frame"],
                )

                frames.append(observation["frame"])

        # collect buffers for n-step computation later
        step_prompts.append(training_messages)
        step_training_responses.append(
            [
                {
                    "role": "assistant",
                    "content": training_move_name,
                }
            ]
        )
        step_frozen_responses.append(
            [
                {
                    "role": "assistant",
                    "content": frozen_move_name,
                }
            ]
        )
        step_rewards.append(move_set_reward)
        step_timer.append(current_timer)
        step_p1_health.append(p1_health_before)
        step_p2_health.append(p2_health_before)

        if move_set_reward == 0:
            steps_without_reward += 1
            if steps_without_reward >= max_steps_without_reward:
                warnings.warn("Max steps without reward reached")
                break
        else:
            steps_without_reward = 0

        if terminated or truncated:
            break

        step_idx += 1
        pbar.update(1)

    pbar.close()
    print("Episode finished.")

    # build n-step preferences, including zero-reward states with simple health/time weighting
    def compute_weight(timer_value: int, p1_h: int, p2_h: int) -> float:
        # later in round more important; timer assumed in [0,100]
        time_factor = max(0.0, min(1.0, (100 - float(timer_value)) / 100.0))
        health_diff = float(p1_h - p2_h)
        health_factor = abs(health_diff) / float(HEALTH_MAX)
        # scaled small to avoid dominating learned signal
        return max(0.0, min(1.0, time_factor * health_factor))

    num_steps = len(step_rewards)
    for i in range(num_steps):
        ret = sum(step_rewards[i : i + max(1, n_move_returns)])

        training_response = step_training_responses[i]
        frozen_response = step_frozen_responses[i]

        if ret > 0:
            step_data.append(
                {
                    "prompt": step_prompts[i],
                    "chosen": training_response,
                    "rejected": frozen_response,
                    "score_chosen": ret,
                    "score_rejected": -ret,
                }
            )
        elif ret < 0:
            step_data.append(
                {
                    "prompt": step_prompts[i],
                    "chosen": frozen_response,
                    "rejected": training_response,
                    "score_chosen": ret,
                    "score_rejected": -ret,
                }
            )
        else:
            w = compute_weight(step_timer[i], step_p1_health[i], step_p2_health[i])
            if step_p1_health[i] >= step_p2_health[i]:
                step_data.append(
                    {
                        "prompt": step_prompts[i],
                        "chosen": training_response,
                        "rejected": frozen_response,
                        "score_chosen": w,
                        "score_rejected": -w,
                    }
                )
            else:
                step_data.append(
                    {
                        "prompt": step_prompts[i],
                        "chosen": frozen_response,
                        "rejected": training_response,
                        "score_chosen": w,
                        "score_rejected": -w,
                    }
                )
    if save_video and len(frames) > 0:
        import cv2

        print("Saving video...")

        out_path = cache_path / run_name / f"{split}_{idx}.mp4"
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

        try:
            for frame in frames:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frame = cv2.resize(
                    frame, (up_width, up_height), interpolation=cv2.INTER_LINEAR
                )
                video_writer.write(frame)
        finally:
            video_writer.release()

        print(f"Saved video to {out_path}")

    print("Cleaning up...")
    try:
        env.close()
    except Exception as e:
        warnings.warn(f"Couldn't close environment: {e}")
    print("Done.")

    return [
        {
            "prompt": step["prompt"],
            "chosen": step["chosen"],
            "rejected": step["rejected"],
            "score_chosen": step["score_chosen"],
            "score_rejected": step["score_rejected"],
        }
        for step in step_data
    ]


@app.function(
    image=train_image, volumes={cache_path: cache_volume}, timeout=60 * minutes
)
async def create_dataset(
    split: str,
    run_name: str,
    n_episodes: int,
    n_move_returns: int,
    frozen_random_prob: float,
    n_videos: int,
    max_steps_without_reward: int,
    current_ckpt_path: str = "",
    prior_ckpt_path: str = "",
):
    import random

    from datasets import Dataset

    video_idxs = range(n_episodes)
    if n_videos < n_episodes:
        video_idxs = random.sample(range(n_episodes), n_videos)

    data = []
    async for sublist in run_rl_episode.starmap.aio(
        [
            (
                idx,
                split,
                run_name,
                n_move_returns,
                frozen_random_prob,
                idx in video_idxs,
                max_steps_without_reward,
                current_ckpt_path,
                prior_ckpt_path,
            )
            for idx in range(n_episodes)
        ]
    ):
        try:
            data.extend(sublist)
        except Exception as e:
            print(f"Ignoring failed episode batch: {e}", file=sys.stderr)
            continue

    if len(data) == 0:
        raise Exception("No data collected")

    ds = Dataset.from_list(data)
    out_path = cache_path / run_name / f"{split}.parquet"
    ds.to_parquet(str(out_path))
    return f"Saved {len(ds)} samples to {out_path}"


# training

n_gpus = 1


@app.function(
    image=train_image,
    gpu=f"b200:{n_gpus}",
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
    max_steps: int,
    current_ckpt_path: str = "",
    prior_ckpt_path: str = "",
):
    import os

    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import ORPOConfig, ORPOTrainer

    cache_volume.reload()

    dataset = load_dataset(
        "parquet",
        data_files={
            "train": str(cache_path / run_name / "train.parquet"),
            "test": str(cache_path / run_name / "val.parquet"),
        },
    )
    train_dataset = dataset["train"]
    val_dataset = dataset["test"]

    os.environ["WANDB_PROJECT"] = f"{app.name}-{MODEL_NAME.split('/')[-1].lower()}-orpo"
    save_path = cache_path / run_name

    load_path = current_ckpt_path or MODEL_NAME
    model = AutoModelForCausalLM.from_pretrained(load_path)
    tokenizer = AutoTokenizer.from_pretrained(load_path)

    batch_size = 8
    log_steps = 10

    training_args = ORPOConfig(
        # sppo
        beta=0.1,
        # hp
        max_steps=max_steps,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=1,
        learning_rate=5e-5,
        lr_scheduler_type="cosine",
        bf16=True,
        # eval
        eval_strategy="steps",
        eval_steps=log_steps,
        per_device_eval_batch_size=batch_size,
        # wandb
        report_to="wandb",
        run_name=run_name,
        logging_steps=log_steps,
        # ckpt
        output_dir=save_path,
        resume_from_checkpoint=current_ckpt_path,
        # misc
        seed=seed,
        remove_unused_columns=False,
    )
    trainer = ORPOTrainer(
        model=model,
        args=training_args,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
    )
    trainer.train()

    return str(save_path / f"checkpoint-{max_steps}"), current_ckpt_path


@app.local_entrypoint()
async def local(
    # data
    n_rounds: int = 10,
    n_train_episodes_per_round: int = 450,
    n_val_episodes_per_round: int = 50,
    n_move_returns: int = 5,
    frozen_random_prob_start: float = 0.75,
    frozen_random_prob_end: float = 0.25,
    n_videos_per_round: int = 1,
    max_steps_without_reward: int = 50,
    # training
    max_steps: int = 500,
):
    import asyncio
    import time

    prior_ckpt_path = ""
    current_ckpt_path = ""

    for round_idx in range(n_rounds):
        run_name = f"{round_idx}-{time.strftime('%Y%m%d_%H%M%S')}"

        # linear curriculum for opponent diversity
        denom = max(1, n_rounds - 1)
        frac = round_idx / denom
        frozen_random_prob = max(
            frozen_random_prob_end,
            frozen_random_prob_start * (1.0 - frac),
        )

        await asyncio.gather(
            create_dataset.remote.aio(
                "train",
                run_name,
                n_train_episodes_per_round,
                n_move_returns,
                frozen_random_prob,
                n_videos_per_round,
                max_steps_without_reward,
                current_ckpt_path,
                prior_ckpt_path,
            ),
            create_dataset.remote.aio(
                "val",
                run_name,
                n_val_episodes_per_round,
                n_move_returns,
                frozen_random_prob,
                n_videos_per_round,
                max_steps_without_reward,
                current_ckpt_path,
                prior_ckpt_path,
            ),
        )
        current_ckpt_path, prior_ckpt_path = train_model.remote(
            run_name, max_steps, current_ckpt_path, prior_ckpt_path
        )
