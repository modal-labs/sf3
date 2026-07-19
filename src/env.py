from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from src.utils import STUN_BAR_MAX, SUPER_BAR_MAX, TIMER_MAX

_ROM_FILENAME = "sfiii3n.zip"
_ROM_SHA256 = "7239b5eb005488db22ace477501c574e9420c0ab70aeeb0795dfeb474284d416"
_CPU_CHARACTER_MENU = 2
_CPU_OPPONENT_MENUS = {3, 9}
_CPU_OPPONENT_CONFIRM_DELAY = 30
_CPU_OPPONENT_CONFIRM_INTERVAL = 30

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


def arcade_level(difficulty: int) -> int:
    """Map public difficulties 1..8 to arcade menu levels 0..7."""
    return max(0, min(7, int(difficulty) - 1))


def _menu_steps(
    frame_ratio: int,
    entries: Sequence[tuple[int, tuple[Any, ...]]],
) -> list[dict[str, Any]]:
    return [
        {"wait": int(wait / frame_ratio), "actions": list(actions)}
        for wait, actions in entries
    ]


def _boot_steps(frame_ratio: int, *, vs_cpu: bool = False):
    # MAME is container-only; local imports must not load its native wheel.
    from MAMEToolkit.sf_environment.Actions import Actions

    coin = (Actions.COIN_P1,) if vs_cpu else (Actions.COIN_P1, Actions.COIN_P2)
    start = (Actions.P1_START,) if vs_cpu else (Actions.P1_START, Actions.P2_START)
    return _menu_steps(
        frame_ratio,
        [
            (0, (Actions.SERVICE,)),
            (30, (Actions.P1_UP,)),
            (30, (Actions.P1_JPUNCH,)),
            (300, coin),
            (10, coin),
            (60, start),
        ],
    )


def _cpu_difficulty_steps(frame_ratio: int, difficulty: int):
    from MAMEToolkit.sf_environment.Actions import Actions

    up = Actions.P1_UP
    down = Actions.P1_DOWN
    jab = Actions.P1_JPUNCH
    entries = [
        (0, (Actions.SERVICE,)),
        *([(10, (up,))] * 4),
        (10, (jab,)),
        (10, (down,)),
        (10, (down,)),
        (10, (jab, Actions.P1_FPUNCH)),
        (10, (up,)),
        (10, (jab,)),
    ]
    level = arcade_level(difficulty)
    direction = Actions.P1_LEFT if level < 3 else Actions.P1_RIGHT
    entries.extend((10, (direction,)) for _ in range(abs(level - 3)))
    tail = [down] * 6 + [jab, down, jab, down, down, jab, down, down, down, jab]
    entries.extend((10, (action,)) for action in tail)
    return _menu_steps(frame_ratio, entries)


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
    vs_cpu: bool = False
    cpu_difficulty: int = 8

    def resolved_env_id(self) -> str:
        return self.env_id or f"sf3-{uuid.uuid4().hex[:8]}"


