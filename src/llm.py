import time
from pathlib import Path

import modal

from .utils import (
    create_random_messages,
    get_available_instructions_for_character,
    local_assets_dir,
    # region,
    minutes,
    parse_move,
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

MODEL_NAME = "Qwen/Qwen3-8B"

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)

vllm_cache_vol = modal.Volume.from_name("sf3-vllm-cache", create_if_missing=True)

cache_path = Path("/cache")
cache_volume = modal.Volume.from_name(f"{app.name}-train-cache", create_if_missing=True)

# inference


def get_latest_checkpoint_file_path():
    import re

    candidates = [d for d in cache_path.iterdir() if d.is_dir()]
    if not candidates:
        return MODEL_NAME

    candidates.sort(key=lambda d: d.name, reverse=True)
    latest_dir = candidates[0]

    ckpt_pattern = re.compile(r"checkpoint-(\d+)")
    ckpt_dirs = [
        d for d in latest_dir.iterdir() if d.is_dir() and ckpt_pattern.match(d.name)
    ]
    if not ckpt_dirs:
        return MODEL_NAME

    ckpt_dirs.sort(key=lambda d: int(ckpt_pattern.match(d.name).group(1)), reverse=True)
    latest_ckpt = ckpt_dirs[0]

    return str(latest_ckpt)


MAX_INPUTS = max_num_seqs = 8


@app.cls(
    image=vllm_image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
        cache_path: cache_volume,
    },
    gpu="b200",
    # region=region,
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    scaledown_window=60 * minutes,
    timeout=24 * 60 * minutes,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class LLMServer:
    ckpt_path: str = modal.parameter(default="")

    @modal.enter()
    async def enter(self):
        from vllm import LLM, SamplingParams

        cache_volume.reload()

        load_path = self.ckpt_path or get_latest_checkpoint_file_path()
        print(f"Loading model from {load_path}")

        self.llm = LLM(
            model=load_path,
            max_num_seqs=max_num_seqs,
            max_num_batched_tokens=40960,  # https://qwen.readthedocs.io/en/latest/deployment/vllm.html#faq, https://docs.vllm.ai/en/latest/configuration/optimization.html#performance-tuning-with-chunked-prefill
            enforce_eager=True,
            swap_space=0,
            enable_prefix_caching=True,  # https://docs.vllm.ai/en/stable/features/automatic_prefix_caching.html#example-workloads,
            gpu_memory_utilization=0.9,
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

        messages, _, _, _, _ = create_random_messages()

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
        self,
        messages: list[dict[str, str]],
        character: str,
        super_art: int,
        super_count: int,
        side: int,
        return_move_name: bool = False,  # for training
    ) -> list[int]:
        from vllm.sampling_params import GuidedDecodingParams

        self.sampling_params.guided_decoding = GuidedDecodingParams(
            choice=get_available_instructions_for_character(
                character, super_art, super_count
            ),
        )

        outputs = self.llm.chat(
            [messages],
            self.sampling_params,
            chat_template=remote_chat_template_path,
        )
        move_name = outputs[0].outputs[0].text

        try:
            move_sequence = parse_move(character, move_name, side)
            if move_sequence is not None:
                if return_move_name:
                    return list(move_sequence), move_name
                else:
                    return list(move_sequence)
            else:
                raise ValueError(f"Invalid move: {move_name}")

        except Exception as e:
            print(f"Error: {e}")
            return [0], ""


@app.local_entrypoint()
async def local(
    n_samples: int = 100,
):
    llm = LLMServer()
    llm.boot.remote()

    ms_per_move = []
    for sample_idx in range(n_samples):
        messages, character, super_art, super_count, side = create_random_messages()
        start_time = time.perf_counter()
        moves = await llm.chat.remote.aio(
            messages, character, super_art, super_count, side
        )
        elapsed = (time.perf_counter() - start_time) * 1000
        n_moves = len(moves) if moves else 1
        ms_per_move.append(elapsed / n_moves)
        print(f"Sample {sample_idx}: {moves}")

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
