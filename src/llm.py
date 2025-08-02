import time
from pathlib import Path

import modal

from .utils import (
    BASE_META_INSTRUCTIONS,
    CHARACTER_MAPPING,
    CHARACTER_TO_ID,
    COMBOS,
    HEALTH_MAX,
    SPECIAL_MOVES,
    STUN_BAR_MAX,
    SUPER_BAR_MAX,
    X_SIZE,
    Y_SIZE,
    GameInfo,
    PlayerState,
    create_messages,
    local_assets_dir,
    # region,
    minutes,
)

# Modal setup

app = modal.App("sf3-llm")

remote_chat_template_path = "/root/qwen3_nonthinking.jinja"

vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(
        "vllm==0.9.2",
        "flashinfer-python==0.2.6.post1",
        "huggingface_hub[hf_transfer]==0.33.4",
        extra_index_url="https://download.pytorch.org/whl/cu128",
        extra_options="--index-strategy unsafe-best-match",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "VLLM_USE_V1": "1",
        }
    )
    .add_local_file(
        local_assets_dir / "llm" / "qwen3_nonthinking.jinja",
        remote_chat_template_path,
    )
)

MODEL_NAME = "Qwen/Qwen3-0.6B"

hf_cache_vol = modal.Volume.from_name(
    f"{app.name}-huggingface-cache", create_if_missing=True
)

vllm_cache_vol = modal.Volume.from_name(
    f"{app.name}-vllm-cache", create_if_missing=True
)

models_path = Path("/models")
checkpoints_volume = modal.Volume.from_name(
    f"{app.name}-train-checkpoints", create_if_missing=True
)

# inference


def get_latest_checkpoint_file_path():
    if not (models_path / "latest_checkpointed_iteration.txt").exists():
        return MODEL_NAME

    with open(models_path / "latest_checkpointed_iteration.txt") as f:
        latest_checkpoint_index = int(f.read())
    return str(
        models_path / f"global_step_{latest_checkpoint_index}" / "actor" / "huggingface"
    )


