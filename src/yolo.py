from pathlib import Path

import modal

from .utils import (
    CHARACTER_MAPPING,
    X_SIZE,
    Y_SIZE,
    minutes,
    seed,
    # region,
)

# Modal setup

app = modal.App("sf3-yolo")

py_version = "3.12"

onnx_image = (
    modal.Image.debian_slim(python_version=py_version)  # matching ld path
    # update locale as required by onnx
    .apt_install("locales")
    .run_commands(
        "sed -i '/^#\\s*en_US.UTF-8 UTF-8/ s/^#//' /etc/locale.gen",  # use sed to uncomment
        "locale-gen en_US.UTF-8",  # set locale
        "update-locale LANG=en_US.UTF-8",
    )
    .env(
        {
            "LD_LIBRARY_PATH": f"/usr/local/lib/python{py_version}/site-packages/tensorrt_libs",
            "LANG": "en_US.UTF-8",
        }
    )
    # install system dependencies
    .apt_install("python3-opencv", "ffmpeg")
    # install Python dependencies
    .pip_install("uv")
    .run_commands(
        "uv pip install --system --compile-bytecode ultralytics==8.3.167 onnx==1.17.0 onnxslim==0.1.59 onnxruntime-gpu==1.21.0 opencv-python==4.11.0.86 tensorrt==10.9.0.34"
    )
)

volume = modal.Volume.from_name(f"{app.name}-train-cache", create_if_missing=True)
volume_path = Path("/root/yolo")
volumes = {volume_path: volume}

runs_dir = volume_path / "runs"


def find_best_model(suffix: str = ""):
    import glob
    import os

    pattern = str(runs_dir / "*" / "weights" / f"best.{suffix}")
    best_pts = glob.glob(pattern)
    if not best_pts:
        return None
    best_pts.sort(key=os.path.getmtime, reverse=True)
    return runs_dir / best_pts[0]


MAX_INPUTS = 64


@app.cls(
    image=onnx_image,
    volumes=volumes,
    gpu="b200",
    # region=region,
    scaledown_window=60 * minutes,
    timeout=24 * 60 * minutes,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class YOLOServer:
    @modal.enter()
    def enter(self):
        import cv2
        import numpy as np
        import onnxruntime

        onnxruntime.set_seed(seed)
        onnxruntime.preload_dlls()

        volume.reload()
        model_file = find_best_model("onnx")
        if model_file is None:
            raise ValueError("No best model found")

        self.session = onnxruntime.InferenceSession(
            model_file,
            providers=[
                (
                    "TensorrtExecutionProvider",
                    {
                        "trt_engine_cache_enable": True,
                        "trt_engine_cache_path": volume_path / "onnx.cache",
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

        # warm up model

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
    async def boot(self):  # so don't have to call `detect_characters` to boot
        pass

    @modal.method()
    async def detect_characters(
        self,
        character_ids: list[int],
        frame=None,
        confidence_threshold: float = 0.0,
        use_dummy_frame: bool = False,
        return_objects: bool = True,
    ):
        import cv2
        import numpy as np

        if use_dummy_frame:
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

        scores = predictions[:, 4]
        class_ids = predictions[:, 5].astype(int)

        confidence_mask = scores >= confidence_threshold
        predictions = predictions[confidence_mask]
        scores = scores[confidence_mask]
        class_ids = class_ids[confidence_mask]

        character_mask = np.isin(class_ids, character_ids)
        filtered_predictions = predictions[character_mask]
        filtered_scores = scores[character_mask]
        filtered_class_ids = class_ids[character_mask]

        if len(set(character_ids)) == 1:
            if len(filtered_scores) > 2:
                top_indices = np.argsort(filtered_scores)[-2:][::-1]
                filtered_predictions = filtered_predictions[top_indices]
                filtered_scores = filtered_scores[top_indices]
                filtered_class_ids = filtered_class_ids[top_indices]
        else:
            final_predictions = []
            final_scores = []
            final_class_ids = []

            for char_id in character_ids:
                char_mask = filtered_class_ids == char_id
                if np.any(char_mask):
                    char_predictions = filtered_predictions[char_mask]
                    char_scores = filtered_scores[char_mask]

                    best_idx = np.argmax(char_scores)
                    final_predictions.append(char_predictions[best_idx])
                    final_scores.append(char_scores[best_idx])
                    final_class_ids.append(char_id)

            if len(final_predictions) > 0:
                filtered_predictions = np.array(final_predictions)
                filtered_scores = np.array(final_scores)
                filtered_class_ids = np.array(final_class_ids)

        boxes = filtered_predictions[:, :4]
        input_shape = np.array(
            [
                self.input_width,
                self.input_height,
                self.input_width,
                self.input_height,
            ]
        )
        boxes = np.divide(boxes, input_shape, dtype=np.float32)
        boxes *= np.array(
            [self.img_width, self.img_height, self.img_width, self.img_height]
        )

        print(f"Detected {len(boxes)} characters")

        if return_objects:
            return boxes, filtered_class_ids


@app.local_entrypoint()
async def main(
    n_samples: int = 100,
):
    import random
    import time

    print("Booting detector...")
    start_time = time.perf_counter()
    detector = YOLOServer()
    detector.boot.remote()
    print(f"Detector booted in {time.perf_counter() - start_time:.2f}s")

    latencies = []
    for _ in range(n_samples):
        start_time = time.perf_counter()
        await detector.detect_characters.remote.aio(
            character_ids=[
                random.choice(list(CHARACTER_MAPPING.keys())),
                random.choice(list(CHARACTER_MAPPING.keys())),
            ],
            use_dummy_frame=True,
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
