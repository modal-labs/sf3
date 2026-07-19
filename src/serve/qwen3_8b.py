import random
import re
import time

import modal

from src.utils import (
    CONTAINER_REGION,
    MAX_CONTEXT_LEN,
    MAX_TOKENS,
    MINUTES,
    ROUTING_REGION,
    create_random_messages,
    get_available_instructions_for_character,
    resolve_move_with_fallback,
)

APP_NAME = "sf3-llm"

app = modal.App(APP_NAME)

sglang_image = (
    modal.Image.from_registry("lmsysorg/sglang:v0.5.9-cu129-amd64-runtime")
    .entrypoint([])
    .uv_pip_install(
        "huggingface-hub==0.36.0",
        "flashinfer-python==0.6.3",
        "qwen-vl-utils==0.0.14",
    )
    .run_commands("python -m pip install --no-deps nvidia-cudnn-cu12==9.16.0.29")
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",
            "TORCHINDUCTOR_COMPILE_THREADS": "1",
        }
    )
)

hf_cache_vol = modal.Volume.from_name("sf3-huggingface-cache", create_if_missing=True)
flashinfer_cache_vol = modal.Volume.from_name(
    "sf3-flashinfer-cache", create_if_missing=True
)
cache_volumes = {
    "/root/.cache/huggingface": hf_cache_vol,
    "/root/.cache/flashinfer": flashinfer_cache_vol,
}

max_inputs = max_num_seqs = 16
gpu = "b200"

_ITER_RE = re.compile(r"^iter_(\d+)(?:_hf)?$")


def checkpoint_iter_index(name: str) -> int:
    match = _ITER_RE.match(name)
    return int(match.group(1)) if match else -1


def completed_sf3_training_run_ids() -> list[str]:
    from modal_training_gym import MetadataStore, Qwen3_VL_8B, list_checkpoints
    from modal_training_gym.utils.metadata import vol_get_summary_items_healed

    runs = vol_get_summary_items_healed(MetadataStore.TRAINING_RUNS_SUMMARY)
    result_run_ids = {
        str(result["training_run_id"])
        for result in vol_get_summary_items_healed(MetadataStore.TRAIN_RESULTS_SUMMARY)
    }
    runs.sort(
        key=lambda run: (
            int(
                run.get("completed_at")
                or run.get("ended_at")
                or run.get("created_at")
                or 0
            ),
            str(run.get("training_run_id") or ""),
        ),
    )

    run_ids: list[str] = []
    for run in runs:
        if run.get("status") != "completed":
            continue
        config = run.get("config")
        if not isinstance(config, dict):
            continue
        model = config.get("model")
        wandb = config.get("wandb")
        if not isinstance(model, dict) or not isinstance(wandb, dict):
            continue
        if model.get("model_name") != Qwen3_VL_8B.model_name:
            continue
        if wandb.get("project") != "sf3-llm-train-qwen3-vl-8b":
            continue

        training_run_id = str(run.get("training_run_id") or "")
        if not training_run_id or training_run_id not in result_run_ids:
            continue
        if list_checkpoints(training_run_id):
            run_ids.append(training_run_id)

    return run_ids


def latest_sf3_training_run_id() -> str:
    run_ids = completed_sf3_training_run_ids()
    if not run_ids:
        raise RuntimeError(
            "No completed SF3 Qwen3-VL-8B Training Gym run with checkpoints was found"
        )
    return run_ids[-1]


def _megatron_has_dcp_metadata(checkpoint) -> bool:
    from modal_training_gym.common.checkpoint import CheckpointType

    if checkpoint.checkpoint_type != CheckpointType.megatron:
        return True
    volume_name = checkpoint.checkpoints_volume_name
    rel = checkpoint.path.lstrip("/")
    mount = (checkpoint.checkpoints_mount_path or "/checkpoints").rstrip("/")
    if rel.startswith(mount.lstrip("/") + "/") or rel.startswith("checkpoints/"):
        prefix = mount.lstrip("/") + "/"
        if rel.startswith(prefix):
            rel = rel[len(prefix) :]
        elif rel.startswith("checkpoints/"):
            rel = rel[len("checkpoints/") :]
    try:
        volume = modal.Volume.from_name(volume_name)
        names = [
            getattr(entry, "path", str(entry)).rstrip("/").split("/")[-1]
            for entry in volume.listdir(f"/{rel}")
        ]
    except Exception as error:
        raise RuntimeError(
            f"cannot list megatron checkpoint {checkpoint.path} on "
            f"volume {volume_name}: {error}"
        ) from error
    return ".metadata" in names


