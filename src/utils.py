import random
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

# Modal constants

local_assets_dir = Path(__file__).parent.parent / "assets"
region = "us-east-1"
minutes = 60

# seed

seed = 42
random.seed(seed)

# arena/game constants (only here because not immediately obvious)

X_SIZE = 384
Y_SIZE = 224
MIN_Y = 80
MAX_Y = 200

STUN_BAR_MAX = 72
SUPER_BAR_MAX = 128
HEALTH_MAX = 160

# moves + characters

MOVES = {
    "No-Move": 0,
    "Left": 1,
    "Left+Up": 2,
    "Up": 3,
    "Right+Up": 4,
    "Right": 5,
    "Right+Down": 6,
    "Down": 7,
    "Left+Down": 8,
    "Low Punch": 9,
    "Medium Punch": 10,
    "High Punch": 11,
    "Low Kick": 12,
    "Medium Kick": 13,
    "High Kick": 14,
    "Low Punch+Low Kick": 15,
    "Medium Punch+Medium Kick": 16,
    "High Punch+High Kick": 17,
}

COMBOS = {
    "Alex": {
        "Power Bomb": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Spiral DDT": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Flash Chop": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Air Knee Smash": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
        },
        "Air Stampede": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
        "Slash Elbow": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Chun-Li": {
        "Kikoken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
        },
        "Hazanshu": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Spinning Bird Kick": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
        "Hyakuretsu Kyaku": {
            "left": [
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Dudley": {
        "Ducking": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
        "Jet Upper": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Punch"],
            ],
        },
        "Machine Gun Blow": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
        },
        "Cross Counter": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Short Swing Blow": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Elena": {
        "Rhino Horn": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Medium Kick"],
            ],
        },
        "Mallet Smash": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Spin Scythe": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Scratch Wheel": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Kick"],
            ],
        },
        "Lynx Tail": {
            "left": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Gouki": {
        "Hadouken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Shakunetsu-Hadouken": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Go Shoryuken": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["High Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["High Punch"],
            ],
        },
        "Tatsumaki Zankuukyaku": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Ashura Senku": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
        "Hyakkishu": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Hugo": {
        "Shootdown Backbreaker": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
        },
        "Ultra Throw": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Moonsault Press": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Right+Up"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Left+Up"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "Meat Squasher": {
            "left": [
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
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Left+Up"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Giant Palm Bomber": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "Monster Lariat": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Ibuki": {
        "Raida": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Kasumi Gake": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Tsuji Goe": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Punch"],
            ],
        },
        "Kunai": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Kubi Ori": {
            "left": [
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Kazekiri": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
        },
        "Hien": {
            "left": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
        },
        "Tsumuji": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Ken": {
        "Hadouken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Shoryuken": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["High Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["High Punch"],
            ],
        },
        "Tatsumaki": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Makoto": {
        "Karakusa": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Hayate": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Fukiage": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Punch"],
            ],
        },
        "Oroshi": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Necro": {
        "Snake Fang": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
        "Denji Blast": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Punch"],
            ],
        },
        "Flying Viper": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "Rising Cobra": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Tornado Hook": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Oro": {
        "Niou Riki": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Nichirin Shou": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Oni Yanma": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
        },
        "Jinchuu Watari": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Q": {
        "Capture & Deadly Blow": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Dashing Straight": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Dashing Head Attack": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["High Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["High Punch"],
            ],
        },
        "Dashing Leg Attack": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "High Speed Barrage": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Remy": {
        "Light of Virtue": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Light of Virtue (low)": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Rising Rage Flash": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
        "Cold Blue Kick": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Ryu": {
        "Hadouken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Shoryuken": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["High Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["High Punch"],
            ],
        },
        "Tatsumaki Senpukyaku": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Air Tatsumaki Senpukyaku": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Joudan Sokutou Geri": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Sean": {
        "Zenten": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "Sean Tackle": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
        },
        "Dragon Smash": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Punch"],
            ],
        },
        "Tornado": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Ryuubi Kyaku": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Twelve": {
        "Kokuu": {
            "left": [
                MOVES["Left"],
                MOVES["Left"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Right"],
            ],
        },
        "N.D.L.": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "A.X.E.": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "D.R.A.": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Urien": {
        "Metallic Sphere": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Chariot Tackle": {
            "left": [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Violence Knee Drop": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ],
        },
        "Dangerous Headbutt": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Yang": {
        "Tourou Zan": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Senkyuutai": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Byakko Soushouda": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "Fake Byakko Soushouda": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
        "Zenpou Tenshin": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Kaihou": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Yun": {
        "Zenpou Tenshin": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "Kobokushi": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "Fake Kobokushi": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
        "Zesshou Hohou": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Tetsuzanko": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Medium Punch"],
            ],
        },
        "Nishoukyaku": {
            "left": [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Low Kick"],
            ],
        },
    },
}

