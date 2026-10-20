import base64
import math
import os
import random
import re
import subprocess
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any, Literal, Sequence, TypedDict

import modal

SEED = 42
random.seed(SEED)


# modal

ROUTING_REGION = "us-east"
CONTAINER_REGION = "us-east"
MINUTES = 60
GB = 1024


# web app


class ParticipantSpec(TypedDict):
    label: str
    kind: Literal["human", "cpu", "model"]
    seats: tuple[str, ...]


PARTICIPANT_SPECS: dict[str, ParticipantSpec] = {
    "human": {
        "label": "YOU",
        "kind": "human",
        "seats": ("P1",),
    },
    "cpu": {
        "label": "CPU",
        "kind": "cpu",
        "seats": ("P2",),
    },
    "qwen3_vl_8b": {
        "label": "QWEN3-VL-8B",
        "kind": "model",
        "seats": ("P1", "P2"),
    },
    "qwen35_9b": {
        "label": "QWEN3.5-9B",
        "kind": "model",
        "seats": ("P1", "P2"),
    },
    "gemma4_31b": {
        "label": "GEMMA4-31B",
        "kind": "model",
        "seats": ("P1", "P2"),
    },
    "ministral3_14b": {
        "label": "MINISTRAL3-14B",
        "kind": "model",
        "seats": ("P1", "P2"),
    },
}
PARTICIPANT_LABELS = {
    participant: spec["label"] for participant, spec in PARTICIPANT_SPECS.items()
}
DEFAULT_PLAYER1_PARTICIPANT = "human"
DEFAULT_PLAYER2_PARTICIPANT = "qwen35_9b"
MAX_CPU_DIFFICULTY = 8
INFERENCE_LATENCY_MS = 200.0


def model_reaction_delay_ms(buttons: Sequence[int], generation_ms: float) -> float:
    n_buttons = sum(button != 0 for button, _ in groupby(buttons))
    if n_buttons == 0:
        return generation_ms
    human_ms = 100.0 + 30.0 * (n_buttons - 1)
    playback_ms = (len(buttons) - 1) * (1000.0 / 60.0)
    return max(generation_ms, human_ms - playback_ms)


def model_reaction_frames(buttons: Sequence[int], generation_ms: float) -> int:
    return math.ceil(model_reaction_delay_ms(buttons, generation_ms) * 60 / 1000)


def is_model_participant(participant: str) -> bool:
    spec = PARTICIPANT_SPECS.get(participant)
    return spec is not None and spec["kind"] == "model"


def normalize_participant(participant: str, *, seat: str) -> str:
    default = (
        DEFAULT_PLAYER1_PARTICIPANT if seat == "P1" else DEFAULT_PLAYER2_PARTICIPANT
    )
    spec = PARTICIPANT_SPECS.get(participant)
    if spec is None or seat not in spec["seats"]:
        return default
    return participant


def normalize_game_participants(game_settings: dict) -> tuple[str, str]:
    player1_participant = normalize_participant(
        game_settings.get("player1Participant", DEFAULT_PLAYER1_PARTICIPANT),
        seat="P1",
    )
    player2_participant = normalize_participant(
        game_settings.get("player2Participant", DEFAULT_PLAYER2_PARTICIPANT),
        seat="P2",
    )
    game_settings["player1Participant"] = player1_participant
    game_settings["player2Participant"] = player2_participant
    return player1_participant, player2_participant


def create_gameplay_image(
    *,
    extra_python_packages: Sequence[str] = (),
    base_image: modal.Image | None = None,
    copy: bool = False,
    add_python_source: bool = False,
) -> modal.Image:
    apt_packages = ["ffmpeg", "libturbojpeg-dev"]
    python_packages = [
        "MAMEToolkit==1.1.0",
        "PyTurboJPEG==1.8.2",
        *extra_python_packages,
    ]
    image = base_image or modal.Image.debian_slim(python_version="3.12")
    image = (
        image.apt_install(*apt_packages)
        .env(
            {
                "SDL_VIDEODRIVER": "dummy",
                "SDL_AUDIODRIVER": "dummy",
                "SF3_WARM_MODELS": os.environ.get("SF3_WARM_MODELS", "0"),
                "XDG_RUNTIME_DIR": "/tmp",
            }
        )
        .uv_pip_install(*python_packages)
        .add_local_file(
            Path(__file__).parent.parent / "assets" / "engine" / "sfiii3n.zip",
            "/root/sfiii3n.zip",
            copy=copy,
        )
    )
    if add_python_source:
        image = image.add_local_python_source("src", copy=copy)
    return image


def _exec_subprocess(cmd: list[str]) -> None:
    process = subprocess.Popen(cmd)
    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)


# game constants

STUN_BAR_MAX = 72
SUPER_BAR_MAX = 128
HEALTH_MAX = 160
TIMER_MAX = 100
EX_METER_COST = 40


# characters

CHARACTER_MAPPING = {
    0: "Gouki",
    1: "Alex",
    2: "Chun-Li",
    3: "Dudley",
    4: "Elena",
    5: "Hugo",
    6: "Ibuki",
    7: "Ken",
    8: "Makoto",
    9: "Necro",
    10: "Oro",
    11: "Q",
    12: "Remy",
    13: "Ryu",
    14: "Sean",
    15: "Twelve",
    16: "Urien",
    17: "Yang",
    18: "Yun",
}
CHARACTER_TO_ID = {v: k for k, v in CHARACTER_MAPPING.items()}


# moves

BUTTON_INPUTS = {
    "Left": "LEFT",
    "Right": "RIGHT",
    "Up": "UP",
    "Down": "DOWN",
    "Low Punch": "JPUNCH",
    "Medium Punch": "SPUNCH",
    "High Punch": "FPUNCH",
    "Low Kick": "SKICK",
    "Medium Kick": "FKICK",
    "High Kick": "RKICK",
}
_BUTTON_BITS = {name: 1 << index for index, name in enumerate(BUTTON_INPUTS)}
_BUTTON_GROUPS = {
    "Two Punches": ("Low Punch", "Medium Punch"),
    "Three Punches": ("Low Punch", "Medium Punch", "High Punch"),
    "Two Kicks": ("Low Kick", "Medium Kick"),
    "Three Kicks": ("Low Kick", "Medium Kick", "High Kick"),
}


def _buttons_mask(*names: str) -> int:
    mask = 0
    for name in names:
        for button in _BUTTON_GROUPS.get(name, (name,)):
            mask |= _BUTTON_BITS[button]
    return mask