def hf_checkpoint(training_run_id: str):
    from modal_training_gym import Qwen3_VL_8B, list_checkpoints
    from modal_training_gym.common.checkpoint import (
        CheckpointType,
        convert_checkpoint_to_hf,
    )
    from modal_training_gym.deploy_recipes import SglangRecipe

    checkpoints = list_checkpoints(training_run_id)
    if not checkpoints:
        raise RuntimeError(
            f"No checkpoints found for training run {training_run_id}. "
            "Did the run reach a save_interval?"
        )
    latest = max(
        checkpoints,
        key=lambda checkpoint: (
            checkpoint_iter_index(checkpoint.name),
            checkpoint.name,
        ),
    )
    if latest.checkpoint_type == CheckpointType.hf:
        return latest
    twin = next(
        (
            checkpoint
            for checkpoint in checkpoints
            if checkpoint.checkpoint_type == CheckpointType.hf
            and checkpoint.name == f"{latest.name}_hf"
        ),
        None,
    )
    if twin is not None:
        return twin
    if not _megatron_has_dcp_metadata(latest):
        raise RuntimeError(
            f"megatron checkpoint {latest.path} is missing torch DCP "
            f".metadata (incomplete save); cannot convert to HF"
        )
    return convert_checkpoint_to_hf(
        checkpoint=latest,
        model=Qwen3_VL_8B(),
        recipe=SglangRecipe(),
    )


CLASS_NAME = "Qwen3VLServer"  # so training code can instantiate this class


@app.cls(
    image=sglang_image,
    gpu=gpu,
    region=CONTAINER_REGION,
    routing_region=ROUTING_REGION,
    volumes=cache_volumes,
    secrets=[modal.Secret.from_name("huggingface-secret")],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    scaledown_window=60 * MINUTES,
    timeout=60 * MINUTES,
)
@modal.concurrent(max_inputs=max_inputs)
class Qwen3VLServer:
    ckpt_path: str = modal.parameter()

    @modal.enter()
    async def enter(self):
        import sglang as sgl

        print(f"Loading model from {self.ckpt_path}")
        self.llm = sgl.Engine(
            model_path=self.ckpt_path,
            context_length=MAX_CONTEXT_LEN,
            chunked_prefill_size=8192,
            max_running_requests=max_num_seqs,
            cuda_graph_max_bs=max_inputs * 2,
            mem_fraction_static=0.9,
            grammar_backend="xgrammar",
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
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            return_dict=False,
            enable_thinking=False,
        )
        await self.llm.async_generate(
            prompt,
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
        seed: int | None = None,
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
        if seed is not None:
            sampling_params["sampling_seed"] = seed

        image_data = []
        for message in messages:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if item.get("type") == "image":
                    image_data.append(item["image"])
                elif item.get("type") == "image_url":
                    image_url = item["image_url"]
                    image_data.append(
                        image_url["url"] if isinstance(image_url, dict) else image_url
                    )

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            return_dict=False,
            enable_thinking=False,
        )
        output = await self.llm.async_generate(
            prompt,
            image_data=image_data or None,
            sampling_params=sampling_params,
        )
        move_name = output["text"].strip()

        move_sequence, resolved_move_name = resolve_move_with_fallback(
            character, move_name, side
        )
        if resolved_move_name == "No-Move":
            print(f"Invalid move: {move_name}")
        return move_sequence, resolved_move_name

    @modal.exit()
    def exit(self):
        self.llm.shutdown()


@app.function(region=CONTAINER_REGION, routing_region=ROUTING_REGION)
async def test(
    n_samples: int,
    checkpoint_path: str,
    checkpoint_volume_name: str,
    checkpoint_mount_path: str,
):
    checkpoint_volume = modal.Volume.from_name(checkpoint_volume_name)
    model_cls = Qwen3VLServer.with_options(  # pyright: ignore[reportAttributeAccessIssue]
        volumes={
            **cache_volumes,
            checkpoint_mount_path: checkpoint_volume,
        }
    )
    llm = model_cls(ckpt_path=checkpoint_path)
    await llm.boot.remote.aio()

    random.seed(0)
    ms_per_move: list[float] = []
    for sample_idx in range(n_samples):
        messages, character, super_art, super_count, side, available_moves = (
            create_random_messages()
        )
        start_time = time.perf_counter()
        buttons, move = await llm.chat.remote.aio(
            messages,
            character,
            super_art,
            super_count,
            side,
            available_moves,
            seed=sample_idx,
        )
        elapsed = (time.perf_counter() - start_time) * 1000
        assert move != "No-Move", f"sample {sample_idx} produced no valid move"
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
def main(n_samples: int = 100, training_run_id: str = ""):
    training_run_id = training_run_id.strip() or latest_sf3_training_run_id()
    print(f"Using Training Gym run {training_run_id}")
    checkpoint = hf_checkpoint(training_run_id)
    test.remote(
        n_samples,
        checkpoint.path,
        checkpoint.checkpoints_volume_name,
        checkpoint.checkpoints_mount_path,
    )
