from textwrap import dedent

minutes = 60

# credit to https://streetfighter.fandom.com/wiki/List_of_moves_in_Street_Fighter_III:_3rd_Strike

MOVES = {
    "No-Move": 0,
    "Left": 1,
    "Left+Up": 2,
    "Up+Left": 2,
    "Up": 3,
    "Up+Right": 4,
    "Right+Up": 4,
    "Right": 5,
    "Right+Down": 6,
    "Down+Right": 6,
    "Down": 7,
    "Down+Left": 8,
    "Left+Down": 8,
    "Low Punch": 9,
    "Medium Punch": 10,
    "High Punch": 11,
    "Low Kick": 12,
    "Low": 12,
    "Medium Kick": 13,
    "Medium": 13,
    "High Kick": 14,
    "Low Punch+Low Kick": 15,
    "Medium Punch+Medium Kick": 16,
    "High Punch+High Kick": 17,
}

COMBOS = {
    "Fireball (Hadouken)": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Punch"],
        ],
    },
    "Dragon Punch (Shoryuken)": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
        ],
        "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["High Punch"]],
    },
    "Hurricane Kick (Tatsumaki Senpukyaku)": {
        "right": [MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["Low Kick"]],
        "left": [MOVES["Down"], MOVES["Down+Right"], MOVES["Right"], MOVES["Low Kick"]],
    },
    # Chun-Li moves
    "Spinning Bird Kick": {
        "right": [MOVES["Down"], MOVES["Up"], MOVES["Low Kick"]],
        "left": [MOVES["Down"], MOVES["Up"], MOVES["Low Kick"]],
    },
    "Kikoken": {
        "right": [
            MOVES["Left"],
            MOVES["Down+Left"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Right"],
            MOVES["Down+Right"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Punch"],
        ],
    },
    # Alex moves
    "Flash Chop": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Punch"],
        ],
    },
    "Power Bomb": {
        "right": [
            MOVES["Left"],
            MOVES["Down+Left"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Right"],
            MOVES["Down+Right"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["High Punch"],
        ],
    },
    # Makoto moves
    "Hayate": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["High Punch"],
        ],
        "left": [MOVES["Down"], MOVES["Down+Left"], MOVES["Left"], MOVES["High Punch"]],
    },
    "Fukiage": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Medium Punch"],
        ],
    },
    # Elena moves
    "Rhino Horn": {
        "right": [
            MOVES["Left"],
            MOVES["Down+Left"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Kick"],
        ],
        "left": [
            MOVES["Right"],
            MOVES["Down+Right"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Kick"],
        ],
    },
    "Scratch Wheel": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Kick"],
        ],
        "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["High Kick"]],
    },
    # Dudley moves
    "Machine Gun Blow": {
        "right": [
            MOVES["Left"],
            MOVES["Down+Left"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Low Punch"],
        ],
        "left": [
            MOVES["Right"],
            MOVES["Down+Right"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Low Punch"],
        ],
    },
    "Jet Upper": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Low Punch"],
        ],
        "left": [MOVES["Left"], MOVES["Down"], MOVES["Down+Left"], MOVES["Low Punch"]],
    },
}

SPECIAL_MOVES = {
    "EX-Fireball (Hadouken)": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Punch"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Punch"],
            MOVES["Medium Punch"],
        ],
    },
    "EX-Dragon Punch (Shoryuken)": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["High Punch"],
            MOVES["High Punch"],
        ],
    },
    "Super Dragon Punch (Shouryuu-Reppa)": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["High Punch"],
        ],
    },
    "Shippuu-Jinrai-Kyaku": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["High Punch"],
            MOVES["Low Kick"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["High Punch"],
            MOVES["Low Kick"],
        ],
    },
    # Chun-Li Super Arts
    "Houyoku Sen": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Kick"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Kick"],
        ],
    },
    # Yun Super Art
    "Genei Jin": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Punch"],
        ],
    },
    # Alex Super Arts
    "Hyper Bomb": {
        "right": [
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Up"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Up"],
            MOVES["High Punch"],
        ],
    },
    "Boomerang Raid": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Low Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Low Punch"],
        ],
    },
    # Makoto Super Arts
    "Seichusen Godanzuki": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Low Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Low Punch"],
        ],
    },
    # Dudley Super Arts
    "Corkscrew Blow": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["High Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["High Punch"],
        ],
    },
    # Urien Super Art
    "Aegis Reflector": {
        "right": [
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Down"],
            MOVES["Down+Right"],
            MOVES["Right"],
            MOVES["Medium Punch"],
        ],
        "left": [
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Down"],
            MOVES["Down+Left"],
            MOVES["Left"],
            MOVES["Medium Punch"],
        ],
    },
}

