import { byId, $$ } from "./utils.js";
import { AudioManager } from "./audioManager.js";
import { SOUND_KEYS } from "./constants.js";

export const GamepadManager = {
  connected: false,
  index: null,
  animationFrame: null,
  state: {
    axes: { left: { x: 0, y: 0 }, right: { x: 0, y: 0 } },
    buttons: {},
  },
  deadzone: 0.15,
  gameplayThreshold: 0.25,
  uiThreshold: 0.7,
  buttonMapping: {
    0: "LP",
    1: "MP",
    2: "LK",
    3: "MK",
    4: "HK",
    5: "HP",
    6: null,
    7: null,
    8: null,
    9: null,
    10: null,
    11: null,
    12: "UP",
    13: "DOWN",
    14: "LEFT",
    15: "RIGHT",
  },

  uiActive: false,
  navState: {
    currentScreen: null,
    currentSection: 0,
    currentElement: 0,
    sections: [],
    lastInput: { x: 0, y: 0, button: null },
    inputCooldown: 200,
    lastInputTime: 0,
    holdStartTime: 0,
    holdThreshold: 500,
    fastRepeatRate: 60,
  },

  onStatusChange: null,
  onInput: null,
  onUIAction: null,

  init(callbacks = {}) {
    this.onStatusChange = callbacks.onStatusChange || (() => {});
    this.onInput = callbacks.onInput || (() => {});
    this.onUIAction = callbacks.onUIAction || (() => {});

    window.addEventListener("gamepadconnected", (e) => this.handleConnect(e));
    window.addEventListener("gamepaddisconnected", (e) =>
      this.handleDisconnect(e)
    );
  },

  handleConnect(e) {
    console.log(
      `Gamepad connected at index ${e.gamepad.index}: ${e.gamepad.id}`
    );
    this.connected = true;
    this.index = e.gamepad.index;

    const gamepadStatus = byId("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.remove("bg-sf-darker", "border-sf-gold-dark");
      gamepadStatus.classList.add("bg-sf-dark", "border-sf-green");
      gamepadStatus.title = `Gamepad Connected: ${e.gamepad.id}`;
    }

    const splashText = byId("splash-skip-text");
    if (splashText) {
      splashText.textContent = "Press A to skip";
    }

    document.body.classList.add("gamepad-connected");

    AudioManager.playSound(SOUND_KEYS.GAMEPAD_CONNECT);
    this.onStatusChange(true);
    this.startPolling();

    // dispatch custom event for mobile requirements check
    window.dispatchEvent(
      new CustomEvent("gamepadStatusChange", {
        detail: { connected: true },
      })
    );
  },

  handleDisconnect(e) {
    if (e.gamepad.index !== this.index) return;

    console.log(
      `Gamepad disconnected from index ${e.gamepad.index}: ${e.gamepad.id}`
    );
    this.connected = false;
    this.index = null;

    const gamepadStatus = byId("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.remove("bg-sf-dark", "border-sf-green");
      gamepadStatus.classList.add("bg-sf-darker", "border-sf-gold-dark");
      gamepadStatus.title = "No Gamepad Connected";
    }

    const splashText = byId("splash-skip-text");
    if (splashText) {
      splashText.textContent = "Click anywhere to skip";
    }

    $$(".gamepad-hover").forEach((el) => {
      el.classList.remove("gamepad-hover");
    });

    document.body.classList.remove("gamepad-connected");

    AudioManager.playSound(SOUND_KEYS.GAMEPAD_DISCONNECT);
    this.onStatusChange(false);
    this.stopPolling();

    window.dispatchEvent(
      new CustomEvent("gamepadStatusChange", {
        detail: { connected: false },
      })
    );
  },

  startPolling() {
    if (!this.connected) return;

    const gamepads = navigator.getGamepads();
    const gamepad = gamepads[this.index];

    if (!gamepad) {
      this.animationFrame = requestAnimationFrame(() => this.startPolling());
      return;
    }

    const currentState = this.readState(gamepad);

    if (this.uiActive) {
      this.processUIInput(currentState);
    } else {
      this.onInput(currentState);
    }

    this.animationFrame = requestAnimationFrame(() => this.startPolling());
  },

  stopPolling() {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
  },

  readState(gamepad) {
    const state = {
      axes: {
        left: {
          x: this.applyDeadzone(gamepad.axes[0]),
          y: this.applyDeadzone(gamepad.axes[1]),
        },
        right: {
          x: this.applyDeadzone(gamepad.axes[2]),
          y: this.applyDeadzone(gamepad.axes[3]),
        },
      },
      buttons: {},
    };

    gamepad.buttons.forEach((button, index) => {
      state.buttons[index] = button.pressed;
    });

    return state;
  },

  applyDeadzone(value) {
    if (Math.abs(value) < this.deadzone) {
      return 0;
    }
    return value;
  },

  processUIInput(currentState) {
    const currentTime = Date.now();

    const directions = {
      left:
        currentState.axes.left.x < -this.uiThreshold ||
        currentState.buttons[14],
      right:
        currentState.axes.left.x > this.uiThreshold || currentState.buttons[15],
      up:
        currentState.axes.left.y < -this.uiThreshold ||
        currentState.buttons[12],
      down:
        currentState.axes.left.y > this.uiThreshold || currentState.buttons[13],
    };

    const buttons = {
      a: currentState.buttons[0],
      b: currentState.buttons[1],
      lb: currentState.buttons[4],
      rb: currentState.buttons[5],
    };

    let inputX = 0,
      inputY = 0;
    if (directions.left) inputX = -1;
    else if (directions.right) inputX = 1;
    if (directions.up) inputY = -1;
    else if (directions.down) inputY = 1;

    const hasInput =
      inputX !== 0 ||
      inputY !== 0 ||
      buttons.a ||
      buttons.b ||
      buttons.lb ||
      buttons.rb;
    const inputChanged =
      inputX !== this.navState.lastInput.x ||
      inputY !== this.navState.lastInput.y ||
      buttons.a !== this.navState.lastInput.a ||
      buttons.b !== this.navState.lastInput.b ||
      buttons.lb !== this.navState.lastInput.lb ||
      buttons.rb !== this.navState.lastInput.rb;

    if (inputChanged) {
      if (hasInput) {
        this.navState.holdStartTime = currentTime;
        this.onUIAction(inputX, inputY, buttons);
        this.navState.lastInputTime = currentTime;
      } else {
        this.navState.holdStartTime = 0;
      }
    } else if (hasInput && (inputX !== 0 || inputY !== 0)) {
      const holdDuration = currentTime - this.navState.holdStartTime;
      const cooldown =
        holdDuration > this.navState.holdThreshold
          ? this.navState.fastRepeatRate
          : this.navState.inputCooldown;

      if (currentTime - this.navState.lastInputTime >= cooldown) {
        this.onUIAction(inputX, inputY, buttons);
        this.navState.lastInputTime = currentTime;
      }
    }

    this.navState.lastInput = { x: inputX, y: inputY, ...buttons };
  },

  setUIActive(active) {
    this.uiActive = active;
  },

  getMapping() {
    return this.buttonMapping;
  },

  isConnected() {
    return this.connected;
  },
};
