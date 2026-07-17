from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.utils import STUN_BAR_MAX, SUPER_BAR_MAX, TIMER_MAX

_ROM_FILENAME = "sfiii3n.zip"
_ROM_SHA256 = "7239b5eb005488db22ace477501c574e9420c0ab70aeeb0795dfeb474284d416"

# Raw emulator ids used by MAME / sfiii-gym.
# Intentionally different than CHARACTER_TO_ID in utils.py
# since the emulator uses a different numbering scheme.
CHARACTER_NAME_TO_LOCAL_ID = {
    "Alex": 1,
    "Ryu": 2,
    "Yun": 3,
    "Dudley": 4,
    "Necro": 5,
    "Hugo": 6,
    "Ibuki": 7,
    "Elena": 8,
    "Oro": 9,
    "Yang": 10,
    "Ken": 11,
    "Sean": 12,
    "Urien": 13,
    "Gouki": 14,
    "Chun-Li": 16,
    "Makoto": 17,
    "Q": 18,
    "Twelve": 19,
    "Remy": 20,
}


def _scalar(value: Any) -> int:
    import numpy as np

    if isinstance(value, np.ndarray):
        return int(value.reshape(-1)[0])
    if isinstance(value, (list, tuple)):
        return int(value[0])
    return int(value)


def _array1(value: int, *, dtype: Any = None) -> Any:
    import numpy as np

    return np.array([value], dtype=dtype or np.int16)


def _normalize_player(
    raw: Mapping[str, Any],
    *,
    prefix: str,
    wins: int,
) -> dict[str, Any]:
    side = _scalar(raw[f"side{prefix}"])
    stun_timer = _scalar(raw[f"stunTimer{prefix}"])
    stun_bar = _scalar(raw[f"stunBar{prefix}"])
    super_bar = _scalar(raw[f"superGauge{prefix}"])
    super_count = _scalar(raw[f"superCount{prefix}"])
    health = _scalar(raw[f"health{prefix}"])

    return {
        "wins": _array1(wins),
        "side": side,
        "stunned": stun_timer > 0,
        "stun_bar": _array1(max(0, min(STUN_BAR_MAX, stun_bar))),
        "health": _array1(health),
        "super_count": _array1(max(0, super_count)),
        "super_bar": _array1(max(0, min(SUPER_BAR_MAX, super_bar))),
    }


def _normalize_local_observation(raw: Mapping[str, Any]) -> dict[str, Any]:
    timer = max(0, min(TIMER_MAX, _scalar(raw["timer"])))
    wins_p1 = _scalar(raw["winsP1"])
    wins_p2 = _scalar(raw["winsP2"])

    return {
        "frame": raw["frame"],
        "timer": _array1(timer),
        "P1": _normalize_player(raw, prefix="P1", wins=wins_p1),
        "P2": _normalize_player(raw, prefix="P2", wins=wins_p2),
    }


def _boot_steps(frame_ratio: int):
    from MAMEToolkit.sf_environment.Actions import Actions

    return [
        {"wait": 0, "actions": [Actions.SERVICE]},
        {"wait": int(30 / frame_ratio), "actions": [Actions.P1_UP]},
        {"wait": int(30 / frame_ratio), "actions": [Actions.P1_JPUNCH]},
        {"wait": int(300 / frame_ratio), "actions": [Actions.COIN_P1, Actions.COIN_P2]},
        {"wait": int(10 / frame_ratio), "actions": [Actions.COIN_P1, Actions.COIN_P2]},
        {
            "wait": int(60 / frame_ratio),
            "actions": [Actions.P1_START, Actions.P2_START],
        },
    ]


def _action_values(player: int, action_id: int):
    from MAMEToolkit.sf_environment.Actions import Actions

    prefix = f"P{player}"
    action_names = {
        0: (),
        1: ("LEFT",),
        2: ("LEFT", "UP"),
        3: ("UP",),
        4: ("UP", "RIGHT"),
        5: ("RIGHT",),
        6: ("RIGHT", "DOWN"),
        7: ("DOWN",),
        8: ("DOWN", "LEFT"),
        9: ("JPUNCH",),
        10: ("SPUNCH",),
        11: ("FPUNCH",),
        12: ("SKICK",),
        13: ("FKICK",),
        14: ("RKICK",),
        15: ("JPUNCH", "SKICK"),
        16: ("SPUNCH", "FKICK"),
        17: ("FPUNCH", "RKICK"),
    }.get(int(action_id), ())
    return [getattr(Actions, f"{prefix}_{name}").value for name in action_names]


@dataclass(frozen=True)
class EnvironmentConfig:
    characters: tuple[str, str]
    outfits: tuple[int, int]
    super_arts: tuple[int, int]
    step_ratio: int
    render_mode: str = "rgb_array"
    roms_path: str = "/root"
    env_id: str | None = None

    def resolved_env_id(self) -> str:
        return self.env_id or f"sf3-{uuid.uuid4().hex[:8]}"


class GameEnvironment(Protocol):
    def reset(self) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def step(
        self,
        actions: dict[str, int],
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]: ...

    def close(self) -> None: ...


