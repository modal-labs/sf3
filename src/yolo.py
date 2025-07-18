from dataclasses import dataclass
from pathlib import Path

import modal

from .config import (
    CHARACTER_MAPPING,
    MAX_Y,
    MIN_Y,
    X_SIZE,
    Y_SIZE,
    minutes,
    seed,
)

# Modal setup

app = modal.App("diambra-yolo")

py_version = "3.12"

train_image = (
    modal.Image.debian_slim(python_version=py_version)
    .apt_install(  # install system libraries for graphics handling
        [
            "libgl1-mesa-glx",
            "libglib2.0-0",
        ]
    )
    .pip_install("uv")
    .run_commands(  # install python libraries for computer vision
        "uv pip install --system --compile-bytecode ultralytics==8.3.167 opencv-python==4.11.0.86 beautifulsoup4~=4.13.4 --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu128"
    )
)

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

volume = modal.Volume.from_name(f"{app.name}-cache", create_if_missing=True)
volume_path = Path("/root/yolo")
volumes = {volume_path: volume}

dataset_dir = volume_path / "dataset"
runs_dir = volume_path / "runs"


# dataset

images_per_character = 13
scenes_per_pair_train = (
    images_per_character * 9
)  # multiple of images_per_character to use all character variations
scenes_per_pair_val = images_per_character * 1  # same as train


# model

model_size = "yolov10n.pt"


@dataclass
class CharacterSprite:
    character_id: int
    character_name: str
    images: list  # PIL
    bboxes: list[tuple[int, int, int, int]]  # x1, y1, x2, y2