META_INSTRUCTIONS = {
    "Move Closer": {
        "right": [MOVES["Right"], MOVES["Right"], MOVES["Right"], MOVES["Right"]],
        "left": [MOVES["Left"], MOVES["Left"], MOVES["Left"], MOVES["Left"]],
    },
    "Move Away": {
        "right": [MOVES["Left"], MOVES["Left"], MOVES["Left"], MOVES["Left"]],
        "left": [MOVES["Right"], MOVES["Right"], MOVES["Right"], MOVES["Right"]],
    },
    # Basic combos (Ken/Ryu/Akuma)
    "Fireball": COMBOS["Fireball (Hadouken)"],
    "Megapunch": COMBOS["Dragon Punch (Shoryuken)"],
    "Hurricane": COMBOS["Hurricane Kick (Tatsumaki Senpukyaku)"],
    # Chun-Li combos
    "Spinning Bird": COMBOS["Spinning Bird Kick"],
    "Kikoken": COMBOS["Kikoken"],
    # Alex combos
    "Flash Chop": COMBOS["Flash Chop"],
    "Power Bomb": COMBOS["Power Bomb"],
    # Makoto combos
    "Hayate": COMBOS["Hayate"],
    "Fukiage": COMBOS["Fukiage"],
    # Elena combos
    "Rhino Horn": COMBOS["Rhino Horn"],
    "Scratch Wheel": COMBOS["Scratch Wheel"],
    # Dudley combos
    "Machine Gun": COMBOS["Machine Gun Blow"],
    "Jet Upper": COMBOS["Jet Upper"],
    # Super/Special moves
    "Megafireball": SPECIAL_MOVES["EX-Fireball (Hadouken)"],
    "Super attack 2": SPECIAL_MOVES["EX-Dragon Punch (Shoryuken)"],
    "Super attack 3": SPECIAL_MOVES["Super Dragon Punch (Shouryuu-Reppa)"],
    "Super attack 4": SPECIAL_MOVES["Shippuu-Jinrai-Kyaku"],
    "Houyoku Sen": SPECIAL_MOVES["Houyoku Sen"],
    "Genei Jin": SPECIAL_MOVES["Genei Jin"],
    "Hyper Bomb": SPECIAL_MOVES["Hyper Bomb"],
    "Boomerang Raid": SPECIAL_MOVES["Boomerang Raid"],
    "Seichusen": SPECIAL_MOVES["Seichusen Godanzuki"],
    "Corkscrew": SPECIAL_MOVES["Corkscrew Blow"],
    "Aegis": SPECIAL_MOVES["Aegis Reflector"],
    **{
        move_name: {"right": [move_nb], "left": [move_nb]}
        for move_name, move_nb in MOVES.items()
        if "Punch" in move_name or "Kick" in move_name
    },
    "Jump Closer": {
        "right": [
            MOVES["Up+Right"],
            MOVES["Up+Right"],
            MOVES["Up+Right"],
            MOVES["Up+Right"],
        ],
        "left": [
            MOVES["Up+Left"],
            MOVES["Up+Left"],
            MOVES["Up+Left"],
            MOVES["Up+Left"],
        ],
    },
    "Jump Away": {
        "right": [
            MOVES["Up+Left"],
            MOVES["Up+Left"],
            MOVES["Up+Left"],
            MOVES["Up+Left"],
        ],
        "left": [
            MOVES["Up+Right"],
            MOVES["Up+Right"],
            MOVES["Up+Right"],
            MOVES["Up+Right"],
        ],
    },
}

