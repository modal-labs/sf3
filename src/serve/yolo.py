from pathlib import Path

import modal

from ..inference_postprocess import postprocess_character_detections
from ..utils import (
    CHARACTER_MAPPING,
    X_SIZE,
    Y_SIZE,
    minutes,
    seed,
)

app = modal.App("sf3-yolo")

py_version = "3.12"
onnx_image = (
    modal.Image.debian_slim(python_version=py_version)
    .apt_install("locales")
    .run_commands(
        "sed -i '/^#\\s*en_US.UTF-8 UTF-8/ s/^#//' /etc/locale.gen",
        "locale-gen en_US.UTF-8",
        "update-locale LANG=en_US.UTF-8",
    )
    .env(
        {
            "LD_LIBRARY_PATH": f"/usr/local/lib/python{py_version}/site-packages/tensorrt_libs",
            "LANG": "en_US.UTF-8",
        }
    )
    .apt_install("python3-opencv", "ffmpeg")
    .uv_pip_install(
        "onnx==1.17.0",
        "onnxruntime-gpu==1.21.0",
        "onnxslim==0.1.59",
        "opencv-python==4.11.0.86",
        "tensorrt==10.9.0.34",
        "ultralytics==8.3.167",
    )
)

cache_volume = modal.Volume.from_name("sf3-yolo-train-cache", create_if_missing=True)
cache_path = Path("/root/yolo")

model_name = cache_path / "runs" / "20251010_235516" / "weights" / "best.onnx"
max_inputs = 512
gpu = "b200"
trt_cache_path = cache_path / "onnx.cache" / gpu / model_name.stem


@app.cls(
    image=onnx_image,
    volumes={cache_path: cache_volume},
    gpu=gpu,
    secrets=[modal.Secret.from_dotenv(Path(__file__).parent.parent.parent)],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    scaledown_window=60 * minutes,
    timeout=60 * minutes,
)
@modal.concurrent(max_inputs=max_inputs)
class YOLOServer:
    @modal.enter()
    async def enter(self):
        import cv2
        import numpy as np
        import onnxruntime

        onnxruntime.set_seed(seed)
        onnxruntime.preload_dlls()

        await cache_volume.reload.aio()
        trt_cache_path.mkdir(parents=True, exist_ok=True)
        print(f"Loading model from {model_name}")

        self.session = onnxruntime.InferenceSession(
            model_name,
            providers=[
                (
                    "TensorrtExecutionProvider",
                    {
                        "trt_engine_cache_enable": True,
                        "trt_engine_cache_path": str(trt_cache_path),
                    },
                ),
                "CUDAExecutionProvider",
            ],
        )

        model_inputs = self.session.get_inputs()
        self.input_names = [model_inputs[i].name for i in range(len(model_inputs))]

        self.input_shape = model_inputs[0].shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]

        model_outputs = self.session.get_outputs()
        self.output_names = [model_outputs[i].name for i in range(len(model_outputs))]

        frame = np.random.randint(0, 256, (Y_SIZE, X_SIZE, 3), dtype=np.uint8)

        self.img_height, self.img_width = frame.shape[:2]
        input_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_img = cv2.resize(input_img, (self.input_width, self.input_height))

        input_img = input_img / 255.0
        input_img = input_img.transpose(2, 0, 1)
        input_tensor = input_img[np.newaxis, :, :, :].astype(np.float16)

        _ = self.session.run(
            self.output_names,
            {self.input_names[0]: input_tensor},
        )

    @modal.method()
    async def boot(self):
        pass

    @modal.method()
    async def detect_characters(
        self,
        character_ids: list[int],
        frame=None,
        confidence_threshold: float = 0.0,
        return_objects: bool = True,
    ):
        import cv2
        import numpy as np

        if frame is None:
            frame = np.random.randint(0, 256, (Y_SIZE, X_SIZE, 3), dtype=np.uint8)

        self.img_height, self.img_width = frame.shape[:2]
        input_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_img = cv2.resize(input_img, (self.input_width, self.input_height))

        input_img = input_img / 255.0
        input_img = input_img.transpose(2, 0, 1)
        input_tensor = input_img[np.newaxis, :, :, :].astype(np.float16)

        outputs = self.session.run(
            self.output_names,
            {self.input_names[0]: input_tensor},
        )

        predictions = np.squeeze(outputs[0])
        boxes, filtered_class_ids = postprocess_character_detections(
            predictions=predictions,
            character_ids=character_ids,
            confidence_threshold=confidence_threshold,
            input_width=self.input_width,
            input_height=self.input_height,
            img_width=self.img_width,
            img_height=self.img_height,
        )

        if return_objects:
            return boxes, filtered_class_ids


@app.local_entrypoint()
async def main(n_samples: int = 100):
    import random
    import time

    print("Booting detector...")
    start_time = time.perf_counter()
    detector = YOLOServer()
    await detector.boot.remote.aio()
    print(f"Detector booted in {time.perf_counter() - start_time:.2f}s")

    latencies = []
    for _ in range(n_samples):
        start_time = time.perf_counter()
        await detector.detect_characters.remote.aio(
            character_ids=[
                random.choice(list(CHARACTER_MAPPING.keys())),
                random.choice(list(CHARACTER_MAPPING.keys())),
            ],
            return_objects=False,
        )
        latencies.append((time.perf_counter() - start_time) * 1000)

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