@app.function(image=train_image, volumes=volumes, timeout=60 * minutes)
def prepare_dataset():
    import random
    from io import BytesIO
    from itertools import product

    import numpy as np
    import requests
    import yaml
    from bs4 import BeautifulSoup
    from PIL import Image, ImageFilter
    from tqdm import tqdm

    np.random.seed(seed)

    print(f"Starting dataset preparation in {dataset_dir}...")
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"

    for dir in [
        images_dir / "train",
        images_dir / "val",
        labels_dir / "train",
        labels_dir / "val",
    ]:
        dir.mkdir(parents=True, exist_ok=True)

    # scrape images

    character_sprites = []
    base_url = "https://www.zytor.com/~johannax/jigsaw/sf/images"

    print("Downloading character sprites...")
    for character_id, character_name in tqdm(
        CHARACTER_MAPPING.items(), desc="Characters"
    ):
        url_name = character_name.lower().replace("-", "")
        response = requests.get(f"{base_url}/{url_name}")
        soup = BeautifulSoup(response.text, "html.parser")
        image_filenames = sorted(
            [
                a["href"]
                for a in soup.find_all("a", href=True)
                if any(
                    a["href"].endswith(f"3s{str(i).zfill(2)}.gif") for i in range(1, 14)
                )
            ]
        )

        images = []
        for image_filename in image_filenames:
            image_url = f"{base_url}/{url_name}/{image_filename}"
            response = requests.get(image_url)
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            images.append(image)

        character_sprites.append(
            CharacterSprite(
                character_id=character_id,
                character_name=character_name,
                images=images,
                bboxes=None,
            )
        )

    def augment_character(img: Image, is_training: bool, flip: bool):
        # horizontal flip
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        if not is_training:
            return img

        # small rotation
        if random.random() > 0.7:
            angle = random.uniform(-5, 5)
            img = img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))

        # gaussian blur
        if random.random() > 0.6:
            radius = random.uniform(0, 2)
            if radius > 0:
                img = img.filter(ImageFilter.GaussianBlur(radius=radius))

        return img

    def create_scene(
        char1_data,
        char2_data,
        char1_img_idx,
        char2_img_idx,
        is_training,
        min_separation: int = 50,
    ):
        scene = Image.new("RGBA", (X_SIZE, Y_SIZE), (0, 0, 0, 255))

        char1_img = char1_data.images[char1_img_idx % len(char1_data.images)].copy()
        char2_img = char2_data.images[char2_img_idx % len(char2_data.images)].copy()

        char1_img = augment_character(char1_img, is_training, flip=False)
        char2_img = augment_character(char2_img, is_training, flip=True)

        max_x_char1 = X_SIZE // 2 - min_separation // 2
        max_x_char2 = X_SIZE // 2 + min_separation // 2

        char1_x = random.randint(10, max_x_char1)
        char2_x = random.randint(max_x_char2, X_SIZE - char2_img.width - 10)

        # clamp Y position to ensure characters are at least partially visible
        max_y_char1 = max(MIN_Y, MAX_Y - char1_img.height)
        max_y_char2 = max(MIN_Y, MAX_Y - char2_img.height)

        char1_y = random.randint(MIN_Y, max_y_char1) if max_y_char1 > MIN_Y else MIN_Y
        char2_y = random.randint(MIN_Y, max_y_char2) if max_y_char2 > MIN_Y else MIN_Y

        scene.paste(char1_img, (char1_x, char1_y), char1_img)
        scene.paste(char2_img, (char2_x, char2_y), char2_img)

        scene_rgb = Image.new("RGB", scene.size, (0, 0, 0))
        scene_rgb.paste(
            scene, mask=scene.split()[3] if len(scene.split()) == 4 else None
        )

        bbox1 = (
            char1_x,
            char1_y,
            char1_x + char1_img.width,
            char1_y + char1_img.height,
        )
        bbox2 = (
            char2_x,
            char2_y,
            char2_x + char2_img.width,
            char2_y + char2_img.height,
        )

        return scene_rgb, [
            (char1_data.character_id, bbox1),
            (char2_data.character_id, bbox2),
        ]

    character_pairs = list(product(character_sprites, character_sprites))

    print("\nGenerating dataset scenes...")
    for split_name, scenes_per_pair in [
        ("train", scenes_per_pair_train),
        ("val", scenes_per_pair_val),
    ]:
        is_training = split_name == "train"
        image_idx = 0

        print(f"\nGenerating {split_name} split:")
        pair_pbar = tqdm(character_pairs, desc=f"{split_name} pairs")

        for char1, char2 in pair_pbar:
            for scene_num in range(scenes_per_pair):
                char1_img_idx = scene_num % images_per_character
                char2_img_idx = (
                    scene_num // images_per_character + scene_num
                ) % images_per_character
                scene_img, detections = create_scene(
                    char1, char2, char1_img_idx, char2_img_idx, is_training
                )

                filename = f"scene_{image_idx:06d}"
                scene_img.save(images_dir / split_name / f"{filename}.png")

                img_w, img_h = scene_img.size
                with open(labels_dir / split_name / f"{filename}.txt", "w") as f:
                    for char_id, bbox in detections:
                        x1, y1, x2, y2 = bbox

                        x_center = (x1 + x2) / 2
                        y_center = (y1 + y2) / 2
                        bbox_w = x2 - x1
                        bbox_h = y2 - y1

                        x_center_norm = x_center / img_w
                        y_center_norm = y_center / img_h
                        width_norm = bbox_w / img_w
                        height_norm = bbox_h / img_h

                        f.write(
                            f"{char_id} {x_center_norm} {y_center_norm} {width_norm} {height_norm}\n"
                        )

                image_idx += 1

    config = {
        "path": str(dataset_dir),
        "train": str(images_dir / "train"),
        "val": str(images_dir / "val"),
        "names": CHARACTER_MAPPING,
    }
    with open(dataset_dir / "data.yaml", "w") as f:
        yaml.dump(config, f)

    total_train_scenes = len(character_pairs) * scenes_per_pair_train
    total_val_scenes = len(character_pairs) * scenes_per_pair_val

    print(
        f"\nDataset prepared:\n"
        f"  {images_per_character} images/sprite × {len(character_sprites)} sprites = {images_per_character * len(character_sprites)} total character images\n"
        f"  {len(character_sprites)}×{len(character_sprites)} = {len(character_pairs)} character pairs\n"
        f"  Training: {len(character_pairs)} pairs × {scenes_per_pair_train} scenes/pair = {total_train_scenes} scenes\n"
        f"  Validation: {len(character_pairs)} pairs × {scenes_per_pair_val} scenes/pair = {total_val_scenes} scenes\n"
        f"  Total: {total_train_scenes + total_val_scenes} scenes\n"
        f"  Image usage: Each character image used {scenes_per_pair_train} times in training, {scenes_per_pair_val} times in validation"
    )


