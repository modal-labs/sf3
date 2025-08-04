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

STUN_BAR_MAX = 72
SUPER_BAR_MAX = 128
HEALTH_MAX = 160

# characters

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


# moves

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

INDEX_TO_MOVE = {v: k for k, v in MOVES.items()}


def mirror_moves(moves):
    mirrored = []
    for move in moves:
        if move == MOVES["Left"]:
            mirrored.append(MOVES["Right"])
        elif move == MOVES["Right"]:
            mirrored.append(MOVES["Left"])
        elif move == MOVES["Left+Up"]:
            mirrored.append(MOVES["Right+Up"])
        elif move == MOVES["Right+Up"]:
            mirrored.append(MOVES["Left+Up"])
        elif move == MOVES["Left+Down"]:
            mirrored.append(MOVES["Right+Down"])
        elif move == MOVES["Right+Down"]:
            mirrored.append(MOVES["Left+Down"])
        else:
            mirrored.append(move)
    return mirrored


def create_move_dict(moves_list):
    return {"left": moves_list, "right": mirror_moves(moves_list)}


COMBOS = {
    "Alex": {
        "Power Bomb": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Spiral DDT": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
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
        "Air Stampede": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
        "Slash Elbow": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Chun-Li": {
        "Kikoken": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ]
        ),
        "Hazanshu": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Spinning Bird Kick": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
        "Hyakuretsu Kyaku": create_move_dict(
            [
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Dudley": {
        "Ducking": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
        "Jet Upper": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
        "Machine Gun Blow": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ]
        ),
        "Cross Counter": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Short Swing Blow": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
    },
    "Elena": {
        "Rhino Horn": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Kick"],
            ]
        ),
        "Mallet Smash": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Shakunetsu-Hadouken": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Ashura Senku": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Low Punch+Low Kick"],
            ]
        ),
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
        "Moonsault Press": create_move_dict(
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
                MOVES["Medium Punch"],
            ]
        ),
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
        "Raida": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Kubi Ori": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Karakusa": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
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
        "Snake Fang": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
        "Denji Blast": create_move_dict(
            [
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Tornado Hook": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ]
        ),
    },
    "Oro": {
        "Niou Riki": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Nichirin Shou": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Oni Yanma": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Capture & Deadly Blow": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Dashing Straight": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Dashing Head Attack": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["High Punch"],
            ]
        ),
        "Dashing Leg Attack": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
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
        "Light of Virtue": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Medium Punch"],
            ]
        ),
        "Light of Virtue (low)": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Rising Rage Flash": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
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
        "Joudan Sokutou Geri": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
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
        "Sean Tackle": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Chariot Tackle": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Violence Knee Drop": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Low Kick"],
            ]
        ),
        "Dangerous Headbutt": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Up"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Fake Byakko Soushouda": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ]
        ),
        "Zenpou Tenshin": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
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
        "Zenpou Tenshin": create_move_dict(
            [
                MOVES["Right"],
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Kick"],
            ]
        ),
        "Kobokushi": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "Fake Kobokushi": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Punch+Low Kick"],
            ]
        ),
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
        "1 Hyper Bomb": create_move_dict(
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
                MOVES["Medium Punch"],
            ]
        ),
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
        "1 Messatsu Gou Hadou": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "2 Messatsu Gou Shoryu": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
        "3 Messatsu-Gourasen": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Down"],
                MOVES["Right+Down"],
                MOVES["Right"],
                MOVES["Low Kick"],
            ]
        ),
        "Max Shungokusatsu (2 bars)": create_move_dict(
            [
                MOVES["Low Punch"],
                MOVES["Low Punch"],
                MOVES["Right"],
                MOVES["Low Kick"],
                MOVES["High Punch"],
            ]
        ),
        "Max Kongou Kokuretsuzan (2 bars)": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Down"],
                MOVES["Low Punch+Low Kick"],
            ]
        ),
    },
    "Hugo": {
        "1 Gigas Breaker": create_move_dict(
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
                MOVES["Right+Down"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Left+Up"],
                MOVES["Up"],
                MOVES["Right+Up"],
                MOVES["Right"],
                MOVES["Medium Punch"],
            ]
        ),
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
        "Max-1 EX Kishin Riki": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ]
        ),
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
        "Max-2 EX Yagyou Dama (3 bars)": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ]
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
        "Max-3 EX Tengu Stone": create_move_dict(
            [
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Down"],
                MOVES["Left+Down"],
                MOVES["Left"],
                MOVES["Low Punch+Low Kick"],
            ]
        ),
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

