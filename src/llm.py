import time
from pathlib import Path
from textwrap import dedent

import modal

# Modal setup

remote_chat_template_path = "/root/qwen3_nonthinking.jinja"

vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("uv")
    .run_commands(
        "uv pip install --system --compile-bytecode vllm==0.9.2 flashinfer-python==0.2.6.post1 --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu128",
    )
    .run_commands(
        "uv pip install --system --compile-bytecode huggingface_hub[hf_transfer]==0.33.4",
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
    "diambra-llm-huggingface-cache", create_if_missing=True
)

vllm_cache_vol = modal.Volume.from_name(
    "diambra-llm-vllm-cache", create_if_missing=True
)

app = modal.App("diambra-llm-vllm")

N_GPU = 1
MINUTES = 60  # seconds
MAX_INPUTS = max_num_seqs = 128

# Prompt helpers

ACTIONS = [
    "NONE",
    "LEFT",
    "LEFT_UP",
    "UP",
    "RIGHT_UP",
    "RIGHT",
    "RIGHT_DOWN",
    "DOWN",
    "LEFT_DOWN",
    "LIGHT_PUNCH",
    "MEDIUM_PUNCH",
    "HEAVY_PUNCH",
    "LIGHT_KICK",
    "MEDIUM_KICK",
    "HEAVY_KICK",
    "LP_LK",
    "MP_MK",
    "HP_HK",
]


@app.cls(
    image=vllm_image,
    gpu=f"B200:{N_GPU}",
    scaledown_window=15 * MINUTES,
    timeout=10 * MINUTES,
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

        self.sampling_params = SamplingParams(
            temperature=0.7,
            top_p=0.8,
            top_k=len(ACTIONS),
            min_p=0.0,
            max_tokens=1,
            presence_penalty=1.5,
            guided_decoding=GuidedDecodingParams(
                choice=[f"{i}" for i in range(len(ACTIONS))],
            ),  # https://huggingface.co/Qwen/Qwen3-0.6B#best-practices
        )
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

    @modal.method()
    def boot(self):  # so don't have to call chat.remote() to boot
        pass

    @modal.method()
    def chat(self, messages: list[dict[str, str]]) -> int:
        outputs = self.llm.chat(
            [messages],
            self.sampling_params,
            chat_template=remote_chat_template_path,
        )
        text = outputs[0].outputs[0].text
        try:
            return int(text)
        except ValueError:
            return 0


@app.local_entrypoint()
async def test(test_timeout=10 * MINUTES, n_samples=100):
    llm_server = LLMServer()

    messages = [  # OpenAI chat format
        {
            "role": "system",
            "content": dedent(
                f"""
                You are a Street Fighter expert.
                Here is a list of moves and corresponding output integers:
                {"\n".join([f"{i}: {a}" for i, a in enumerate(ACTIONS)])}

                Given your and your opponent's health and xy positions, determine the best move to counter the opponent's move.
                Simply output the integer of the best move.

                For example:
                Input:
                You:
                - health: 100
                - x pos: -30
                - y pos: 0
                Opponent:
                - health: 100
                - x pos: 30
                - y pos: 0
                Output:
                1
                """
            ),
        },
        {
            "role": "user",
            "content": dedent("""
                You:
                - health: 100
                - x pos: -30
                - y pos: 0
                Opponent:
                - health: 100
                - x pos: 30
                - y pos: 0
            """),
        },
    ]

    ttfts_ms = []
    for _ in range(n_samples):
        start_time = time.perf_counter()
        _ = llm_server.chat.remote(messages)
        ttft_ms = (time.perf_counter() - start_time) * 1000
        ttfts_ms.append(ttft_ms)

    p50 = sorted(ttfts_ms)[int(len(ttfts_ms) * 0.5) - 1]
    p90 = sorted(ttfts_ms)[int(len(ttfts_ms) * 0.9) - 1]
    print("--------------------------------")
    print(f"ttft (p50, p90): ({p50:.2f}ms, {p90:.2f}ms)")
    print("--------------------------------")
