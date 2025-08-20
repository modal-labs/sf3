import random
from dataclasses import dataclass
from textwrap import dedent

# constants

# seed
seed = 42
random.seed(seed)

# modal
region = "us-east-1"
minutes = 60
gb = 1024

# sf3
X_SIZE = 384
Y_SIZE = 224
STUN_BAR_MAX = 72
SUPER_BAR_MAX = 128
HEALTH_MAX = 160

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


CLOSE_IN_MOVES = {
    "Move Closer": create_move_dict([MOVES["Right"]] * 4),
    "Jump Closer": create_move_dict([MOVES["Right+Up"]] * 4),
}

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

# instructions


BASE_META_INSTRUCTIONS = {
    "Move Away": create_move_dict([MOVES["Right"]] * 8),
    "Jump Away": create_move_dict([MOVES["Right+Up"]] * 4),
    **CLOSE_IN_MOVES,
    **{
        move_name: create_move_dict([move_nb])
        for move_name, move_nb in MOVES.items()
        if "Punch" in move_name or "Kick" in move_name
    },
}


def get_available_instructions_for_character(
    character: str,
    super_art: int,
    super_count: int,
    difficulty: str = "expert",
) -> list[str]:
    instructions = []
    instructions.extend(BASE_META_INSTRUCTIONS.keys())
    if difficulty in ["advanced", "expert"]:
        instructions.extend(COMBOS[character].keys())

    if difficulty == "expert" and super_count > 0:
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
    timer: int
    boxes: list
    class_ids: list


def assign_boxes(
    p1_char: str,
    p1_side: int,
    p2_char: str,
    boxes: list[list[int]],
    class_ids: list[int],
) -> tuple:
    p1_box = None
    p2_box = None

    p1_char_id = CHARACTER_TO_ID[p1_char]
    p2_char_id = CHARACTER_TO_ID[p2_char]

    if p1_char_id != p2_char_id:  # characters are different
        for i, class_id in enumerate(class_ids):
            if class_id == -1:
                continue
            if class_id == p1_char_id and i < len(boxes):
                p1_box = boxes[i]
            elif class_id == p2_char_id and i < len(boxes):
                p2_box = boxes[i]
    else:  # characters are the same
        valid_boxes = [
            (i, box)
            for i, (class_id, box) in enumerate(zip(class_ids, boxes))
            if class_id != -1
        ]
        if len(valid_boxes) == 2:  # two characters detected
            (i0, box0), (i1, box1) = valid_boxes
            x_center_0 = (box0[0] + box0[2]) / 2
            x_center_1 = (box1[0] + box1[2]) / 2

            if p1_side == 0:
                if x_center_0 < x_center_1:
                    p1_box = box0
                    p2_box = box1
                else:
                    p1_box = box1
                    p2_box = box0
            else:
                if x_center_0 > x_center_1:
                    p1_box = box0
                    p2_box = box1
                else:
                    p1_box = box1
                    p2_box = box0
        elif len(valid_boxes) == 1:  # only one character detected
            _, box = valid_boxes[0]
            x_center = (box[0] + box[2]) / 2
            x_mid = X_SIZE / 2

            if p1_side == 0:
                if x_center < x_mid:
                    p1_box = box
                else:
                    p2_box = box
            else:
                if x_center > x_mid:
                    p1_box = box
                else:
                    p2_box = box

    return p1_box, p2_box