BASE_META_INSTRUCTIONS = {
    "Move Closer": create_move_dict([MOVES["Left"]] * 4),
    "Move Away": create_move_dict([MOVES["Right"]] * 4),
    "Jump Closer": create_move_dict([MOVES["Left+Up"]] * 4),
    "Jump Away": create_move_dict([MOVES["Right+Up"]] * 4),
    **{
        move_name: create_move_dict([move_nb])
        for move_name, move_nb in MOVES.items()
        if "Punch" in move_name or "Kick" in move_name
    },
}

# instructions


def get_available_instructions_for_character(
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
            if class_id == -1:
                continue
            if class_id == player1_char_id and i < len(game_info.boxes):
                player1_box = game_info.boxes[i]
            elif class_id == player2_char_id and i < len(game_info.boxes):
                player2_box = game_info.boxes[i]
    else:  # characters are the same
        valid_boxes = [
            (i, box)
            for i, (class_id, box) in enumerate(
                zip(game_info.class_ids, game_info.boxes)
            )
            if class_id != -1
        ]
        if len(valid_boxes) == 2:  # two characters detected
            (i0, box0), (i1, box1) = valid_boxes
            x_center_0 = (box0[0] + box0[2]) / 2
            x_center_1 = (box1[0] + box1[2]) / 2

            if player1.side == 0:
                if x_center_0 < x_center_1:
                    player1_box = box0
                    player2_box = box1
                else:
                    player1_box = box1
                    player2_box = box0
            else:
                if x_center_0 > x_center_1:
                    player1_box = box0
                    player2_box = box1
                else:
                    player1_box = box1
                    player2_box = box0
        elif len(valid_boxes) == 1:  # only one character detected
            _, box = valid_boxes[0]
            x_center = (box[0] + box[2]) / 2
            x_mid = X_SIZE / 2

            if player1.side == 0:
                if x_center < x_mid:
                    player1_box = box
                else:
                    player2_box = box
            else:
                if x_center > x_mid:
                    player1_box = box
                else:
                    player2_box = box

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

    # moves
    moves_prompt = "You can use the following moves:\n"
    moves_prompt += chr(10).join(
        "- " + move
        for move in get_available_instructions_for_character(
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
                {moves_prompt}

                Simply respond with just the name of the best move, no other text.
                """
            ),
        },
        {"role": "user", "content": "Your next move is:"},
    ]


def calculate_super_count(super_bar: int) -> int:
    if super_bar == SUPER_BAR_MAX:
        return 3
    elif super_bar >= (SUPER_BAR_MAX // 3) * 2:
        return 2
    elif super_bar >= SUPER_BAR_MAX // 3:
        return 1
    else:
        return 0


def create_random_messages():  # for warmup, testing
    import random

    n_detected_characters = random.randint(1, 2)

    player1_character = random.choice(list(CHARACTER_MAPPING.values()))
    player2_character = random.choice(list(CHARACTER_MAPPING.values()))

    player1_super_art = random.randint(1, 3)
    player2_super_art = random.randint(1, 3)

    side = random.randint(0, 1)

    player1_stun_bar = random.randint(0, STUN_BAR_MAX)
    player2_stun_bar = random.randint(0, STUN_BAR_MAX)

    player1_super_bar = random.randint(0, SUPER_BAR_MAX)
    player2_super_bar = random.randint(0, SUPER_BAR_MAX)

    player1_super_count = calculate_super_count(player1_super_bar)
    player2_super_count = calculate_super_count(player2_super_bar)

    game_info = GameInfo(
        stage=random.randint(1, 3),
        timer=random.randint(0, 100),
        boxes=[
            [
                random.randint(0, X_SIZE),
                random.randint(0, Y_SIZE),
                random.randint(0, X_SIZE),
                random.randint(0, Y_SIZE),
            ]
            for _ in range(n_detected_characters)
        ],
        class_ids=[
            CHARACTER_TO_ID[player1_character],
            CHARACTER_TO_ID[player2_character],
        ][:n_detected_characters],
    )

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

    return (
        create_messages(game_info, player1, player2),
        player2_character,
        player2_super_art,
        player2_super_count,
        side,
    )


def parse_move(character: str, move_name: str, side: int) -> list[int] | None:
    current_direction = "left" if side == 0 else "right"

    if move_name in BASE_META_INSTRUCTIONS:
        return BASE_META_INSTRUCTIONS[move_name][current_direction]
    elif move_name in COMBOS[character]:
        return COMBOS[character][move_name][current_direction]
    elif move_name in SPECIAL_MOVES[character]:
        return SPECIAL_MOVES[character][move_name][current_direction]
    return None