MOVES = {
    "No-Move": 0,
    **{
        name: _buttons_mask(*name.split("+"))
        for name in (
            "Left",
            "Left+Up",
            "Up",
            "Right+Up",
            "Right",
            "Right+Down",
            "Down",
            "Left+Down",
            "Low Punch",
            "Medium Punch",
            "High Punch",
            "Low Kick",
            "Medium Kick",
            "High Kick",
            "Low Punch+Low Kick",
            "Medium Punch+Medium Kick",
            "High Punch+High Kick",
            "Low Kick+High Punch",
            "Three Punches",
            "Two Punches",
            "Down+Three Punches",
            "Two Kicks",
            "Three Kicks",
        )
    },
}
DIRECTION_MASK = _buttons_mask("Left", "Right", "Up", "Down")
ATTACK_MASK = _buttons_mask(
    "Low Punch", "Medium Punch", "High Punch", "Low Kick", "Medium Kick", "High Kick"
)


def chord(*names: str) -> int:
    mask = 0
    for name in names:
        mask |= MOVES[name]
    return mask


def frame_inputs(frame: int) -> tuple[str, ...]:
    return tuple(
        emulator
        for index, emulator in enumerate(BUTTON_INPUTS.values())
        if frame & (1 << index)
    )


def mirror_moves(moves):
    left, right = _BUTTON_BITS["Left"], _BUTTON_BITS["Right"]
    return [
        move & ~(left | right) | (move & left) << 1 | (move & right) >> 1
        for move in moves
    ]


def create_move_dict(moves_list):
    moves = list(moves_list)
    if (
        len(moves) > 1
        and moves[-2]
        and not moves[-2] & ~DIRECTION_MASK
        and moves[-1]
        and not moves[-1] & ~ATTACK_MASK
        and not moves[-1] & (moves[-1] - 1)
    ):
        moves[-2:] = [moves[-2] | moves[-1]]
    return {"left": tuple(moves), "right": tuple(mirror_moves(moves))}


def create_motion_dict(motion: str, button: str, hold: int = 1):
    motions = {
        "qcf": ("Down", "Left+Down", "Left"),
        "qcb": ("Down", "Right+Down", "Right"),
        "hcf": ("Right", "Right+Down", "Down", "Left+Down", "Left"),
        "hcb": ("Left", "Left+Down", "Down", "Right+Down", "Right"),
        "charge_back": ("Right",) * 60 + ("Left",),
        "charge_down": ("Down",) * 60 + ("Up",),
        "double_qcf": ("Down", "Left+Down", "Left") * 2,
        "double_qcb": ("Down", "Right+Down", "Right") * 2,
        "dp": ("Left", "Down", "Left+Down"),
        "rdp": ("Right", "Down", "Right+Down"),
        "360": ("Right", "Down", "Left", "Up"),
        "720": ("Right", "Down", "Left", "Up", "Right", "Down", "Left"),
    }
    sequence = [MOVES[name] for name in motions[motion]]
    return create_move_dict(
        sequence[:-1] + [sequence[-1] | MOVES[button]] + [MOVES[button]] * (hold - 1)
    )


COMBOS = {
    "Alex": {
        "Power Bomb": create_motion_dict("hcb", "Medium Punch"),
        "Spiral DDT": create_motion_dict("hcb", "Low Kick"),
        "Flash Chop": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Air Knee Smash": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ]
        ),
        "Air Stampede": create_motion_dict("charge_down", "Low Kick"),
        "Slash Elbow": create_motion_dict("charge_back", "Low Kick"),
    },
    "Chun-Li": {
        "Kikoken": create_motion_dict("hcf", "Medium Punch"),
        "Hazanshu": create_motion_dict("hcb", "Low Kick"),
        "Spinning Bird Kick": create_motion_dict("charge_down", "Low Kick"),
        "Hyakuretsu Kyaku": create_move_dict([MOVES["Low Kick"], 0] * 10),
    },
    "Dudley": {
        "Ducking": create_motion_dict("hcf", "Low Kick"),
        "Jet Upper": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
        "Machine Gun Blow": create_motion_dict("hcf", "Medium Punch"),
        "Cross Counter": create_motion_dict("hcb", "Medium Punch"),
        "Short Swing Blow": create_motion_dict("hcb", "Low Kick"),
    },
    "Elena": {
        "Rhino Horn": create_motion_dict("hcf", "Medium Kick"),
        "Mallet Smash": create_motion_dict("hcb", "Medium Punch"),
        "Spin Scythe": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Scratch Wheel": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Kick"],
            ]
        ),
        "Lynx Tail": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Gouki": {
        "Hadouken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Shakunetsu-Hadouken": create_motion_dict("hcb", "Medium Punch"),
        "Go Shoryuken": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["High Punch"],
            ]
        ),
        "Tatsumaki Zankuukyaku": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Ashura Senku": create_motion_dict("dp", "Two Punches"),
        "Hyakkishu": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Hugo": {
        "Shootdown Backbreaker": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ]
        ),
        "Ultra Throw": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Moonsault Press": create_motion_dict("360", "Medium Punch"),
        "Meat Squasher": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Right+Up"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Giant Palm Bomber": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "Monster Lariat": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Ibuki": {
        "Raida": create_motion_dict("hcb", "Medium Punch"),
        "Kasumi Gake": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Tsuji Goe": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
        "Kunai": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Kubi Ori": create_motion_dict("qcf", "Medium Punch"),
        "Kazekiri": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ]
        ),
        "Hien": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ]
        ),
        "Tsumuji": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Ken": {
        "Hadouken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Shoryuken": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["High Punch"],
            ]
        ),
        "Tatsumaki": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Makoto": {
        "Karakusa": create_motion_dict("hcb", "Low Kick"),
        "Hayate": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Fukiage": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
        "Oroshi": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Necro": {
        "Snake Fang": create_motion_dict("hcf", "Low Kick"),
        "Denji Blast": create_move_dict([MOVES["Medium Punch"], 0] * 5),
        "Flying Viper": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "Rising Cobra": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Tornado Hook": create_motion_dict("hcf", "Medium Punch"),
    },
    "Oro": {
        "Niou Riki": create_motion_dict("hcb", "Medium Punch"),
        "Nichirin Shou": create_motion_dict("charge_back", "Medium Punch"),
        "Oni Yanma": create_motion_dict("charge_down", "Medium Punch"),
        "Jinchuu Watari": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Q": {
        "Capture & Deadly Blow": create_motion_dict("hcb", "Low Kick"),
        "Dashing Straight": create_motion_dict("charge_back", "Medium Punch"),
        "Dashing Head Attack": create_motion_dict("charge_back", "High Punch"),
        "Dashing Leg Attack": create_motion_dict("charge_back", "Low Kick"),
        "High Speed Barrage": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Remy": {
        "Light of Virtue": create_motion_dict("charge_back", "Medium Punch"),
        "Light of Virtue (low)": create_motion_dict("charge_back", "Low Kick"),
        "Rising Rage Flash": create_motion_dict("charge_down", "Low Kick"),
        "Cold Blue Kick": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Ryu": {
        "Hadouken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Shoryuken": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["High Punch"],
            ]
        ),
        "Tatsumaki Senpukyaku": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Air Tatsumaki Senpukyaku": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Joudan Sokutou Geri": create_motion_dict("hcf", "Low Kick"),
    },
    "Sean": {
        "Zenten": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "Sean Tackle": create_motion_dict("hcb", "Medium Punch", hold=30),
        "Dragon Smash": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
        "Tornado": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Ryuubi Kyaku": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Twelve": {
        "Kokuu": create_move_dict(
            [
                MOVES["Left"],
                0,
                MOVES["Left"],
            ]
        ),
        "N.D.L.": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "A.X.E.": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "D.R.A.": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Urien": {
        "Metallic Sphere": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Chariot Tackle": create_motion_dict("charge_back", "Low Kick"),
        "Violence Knee Drop": create_motion_dict("charge_down", "Low Kick"),
        "Dangerous Headbutt": create_motion_dict("charge_down", "Medium Punch"),
    },
    "Yang": {
        "Tourou Zan": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Senkyuutai": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Byakko Soushouda": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "Fake Byakko Soushouda": create_motion_dict("qcb", "Medium Punch", hold=30),
        "Zenpou Tenshin": create_motion_dict("hcb", "Low Kick"),
        "Kaihou": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Yun": {
        "Zenpou Tenshin": create_motion_dict("hcb", "Low Kick"),
        "Kobokushi": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "Fake Kobokushi": create_motion_dict("qcb", "Two Punches"),
        "Zesshou Hohou": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Tetsuzanko": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
        "Nishoukyaku": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ]
        ),
    },
}