TRAIN_GPU_COUNT = 1
TRAIN_CPU_COUNT = TRAIN_GPU_COUNT * 8


@app.function(
    image=train_image,
    volumes=volumes,
    gpu=f"b200:{TRAIN_GPU_COUNT}",
    cpu=TRAIN_CPU_COUNT,
    timeout=24 * 60 * minutes,
)
def train_model(epochs: int, batch_size_per_gpu: int):
    from datetime import datetime

    from ultralytics import YOLO

    volume.reload()

    model = YOLO(model_size)
    model.train(
        # dataset config
        data=str(dataset_dir / "data.yaml"),
        # optimization config
        device=list(range(TRAIN_GPU_COUNT)),  # use the GPU(s)
        epochs=epochs,
        batch=batch_size_per_gpu * TRAIN_GPU_COUNT,
        seed=seed,
        # data processing config
        workers=max(
            TRAIN_CPU_COUNT // TRAIN_GPU_COUNT, 1
        ),  # split CPUs evenly across GPUs
        cache="disk",  # cache preprocessed images deterministically
        # model saving config
        project=str(runs_dir),
        name=datetime.now().strftime("%Y-%m-%d"),
        exist_ok=True,  # overwrite previous model if it exists
        verbose=True,  # detailed logs
        # disable geometric transforms since camera POV is fixed
        degrees=0.0,
        translate=0.0,
        scale=0.0,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.0,
        bgr=0.0,
        # disable complex augmentations since we create synthetic scenes
        mosaic=0.0,  # no mosaic (we control character placements)
        mixup=0.0,  # no mixup (character identities must be preserved)
        copy_paste=0.0,
        auto_augment=None,  # disable auto augment for classification
        erasing=0.0,
    )


def find_best_model(suffix: str = ""):
    import glob
    import os

    pattern = str(runs_dir / "*" / "weights" / f"best.{suffix}")
    best_pts = glob.glob(pattern)
    if not best_pts:
        return None
    best_pts.sort(key=os.path.getmtime, reverse=True)
    return runs_dir / best_pts[0]


@app.function(image=onnx_image, volumes=volumes, gpu="l40s", timeout=10 * minutes)
def export_onnx():
    from ultralytics import YOLO

    volume.reload()
    model_file = find_best_model("pt")
    if model_file is None:
        raise ValueError("No best model found")

    model = YOLO(str(model_file))
    model.export(format="onnx", half=True, device=0)

    print(f"Exported model to {model_file.with_suffix('.onnx')}")


MAX_INPUTS = 512


@app.cls(
    image=onnx_image,
    volumes=volumes,
    gpu="b200",
    scaledown_window=15 * minutes,
    timeout=10 * minutes,
)
@modal.concurrent(max_inputs=MAX_INPUTS)
class YOLOServer:
    @modal.enter()
    def load_model(self):
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

    @modal.method()
    async def boot(self):  # so don't have to call `detect_characters` to boot
        pass

    @modal.method()
    async def detect_characters(
        self,
        character_ids: list[int],
        frame=None,
        confidence_threshold=0.0,
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
    prepare: bool = False,
    train: bool = False,
    epochs: int = 30,
    batch_size_per_gpu: int = 512,
    export: bool = False,
    test: bool = False,
    n_samples: int = 100,
):
    if prepare:
        prepare_dataset.remote()

    if train:
        train_model.remote(epochs, batch_size_per_gpu)

    if export:
        export_onnx.remote()

    if test:
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