@dataclass
class _CpuMenuAdvanceState:
    pending_p1_states: set[int]
    opponent_menu_frames: int = 0


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
            "menuState": Address("0x0201546B", "u8"),
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
        self._cpu_character_lock_installed = False

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
        pressed = _action_values(1, actions.get("agent_0", 0))
        if not self.config.vs_cpu:
            pressed = pressed + _action_values(2, actions.get("agent_1", 0))
        raw = self._sub_step(pressed)
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

    def _register_cpu_character_lock(self) -> None:
        if self._cpu_character_lock_installed:
            return
        address = self.memory_addresses["characterP2"].address
        character = CHARACTER_NAME_TO_LOCAL_ID[self.config.characters[1]]
        # Story mode assigns its route opponent during the frame after pre-step writes.
        # Install after boot/difficulty inputs so the service menu is untouched.
        self.emu.console.writeln(
            "function lockConfiguredCpuCharacter() "
            f"mem:write_u8({address}, {character}) "
            "end"
        )
        self.emu.console.writeln(
            'emu.register_frame(lockConfiguredCpuCharacter, "configured-cpu-character")'
        )
        self._cpu_character_lock_installed = True

    def _lock_matchup_characters(self) -> None:
        for player, character in enumerate(self.config.characters, start=1):
            self._write_u8(
                f"characterP{player}",
                CHARACTER_NAME_TO_LOCAL_ID[character],
            )

    def _advance_cpu_menus(
        self,
        state: _CpuMenuAdvanceState,
        *,
        p1_char: int,
        p2_char: int,
        p1_jab: int,
    ) -> list[int]:
        pressed: list[int] = []
        menu_state = int(self._data["menuState"])
        p1_state = int(self._data["characterSelectStateP1"])
        if menu_state == _CPU_CHARACTER_MENU and p1_state in state.pending_p1_states:
            pressed.append(p1_jab)
            state.pending_p1_states.remove(p1_state)
        if menu_state in _CPU_OPPONENT_MENUS:
            state.opponent_menu_frames += 1
        else:
            state.opponent_menu_frames = 0
        cpu_confirm_elapsed = state.opponent_menu_frames - _CPU_OPPONENT_CONFIRM_DELAY
        if (
            cpu_confirm_elapsed >= 0
            and cpu_confirm_elapsed % _CPU_OPPONENT_CONFIRM_INTERVAL == 0
        ):
            self._write_u8("characterP1", p1_char)
            self._write_u8("characterP2", p2_char)
            self._write_u8(
                "characterSelectColorP2",
                max(0, self.config.outfits[1] - 1),
            )
            pressed.append(p1_jab)
        return pressed

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

        players = ("P1",) if self.config.vs_cpu else ("P1", "P2")
        start_actions = [Actions.P1_START.value]
        if not self.config.vs_cpu:
            start_actions.append(Actions.P2_START.value)
        for _ in range(240):
            self._data = self.emu.step([])
            states = [
                int(self._data[f"characterSelectState{player}"]) for player in players
            ]
            if all(state >= 2 for state in states):
                return
            if any(state == 0 for state in states):
                self._data = self.emu.step(start_actions)
        mode = "1-player" if self.config.vs_cpu else "2-player"
        raise TimeoutError(f"Timed out waiting for {mode} character select")

    def _select_characters(self) -> None:
        from MAMEToolkit.sf_environment.Actions import Actions

        players = [
            (
                f"P{index + 1}",
                CHARACTER_NAME_TO_LOCAL_ID[character],
                max(0, self.config.outfits[index] - 1),
                max(0, self.config.super_arts[index] - 1),
                (Actions.P1_JPUNCH if index == 0 else Actions.P2_JPUNCH).value,
            )
            for index, character in enumerate(self.config.characters)
            if index == 0 or not self.config.vs_cpu
        ]
        character_locked = {player: False for player, *_ in players}
        sa_locked = character_locked.copy()

        for _ in range(240):
            self._data = self.emu.step([])
            pressed = []
            states = {}
            for player, character, color, super_art, jab in players:
                state = int(self._data[f"characterSelectState{player}"])
                states[player] = state
                self._write_u8(f"character{player}", character)
                self._write_u8(f"characterSelectColor{player}", color)
                if state == 2 and not character_locked[player]:
                    pressed.append(jab)
                    character_locked[player] = True
                if state >= 3:
                    self._write_u8(f"characterSelectSa{player}", super_art)
                if state == 4 and not sa_locked[player]:
                    pressed.append(jab)
                    sa_locked[player] = True

            if pressed:
                self._data = self.emu.step(pressed)
                states = {
                    player: int(self._data[f"characterSelectState{player}"])
                    for player, *_ in players
                }
            if all(state == 5 for state in states.values()):
                self._lock_matchup_characters()
                return

        raise TimeoutError("Timed out locking characters/super arts")

    def _wait_for_fight_start(self) -> dict[str, Any]:
        p1_char = CHARACTER_NAME_TO_LOCAL_ID[self.config.characters[0]]
        p2_char = CHARACTER_NAME_TO_LOCAL_ID[self.config.characters[1]]
        cpu_menus = None
        p1_jab = 0
        if self.config.vs_cpu:
            from MAMEToolkit.sf_environment.Actions import Actions

            cpu_menus = _CpuMenuAdvanceState(pending_p1_states={2, 4})
            p1_jab = Actions.P1_JPUNCH.value
        for _ in range(900):
            self._lock_matchup_characters()
            pressed = (
                self._advance_cpu_menus(
                    cpu_menus,
                    p1_char=p1_char,
                    p2_char=p2_char,
                    p1_jab=p1_jab,
                )
                if cpu_menus is not None
                else []
            )
            self._data = self.emu.step(pressed)
            if int(self._data["fighting"]) != 0:
                break
        else:
            raise TimeoutError(
                "Timed out waiting for fight start "
                f"(p1_state={int(self._data['characterSelectStateP1'])}, "
                f"p2_state={int(self._data['characterSelectStateP2'])}, "
                f"menu={int(self._data['menuState'])}, "
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
        data = self._sub_step([])
        actual_p1 = int(data["characterP1"])
        actual_p2 = int(data["characterP2"])
        if actual_p1 != p1_char or actual_p2 != p2_char:
            raise RuntimeError(
                "fight started with unexpected matchup "
                f"(p1={actual_p1}, p2={actual_p2}; "
                f"expected p1={p1_char}, p2={p2_char})"
            )
        return data

    def _new_game(self) -> None:
        self._wait_for_boot_ready()
        if self.config.vs_cpu:
            self._run_steps(
                _cpu_difficulty_steps(
                    self.config.step_ratio, self.config.cpu_difficulty
                )
            )
            self._run_steps(_boot_steps(self.config.step_ratio, vs_cpu=True))
            self._register_cpu_character_lock()
        else:
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