SPECIAL_MOVES = {
    "Alex": {
        "1 Hyper Bomb": create_motion_dict("360", "Medium Punch"),
        "2 Boomerang Raid": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch"],
            ]
        ),
        "3 Stun Gun Headbutt": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Chun-Li": {
        "1 Kikou Shou": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Houyoku Sen": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Kick"],
            ]
        ),
        "3 Tensei Ranka": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Dudley": {
        "1 Rocket Upper": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Rolling Thunder": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Corkscrew Blow": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["High Punch"],
            ]
        ),
    },
    "Elena": {
        "1 Spinning Beat": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "2 Brave Dance": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 Healing": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Gouki": {
        "1 Messatsu Gou Hadou": create_motion_dict("double_qcf", "Medium Punch"),
        "2 Messatsu Gou Shoryu": create_motion_dict("double_qcf", "Medium Punch"),
        "3 Messatsu-Gourasen": create_motion_dict("double_qcf", "Low Kick"),
        "Max Shungokusatsu (2 bars)": create_move_dict(
            [
                MOVES["Low Punch"],
                0,
                MOVES["Low Punch"],
                MOVES["Left"],
                MOVES["Low Kick+High Punch"],
            ]
        ),
        "Max Kongou Kokuretsuzan (2 bars)": create_move_dict(
            [
                MOVES["Down"],
                0,
                MOVES["Down"],
                0,
                MOVES["Down+Three Punches"],
            ]
        ),
    },
    "Hugo": {
        "1 Gigas Breaker": create_motion_dict("720", "Medium Punch"),
        "2 Megaton Press": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 Hammer Frenzy": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Ibuki": {
        "1 Kasumi Suzaku": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Yoroi Dooshi": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Yami Shigure": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Ken": {
        "1 Shoryureppa": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Shinryuken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 Shippu Jinraikyaku": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Makoto": {
        "1 Seichusen Godanzuki": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch"],
            ]
        ),
        "2 Abare Tosanami": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 Tanden Renki": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Necro": {
        "1 Magnetic Storm": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Slam Dance": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Electric Snake": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Oro": {
        "1 Kishin Riki": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Max-1 EX Kishin Riki": create_motion_dict("double_qcf", "Two Punches"),
        "2 Yagyou Dama": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Max-2 EX Yagyou Dama (3 bars)": create_motion_dict(
            "double_qcf", "Two Punches"
        ),
        "3 Tengu Stone": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Max-3 EX Tengu Stone": create_motion_dict("double_qcf", "Two Punches"),
    },
    "Q": {
        "1 Critical Combo Attack": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Deadly Double Combination": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Total Destruction": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Remy": {
        "1 Light of Justice": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Supreme Rising Rage Flash": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 Blue Nocturne": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Ryu": {
        "1 Shinkuu-Hadouken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Shin Shoryuken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Denjin Hadouken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Sean": {
        "1 Hadou Burst": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Shoryuu Cannon": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Hyper Tornado": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Twelve": {
        "1 X.N.D.L": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 X.F.L.A.T": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 X.C.O.P.Y": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Urien": {
        "1 Tyrant Slaughter": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Temporal Thunder": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Aegis Reflector": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Yang": {
        "1 Raishin Mahha Ken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Tenshin Senkyutai": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "3 Sei'ei Enbu": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Yun": {
        "1 You-hou": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Sourai Rengeki": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Genei-jin": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
    },
}


# Sources: Capcom's 3rd Strike manual and StrategyWiki's 3rd Strike move lists.
# Inputs use the facing-left convention; create_move_dict mirrors the other side.
MOVE_REQUIREMENTS = {
    "Gouki": {
        "Air Hadouken": "airborne",
        "Air Tatsumaki": "airborne",
        "Tenma Kuujin Kyaku": "forward jump, near its apex",
        "Demon Flip Palm": "during Hyakkishu",
        "Demon Flip Kick": "during Hyakkishu",
        "Demon Flip Throw": "during Hyakkishu, close to the opponent",
        "Demon Flip Sweep": "during Hyakkishu",
        "1 Tenma Gou Zankuu": "airborne",
        "3 Messatsu-GouSenpuu": "airborne",
    },
    "Alex": {
        "Flying Cross Chop": "airborne",
        "Power Backdrop": "close to an opponent facing away",
        "Air Knee Smash": "opponent airborne and within grab range",
    },
    "Chun-Li": {
        "Yousou Kyaku": "airborne",
        "Suitotsu Da": "forward jump",
        "Air Throw": "airborne and close",
    },
    "Hugo": {
        "Body Press": "airborne",
        "Shootdown Backbreaker": "opponent airborne and within grab range",
    },
    "Ibuki": {
        "Kunai": "airborne",
        "1 Kasumi Suzaku": "airborne",
        "Air Throw": "airborne and close",
    },
    "Ken": {"Air Tatsumaki": "airborne"},
    "Makoto": {
        "Tsurugi": "airborne",
        "Hayate Cancel": "while charging Hayate",
        "Fukiage": "opponent airborne",
    },
    "Necro": {"Drill Kick": "airborne"},
    "Oro": {
        "Hitobashira Nobori": "airborne",
        "Double Jump": "airborne",
        "Air Throw": "airborne and close",
        "Kishin Riki Grab": "during Super Art I, close",
        "Kishin Riki Air Grab": "during Super Art I, airborne and close",
    },
    "Q": {
        "Total Destruction Blow": "during Super Art III",
        "Total Destruction Grab": "during Super Art III, close",
    },
    "Ryu": {"Air Tatsumaki Senpukyaku": "airborne"},
    "Twelve": {
        "Kokuu": "airborne",
        "D.R.A.": "airborne",
        "2 X.F.L.A.T": "airborne",
        "Wall Bounce": "air dash near a wall",
    },
    "Yang": {"Raigeki Shuu": "airborne"},
    "Yun": {"Raigeki Shuu": "airborne"},
    "Dudley": {"Ducking Straight": "during Ducking", "Ducking Upper": "during Ducking"},
}

_ADDITIONAL_SPECIALS = {
    "Gouki": {
        "Air Hadouken": ("qcf", "Medium Punch"),
        "Air Tatsumaki": ("qcb", "Low Kick"),
        "Ashura Senku Back": ("rdp", "Two Punches"),
        "Ashura Senku Short": ("dp", "Two Kicks"),
        "Ashura Senku Back Short": ("rdp", "Two Kicks"),
    },
    "Ken": {"Air Tatsumaki": ("qcb", "Low Kick")},
    "Makoto": {"Tsurugi": ("qcb", "Low Kick")},
    "Oro": {"Hitobashira Nobori": ("qcf", "Low Kick")},
}
for _character, _names in {
    "Alex": ("Power Bomb", "Spiral DDT", "Power Backdrop"),
    "Hugo": (
        "Moonsault Press",
        "Ultra Throw",
        "Meat Squasher",
        "Shootdown Backbreaker",
    ),
    "Ibuki": ("Raida",),
    "Makoto": ("Karakusa",),
    "Necro": ("Snake Fang",),
    "Oro": ("Niou Riki",),
    "Q": ("Capture & Deadly Blow",),
    "Yang": ("Zenpou Tenshin",),
    "Yun": ("Zenpou Tenshin",),
}.items():
    for _name in _names:
        MOVE_REQUIREMENTS.setdefault(_character, {}).setdefault(
            _name, "close to the opponent"
        )
for _character, _specs in _ADDITIONAL_SPECIALS.items():
    COMBOS[_character].update(
        {
            name: create_motion_dict(motion, button)
            for name, (motion, button) in _specs.items()
        }
    )

COMBOS["Alex"]["Power Backdrop"] = create_motion_dict("hcb", "Medium Punch")
COMBOS["Makoto"]["Hayate Charged"] = create_motion_dict("qcf", "Medium Punch", hold=180)
SPECIAL_MOVES["Gouki"]["1 Tenma Gou Zankuu"] = create_motion_dict(
    "double_qcf", "Medium Punch"
)
SPECIAL_MOVES["Gouki"]["3 Messatsu-GouSenpuu"] = create_motion_dict(
    "double_qcf", "Low Kick"
)
SPECIAL_MOVES["Ryu"]["3 Denjin Hadouken Charged"] = create_motion_dict(
    "double_qcf", "Medium Punch", hold=120
)

EX_SPECIALS = {
    "Alex": ("Flash Chop", "Air Knee Smash", "Air Stampede", "Slash Elbow"),
    "Chun-Li": ("Kikoken", "Hazanshu", "Spinning Bird Kick", "Hyakuretsu Kyaku"),
    "Dudley": ("Jet Upper", "Machine Gun Blow", "Cross Counter", "Short Swing Blow"),
    "Elena": (
        "Rhino Horn",
        "Mallet Smash",
        "Spin Scythe",
        "Scratch Wheel",
        "Lynx Tail",
    ),
    "Gouki": (),
    "Hugo": ("Giant Palm Bomber", "Monster Lariat"),
    "Ibuki": ("Kunai", "Kubi Ori", "Kazekiri", "Hien", "Tsumuji"),
    "Ken": ("Hadouken", "Shoryuken", "Tatsumaki", "Air Tatsumaki"),
    "Makoto": ("Hayate", "Fukiage", "Oroshi", "Tsurugi"),
    "Necro": ("Tornado Hook", "Flying Viper", "Rising Cobra"),
    "Oro": ("Nichirin Shou", "Oni Yanma", "Jinchuu Watari", "Hitobashira Nobori"),
    "Q": ("Dashing Straight", "Dashing Leg Attack", "High Speed Barrage"),
    "Remy": (
        "Light of Virtue",
        "Light of Virtue (low)",
        "Rising Rage Flash",
        "Cold Blue Kick",
    ),
    "Ryu": (
        "Hadouken",
        "Shoryuken",
        "Tatsumaki Senpukyaku",
        "Air Tatsumaki Senpukyaku",
        "Joudan Sokutou Geri",
    ),
    "Sean": ("Sean Tackle", "Dragon Smash", "Tornado", "Ryuubi Kyaku"),
    "Twelve": ("N.D.L.", "A.X.E.", "D.R.A."),
    "Urien": (
        "Metallic Sphere",
        "Chariot Tackle",
        "Violence Knee Drop",
        "Dangerous Headbutt",
    ),
    "Yang": ("Tourou Zan", "Senkyuutai"),
    "Yun": ("Zesshou Hohou", "Tetsuzanko", "Nishoukyaku"),
}
ATTACK_BUTTONS = {
    "LP": "Low Punch",
    "MP": "Medium Punch",
    "HP": "High Punch",
    "LK": "Low Kick",
    "MK": "Medium Kick",
    "HK": "High Kick",
}
_STRENGTHS = {
    "punch": (("LP", "Low Punch"), ("MP", "Medium Punch"), ("HP", "High Punch")),
    "kick": (("LK", "Low Kick"), ("MK", "Medium Kick"), ("HK", "High Kick")),
}
_PUNCH_MASK = _buttons_mask(*[button for _, button in _STRENGTHS["punch"]])


def _replace_attack(sequence, old, new):
    return [(frame & ~old) | new if frame & old else frame for frame in sequence]


def _inherit_requirement(character: str, name: str, variant: str) -> None:
    requirements = MOVE_REQUIREMENTS.get(character, {})
    if name in requirements:
        requirements[variant] = requirements[name]


for _catalog in (COMBOS, SPECIAL_MOVES):
    for _character, _moves in _catalog.items():
        for _name, _directions in list(_moves.items()):
            _sequence = _directions["left"]
            _attacks = [frame & ATTACK_MASK for frame in _sequence]
            _old = next((attack for attack in reversed(_attacks) if attack), 0)
            if not _old:
                continue
            if any(attack & (attack - 1) for attack in _attacks):
                continue
            _kind = "punch" if _old & _PUNCH_MASK else "kick"
            for _short, _button in _STRENGTHS[_kind]:
                _variant = f"{_name} ({_short})"
                _moves[_variant] = create_move_dict(
                    _replace_attack(_sequence, _old, MOVES[_button])
                )
                _inherit_requirement(_character, _name, _variant)
            if _catalog is COMBOS and _name in EX_SPECIALS[_character]:
                for _index, _pair in enumerate(((0, 1), (0, 2), (1, 2))):
                    _buttons = [_STRENGTHS[_kind][i] for i in _pair]
                    _variant = f"EX {_name}" + (
                        f" ({_buttons[0][0]}+{_buttons[1][0]})" if _index else ""
                    )
                    _moves[_variant] = create_move_dict(
                        _replace_attack(
                            _sequence, _old, chord(*[b for _, b in _buttons])
                        )
                    )
                    _inherit_requirement(_character, _name, _variant)


def _normal_input(code):
    direction = {
        "f": "Left",
        "b": "Right",
        "d": "Down",
        "df": "Left+Down",
        "db": "Right+Down",
    }
    strength = code[-2:]
    prefix = code[:-2].removeprefix("j")
    button = ATTACK_BUTTONS[strength]
    return chord(direction[prefix], button) if prefix else MOVES[button]


_COMMAND_NORMALS = {
    "Gouki": {"Zugai Hasatsu": "fMP", "Tenma Kuujin Kyaku": "dMK"},
    "Alex": {
        "Flying Cross Chop": "dHP",
        "Chop": "fMP",
        "Lariat": "fHP",
        "Headbutt": "bHP",
    },
    "Chun-Li": {
        "Souren Shou": "bMP",
        "Hakkei": "bHP",
        "Senjou Shuu": "fMK",
        "Yoku Sen Kyaku": "fHK",
        "Tenshin Shuu Kyaku": "dfHK",
        "Yousou Kyaku": "dMK",
        "Suitotsu Da": "dHP",
    },
    "Dudley": {
        "Slipping Jab": "fLP",
        "Stomach Blow": "fMP",
        "Step Straight": "fHP",
        "Liver Blow": "fMK",
        "Dart Shot": "fHK",
    },
    "Elena": {
        "Handstand Kick": "fMP",
        "Handstand Whip": "fMK",
        "Round Arch": "bHK",
        "Sliding": "dfHK",
    },
    "Hugo": {"Body Press": "dHP", "Drop Kick Forward": "fHK", "Drop Kick Back": "bHK"},
    "Ibuki": {
        "Maki Geri": "fLK",
        "Koube Kudaki": "fMK",
        "Bonshou Geri": "fHK",
        "You Men": "bMP",
        "Ura Maki Geri": "bMK",
        "Sazan": "dfMK",
    },
    "Ken": {
        "Inazuma Kakato Wari": "bMK",
        "Fumikomi Mae Geri": "fMK",
        "Shiden Kakato Otoshi": "fHK",
    },
    "Makoto": {
        "Kote Tsuki": "fLP",
        "Gezuki": "fMP",
        "Fumikomi Seiken": "fHP",
        "Mae Geri": "fLK",
        "Fumikomi Mawashi Geri": "fMK",
        "Fumikomi Soku Barai": "fHK",
    },
    "Necro": {
        "Drill Kick": "dMK",
        "Elbow": "bLP",
        "Necro Upper": "bMP",
        "Knee Dagger": "bLK",
        "Knee Attack": "bMK",
        "Knee Missile": "bHK",
        "Elbow Cannon": "dbHP",
    },
    "Oro": {"Mawashi Hiji": "fMP"},
    "Q": {
        "Toubu Kougeki": "bMP",
        "Ryouude Tsuugeki": "bHP",
        "Tentou Toubu": "dbHP",
        "Tentou Kyakubu": "dbHK",
    },
    "Remy": {"Excessive Pure Needle": "fMK"},
    "Ryu": {"Sakotsu Wari": "fMP", "Kyuubi Kudaki": "fHP"},
    "Sean": {"Rolling Sobat": "fHK", "Sean Pachiki": "fHP"},
    "Twelve": {"B.M.K.": "bMK"},
    "Urien": {"Quarrel Punch": "fMP", "Quarrel Kick": "fMK", "Terrible Smash": "fHP"},
    "Yang": {"Raigeki Shuu": "dfMK", "Senpuu Kyaku": "fMK", "Koushu": "fHP"},
    "Yun": {"Raigeki Shuu": "dfMK", "Senpuu Kyaku": "fMK", "Dakai": "fHP"},
}
for _character, _normals in _COMMAND_NORMALS.items():
    COMBOS[_character].update(
        {
            name: create_move_dict([_normal_input(code)])
            for name, code in _normals.items()
        }
    )

_FOLLOW_UPS = {
    "Gouki": {"Demon Flip Palm": "MP", "Demon Flip Kick": "MK"},
    "Dudley": {
        "Ducking Straight": "MP",
        "Ducking Upper": "MK",
        "Punch and Cross": "fMP",
    },
    "Ibuki": {
        "Tsumuji High Finish": "MK",
        "Tsumuji Low Finish": "dMK",
        "Oiura Ken": "HP",
    },
    "Makoto": {"Hayate Cancel": "LK", "Fumikomi Seiken Follow Up": "HP"},
    "Oro": {
        "Kishin Riki Grab": "MP",
        "Kishin Riki Air Grab": "MP",
        "Hitobashira Follow Up": "MK",
    },
    "Q": {"Total Destruction Blow": "MP", "Total Destruction Grab": "MK"},
}
for _character, _follow_ups in _FOLLOW_UPS.items():
    COMBOS[_character].update(
        {
            name: create_move_dict([_normal_input(code)])
            for name, code in _follow_ups.items()
        }
    )
    for _name in _follow_ups:
        MOVE_REQUIREMENTS.setdefault(_character, {}).setdefault(
            _name, "during the corresponding parent move"
        )
COMBOS["Gouki"]["Demon Flip Throw"] = create_move_dict([MOVES["Low Punch+Low Kick"]])
COMBOS["Gouki"]["Demon Flip Sweep"] = create_move_dict([0] * 12)
COMBOS["Chun-Li"]["Wall Jump"] = create_move_dict([MOVES["Left+Up"]] * 4)
MOVE_REQUIREMENTS["Chun-Li"]["Wall Jump"] = (
    "airborne, next to a wall; jump away from that wall"
)
COMBOS["Chun-Li"]["Kakushu Raku Kyaku"] = create_move_dict([MOVES["Medium Kick"]] * 20)
COMBOS["Oro"]["Double Jump"] = create_move_dict([0] + [MOVES["Up"]] * 4)
COMBOS["Twelve"]["Air Dash Back"] = create_move_dict(
    [
        MOVES["Right"],
        0,
        MOVES["Right"],
    ]
)
COMBOS["Twelve"]["Wall Bounce"] = create_move_dict([MOVES["Left"]] * 4)
for _character in ("Chun-Li", "Ibuki", "Oro"):
    COMBOS[_character]["Air Throw"] = create_move_dict([MOVES["Low Punch+Low Kick"]])
for _character in ("Yang", "Yun"):
    for _strength, _button in _STRENGTHS["kick"]:
        COMBOS[_character][f"Raigeki Shuu ({_strength})"] = create_move_dict(
            [chord("Left+Down", _button)]
        )
        MOVE_REQUIREMENTS[_character][f"Raigeki Shuu ({_strength})"] = "diagonal jump"
for _strength, _button in _STRENGTHS["kick"]:
    COMBOS["Necro"][f"Drill Kick ({_strength})"] = create_move_dict(
        [chord("Down", _button)]
    )
    MOVE_REQUIREMENTS["Necro"][f"Drill Kick ({_strength})"] = "airborne"

_TARGET_COMBOS = {
    "Gouki": ("MP HP",),
    "Alex": ("dLK dMK",),
    "Chun-Li": ("jHP jHP",),
    "Dudley": (
        "LP MP MK",
        "fLP MP",
        "dLK MP HP",
        "dLK dMK",
        "MK HK HP",
        "fHK MK",
        "MP MK HP",
        "LK MK MP HP",
        "fMK MK HP",
    ),
    "Elena": ("jLP jMK", "jMP jHP", "HP HK", "MK dHP"),
    "Ibuki": (
        "bMP HP",
        "bMP dHK HK",
        "LP MP HP",
        "LK MK HK",
        "LP MP dHK HK",
        "dMK fMK bMK fMK",
        "LP MP fLK",
        "HP dHK HK",
        "jLK fMK",
        "jLP fHP",
        "jHP fMK",
    ),
    "Ken": ("MP HP",),
    "Makoto": ("fMK HK", "LK MK"),
    "Necro": ("bLK MP",),
    "Oro": ("LK MK",),
    "Remy": ("MK HK",),
    "Ryu": ("HP HK",),
    "Sean": ("MP HK", "HP fHP"),
    "Urien": ("LP MP", "fMP HP"),
    "Yang": ("LK MK HK", "MP HP bHP", "jMK dfMK"),
    "Yun": ("dHK HK", "MP HP bHP", "LP LK MP", "jLP fHP", "dMP dHP"),
}
for _character, _chains in _TARGET_COMBOS.items():
    for _chain in _chains:
        _name = f"Target {_chain}"
        COMBOS[_character][_name] = create_move_dict(
            [frame for code in _chain.split() for frame in [_normal_input(code), 0] * 3]
        )
        if "j" in _chain:
            MOVE_REQUIREMENTS.setdefault(_character, {})[_name] = "airborne"
for _character, _parent in (("Yang", "Tourou Zan"), ("Elena", "Spin Scythe")):
    for _name, _directions in list(COMBOS[_character].items()):
        if (
            _name == _parent
            or _name.startswith(f"{_parent} (")
            or _name.startswith(f"EX {_parent}")
        ):
            _count = (
                5
                if _character == "Yang" and _name.startswith("EX ")
                else 3
                if _character == "Yang"
                else 2
            )
            COMBOS[_character][f"{_name} Chain"] = create_move_dict(
                [
                    frame
                    for _ in range(_count)
                    for frame in [*_directions["left"], *([0] * 6)]
                ]
            )
for _character, _name in (
    ("Dudley", "2 Rolling Thunder"),
    ("Ibuki", "1 Kasumi Suzaku"),
    ("Ken", "2 Shinryuken"),
    ("Necro", "1 Magnetic Storm"),
    ("Sean", "2 Shoryuu Cannon"),
):
    _sequence = SPECIAL_MOVES[_character][_name]["left"]
    SPECIAL_MOVES[_character][f"{_name} Mash"] = create_move_dict(
        [
            *_sequence,
            *([MOVES["Medium Punch"], 0] * 12),
        ]
    )
    if _character == "Ibuki":
        MOVE_REQUIREMENTS[_character][f"{_name} Mash"] = "airborne"
COMBOS["Elena"]["Cancel Healing"] = create_move_dict([MOVES["Two Punches"]])
MOVE_REQUIREMENTS["Elena"]["Cancel Healing"] = "during Super Art III Healing"
for _short, _button in _STRENGTHS["punch"]:
    COMBOS["Makoto"][f"Hayate Feint ({_short})"] = create_move_dict(
        [
            *create_motion_dict("qcf", _button, hold=12)["left"],
            chord(_button, "Low Kick"),
            0,
        ]
    )
for _short, _button in _STRENGTHS["kick"]:
    for _follow_up, _attack in (("Straight", "Medium Punch"), ("Upper", "Medium Kick")):
        COMBOS["Dudley"][f"Ducking {_follow_up} ({_short})"] = create_move_dict(
            [
                *create_motion_dict("hcf", _button)["left"],
                *([0] * 8),
                MOVES[_attack],
            ]
        )
COPY_MOVES = {}
for _character, _moves in list(COMBOS.items()):
    if _character == "Twelve":
        continue
    for _name, _directions in list(_moves.items()):
        if (
            _name.startswith("EX ")
            or _name.startswith(("Kishin Riki ", "Total Destruction "))
            or _name == "Cancel Healing"
        ):
            continue
        _copy_name = f"Copy {_character}: {_name}"
        COPY_MOVES.setdefault(_character, {})[_copy_name] = _directions
        if _name in MOVE_REQUIREMENTS.get(_character, {}):
            MOVE_REQUIREMENTS["Twelve"][_copy_name] = MOVE_REQUIREMENTS[_character][
                _name
            ]


# instructions


CLOSE_IN_MOVES = {
    "Move Closer": create_move_dict([MOVES["Left"]] * 4),
    "Jump Closer": create_move_dict([MOVES["Left+Up"]] * 4),
}

BASE_META_INSTRUCTIONS = {
    **CLOSE_IN_MOVES,
    "No-Move": create_move_dict([0]),
    "Wait": create_move_dict([0] * 12),
    "Move Away": create_move_dict([MOVES["Right"]] * 4),
    "Walk Forward": create_move_dict([MOVES["Left"]] * 12),
    "Crouch": create_move_dict([MOVES["Down"]] * 12),
    "Guard High": create_move_dict([MOVES["Right"]] * 12),
    "Guard Low": create_move_dict([MOVES["Right+Down"]] * 12),
    "Charge Back": create_move_dict([MOVES["Right"]] * 60),
    "Charge Down": create_move_dict([MOVES["Down"]] * 60),
    "Charge Down Back": create_move_dict([MOVES["Right+Down"]] * 60),
    "Jump Up": create_move_dict([MOVES["Up"]] * 4),
    "Jump Away": create_move_dict([MOVES["Right+Up"]] * 4),
    "Dash Forward": create_move_dict([MOVES["Left"], 0] + [MOVES["Left"]] * 4),
    "Dash Back": create_move_dict([MOVES["Right"], 0] + [MOVES["Right"]] * 4),
    "Parry High": create_move_dict([0, MOVES["Left"], 0]),
    "Parry Low": create_move_dict([0, MOVES["Down"], 0]),
    "Throw": create_move_dict([MOVES["Low Punch+Low Kick"]]),
    "Throw Forward": create_move_dict([chord("Left", "Low Punch+Low Kick")]),
    "Throw Back": create_move_dict([chord("Right", "Low Punch+Low Kick")]),
    "Overhead": create_move_dict([MOVES["Medium Punch+Medium Kick"]]),
    "Taunt": create_move_dict([MOVES["High Punch+High Kick"]]),
    "Recover From Stun": create_move_dict([MOVES[name] for name in BUTTON_INPUTS] * 3),
    **{
        move_name: create_move_dict([MOVES[move_name]])
        for move_name in (
            *ATTACK_BUTTONS.values(),
            "Low Punch+Low Kick",
            "Medium Punch+Medium Kick",
            "High Punch+High Kick",
        )
    },
}
for _direction, _button in (
    ("Forward", "Left"),
    ("Back", "Right"),
    ("Down Forward", "Left+Down"),
    ("Down Back", "Right+Down"),
):
    for _strength, _attack in ATTACK_BUTTONS.items():
        BASE_META_INSTRUCTIONS[f"{_direction} {_strength}"] = create_move_dict(
            [chord(_button, _attack)]
        )
for _strength, _attack in ATTACK_BUTTONS.items():
    BASE_META_INSTRUCTIONS[f"Crouching {_strength}"] = create_move_dict(
        [chord("Down", _attack)]
    )
    for _direction, _jump in (
        ("Up", "Up"),
        ("Forward", "Left+Up"),
        ("Back", "Right+Up"),
    ):
        BASE_META_INSTRUCTIONS[f"Jump {_direction} {_strength}"] = create_move_dict(
            [MOVES[_jump]] * 4 + [0] * 12 + [MOVES[_attack]]
        )
for _direction, _jump in (("Up", "Up"), ("Forward", "Left+Up"), ("Back", "Right+Up")):
    BASE_META_INSTRUCTIONS[f"Super Jump {_direction}"] = create_move_dict(
        [MOVES["Down"]] + [MOVES[_jump]] * 4
    )

MAX_MACRO_FRAMES = max(
    len(sequence)
    for moves in (BASE_META_INSTRUCTIONS, *COMBOS.values(), *SPECIAL_MOVES.values())
    for directions in moves.values()
    for sequence in directions.values()
)


RECENT_MOVE_LIMIT = 4


def get_available_instructions_for_character(
    character: str,
    super_art: int,
    super_count: int,
    super_bar: int = 0,
    opponent_character: str | None = None,
) -> list[str]:
    instructions = []
    instructions.extend(BASE_META_INSTRUCTIONS.keys())
    for name in COMBOS[character]:
        if name.startswith("EX ") and super_count == 0 and super_bar < EX_METER_COST:
            continue
        if name.startswith("Kishin Riki ") and super_art != 1:
            continue
        if name.startswith("Total Destruction ") and super_art != 3:
            continue
        if name == "Cancel Healing" and super_art != 3:
            continue
        instructions.append(name)
    if character == "Twelve" and super_art == 3:
        instructions.extend(COPY_MOVES.get(opponent_character, {}))

    if super_count > 0:
        for special_move in SPECIAL_MOVES[character].keys():
            if special_move.startswith(f"{super_art}"):
                instructions.append(str(special_move))

            bars_required = 1
            for i in range(1, 4):
                if f"({i} bars)" in special_move:
                    bars_required = i
                    break

            if super_count >= bars_required:
                # "Max-{number}" (e.g., Oro's moves)
                if special_move.startswith(f"Max-{super_art}"):
                    instructions.append(special_move)
                # Generic "Max" moves (e.g., Gouki's moves)
                elif special_move.startswith("Max "):
                    instructions.append(special_move)

    return instructions


def move_regex(available_moves: list[str]) -> str:
    alternatives = sorted(
        (re.escape(move).replace(r"\ ", " ") for move in available_moves),
        key=len,
        reverse=True,
    )
    return "(?:" + "|".join(alternatives) + ")"


@dataclass
class PlayerState:
    character: str
    super_art: int
    wins: int
    side: int
    stunned: bool
    stun_bar: int
    health: int
    super_count: int
    super_bar: int


class FrameEncoder:
    """Caches the JPEG data URL of the most recent frame. Needs the gameplay image."""

    def __init__(self) -> None:
        import numpy
        from turbojpeg import TJPF_RGB, TJSAMP_420, TurboJPEG

        self._numpy = numpy
        self._pixel_format = TJPF_RGB
        self._subsample = TJSAMP_420
        self._encoder = TurboJPEG()
        self._frame = None
        self._data_url = ""

    def data_url(self, frame: Any) -> str:
        if self._frame is not frame:
            jpeg = self._encoder.encode(
                self._numpy.ascontiguousarray(frame),
                quality=85,
                pixel_format=self._pixel_format,
                jpeg_subsample=self._subsample,
            )
            self._frame = frame
            self._data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode(
                "utf-8"
            )
        return self._data_url


def player_state(
    observation: dict[str, Any],
    settings: dict[str, Any],
    player: str,
) -> PlayerState:
    raw = observation[player]
    return PlayerState(
        character=settings["character"],
        super_art=settings["superArt"],
        wins=int(raw["wins"][0]),
        side=int(raw["side"]),
        stunned=bool(raw["stunned"]),
        stun_bar=int(raw["stun_bar"][0]),
        health=int(raw["health"][0]),
        super_count=int(raw["super_count"][0]),
        super_bar=int(raw["super_bar"][0]),
    )


NEXT_MOVE_PROMPT = "Your next move is:"


def create_messages(
    player1: PlayerState,
    player2: PlayerState,
    frame: str,
    recent_moves: Sequence[str] | None = None,
) -> tuple[list[dict], list[str]]:
    available_moves = get_available_instructions_for_character(
        player2.character,
        player2.super_art,
        player2.super_count,
        player2.super_bar,
        player1.character,
    )
    history = ", ".join(list(recent_moves or ())[-RECENT_MOVE_LIMIT:]) or "none"
    facing = "left side facing right" if player2.side else "right side facing left"
    requirements = MOVE_REQUIREMENTS.get(player2.character, {})
    grouped_requirements: dict[str, list[str]] = {}
    for name in available_moves:
        if name in requirements:
            family = re.sub(r" \([LMH][PK](?:\+[LMH][PK])?\)$", "", name)
            group = grouped_requirements.setdefault(requirements[name], [])
            if family not in group:
                group.append(family)
    lines = [
        f"You are {player2.character} fighting {player1.character} in Street Fighter III: 3rd Strike, on the {facing}.",
        f"Best of 3 rounds: you have won {player2.wins}, your opponent {player1.wins}.",
        "Moves:",
        *("- " + move for move in available_moves),
        "LP/MP/HP and LK/MK/HK are light/medium/heavy. Forward/Back are relative to your facing; Target names use f/b/d/df for forward/back/down/down-forward.",
        *(
            f"{requirement}: {', '.join(names)}."
            for requirement, names in grouped_requirements.items()
        ),
        f"Your last moves: {history}.",
        "Respond with only the name of your next move.",
    ]

    return [
        {"role": "system", "content": "\n".join(lines)},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": frame},
                {
                    "type": "text",
                    "text": NEXT_MOVE_PROMPT,
                },
            ],
        },
    ], available_moves


