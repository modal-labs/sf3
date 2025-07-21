import time
from pathlib import Path

import modal

from .utils import (
    BASE_META_INSTRUCTIONS,
    CHARACTER_MAPPING,
    CHARACTER_TO_ID,
    COMBOS,
    HEALTH_MAX,
    MAX_Y,
    MIN_Y,
    SPECIAL_MOVES,
    STUN_BAR_MAX,
    SUPER_BAR_MAX,
    X_SIZE,
    create_messages,
    minutes,
    # region,
)

# Modal setup

app = modal.App("sf3-llm")

remote_chat_template_path = "/root/qwen3_nonthinking.jinja"

vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("uv")
    .run_commands(
        "uv pip install --system --compile-bytecode vllm==0.9.2 flashinfer-python==0.2.6.post1 huggingface_hub[hf_transfer]==0.33.4 --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu128",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "VLLM_USE_V1": "1",
        }
    )
    .add_local_file(
        Path(__file__).parent.parent / "assets" / "qwen3_nonthinking.jinja",
        remote_chat_template_path,
    )
)

MODEL_NAME = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "e6de91484c29aa9480d55605af694f39b081c455"

hf_cache_vol = modal.Volume.from_name(
    f"{app.name}-huggingface-cache", create_if_missing=True
)

vllm_cache_vol = modal.Volume.from_name(
    f"{app.name}-vllm-cache", create_if_missing=True
)


def create_random_messages():
    import random

    n_detected_characters = random.randint(1, 2)

    player1_character = random.choice(list(CHARACTER_MAPPING.values()))
    player2_character = random.choice(list(CHARACTER_MAPPING.values()))

    side = random.randint(0, 1)

    return (
        create_messages(
            stage=random.randint(1, 3),
            timer=random.randint(0, 100),
            boxes=[
                [
                    random.randint(0, X_SIZE // 2),
                    random.randint(MIN_Y, MAX_Y // 2),
                    random.randint(X_SIZE // 2, X_SIZE),
                    random.randint(MAX_Y // 2, MAX_Y),
                ]
                for _ in range(n_detected_characters)
            ],
            class_ids=[
                CHARACTER_TO_ID[player1_character],
                CHARACTER_TO_ID[player2_character],
            ][:n_detected_characters],
            player1_character=player1_character,
            player1_super_art=random.randint(1, 3),
            player1_wins=random.randint(0, 2),
            player1_side=side,
            player1_stunned=random.random() < 0.1,
            player1_stun_bar=random.randint(0, STUN_BAR_MAX),
            player1_health=random.randint(0, HEALTH_MAX),
            player1_super_count=random.randint(0, 2),
            player1_super_bar=random.randint(0, SUPER_BAR_MAX),
            player2_character=player2_character,
            player2_super_art=random.randint(1, 3),
            player2_wins=random.randint(0, 2),
            player2_side=1 - side,
            player2_stunned=random.random() < 0.1,
            player2_stun_bar=random.randint(0, STUN_BAR_MAX),
            player2_health=random.randint(0, HEALTH_MAX),
            player2_super_count=random.randint(0, 2),
            player2_super_bar=random.randint(0, SUPER_BAR_MAX),
        ),
        side,
        player2_character,
    )


MAX_INPUTS = max_num_seqs = 128


@app.cls(
    image=vllm_image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    gpu="b200",
    # region=region,
    scaledown_window=15 * minutes,
    timeout=10 * minutes,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class LLMServer:
    @modal.enter()
    async def enter(self):
        from vllm import LLM, SamplingParams
        from vllm.sampling_params import GuidedDecodingParams

        self.llm = LLM(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            max_num_seqs=max_num_seqs,
            max_num_batched_tokens=40960,  # https://qwen.readthedocs.io/en/latest/deployment/vllm.html#faq, https://docs.vllm.ai/en/latest/configuration/optimization.html#performance-tuning-with-chunked-prefill
            enforce_eager=True,
            enable_prefix_caching=True,  # https://docs.vllm.ai/en/stable/features/automatic_prefix_caching.html#example-workloads,
            swap_space=0,  # store everything in GPU memory
            gpu_memory_utilization=0.95,
            disable_log_stats=True,  # reduce overhead
        )

        choices = list(
            set(
                list(BASE_META_INSTRUCTIONS.keys())
                + list(
                    [
                        combo
                        for character in COMBOS.keys()
                        for combo in COMBOS[character].keys()
                    ]
                )
                + list(
                    [
                        special_move
                        for character in SPECIAL_MOVES.keys()
                        for special_move in SPECIAL_MOVES[character].keys()
                    ]
                )
            )
        )

        self.sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            min_p=0.0,
            max_tokens=8,  # roughly len("<longest meta instruction name>")
            presence_penalty=1.5,
            guided_decoding=GuidedDecodingParams(
                choice=choices,
            ),  # https://huggingface.co/Qwen/Qwen3-0.6B#best-practices
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
    ) -> int:
        outputs = self.llm.chat(
            [messages],
            self.sampling_params,
            chat_template=remote_chat_template_path,
        )
        text = outputs[0].outputs[0].text

        current_direction = "left" if side == 0 else "right"

        try:
            if text in BASE_META_INSTRUCTIONS:
                return [
                    button for button in BASE_META_INSTRUCTIONS[text][current_direction]
                ]
            elif text in COMBOS[character]:
                return [button for button in COMBOS[character][text][current_direction]]
            elif text in SPECIAL_MOVES[character]:
                return [
                    button
                    for button in SPECIAL_MOVES[character][text][current_direction]
                ]
            else:
                raise ValueError(f"Invalid move: {text}")
        except Exception as e:
            print(f"Error: {e}")
            return [0]


@app.local_entrypoint()
async def test(n_samples=100):
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