META_INSTRUCTIONS_WITH_LOWER = {
    **META_INSTRUCTIONS,
    **{key.lower(): value for key, value in META_INSTRUCTIONS.items()},
    # also add the combos for Lower, Medium and High
    "lower": {"right": [12], "left": [12]},
    "medium": {"right": [13], "left": [13]},
    "high": {"right": [14], "left": [14]},
}

INDEX_TO_MOVE = {v: k for k, v in MOVES.items()}

X_SIZE = 384
Y_SIZE = 224

CHARACTER_MAPPING = {
    0: "Alex",
    1: "Ryu",
    2: "Yun",
    3: "Dudley",
    4: "Necro",
    5: "Hugo",
    6: "Ibuki",
    7: "Elena",
    8: "Oro",
    9: "Yang",
    10: "Ken",
    11: "Sean",
    12: "Urien",
    13: "Gouki",
    14: "Chun-Li",
    15: "Makoto",
    16: "Q",
    17: "Twelve",
    18: "Remy",
}
CHARACTER_TO_ID = {v: k for k, v in CHARACTER_MAPPING.items()}


def create_messages(
    stage,
    own_wins,
    opp_wins,
    timer,
    own_character,
    opp_character,
    own_side,
    opp_side,
    # own_pos,
    # opp_pos,
    own_stunned,
    own_stun_bar,
    opp_stunned,
    opp_stun_bar,
    own_health,
    opp_health,
    own_super_count,
    own_super_bar,
    opp_super_count,
    opp_super_bar,
):
    # game info

    game_info_prompt = f"Stage: {stage}, Own wins: {own_wins}, Opp wins: {opp_wins}, Timer: {timer}, Your character: {own_character}, Opponent character: {opp_character}"

    # position

    position_prompt = ""
    if own_side == 0:
        position_prompt = "You are on the left side of the screen. "
    else:
        position_prompt = "You are on the right side of the screen. "
    if opp_side == 0:
        position_prompt += "Your opponent is on the left side of the screen."
    else:
        position_prompt += "Your opponent is on the right side of the screen."

    # TODO: uncomment once we have actual positions

    # position_prompt = ""
    # relative_position = [own_pos[0] - opp_pos[0], own_pos[1] - opp_pos[1]]
    # normalized_relative_position = [
    #     relative_position[0] / X_SIZE,
    #     relative_position[1] / Y_SIZE,
    # ]
    # if abs(normalized_relative_position[0]) > 0.1:
    #     position_prompt = (
    #         "You are very far from the opponent. Move closer to the opponent. "
    #     )
    #     if normalized_relative_position[0] < 0:
    #         position_prompt += "Your opponent is on the right."
    #     else:
    #         position_prompt += "Your opponent is on the left."
    # else:
    #     position_prompt = "You are close to the opponent. You should attack them."

    # stun

    stun_prompt = ""
    if own_stunned:
        stun_prompt = "You are stunned. You cannot move or attack."
    elif opp_stunned:
        stun_prompt = "Your opponent is stunned. You can attack them."
    else:
        stun_prompt = f"Your stun bar is at {own_stun_bar}. Your opponent's stun bar is at {opp_stun_bar}."

    # health

    health_prompt = (
        f"Your health is at {own_health}. Your opponent's health is at {opp_health}."
    )

    # power

    power_prompt = ""

    if own_super_count == 0:
        power_prompt = "You have no super moves available. "
    elif own_super_bar >= 30 and own_super_bar < 120 and own_super_count > 0:
        power_prompt = "You can now use a powerful move. "
    elif own_super_bar >= 120 or own_super_bar == 0:
        power_prompt = "You can now use a very powerful move. "

    if opp_super_count == 0:
        power_prompt += "Your opponent has no super moves available."
    elif opp_super_bar >= 30 and opp_super_bar < 120 and opp_super_count > 0:
        power_prompt += "Your opponent can now use a powerful move."
    elif opp_super_bar >= 120 or opp_super_bar == 0:
        power_prompt += "Your opponent can now use a very powerful move."

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

                The moves you can use are:
                {chr(10).join("- " + move for move in META_INSTRUCTIONS_WITH_LOWER.keys())}
                
                Respond simply with the best move.
                """
            ),
        },
        {"role": "user", "content": "Your next move is:"},
    ]
