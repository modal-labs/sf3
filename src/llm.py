import time
from pathlib import Path

import modal

from .config import (
    CHARACTER_MAPPING,
    CHARACTER_TO_ID,
    META_INSTRUCTIONS_WITH_LOWER,
    X_SIZE,
    Y_SIZE,
    create_messages,
    minutes,
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


MAX_INPUTS = max_num_seqs = 128


@app.cls(
    image=vllm_image,
    gpu="b200",
    scaledown_window=15 * minutes,
    timeout=10 * minutes,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class LLMServer:
    @modal.enter()
    def enter(self):
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

        self.sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.8,
            top_k=len(META_INSTRUCTIONS_WITH_LOWER),
            min_p=0.0,
            max_tokens=8,  # roughly len("<longest meta instruction name>")
            presence_penalty=1.5,
            guided_decoding=GuidedDecodingParams(
                choice=META_INSTRUCTIONS_WITH_LOWER.keys(),
            ),  # https://huggingface.co/Qwen/Qwen3-0.6B#best-practices
        )

    @modal.method()
    async def boot(self):  # so don't have to call `chat` to boot
        pass

    @modal.method()
    async def chat(self, messages: list[dict[str, str]], current_direction: str) -> int:
        outputs = self.llm.chat(
            [messages],
            self.sampling_params,
            chat_template=remote_chat_template_path,
        )
        text = outputs[0].outputs[0].text
        try:
            return [
                button
                for button in META_INSTRUCTIONS_WITH_LOWER[text][current_direction]
            ]
        except ValueError:
            return [0]


@app.local_entrypoint()
async def test(n_samples=100):
    import random

    llm = LLMServer()
    llm.boot.remote()

    latencies = []
    for sample_idx in range(n_samples):
        side = random.randint(0, 1)
        own_character = random.choice(list(CHARACTER_MAPPING.values()))
        opp_character = random.choice(list(CHARACTER_MAPPING.values()))

        n_detected_characters = random.randint(1, 2)

        messages = create_messages(
            stage=random.randint(1, 3),
            own_wins=random.randint(0, 2),
            opp_wins=random.randint(0, 2),
            timer=random.randint(0, 100),
            own_character=own_character,
            opp_character=opp_character,
            own_side=side,
            opp_side=1 - side,
            boxes=[
                [
                    random.randint(0, X_SIZE // 2),
                    random.randint(0, Y_SIZE // 2),
                    random.randint(X_SIZE // 2, X_SIZE),
                    random.randint(Y_SIZE // 2, Y_SIZE),
                ]
                for _ in range(n_detected_characters)
            ],
            class_ids=[
                CHARACTER_TO_ID[own_character],
                CHARACTER_TO_ID[opp_character],
            ][:n_detected_characters],
            own_stunned=random.random() < 0.1,
            own_stun_bar=random.randint(0, 120),
            opp_stunned=random.random() < 0.1,
            opp_stun_bar=random.randint(0, 120),
            own_health=random.randint(0, 160),
            opp_health=random.randint(0, 160),
            own_super_count=random.randint(0, 2),
            own_super_bar=random.randint(0, 120),
            opp_super_count=random.randint(0, 2),
            opp_super_bar=random.randint(0, 120),
        )

        start_time = time.perf_counter()
        moves = await llm.chat.remote.aio(messages, "left" if side == 0 else "right")
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
