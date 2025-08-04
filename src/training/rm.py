import random
import time

import modal

from src.utils import (
    create_random_messages,
    get_available_instructions_for_character,
    minutes,
)

# Modal setup

app = modal.App("sf3-rm")

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
)

MODEL_NAME = "Skywork/Skywork-Reward-V2-Qwen3-0.6B"

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)

vllm_cache_vol = modal.Volume.from_name("sf3-vllm-cache", create_if_missing=True)


# inference

MAX_INPUTS = max_num_seqs = 32


@app.cls(
    image=vllm_image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    gpu="b200",
    scaledown_window=60 * minutes,
    timeout=24 * 60 * minutes,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class RMServer:
    @modal.enter()
    async def enter(self):
        from transformers import AutoTokenizer
        from vllm import LLM

        self.llm = LLM(
            model=MODEL_NAME,
            task="classify",
            override_pooler_config={"softmax": False},
            max_num_seqs=max_num_seqs,
            max_num_batched_tokens=40960,  # https://qwen.readthedocs.io/en/latest/deployment/vllm.html#faq, https://docs.vllm.ai/en/latest/configuration/optimization.html#performance-tuning-with-chunked-prefill
            enforce_eager=True,
            swap_space=0,
            enable_prefix_caching=True,  # https://docs.vllm.ai/en/stable/features/automatic_prefix_caching.html#example-workloads,
            gpu_memory_utilization=0.95,
            disable_log_stats=True,  # reduce overhead
        )

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        # warm up model

        messages, character, super_art, super_count, _ = create_random_messages()
        messages.append(
            {
                "role": "assistant",
                "content": random.choice(
                    get_available_instructions_for_character(
                        character, super_art, super_count
                    )
                ),
            }
        )

        messages_formatted = self.tokenizer.apply_chat_template(
            messages, tokenize=False
        )
        messages_tokenized = self.tokenizer(messages_formatted)
        _ = self.llm.encode(prompt_token_ids=messages_tokenized["input_ids"])

    @modal.method()
    async def boot(self):  # so don't have to call `chat` to boot
        pass

    @modal.fastapi_endpoint(method="POST")
    async def chat(self, messages: list[dict[str, str]]) -> float:
        conv = self.tokenizer.apply_chat_template(messages, tokenize=False)
        conv_tokenized = self.tokenizer(conv)
        out = self.llm.encode(prompt_token_ids=conv_tokenized["input_ids"])
        return float(out[0].outputs.data)


@app.local_entrypoint()
async def local(
    n_samples: int = 100,
):
    import json
    import urllib.request

    rm = RMServer()
    rm.boot.remote()
    web_url = rm.chat.get_web_url()
    print(f"RM server running at {web_url}")

    latencies = []
    for sample_idx in range(n_samples):
        messages, character, super_art, super_count, _ = create_random_messages()
        messages.append(
            {
                "role": "assistant",
                "content": random.choice(
                    get_available_instructions_for_character(
                        character, super_art, super_count
                    )
                ),
            }
        )
        start_time = time.perf_counter()

        data = json.dumps(messages).encode("utf-8")
        req = urllib.request.Request(
            web_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            score = json.load(resp)

        latencies.append((time.perf_counter() - start_time) * 1000)
        print(f"Sample {sample_idx}: {score}")

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
