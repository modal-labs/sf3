import { GameState } from "./gameState.js";
import { GamepadManager } from "./gamepadManager.js";
import { WebSocketManager } from "./webSocketManager.js";
import { MovesEngine } from "./movesEngine.js";

const createInputController = () => {
  const actions = {
    NO_MOVE: 0,
    LEFT: 1,
    LEFT_UP: 2,
    UP: 3,
    UP_RIGHT: 4,
    RIGHT: 5,
    RIGHT_DOWN: 6,
    DOWN: 7,
    DOWN_LEFT: 8,
    LOW_PUNCH: 9,
    MEDIUM_PUNCH: 10,
    HIGH_PUNCH: 11,
    LOW_KICK: 12,
    MEDIUM_KICK: 13,
    HIGH_KICK: 14,
    LOW_PUNCH_LOW_KICK: 15,
    MEDIUM_PUNCH_MEDIUM_KICK: 16,
    HIGH_PUNCH_HIGH_KICK: 17,
    SUPER_ART: 18,
    COMBO: 19,
  };

  const idxToMove = [
    { name: "No-Move", display: "", gamepadDisplay: "" },
    { name: "Left", display: "←", gamepadDisplay: "←" },
    { name: "Left+Up", display: "↖", gamepadDisplay: "↖" },
    { name: "Up", display: "↑", gamepadDisplay: "↑" },
    { name: "Up+Right", display: "↗", gamepadDisplay: "↗" },
    { name: "Right", display: "→", gamepadDisplay: "→" },
    { name: "Right+Down", display: "↘", gamepadDisplay: "↘" },
    { name: "Down", display: "↓", gamepadDisplay: "↓" },
    { name: "Down+Left", display: "↙", gamepadDisplay: "↙" },
    { name: "Low Punch", display: "J", gamepadDisplay: "A" },
    { name: "Medium Punch", display: "K", gamepadDisplay: "B" },
    { name: "High Punch", display: "L", gamepadDisplay: "RB" },
    { name: "Low Kick", display: "U", gamepadDisplay: "X" },
    { name: "Medium Kick", display: "I", gamepadDisplay: "Y" },
    { name: "High Kick", display: "O", gamepadDisplay: "LB" },
    { name: "Low Punch+Low Kick", display: "J + U", gamepadDisplay: "A + X" },
    {
      name: "Medium Punch+Medium Kick",
      display: "K + I",
      gamepadDisplay: "B + Y",
    },
    {
      name: "High Punch+High Kick",
      display: "L + O",
      gamepadDisplay: "RB + LB",
    },
  ];

  let movesByLength = {};
  let combos = {};
  let specialMoves = {};

  const comboTimeout = 750;

  const getActionFromKeys = () => {
    const keyState = GameState.getKeyState();

    const attacks = {
      LP: keyState["KeyJ"],
      MP: keyState["KeyK"],
      HP: keyState["KeyL"],
      LK: keyState["KeyU"],
      MK: keyState["KeyI"],
      HK: keyState["KeyO"],
    };

    if (attacks.LP && attacks.LK) return actions.LOW_PUNCH_LOW_KICK;
    if (attacks.MP && attacks.MK) return actions.MEDIUM_PUNCH_MEDIUM_KICK;
    if (attacks.HP && attacks.HK) return actions.HIGH_PUNCH_HIGH_KICK;

    if (attacks.HP) return actions.HIGH_PUNCH;
    if (attacks.MP) return actions.MEDIUM_PUNCH;
    if (attacks.LP) return actions.LOW_PUNCH;
    if (attacks.HK) return actions.HIGH_KICK;
    if (attacks.MK) return actions.MEDIUM_KICK;
    if (attacks.LK) return actions.LOW_KICK;

    const directions = {
      left: keyState["KeyA"] || keyState["ArrowLeft"],
      right: keyState["KeyD"] || keyState["ArrowRight"],
      up: keyState["KeyW"] || keyState["ArrowUp"],
      down: keyState["KeyS"] || keyState["ArrowDown"],
    };

    if (directions.left && directions.up) return actions.LEFT_UP;
    if (directions.right && directions.up) return actions.UP_RIGHT;
    if (directions.left && directions.down) return actions.DOWN_LEFT;
    if (directions.right && directions.down) return actions.RIGHT_DOWN;

    if (directions.left) return actions.LEFT;
    if (directions.right) return actions.RIGHT;
    if (directions.up) return actions.UP;
    if (directions.down) return actions.DOWN;

    return actions.NO_MOVE;
  };

  const processGamepadInput = (currentState) => {
    const threshold = GamepadManager.gameplayThreshold;

    const stickX = currentState.axes.left.x;
    const stickY = currentState.axes.left.y;

    const isDiagonal =
      Math.abs(stickX) > threshold && Math.abs(stickY) > threshold;

    const directions = {
      left: stickX < -threshold || currentState.buttons[14],
      right: stickX > threshold || currentState.buttons[15],
      up: stickY < -threshold || currentState.buttons[12],
      down: stickY > threshold || currentState.buttons[13],
    };

    const attacks = {
      LP: currentState.buttons[0],
      MP: currentState.buttons[1],
      LK: currentState.buttons[2],
      MK: currentState.buttons[3],
      HK: currentState.buttons[4],
      HP: currentState.buttons[5],
    };

    let action = actions.NO_MOVE;

    if (attacks.LP && attacks.LK) {
      action = actions.LOW_PUNCH_LOW_KICK;
    } else if (attacks.MP && attacks.MK) {
      action = actions.MEDIUM_PUNCH_MEDIUM_KICK;
    } else if (attacks.HP && attacks.HK) {
      action = actions.HIGH_PUNCH_HIGH_KICK;
    } else if (attacks.HP) {
      action = actions.HIGH_PUNCH;
    } else if (attacks.MP) {
      action = actions.MEDIUM_PUNCH;
    } else if (attacks.LP) {
      action = actions.LOW_PUNCH;
    } else if (attacks.HK) {
      action = actions.HIGH_KICK;
    } else if (attacks.MK) {
      action = actions.MEDIUM_KICK;
    } else if (attacks.LK) {
      action = actions.LOW_KICK;
    } else if (isDiagonal) {
      if (directions.left && directions.up) {
        action = actions.LEFT_UP;
      } else if (directions.right && directions.up) {
        action = actions.UP_RIGHT;
      } else if (directions.left && directions.down) {
        action = actions.DOWN_LEFT;
      } else if (directions.right && directions.down) {
        action = actions.RIGHT_DOWN;
      }
    } else if (directions.left) {
      action = actions.LEFT;
    } else if (directions.right) {
      action = actions.RIGHT;
    } else if (directions.up) {
      action = actions.UP;
    } else if (directions.down) {
      action = actions.DOWN;
    }

    handleActionFromInput(action);
  };

  const handleActionFromInput = (action) => {
    WebSocketManager.send("player_action", { action });

    if (action !== actions.NO_MOVE) {
      const input = { action, time: Date.now() };
      GameState.addInputToHistory(input);

      const inputHistory = GameState.getInputHistory();
      const { match, history } = MovesEngine.detectExtra(
        inputHistory,
        comboTimeout,
        movesByLength
      );

      GameState.clearInputHistory();
      history.forEach((h) => GameState.addInputToHistory(h));

      if (match) {
        WebSocketManager.send("player_action", {
          action:
            match.type === "super_art" ? actions.SUPER_ART : actions.COMBO,
          [match.type === "super_art" ? "super_art" : "combo"]: match.name,
        });
      }
    }
  };

  const handleKeyboardEvent = (e, isDown) => {
    const state = GameState.get();
    if (!state.loaded || !state.humanVsLlm) return;

    GameState.setKeyState(e.code, isDown);
    const action = getActionFromKeys();
    handleActionFromInput(action);
    e.preventDefault();
  };

  const updateMovesList = (character, direction, superArt) => {
    movesByLength = MovesEngine.preprocessMoves(
      character,
      specialMoves,
      combos,
      direction,
      superArt
    );
  };

  const setExtraMoves = (extraCombos, extraSpecialMoves) => {
    combos = extraCombos;
    specialMoves = extraSpecialMoves;
  };

  const init = () => {
    document.addEventListener("keydown", (e) => handleKeyboardEvent(e, true));
    document.addEventListener("keyup", (e) => handleKeyboardEvent(e, false));
  };

  const initGamepadInput = () => {
    const originalOnInput = GamepadManager.onInput;
    GamepadManager.onInput = (state) => {
      const gameState = GameState.get();
      if (gameState.loaded && gameState.humanVsLlm) {
        processGamepadInput(state);
      } else if (originalOnInput) {
        originalOnInput(state);
      }
    };
  };

  return {
    actions,
    idxToMove,
    init,
    initGamepadInput,
    handleActionFromInput,
    processGamepadInput,
    updateMovesList,
    setExtraMoves,
    getCombos: () => combos,
    getSpecialMoves: () => specialMoves,
  };
};

export const InputController = createInputController();