SPECIAL_MOVES = {
    "Alex": {
        "1 Hyper Bomb": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Right+Up"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Left+Up"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Boomerang Raid": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch"],
            ],
        },
        "3 Stun Gun Headbutt": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Chun-Li": {
        "1 Kikou Shou": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Houyoku Sen": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Kick"],
            ],
        },
        "3 Tensei Ranka": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Dudley": {
        "1 Rocket Upper": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Rolling Thunder": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Corkscrew Blow": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["High Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["High Punch"],
            ],
        },
    },
    "Elena": {
        "1 Spinning Beat": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "2 Brave Dance": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 Healing": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Gouki": {
        "1 Messatsu Gou Hadou": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Messatsu Gou Shoryu": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Messatsu-Gourasen": {
            "left": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
        },
        "Max Shungokusatsu (2 bars)": {
            "left": [
                MOVES["Low Punch"],
                MOVES["Low Punch"],
                MOVES["Right"],
                MOVES["Low Kick"],
                MOVES["High Punch"],
            ],
            "right": [
                MOVES["Low Punch"],
                MOVES["Low Punch"],
                MOVES["Left"],
                MOVES["Low Kick"],
                MOVES["High Punch"],
            ],
        },
        "Max Kongou Kokuretsuzan (2 bars)": {
            "left": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
    },
    "Hugo": {
        "1 Gigas Breaker": {
            "left": [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Right+Up"],
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Right+Up"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Left+Up"],
                MOVES["Left"],
                MOVES["Left+Down"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Right+Up"],
                MOVES["Up"],
                MOVES["Left+Up"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Megaton Press": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 Hammer Frenzy": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Ibuki": {
        "1 Kasumi Suzaku": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Yoroi Dooshi": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Yami Shigure": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Ken": {
        "1 Shoryureppa": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Shinryuken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 Shippu Jinraikyaku": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Makoto": {
        "1 Seichusen Godanzuki": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch"],
            ],
        },
        "2 Abare Tosanami": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 Tanden Renki": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Necro": {
        "1 Magnetic Storm": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Slam Dance": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Electric Snake": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Oro": {
        "1 Kishin Riki": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Max-1 EX Kishin Riki": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
        "2 Yagyou Dama": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Max-2 EX Yagyou Dama (3 bars)": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
        "3 Tengu Stone": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "Max-3 EX Tengu Stone": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ],
        },
    },
    "Q": {
        "1 Critical Combo Attack": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Deadly Double Combination": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Total Destruction": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Remy": {
        "1 Light of Justice": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Supreme Rising Rage Flash": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 Blue Nocturne": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
    },
    "Ryu": {
        "1 Shinkuu-Hadouken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Shin Shoryuken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Denjin Hadouken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Sean": {
        "1 Hadou Burst": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Shoryuu Cannon": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Hyper Tornado": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Twelve": {
        "1 X.N.D.L": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 X.F.L.A.T": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 X.C.O.P.Y": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Urien": {
        "1 Tyrant Slaughter": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Temporal Thunder": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Aegis Reflector": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Yang": {
        "1 Raishin Mahha Ken": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Tenshin Senkyutai": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ],
        },
        "3 Sei'ei Enbu": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
    "Yun": {
        "1 You-hou": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "2 Sourai Rengeki": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
        "3 Genei-jin": {
            "left": [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ],
            "right": [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ],
        },
    },
}

BASE_META_INSTRUCTIONS = {
    "Move Closer": {
        "left": [MOVES["Left"], MOVES["Left"], MOVES["Left"], MOVES["Left"]],
        "right": [MOVES["Right"], MOVES["Right"], MOVES["Right"], MOVES["Right"]],
    },
    "Move Away": {
        "left": [MOVES["Right"], MOVES["Right"], MOVES["Right"], MOVES["Right"]],
        "right": [MOVES["Left"], MOVES["Left"], MOVES["Left"], MOVES["Left"]],
    },
    "Jump Closer": {
        "left": [
            MOVES["Left+Up"],
            MOVES["Left+Up"],
            MOVES["Left+Up"],
            MOVES["Left+Up"],
        ],
        "right": [
            MOVES["Right+Up"],
            MOVES["Right+Up"],
            MOVES["Right+Up"],
            MOVES["Right+Up"],
        ],
    },
    "Jump Away": {
        "left": [
            MOVES["Right+Up"],
            MOVES["Right+Up"],
            MOVES["Right+Up"],
            MOVES["Right+Up"],
        ],
        "right": [
            MOVES["Left+Up"],
            MOVES["Left+Up"],
            MOVES["Left+Up"],
            MOVES["Left+Up"],
        ],
    },
    **{
        move_name: {"left": [move_nb], "right": [move_nb]}
        for move_name, move_nb in MOVES.items()
        if "Punch" in move_name or "Kick" in move_name
    },
}


def get_meta_instructions_for_character(
    character: str, super_art: int, super_count: int
) -> list[str]:
    instructions = []
    instructions.extend(BASE_META_INSTRUCTIONS.keys())
    instructions.extend(COMBOS[character].keys())

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
    last_move: str


@dataclass
class GameInfo:
    stage: int
    timer: int
    boxes: list
    class_ids: list


def create_messages(
    game_info: GameInfo,
    player1: PlayerState,
    player2: PlayerState,
):
    # game info
    game_info_prompt = f"Stage: {game_info.stage}, Timer: {game_info.timer}, Your character: {player2.character}, Opponent character: {player1.character}"
    game_info_prompt += f", Best of 3: you've won {player2.wins} rounds, opponent has won {player1.wins} rounds"

    # position
    position_prompt = ""

    player1_box = None
    player2_box = None

    player1_char_id = CHARACTER_TO_ID[player1.character]
    player2_char_id = CHARACTER_TO_ID[player2.character]

    if player1_char_id != player2_char_id:  # characters are different
        for i, class_id in enumerate(game_info.class_ids):
            if class_id == player1_char_id and i < len(game_info.boxes):
                player1_box = game_info.boxes[i]
            elif class_id == player2_char_id and i < len(game_info.boxes):
                player2_box = game_info.boxes[i]
    else:  # characters are the same
        if len(game_info.boxes) == 2:  # two characters detected
            x_center_0 = (game_info.boxes[0][0] + game_info.boxes[0][2]) / 2
            x_center_1 = (game_info.boxes[1][0] + game_info.boxes[1][2]) / 2

            if player1.side == 0:
                if x_center_0 < x_center_1:
                    player1_box = game_info.boxes[0]
                    player2_box = game_info.boxes[1]
                else:
                    player1_box = game_info.boxes[1]
                    player2_box = game_info.boxes[0]
            else:
                if x_center_0 > x_center_1:
                    player1_box = game_info.boxes[0]
                    player2_box = game_info.boxes[1]
                else:
                    player1_box = game_info.boxes[1]
                    player2_box = game_info.boxes[0]
        elif len(game_info.boxes) == 1:  # only one character detected
            x_center = (game_info.boxes[0][0] + game_info.boxes[0][2]) / 2
            x_mid = X_SIZE / 2

            if player1.side == 0:
                if x_center < x_mid:
                    player1_box = game_info.boxes[0]
                else:
                    player2_box = game_info.boxes[0]
            else:
                if x_center > x_mid:
                    player1_box = game_info.boxes[0]
                else:
                    player2_box = game_info.boxes[0]

    position_prompt = f"Arena width: {X_SIZE}, height: {Y_SIZE}. "

    if player2_box is not None:
        player2_x_center = (player2_box[0] + player2_box[2]) / 2
        player2_y_center = (player2_box[1] + player2_box[3]) / 2
        position_prompt = (
            f"You are at position ({int(player2_x_center)}, {int(player2_y_center)}). "
        )
    else:
        position_prompt = "Your position is unknown. "

    if player1_box is not None:
        player1_x_center = (player1_box[0] + player1_box[2]) / 2
        player1_y_center = (player1_box[1] + player1_box[3]) / 2
        position_prompt += f"Your opponent is at position ({int(player1_x_center)}, {int(player1_y_center)})."
    else:
        position_prompt += "Your opponent's position is unknown."

    # stun
    stun_prompt = f"Stun bar max: {STUN_BAR_MAX}. Your stun bar is at {player2.stun_bar}. Your opponent's stun bar is at {player1.stun_bar}."
    if player2.stunned:
        stun_prompt += " You are stunned. You cannot move or attack."
    if player1.stunned:
        stun_prompt += " Your opponent is stunned. You can attack them."

    # health
    health_prompt = f"Health max: {HEALTH_MAX}. Your health is at {player2.health}. Your opponent's health is at {player1.health}."

    # power
    power_prompt = f"Super bar max: {SUPER_BAR_MAX}. Your super bar is at {player2.super_bar}. Your opponent's super bar is at {player1.super_bar}."

    # last move
    last_move_prompt = f"Your last move was {player2.last_move}. Your opponent's last move was {player1.last_move}."

    # moves
    moves_prompt = "You can use the following moves:\n"
    moves_prompt += chr(10).join(
        "- " + move
        for move in get_meta_instructions_for_character(
            player2.character, player2.super_art, player2.super_count
        )
    )

    return [  # OpenAI chat format
        {
            "role": "system",
            "content": dedent(
                f"""
                You are the best Street Fighter III 3rd strike player in the world.

                {game_info_prompt}
                {position_prompt}
                {health_prompt}
                {stun_prompt}
                {power_prompt}
                {last_move_prompt}
                {moves_prompt}

                Respond simply with the best move.
                """
            ),
        },
        {"role": "user", "content": "Your next move is:"},
    ]


INDEX_TO_MOVE = {v: k for k, v in MOVES.items()}

CHARACTER_MAPPING = {
    1: "Alex",
    2: "Chun-Li",
    3: "Dudley",
    4: "Elena",
    0: "Gouki",
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
