from typing import Any, NamedTuple

from src.serve import gemma4_31b, ministral3_14b, qwen35_9b


class ModelSpec(NamedTuple):
    app: Any
    server: Any
    eval_gpu: str
    version: dict[str, Any]


MODELS = {
    key: ModelSpec(
        module.app,
        server,
        module.eval_gpu,
        {
            "model": module.model_name,
            "revision": module.model_revision,
            "gpu": module.eval_gpu,
        },
    )
    for key, module, server in (
        ("qwen35_9b", qwen35_9b, qwen35_9b.Qwen35Server),
        ("gemma4_31b", gemma4_31b, gemma4_31b.Gemma4Server),
        ("ministral3_14b", ministral3_14b, ministral3_14b.Ministral3Server),
    )
}