def calculate_super_count(super_bar: int) -> int:
    if super_bar == SUPER_BAR_MAX:
        return 3
    elif super_bar >= (SUPER_BAR_MAX // 3) * 2:
        return 2
    elif super_bar >= SUPER_BAR_MAX // 3:
        return 1
    else:
        return 0


def create_random_messages():  # for warmup, testing
    import random

    n_detected_characters = random.randint(1, 2)

    player1_character = random.choice(list(CHARACTER_MAPPING.values()))
    player2_character = random.choice(list(CHARACTER_MAPPING.values()))

    player1_super_art = random.randint(1, 3)
    player2_super_art = random.randint(1, 3)

    side = random.randint(0, 1)

    player1_stun_bar = random.randint(0, STUN_BAR_MAX)
    player2_stun_bar = random.randint(0, STUN_BAR_MAX)

    player1_super_bar = random.randint(0, SUPER_BAR_MAX)
    player2_super_bar = random.randint(0, SUPER_BAR_MAX)

    player1_super_count = calculate_super_count(player1_super_bar)
    player2_super_count = calculate_super_count(player2_super_bar)

    game_info = GameInfo(
        stage=random.randint(1, 3),
        timer=random.randint(0, 100),
        boxes=[
            [
                random.randint(0, X_SIZE),
                random.randint(0, Y_SIZE),
                random.randint(0, X_SIZE),
                random.randint(0, Y_SIZE),
            ]
            for _ in range(n_detected_characters)
        ],
        class_ids=[
            CHARACTER_TO_ID[player1_character],
            CHARACTER_TO_ID[player2_character],
        ][:n_detected_characters],
    )

    player1 = PlayerState(
        character=player1_character,
        super_art=player1_super_art,
        wins=random.randint(0, 2),
        side=side,
        stunned=player1_stun_bar == STUN_BAR_MAX,
        stun_bar=player1_stun_bar,
        health=random.randint(0, HEALTH_MAX),
        super_count=player1_super_count,
        super_bar=player1_super_bar,
    )

    player2 = PlayerState(
        character=player2_character,
        super_art=player2_super_art,
        wins=random.randint(0, 2),
        side=1 - side,
        stunned=player2_stun_bar == STUN_BAR_MAX,
        stun_bar=player2_stun_bar,
        health=random.randint(0, HEALTH_MAX),
        super_count=player2_super_count,
        super_bar=player2_super_bar,
    )

    return (
        create_messages(game_info, player1, player2),
        side,
        player2_character,
    )


MAX_INPUTS = max_num_seqs = 32


@app.cls(
    image=vllm_image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
        models_path: checkpoints_volume,
    },
    gpu="b200",
    # region=region,
    scaledown_window=60 * minutes,
    timeout=24 * 60 * minutes,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class LLMServer:
    @modal.enter()
    async def enter(self):
        from vllm import LLM, SamplingParams

        checkpoints_volume.reload()

        self.llm = LLM(
            model=get_latest_checkpoint_file_path(),
            max_num_seqs=max_num_seqs,
            max_num_batched_tokens=40960,  # https://qwen.readthedocs.io/en/latest/deployment/vllm.html#faq, https://docs.vllm.ai/en/latest/configuration/optimization.html#performance-tuning-with-chunked-prefill
            enforce_eager=True,
            swap_space=0,
            enable_prefix_caching=True,  # https://docs.vllm.ai/en/stable/features/automatic_prefix_caching.html#example-workloads,
            gpu_memory_utilization=0.95,
            disable_log_stats=True,  # reduce overhead
        )

        self.sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            min_p=0.0,
            max_tokens=32,  # roughly len("<longest meta instruction name>")
            presence_penalty=1.5,
        )

        # warm up model

        messages, _, _ = create_random_messages()

        _ = self.llm.chat(
            [messages],
            self.sampling_params,
            chat_template=remote_chat_template_path,
        )

    @modal.method()
    async def boot(self):  # so don't have to call `chat` to boot
        pass

    @modal.method()
    async def chat(
        self, messages: list[dict[str, str]], character: str, side: int
    ) -> list[int]:
        from vllm.sampling_params import GuidedDecodingParams

        choices = []
        choices.extend(BASE_META_INSTRUCTIONS.keys())
        if character in COMBOS:
            choices.extend(COMBOS[character].keys())
        if character in SPECIAL_MOVES:
            choices.extend(SPECIAL_MOVES[character].keys())
        choices = list(set(choices))

        self.sampling_params.guided_decoding = GuidedDecodingParams(
            choice=choices,
        )

        outputs = self.llm.chat(
            [messages],
            self.sampling_params,
            chat_template=remote_chat_template_path,
        )
        move_name = outputs[0].outputs[0].text

        current_direction = "left" if side == 0 else "right"

        try:
            move_sequence = None

            if move_name in BASE_META_INSTRUCTIONS:
                move_sequence = BASE_META_INSTRUCTIONS[move_name][current_direction]
            elif move_name in COMBOS[character]:
                move_sequence = COMBOS[character][move_name][current_direction]
            elif move_name in SPECIAL_MOVES[character]:
                move_sequence = SPECIAL_MOVES[character][move_name][current_direction]

            if move_sequence is not None:
                return list(move_sequence)
            else:
                raise ValueError(f"Invalid move: {move_name}")

        except Exception as e:
            print(f"Error: {e}")
            return [0]


@app.local_entrypoint()
async def local(
    n_samples: int = 100,
):
    llm = LLMServer()
    llm.boot.remote()

    latencies = []
    for sample_idx in range(n_samples):
        messages, side, character = create_random_messages()
        start_time = time.perf_counter()
        moves = await llm.chat.remote.aio(messages, character, side)
        latencies.append((time.perf_counter() - start_time) * 1000)

        print(f"Sample {sample_idx}: {moves}")

    percentiles = [50, 90, 95, 99]
    sorted_latencies = sorted(latencies)
    results = {}
    for p in percentiles:
        idx = int(len(sorted_latencies) * p / 100)
        idx = min(max(idx - 1, 0), len(sorted_latencies) - 1)
        results[p] = sorted_latencies[idx]
    print("--------------------------------")
    print("Latency percentiles (ms):")
    for p in percentiles:
        print(f"  p{p}: {results[p]:.2f}ms")
    print("--------------------------------")