class LocalSfiiiAdapter:
    """One-game emulator adapter. Create a new instance for each game."""

    def __init__(self, config: EnvironmentConfig):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp")

        rom_path = Path(config.roms_path) / _ROM_FILENAME
        if not rom_path.is_file():
            raise FileNotFoundError(f"Local SFIII runtime expected ROM at {rom_path}")

        actual_sha256 = hashlib.sha256(rom_path.read_bytes()).hexdigest()
        if actual_sha256 != _ROM_SHA256:
            raise ValueError(
                f"ROM '{_ROM_FILENAME}' failed SHA256 checksum verification. "
                f"Expected {_ROM_SHA256}, got {actual_sha256}"
            )

        from MAMEToolkit.emulator import Address, Emulator

        self.config = config
        self.memory_addresses = {
            "fighting": Address("0x02011389", "u8"),
            "winsP1": Address("0x02011383", "u8"),
            "winsP2": Address("0x02011385", "u8"),
            "timer": Address("0x02011377", "u8"),
            "healthP1": Address("0x02068D0A", "s16"),
            "healthP2": Address("0x020691A2", "s16"),
            "sideP1": Address("0x02016B8E", "u8"),
            "sideP2": Address("0x02068C76", "u8"),
            "superGaugeP1": Address("0x020695B5", "u8"),
            "superCountP1": Address("0x020695BF", "u8"),
            "superGaugeP2": Address("0x020695E1", "u8"),
            "superCountP2": Address("0x020695EB", "u8"),
            "stunTimerP1": Address("0x020695F9", "u8"),
            "stunBarP1": Address("0x020695FD", "u32"),
            "stunTimerP2": Address("0x0206960D", "u8"),
            "stunBarP2": Address("0x02069611", "u32"),
            "characterP1": Address("0x02011387", "u8"),
            "characterP2": Address("0x02011388", "u8"),
            "characterSelectStateP1": Address("0x0201553D", "u8"),
            "characterSelectStateP2": Address("0x02015545", "u8"),
            "characterSelectSaP1": Address("0x020154D3", "u8"),
            "characterSelectSaP2": Address("0x020154D5", "u8"),
            "characterSelectColorP1": Address("0x02015683", "u8"),
            "characterSelectColorP2": Address("0x02015684", "u8"),
        }

        self.emu = Emulator(
            config.resolved_env_id(),
            config.roms_path,
            "sfiii3n",
            self.memory_addresses,
            frame_ratio=config.step_ratio,
            render=config.render_mode == "human",
            throttle=False,
            frame_skip=0,
            sound=False,
            debug=False,
            binary_path=None,
        )
        self._data: dict[str, Any] = {}
        self.expected_health = {"P1": 0, "P2": 0}
        self.expected_wins = {"P1": 0, "P2": 0}
        self._reset_called = False
        self._closed = False

    def reset(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._closed:
            raise RuntimeError("Cannot reset a closed LocalSfiiiAdapter")
        if self._reset_called:
            raise RuntimeError(
                "LocalSfiiiAdapter supports one reset; create a new environment "
                "for each game"
            )
        self._reset_called = True
        self._new_game()
        return _normalize_local_observation(self._data), {}

    def step(
        self,
        actions: dict[str, int],
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        raw = self._sub_step(
            _action_values(1, actions.get("agent_0", 0))
            + _action_values(2, actions.get("agent_1", 0))
        )
        reward = float(raw["reward"])
        round_done = False
        game_done = False

        if int(raw["fighting"]) == 0:
            raw = self._run_till_victor(raw)
            reward = float(raw["reward"])
            round_done = True
            game_done = int(raw["winsP1"]) >= 2 or int(raw["winsP2"]) >= 2
            if not game_done:
                self._data = self._wait_for_fight_start()
                self._data["reward"] = reward
            else:
                self._data = raw
        else:
            self._data = raw

        observation = _normalize_local_observation(self._data)
        info = {
            "game_done": game_done,
            "round_done": round_done,
            "stage_done": False,
        }
        return observation, reward, game_done, False, info

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.emu.close()

    def _run_steps(self, steps: list[dict[str, Any]]) -> None:
        for step in steps:
            for _ in range(step["wait"]):
                self._data = self.emu.step([])
            actions = [action.value for action in step["actions"]]
            self._data = self.emu.step(actions)

    def _write_u8(self, address_name: str, value: int) -> None:
        address = self.memory_addresses[address_name].address
        self.emu.console.writeln(f"mem:write_u8({address}, {int(value)})")

    def _wait_for_boot_ready(self) -> None:
        stable_frames = 0
        for _ in range(240):
            self._data = self.emu.step([])
            if (
                int(self._data["characterSelectStateP1"]) == 0
                and int(self._data["characterSelectStateP2"]) == 0
            ):
                stable_frames += 1
                if stable_frames >= 5:
                    return
            else:
                stable_frames = 0
        # These bytes are not a reliable readiness signal before service inputs.
        # This bounded wait is only a warm-up; later transitions enforce readiness.
        return

    def _wait_for_character_select(self) -> None:
        from MAMEToolkit.sf_environment.Actions import Actions

        for _ in range(240):
            self._data = self.emu.step([])
            state_p1 = int(self._data["characterSelectStateP1"])
            state_p2 = int(self._data["characterSelectStateP2"])
            if state_p1 >= 2 and state_p2 >= 2:
                return
            if state_p1 == 0 or state_p2 == 0:
                self._data = self.emu.step([
                    Actions.P1_START.value,
                    Actions.P2_START.value,
                ])
        raise TimeoutError("Timed out waiting for 2-player character select")

    def _select_characters(self) -> None:
        from MAMEToolkit.sf_environment.Actions import Actions

        p1_char = CHARACTER_NAME_TO_LOCAL_ID[self.config.characters[0]]
        p2_char = CHARACTER_NAME_TO_LOCAL_ID[self.config.characters[1]]
        p1_color = max(0, self.config.outfits[0] - 1)
        p2_color = max(0, self.config.outfits[1] - 1)
        p1_sa = max(0, self.config.super_arts[0] - 1)
        p2_sa = max(0, self.config.super_arts[1] - 1)

        character_locked = {"P1": False, "P2": False}
        sa_locked = {"P1": False, "P2": False}

        for _ in range(240):
            self._data = self.emu.step([])
            state_p1 = int(self._data["characterSelectStateP1"])
            state_p2 = int(self._data["characterSelectStateP2"])

            self._write_u8("characterP1", p1_char)
            self._write_u8("characterP2", p2_char)
            self._write_u8("characterSelectColorP1", p1_color)
            self._write_u8("characterSelectColorP2", p2_color)

            pressed = []
            if state_p1 == 2 and not character_locked["P1"]:
                pressed.append(Actions.P1_JPUNCH.value)
                character_locked["P1"] = True
            if state_p2 == 2 and not character_locked["P2"]:
                pressed.append(Actions.P2_JPUNCH.value)
                character_locked["P2"] = True

            if state_p1 >= 3:
                self._write_u8("characterSelectSaP1", p1_sa)
            if state_p2 >= 3:
                self._write_u8("characterSelectSaP2", p2_sa)

            if state_p1 == 4 and not sa_locked["P1"]:
                pressed.append(Actions.P1_JPUNCH.value)
                sa_locked["P1"] = True
            if state_p2 == 4 and not sa_locked["P2"]:
                pressed.append(Actions.P2_JPUNCH.value)
                sa_locked["P2"] = True

            if pressed:
                self._data = self.emu.step(pressed)
                state_p1 = int(self._data["characterSelectStateP1"])
                state_p2 = int(self._data["characterSelectStateP2"])

            if state_p1 == 5 and state_p2 == 5:
                return

        raise TimeoutError("Timed out locking characters/super arts")

    def _wait_for_fight_start(self) -> dict[str, Any]:
        self._data = self.emu.step([])
        for _ in range(900):
            if int(self._data["fighting"]) != 0:
                break
            self._data = self.emu.step([])
        else:
            raise TimeoutError(
                "Timed out waiting for fight start "
                f"(p1_state={int(self._data['characterSelectStateP1'])}, "
                f"p2_state={int(self._data['characterSelectStateP2'])}, "
                f"fighting={int(self._data['fighting'])})"
            )

        self.expected_health = {
            "P1": int(self._data["healthP1"]),
            "P2": int(self._data["healthP2"]),
        }
        self.expected_wins = {
            "P1": int(self._data["winsP1"]),
            "P2": int(self._data["winsP2"]),
        }
        return self._sub_step([])

    def _new_game(self) -> None:
        self._wait_for_boot_ready()
        self._run_steps(_boot_steps(self.config.step_ratio))
        self._wait_for_character_select()
        self._select_characters()
        self.expected_health = {"P1": 0, "P2": 0}
        self.expected_wins = {"P1": 0, "P2": 0}
        self._data = self._wait_for_fight_start()

    def _sub_step(self, actions: list[Any]) -> dict[str, Any]:
        data = self.emu.step(actions)

        p1_diff = self.expected_health["P1"] - int(data["healthP1"])
        p2_diff = self.expected_health["P2"] - int(data["healthP2"])
        self.expected_health = {
            "P1": int(data["healthP1"]),
            "P2": int(data["healthP2"]),
        }

        data["stunBarP1"] = int(data["stunBarP1"]) >> 24
        data["stunBarP2"] = int(data["stunBarP2"]) >> 24
        data["reward"] = float(p2_diff - p1_diff)
        return data

    def _run_till_victor(self, data: dict[str, Any]) -> dict[str, Any]:
        total_reward = float(data["reward"])
        while self.expected_wins["P1"] == int(data["winsP1"]) and self.expected_wins[
            "P2"
        ] == int(data["winsP2"]):
            data = self._sub_step([])
            total_reward += float(data["reward"])
        self.expected_wins = {
            "P1": int(data["winsP1"]),
            "P2": int(data["winsP2"]),
        }
        data["reward"] = total_reward
        return data


def create_environment(config: EnvironmentConfig) -> GameEnvironment:
    return LocalSfiiiAdapter(config)