def create_messages(
    game_info: GameInfo,
    player1: PlayerState,
    player2: PlayerState,
    prev_game_info=None,
    prev_player1=None,
    prev_player2=None,
    recent_moves=None,
    difficulty: str = "expert",
) -> tuple[list[dict[str, str]], list[str]]:
    past_info_available = (
        prev_game_info is not None
        and prev_player1 is not None
        and prev_player2 is not None
        and recent_moves is not None
    )

    # game info
    game_info_prompt = f"Timer: {game_info.timer}, your character: {player2.character}, opponent character: {player1.character}, best of 3: you've won {player2.wins} rounds, opponent has won {player1.wins} rounds"

    # position
    p1_box, p2_box = assign_boxes(
        player1.character,
        player1.side,
        player2.character,
        game_info.boxes,
        game_info.class_ids,
    )
    distance = None
    position_prompt = ""
    if p1_box is not None and p2_box is not None:
        p2_x_center = (p2_box[0] + p2_box[2]) / 2
        p1_x_center = (p1_box[0] + p1_box[2]) / 2
        dx = abs(p1_x_center - p2_x_center)
        distance = dx / float(X_SIZE)
    if distance is not None:
        if distance > 0.1:
            position_prompt = "You are far away from your opponent. Move closer."
        else:
            position_prompt = "You are close to your opponent. Attack!"
    if past_info_available:
        prev_p1_box, prev_p2_box = assign_boxes(
            prev_player1.character,
            prev_player1.side,
            prev_player2.character,
            prev_game_info.boxes,
            prev_game_info.class_ids,
        )

        if (
            prev_p2_box is not None
            and prev_p1_box is not None
            and p2_box is not None
            and p1_box is not None
        ):
            p2_prev_x = (prev_p2_box[0] + prev_p2_box[2]) / 2
            p2_curr_x = (p2_box[0] + p2_box[2]) / 2
            p2_movement = p2_curr_x - p2_prev_x

            p1_prev_x = (prev_p1_box[0] + prev_p1_box[2]) / 2
            p1_curr_x = (p1_box[0] + p1_box[2]) / 2
            p1_movement = p1_curr_x - p1_prev_x

            if p2_movement * p1_movement < 0:  # opposite directions
                if abs(p2_curr_x - p1_curr_x) < abs(p2_prev_x - p1_prev_x):
                    position_prompt += (
                        " You are closing distance. Keep going or attack!"
                    )
                else:
                    position_prompt += " Distance is increasing. Move closer."

    # stun
    stun_prompt = f"Your stun bar is at {player2.stun_bar / STUN_BAR_MAX * 100}% . Your opponent's stun bar is at {player1.stun_bar / STUN_BAR_MAX * 100}%."
    if player2.stunned:
        stun_prompt += " You are stunned."
    if player1.stunned:
        stun_prompt += " Your opponent is stunned."
    if past_info_available:
        p2_stun_change = player2.stun_bar - prev_player2.stun_bar
        p1_stun_change = player1.stun_bar - prev_player1.stun_bar
        if p2_stun_change > 0:
            stun_prompt += (
                f" Your stun bar increased by {p2_stun_change / STUN_BAR_MAX * 100}%."
            )
        if p1_stun_change > 0:
            stun_prompt += f" You inflicted {p1_stun_change / STUN_BAR_MAX * 100}% stun on your opponent."

    # health
    health_prompt = f"Your health is at {player2.health / HEALTH_MAX * 100}%. Your opponent's health is at {player1.health / HEALTH_MAX * 100}%."
    if past_info_available:
        p2_damage_taken = prev_player2.health - player2.health
        p1_damage_taken = prev_player1.health - player1.health
        if p2_damage_taken > 0:
            health_prompt += (
                f" You've taken {p2_damage_taken / HEALTH_MAX * 100}% damage."
            )
        if p1_damage_taken > 0:
            health_prompt += f" You inflicted {p1_damage_taken / HEALTH_MAX * 100}% damage on your opponent."

    # super bar
    power_prompt = f"Your super bar is at {player2.super_bar / SUPER_BAR_MAX * 100}%. Your opponent's super bar is at {player1.super_bar / SUPER_BAR_MAX * 100}%."
    if past_info_available:
        p2_super_change = player2.super_bar - prev_player2.super_bar
        p1_super_change = player1.super_bar - prev_player1.super_bar
        if p2_super_change > 0:
            power_prompt += f" Your super bar increased by {p2_super_change / SUPER_BAR_MAX * 100}%."
        if p1_super_change > 0:
            power_prompt += f" Opponent's super bar increased by {p1_super_change / SUPER_BAR_MAX * 100}%."

    # moves
    available_moves = get_available_instructions_for_character(
        player2.character, player2.super_art, player2.super_count, difficulty
    )
    if past_info_available:
        # encourage close-in moves to avoid spamming + distancing
        filtered_recent_moves = list(set(recent_moves) - set(CLOSE_IN_MOVES.keys()))
        available_moves = [m for m in available_moves if m not in filtered_recent_moves]
        if not available_moves:
            available_moves = list(CLOSE_IN_MOVES.keys())
    moves_prompt = "You may only use the following moves:\n"
    moves_prompt += chr(10).join("- " + move for move in available_moves)

    messages = [  # OpenAI chat format
        {
            "role": "system",
            "content": dedent(
                f"""
                You are the most aggressive Street Fighter III 3rd strike player in the world.

                {game_info_prompt}
                {position_prompt}
                {health_prompt}
                {stun_prompt}
                {power_prompt}
                {moves_prompt}

                Simply respond with just the entire name of the best move.
                """
            ),
        },
        {"role": "user", "content": "Your next move is:"},
    ]
    return messages, available_moves


def est_super_ct(super_bar: int) -> int:
    if super_bar == SUPER_BAR_MAX:
        return 3
    elif super_bar >= (SUPER_BAR_MAX // 3) * 2:
        return 2
    elif super_bar >= SUPER_BAR_MAX // 3:
        return 1
    else:
        return 0


def create_random_messages() -> tuple[
    list[dict[str, str]], str, int, int, int, list[str]
]:  # for warmup, testing
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

    player1_super_count = est_super_ct(player1_super_bar)
    player2_super_count = est_super_ct(player2_super_bar)

    game_info = GameInfo(
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

    random_difficulty = random.choice(["basic", "advanced", "expert"])

    messages, available_moves = create_messages(
        game_info, player1, player2, difficulty=random_difficulty
    )

    return (
        messages,
        player2_character,
        player2_super_art,
        player2_super_count,
        side,
        available_moves,
    )


# llm post-processing


def parse_move(character: str, move_name: str, side: int) -> list[int] | None:
    current_direction = "left" if side == 0 else "right"

    if move_name in BASE_META_INSTRUCTIONS:
        return BASE_META_INSTRUCTIONS[move_name][current_direction]
    elif move_name in COMBOS[character]:
        return COMBOS[character][move_name][current_direction]
    elif move_name in SPECIAL_MOVES[character]:
        return SPECIAL_MOVES[character][move_name][current_direction]
    return None