async def generate_move(
    chat: Any,
    controlled: PlayerState,
    opponent: PlayerState,
    frame_url: str,
    recent_moves: Sequence[str] | None = None,
) -> tuple[list[int], str]:
    messages, available_moves = create_messages(
        opponent,
        controlled,
        frame_url,
        recent_moves,
    )
    return await chat(
        messages,
        controlled.character,
        controlled.super_art,
        controlled.super_count,
        controlled.side,
        available_moves,
    )


def est_super_ct(super_bar: int) -> int:
    if super_bar == SUPER_BAR_MAX:
        return 3
    elif super_bar >= (SUPER_BAR_MAX // 3) * 2:
        return 2
    elif super_bar >= SUPER_BAR_MAX // 3:
        return 1
    else:
        return 0


def create_random_messages() -> tuple[list[dict], str, int, int, int, list[str]]:
    player1_character = random.choice(list(CHARACTER_MAPPING.values()))
    player2_character = random.choice(list(CHARACTER_MAPPING.values()))

    player1_super_art = random.randint(1, 3)
    player2_super_art = random.randint(1, 3)

    side = random.randint(0, 1)

    player1_stun_bar = random.randint(0, STUN_BAR_MAX)
    player2_stun_bar = random.randint(0, STUN_BAR_MAX)

    player1_super_bar = random.randint(0, SUPER_BAR_MAX)
    player2_super_bar = random.randint(0, SUPER_BAR_MAX)

    player1_super_count = est_super_ct(player1_super_bar)
    player2_super_count = est_super_ct(player2_super_bar)

    player1 = PlayerState(
        character=player1_character,
        super_art=player1_super_art,
        wins=random.randint(0, 2),
        side=side,
        stunned=player1_stun_bar == STUN_BAR_MAX,
        stun_bar=player1_stun_bar,
        health=random.randint(0, HEALTH_MAX),
        super_count=player1_super_count,
        super_bar=player1_super_bar,
    )
    player2 = PlayerState(
        character=player2_character,
        super_art=player2_super_art,
        wins=random.randint(0, 2),
        side=1 - side,
        stunned=player2_stun_bar == STUN_BAR_MAX,
        stun_bar=player2_stun_bar,
        health=random.randint(0, HEALTH_MAX),
        super_count=player2_super_count,
        super_bar=player2_super_bar,
    )

    warmup_frame_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAYAAAADgCAIAAACFJiYGAAABEUlEQVR42u3BMQEAAADCoPVP7WsIoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB4A/ENAAEh48SMAAAAAElFTkSuQmCC"
    )
    messages, available_moves = create_messages(
        player1,
        player2,
        frame=warmup_frame_data_url,
    )

    return (
        messages,
        player2_character,
        player2_super_art,
        player2_super_count,
        side,
        available_moves,
    )


MAX_CONTEXT_LEN = 4096
MAX_TOKENS = 32
TEMPERATURE = 1.0
TOP_P = 0.8


# llm post-processing


def parse_move(character: str, move_name: str, side: int) -> tuple[int, ...] | None:
    current_direction = "left" if side == 0 else "right"
    if character == "Twelve" and move_name.startswith("Copy "):
        copied_character = move_name.removeprefix("Copy ").partition(": ")[0]
        copied = COPY_MOVES.get(copied_character, {}).get(move_name)
        return copied[current_direction] if copied is not None else None

    if move_name in BASE_META_INSTRUCTIONS:
        return BASE_META_INSTRUCTIONS[move_name][current_direction]
    elif move_name in COMBOS[character]:
        return COMBOS[character][move_name][current_direction]
    elif move_name in SPECIAL_MOVES[character]:
        return SPECIAL_MOVES[character][move_name][current_direction]
    return None


def resolve_move_with_fallback(
    character: str,
    move_name: str,
    side: int,
) -> tuple[list[int], str]:
    move_sequence = parse_move(character, move_name, side)
    if move_sequence is not None:
        return list(move_sequence), move_name
    return [0], "No-Move"
