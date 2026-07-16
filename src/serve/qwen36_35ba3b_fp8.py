# https://modal.com/docs/examples/sglang_low_latency
# https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8#best-practices
# https://cookbook.sglang.io/autoregressive/Qwen/Qwen3.6

import os
import re
import subprocess
import time
from pathlib import Path

import modal

from src.utils import (
    MAX_CONTEXT_LEN,
    MAX_TOKENS,
    MINUTES,
    ROUTING_REGION,
    create_random_messages,
    get_available_instructions_for_character,
    resolve_move_with_fallback,
)

app = modal.App("sf3-llm")

sglang_image = (
    modal.Image
    .from_registry("lmsysorg/sglang:v0.5.9-cu129-amd64-runtime")
    .entrypoint([])
    .uv_pip_install(
        "huggingface-hub==0.36.0",
        "flashinfer-python==0.6.3",
        "qwen-vl-utils==0.0.14",
    )
    .run_commands("python -m pip install --no-deps nvidia-cudnn-cu12==9.16.0.29")
    .env({
        "HF_XET_HIGH_PERFORMANCE": "1",
        "TORCHINDUCTOR_COMPILE_THREADS": "1",
        "SGLANG_ENABLE_JIT_DEEPGEMM": "1",
    })
)

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)
flashinfer_cache_vol = modal.Volume.from_name(
    "sf3-flashinfer-cache", create_if_missing=True
)
dg_cache_vol = modal.Volume.from_name("sf3-deepgemm-cache", create_if_missing=True)

model_name = "Qwen/Qwen3.6-35B-A3B-FP8"
model_revision = "61a5771f218894aaacf97551e24a25b866750fc2"

max_inputs = max_num_seqs = 16
gpu = "b200"


def compile_deep_gemm():
    if int(os.environ.get("SGLANG_ENABLE_JIT_DEEPGEMM", "1")):
        subprocess.run(
            f"python3 -m sglang.compile_deep_gemm --model-path {model_name} --revision {model_revision} --tp 1",
            shell=True,
            check=True,
        )


sglang_image = sglang_image.run_function(
    compile_deep_gemm,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/flashinfer": flashinfer_cache_vol,
        "/root/.cache/deepgemm": dg_cache_vol,
    },
    gpu=gpu,
)


@app.cls(
    image=sglang_image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/flashinfer": flashinfer_cache_vol,
        "/root/.cache/deepgemm": dg_cache_vol,
    },
    secrets=[modal.Secret.from_dotenv(Path(__file__).parent.parent.parent)],
    gpu=gpu,
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    scaledown_window=60 * MINUTES,
    timeout=60 * MINUTES,
)
@modal.concurrent(max_inputs=max_inputs)
class Qwen36Server:
    ckpt_path: str = modal.parameter(default="")

    @modal.enter()
    async def enter(self):
        import sglang as sgl

        load_path = self.ckpt_path or model_name
        revision = None if self.ckpt_path else model_revision
        print(f"Loading model from {load_path}")

        self.llm = sgl.Engine(
            model_path=str(load_path),
            revision=revision,
            context_length=MAX_CONTEXT_LEN,
            chunked_prefill_size=8192,
            max_running_requests=max_num_seqs,
            cuda_graph_max_bs=max_inputs * 2,
            mem_fraction_static=0.9,
            kv_cache_dtype="fp8_e4m3",
            grammar_backend="xgrammar",
            speculative_algorithm="NEXTN",
            speculative_num_steps=3,
            speculative_eagle_topk=1,
            speculative_num_draft_tokens=4,
        )
        self.tokenizer = self.llm.tokenizer_manager.tokenizer

        self.sampling_params = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
            "max_new_tokens": MAX_TOKENS,
        }

        messages, _, _, _, _, _ = create_random_messages()

        _ = await self.llm.async_generate(
            [
                self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    return_dict=False,
                    enable_thinking=False,
                )
            ],
            sampling_params=self.sampling_params,
        )

    @modal.method()
    async def boot(self):
        pass

    @modal.method()
    async def chat(
        self,
        messages: list[dict],
        character: str,
        super_art: int,
        super_count: int,
        side: int,
        available_moves: list[str] | None = None,
    ) -> tuple[list[int], str]:
        if available_moves is None:
            available_moves = get_available_instructions_for_character(
                character, super_art, super_count
            )

        sampling_params = {
            **self.sampling_params,
            "regex": "(?:"
            + "|".join(
                sorted(
                    (re.escape(move).replace(r"\ ", " ") for move in available_moves),
                    key=len,
                    reverse=True,
                )
            )
            + ")",
        }
        outputs = await self.llm.async_generate(
            [
                self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    return_dict=False,
                    enable_thinking=False,
                )
            ],
            sampling_params=sampling_params,
        )
        move_name = outputs[0]["text"].strip()

        move_sequence, resolved_move_name = resolve_move_with_fallback(
            character, move_name, side
        )
        if resolved_move_name == "No-Move":
            print(f"Invalid move: {move_name}")
        return move_sequence, resolved_move_name

    @modal.exit()
    async def exit(self):
        self.llm.shutdown()


@app.function(routing_region=ROUTING_REGION)
async def test_qwen36(n_samples: int):
    llm = Qwen36Server()
    await llm.boot.remote.aio()

    ms_per_move = []
    for sample_idx in range(n_samples):
        messages, character, super_art, super_count, side, available_moves = (
            create_random_messages()
        )
        start_time = time.perf_counter()
        buttons, move = await llm.chat.remote.aio(
            messages, character, super_art, super_count, side, available_moves
        )
        elapsed = (time.perf_counter() - start_time) * 1000
        ms_per_move.append(elapsed)
        print(f"Sample {sample_idx}: {move}, {buttons}")

    percentiles = [50, 90, 95, 99]
    sorted_ms = sorted(ms_per_move)
    results = {}
    for p in percentiles:
        idx = int(len(sorted_ms) * p / 100)
        idx = min(max(idx - 1, 0), len(sorted_ms) - 1)
        results[p] = sorted_ms[idx]
    print("--------------------------------")
    print("Latency per move percentiles (ms):")
    for p in percentiles:
        print(f"  p{p}: {results[p]:.2f}ms")
    print("--------------------------------")


@app.local_entrypoint()
async def main(n_samples: int = 100):
    await test_qwen36.remote.aio(n_samples)
