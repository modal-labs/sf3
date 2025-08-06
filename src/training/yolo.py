from dataclasses import dataclass
from pathlib import Path

import modal

from ..utils import (
    CHARACTER_MAPPING,
    X_SIZE,
    Y_SIZE,
    minutes,
    seed,
)

# Modal setup

app = modal.App("sf3-yolo-train")

py_version = "3.12"

train_image = (
    modal.Image.debian_slim(python_version=py_version)
    .apt_install(  # install system libraries for graphics handling
        [
            "libgl1-mesa-glx",
            "libglib2.0-0",
        ]
    )
    .uv_pip_install(
        "ultralytics==8.3.167",
        "opencv-python==4.11.0.86",
        "beautifulsoup4~=4.13.4",
        extra_index_url="https://download.pytorch.org/whl/cu128",
        extra_options="--index-strategy unsafe-best-match",
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
    .uv_pip_install(
        "ultralytics==8.3.167",
        "onnx==1.17.0",
        "onnxslim==0.1.59",
        "onnxruntime-gpu==1.21.0",
        "opencv-python==4.11.0.86",
        "tensorrt==10.9.0.34",
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

    original_image_dir = volume_path / "original_images"
    original_image_dir.mkdir(parents=True, exist_ok=True)

    character_sprites = []
    base_url = "https://www.zytor.com/~johannax/jigsaw/sf/images"

    print("Downloading character sprites...")
    for character_id, character_name in tqdm(
        CHARACTER_MAPPING.items(), desc="Characters"
    ):
        url_name = character_name.lower().replace("-", "")
        char_dir = original_image_dir / character_name
        char_dir.mkdir(parents=True, exist_ok=True)

        all_exist = all(
            (char_dir / f"{idx}.png").exists() for idx in range(images_per_character)
        )

        images = []
        if all_exist:
            for idx in range(images_per_character):
                image = Image.open(char_dir / f"{idx}.png").convert("RGBA")
                images.append(image)
        else:
            response = requests.get(f"{base_url}/{url_name}")
            soup = BeautifulSoup(response.text, "html.parser")
            image_filenames = sorted(
                [
                    a["href"]
                    for a in soup.find_all("a", href=True)
                    if any(
                        a["href"].endswith(f"3s{str(i).zfill(2)}.gif")
                        for i in range(1, images_per_character + 1)
                    )
                ]
            )

            for idx, image_filename in enumerate(image_filenames):
                image_url = f"{base_url}/{url_name}/{image_filename}"
                response = requests.get(image_url)
                image = Image.open(BytesIO(response.content)).convert("RGBA")
                image.save(char_dir / f"{idx}.png")
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
        max_y_char1 = max(0, Y_SIZE - char1_img.height)
        max_y_char2 = max(0, Y_SIZE - char2_img.height)

        char1_y = random.randint(0, max_y_char1) if max_y_char1 > 0 else 0
        char2_y = random.randint(0, max_y_char2) if max_y_char2 > 0 else 0

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


# model

model_size = "yolov10n.pt"

TRAIN_GPU_COUNT = 4
TRAIN_CPU_COUNT = TRAIN_GPU_COUNT * 8


@app.function(
    image=train_image,
    volumes=volumes,
    gpu=f"b200:{TRAIN_GPU_COUNT}",
    cpu=TRAIN_CPU_COUNT,
    timeout=24 * 60 * minutes,
)
def train_model():
    import time

    from ultralytics import YOLO

    volume.reload()

    model = YOLO(model_size)
    model.train(
        # dataset config
        data=str(dataset_dir / "data.yaml"),
        # optimization config
        device=list(range(TRAIN_GPU_COUNT)),  # use the GPU(s)
        batch=512 * TRAIN_GPU_COUNT,
        seed=seed,
        epochs=50,
        # data processing config
        workers=max(
            TRAIN_CPU_COUNT // TRAIN_GPU_COUNT, 1
        ),  # split CPUs evenly across GPUs
        cache="disk",  # cache preprocessed images deterministically
        # model saving config
        project=str(runs_dir),
        name=time.strftime("%Y%m%d_%H%M%S"),
        exist_ok=True,
        verbose=True,
        # disable all color, geometric, and complex augmentations
        hsv_h=0.0,
        hsv_s=0.0,
        hsv_v=0.0,
        degrees=0.0,
        translate=0.0,
        scale=0.0,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.0,
        bgr=0.0,
        mosaic=0.0,
        mixup=0.0,
        cutmix=0.0,
        copy_paste=0.0,
        auto_augment=None,
        erasing=0.0,
    )


def find_best_model(suffix: str):
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


@app.local_entrypoint()
async def main(
    prepare: bool = False,
    train: bool = False,
    export: bool = False,
):
    if prepare:
        prepare_dataset.remote()

    if train:
        train_model.remote()

    if export:
        export_onnx.remote()
