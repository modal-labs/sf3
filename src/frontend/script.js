const AudioManager = {
  sounds: {},
  enabled: true,
  volume: 0.5,
  currentEffects: [],
  selectSound: null,
  transitionSound: null,
  winLoseSound: null,

  init() {
    this.enabled = localStorage.getItem("audioEnabled") !== "false";
    this.setupMuteButton();
  },

  async preloadSounds(soundFiles, gameplayMusicMap) {
    const promises = [];

    Object.entries(soundFiles).forEach(([, filename]) => {
      const asset = new Audio(`/sounds/${filename}.mp3`);
      asset.volume = this.volume;
      asset.preload = "auto";
      this.sounds[filename] = asset;
      promises.push(
        new Promise((resolve) => {
          asset.addEventListener("canplaythrough", resolve, { once: true });
          asset.addEventListener("error", resolve, { once: true });
        })
      );
    });

    Object.entries(gameplayMusicMap).forEach(([key, filename]) => {
      const asset = new Audio(`/sounds/gameplay/${filename}.mp3`);
      asset.volume = this.volume;
      asset.preload = "auto";
      this.sounds[key] = asset;
      promises.push(
        new Promise((resolve) => {
          asset.addEventListener("canplaythrough", resolve, { once: true });
          asset.addEventListener("error", resolve, { once: true });
        })
      );
    });

    await Promise.all(promises);
  },

  play(soundName, options = {}) {
    const {
      volume = 1,
      loop = false,
      trackAs = "effect",
      onEnd = null,
    } = options;

    const sound = this.sounds[soundName];
    if (!sound) {
      console.warn(`No sound found for: ${soundName}`);
      return;
    }

    if (trackAs === "select") this.stopTrack("select");
    else if (trackAs === "transition") this.stopTrack("transition");
    else if (trackAs === "winLose") this.stopTrack("winLose");

    sound.currentTime = 0;
    sound.loop = loop;
    sound.volume = this.enabled ? this.volume * volume : 0;

    if (trackAs === "select") {
      this.selectSound = sound;
    } else if (trackAs === "transition") {
      this.transitionSound = sound;
    } else if (trackAs === "winLose") {
      this.winLoseSound = sound;
    } else {
      sound._volumeMultiplier = volume;
      this.currentEffects.push(sound);
    }

    const onEndHandler = () => {
      if (trackAs === "effect") {
        const index = this.currentEffects.indexOf(sound);
        if (index > -1) this.currentEffects.splice(index, 1);
        delete sound._volumeMultiplier;
      } else if (trackAs === "winLose") {
        this.winLoseSound = null;
      }

      if (onEnd) onEnd();
      sound.removeEventListener("ended", onEndHandler);
    };

    if (trackAs === "effect" || trackAs === "winLose" || onEnd) {
      sound.addEventListener("ended", onEndHandler);
    }

    sound.play().catch(() => {
      if (trackAs === "effect") {
        const index = this.currentEffects.indexOf(sound);
        if (index > -1) this.currentEffects.splice(index, 1);
        delete sound._volumeMultiplier;
      } else if (trackAs === "winLose") {
        this.winLoseSound = null;
      }
      if (trackAs === "effect" || trackAs === "winLose" || onEnd) {
        sound.removeEventListener("ended", onEndHandler);
      }
    });
  },

  playSound(soundName) {
    this.play(soundName, { trackAs: "effect" });
  },

  stopTrack(trackType) {
    const trackMap = {
      select: "selectSound",
      winLose: "winLoseSound",
      transition: "transitionSound",
    };

    const soundProp = trackMap[trackType];
    const sound = this[soundProp];

    if (sound) {
      sound.pause();
      sound.currentTime = 0;
      sound.loop = false;
      this[soundProp] = null;
    }
  },

  stopAll() {
    this.stopTrack("select");
    this.stopTrack("winLose");
    this.stopTrack("transition");

    this.currentEffects.forEach((sound) => {
      sound.pause();
      sound.currentTime = 0;
    });
    this.currentEffects = [];
  },

  toggleMute() {
    this.enabled = !this.enabled;
    localStorage.setItem("audioEnabled", this.enabled);

    const muteIcon = document.getElementById("mute-icon");
    if (muteIcon) {
      muteIcon.src = this.enabled ? "/icons/unmute.svg" : "/icons/mute.svg";
    }

    if (this.selectSound) {
      this.selectSound.volume = this.enabled ? this.volume * 0.2 : 0;
    }

    if (this.transitionSound) {
      this.transitionSound.volume = this.enabled ? this.volume * 0.2 : 0;
    }

    if (this.winLoseSound) {
      this.winLoseSound.volume = this.enabled ? this.volume * 0.2 : 0;
    }

    this.currentEffects.forEach((sound) => {
      const multiplier = sound._volumeMultiplier || 1;
      sound.volume = this.enabled ? this.volume * multiplier : 0;
    });
  },

  setupMuteButton() {
    const muteButton = document.getElementById("mute-toggle");
    if (muteButton) {
      muteButton.addEventListener("click", () => {
        this.toggleMute();
        AudioManager.playSound("click");
      });

      muteButton.addEventListener("mouseenter", () => {
        AudioManager.playSound("hover");
      });

      const muteIcon = document.getElementById("mute-icon");
      if (muteIcon) {
        muteIcon.src = this.enabled ? "/icons/unmute.svg" : "/icons/mute.svg";
      }
    }
  },
};

const GamepadManager = {
  connected: false,
  index: null,
  animationFrame: null,
  state: {
    axes: { left: { x: 0, y: 0 }, right: { x: 0, y: 0 } },
    buttons: {},
  },
  deadzone: 0.2,
  buttonMapping: {
    0: "LP", // A/X button -> Light Punch
    1: "MP", // B/Circle button -> Medium Punch
    2: "LK", // X/Square button -> Light Kick
    3: "MK", // Y/Triangle button -> Medium Kick
    4: "HK", // Left Bumper -> Heavy Kick
    5: "HP", // Right Bumper -> Heavy Punch
    6: null, // Left Trigger
    7: null, // Right Trigger
    8: null, // Select/Back
    9: null, // Start
    10: null, // Left Stick Click
    11: null, // Right Stick Click
    12: "UP", // D-Pad Up
    13: "DOWN", // D-Pad Down
    14: "LEFT", // D-Pad Left
    15: "RIGHT", // D-Pad Right
  },

  // ui nav state
  uiActive: false,
  uiState: {
    currentScreen: null,
    currentSection: 0,
    currentElement: 0,
    sections: [],
    lastInput: { x: 0, y: 0, button: null },
    inputCooldown: 100,
    lastInputTime: 0,
  },

  // callbacks
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

    const gamepadStatus = document.getElementById("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.remove("bg-sf-darker", "border-sf-gold-dark");
      gamepadStatus.classList.add("bg-sf-dark", "border-sf-green");
      gamepadStatus.title = `Gamepad Connected: ${e.gamepad.id}`;
    }

    const gamepadHelp = document.getElementById("gamepad-help");
    if (gamepadHelp) {
      gamepadHelp.classList.remove("hidden");
    }

    const splashText = document.getElementById("splash-skip-text");
    if (splashText) {
      splashText.textContent = "Press A/X to skip";
    }

    document.body.classList.add("gamepad-connected");

    AudioManager.playSound("gamepad-connect");
    this.onStatusChange(true);
    this.startPolling();
  },

  handleDisconnect(e) {
    if (e.gamepad.index !== this.index) return;

    console.log(
      `Gamepad disconnected from index ${e.gamepad.index}: ${e.gamepad.id}`
    );
    this.connected = false;
    this.index = null;

    const gamepadStatus = document.getElementById("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.remove("bg-sf-dark", "border-sf-green");
      gamepadStatus.classList.add("bg-sf-darker", "border-sf-gold-dark");
      gamepadStatus.title = "No Gamepad Connected";
    }

    const gamepadHelp = document.getElementById("gamepad-help");
    if (gamepadHelp) {
      gamepadHelp.classList.add("hidden");
    }

    const splashText = document.getElementById("splash-skip-text");
    if (splashText) {
      splashText.textContent = "Click anywhere to skip";
    }

    document.querySelectorAll(".gamepad-hover").forEach((el) => {
      el.classList.remove("gamepad-hover");
    });

    document.body.classList.remove("gamepad-connected");

    AudioManager.playSound("gamepad-disconnect");
    this.onStatusChange(false);
    this.stopPolling();
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

    if (currentTime - this.uiState.lastInputTime < this.uiState.inputCooldown) {
      return;
    }

    const directions = {
      left: currentState.axes.left.x < -0.5 || currentState.buttons[14],
      right: currentState.axes.left.x > 0.5 || currentState.buttons[15],
      up: currentState.axes.left.y < -0.5 || currentState.buttons[12],
      down: currentState.axes.left.y > 0.5 || currentState.buttons[13],
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
      inputX !== this.uiState.lastInput.x ||
      inputY !== this.uiState.lastInput.y ||
      buttons.a !== this.uiState.lastInput.a ||
      buttons.b !== this.uiState.lastInput.b ||
      buttons.lb !== this.uiState.lastInput.lb ||
      buttons.rb !== this.uiState.lastInput.rb;

    if (inputChanged && hasInput) {
      this.onUIAction(inputX, inputY, buttons);
      this.uiState.lastInputTime = currentTime;
    }

    this.uiState.lastInput = { x: inputX, y: inputY, ...buttons };
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

const WebSocketManager = {
  socket: null,
  onMessage: null,

  init(callbacks = {}) {
    this.onMessage = callbacks.onMessage || (() => {});

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.socket = new WebSocket(wsUrl);
    const startButton = document.getElementById("start-game-btn");

    this.socket.onopen = () => console.log("Connected to server");

    this.socket.onclose = () => {
      console.log("Disconnected from server");
      if (startButton && !startButton.textContent.includes("START GAME")) {
        startButton.textContent = "Connection Lost";
        startButton.disabled = true;
        startButton.classList.add("opacity-50");
      }
    };

    this.socket.onerror = (event) => {
      console.error("WebSocket connection error", event);
      if (startButton && !startButton.textContent.includes("START GAME")) {
        startButton.textContent = "Connection Error";
        startButton.disabled = true;
        startButton.classList.add("opacity-50");
      }
    };

    this.socket.onmessage = (event) => this.onMessage(event);

    startButton.disabled = true;
    startButton.classList.add("opacity-50");
  },

  send(type, data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(
          JSON.stringify({
            type: type,
            data: data,
          })
        );
      } catch (e) {
        console.error("websocket send fail", e);
      }
    }
  },

  close() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  },
};

class StreetFighterGame {
  // init

  constructor() {
    this.initializeState();
    this.initializeConstants();
    this.preloadAllAssets().then(() => {
      this.assetsLoaded = true;
      document.getElementById("loading-status").textContent =
        "Connecting to server...";

      AudioManager.init();
      this.initializeUI();
      this.initializeEventListeners();
      this.initializeGamepadManager();
      this.initializeWebSocketManager();
    });

    window.addEventListener("beforeunload", () => this.cleanup());
  }

  initializeState() {
    // per session
    this.assetsLoaded = false;
    this.capcomTimeout = null;

    // game state
    this.gameState = {
      // settings
      difficulty: 1,
      humanVsLlm: true,

      // player state
      player1: { character: null, outfit: 1, superArt: 1 },
      player2: { character: null, outfit: 1, superArt: 1 },

      // game status
      loaded: false,
      serverReady: false,
      firstFrameReceived: false,
      inTransition: false,
      transitionStartTime: null,
      readyToHideTransition: false,
    };

    // keys
    this.keyState = {};
    this.inputHistory = [];
    this.movesByLength = {};
    this.combos = {};
    this.specialMoves = {};

    // gamepad UI state
    this.gamepadUIState = {
      currentScreen: null,
      currentSection: 0,
      currentElement: 0,
      sections: [],
    };

    // character select
    this.currentCharacter = null;
    this.playerDirection = "right";
    this.characterGrid = {
      activePlayer: "p1",
      p1: { selected: false, character: null, outfit: 1 },
      p2: { selected: false, character: null, outfit: 1 },
    };
  }

  initializeConstants() {
    // sf3-specific
    this.characters = [
      "Alex",
      "Chun-Li",
      "Dudley",
      "Elena",
      "Gouki",
      "Hugo",
      "Ibuki",
      "Ken",
      "Makoto",
      "Necro",
      "Oro",
      "Q",
      "Remy",
      "Ryu",
      "Sean",
      "Twelve",
      "Urien",
      "Yang",
      "Yun",
    ];
    this.idxToMove = [
      { name: "No-Move", display: "", gamepadDisplay: "" },
      { name: "Left", display: "←", gamepadDisplay: "←" },
      { name: "Left+Up", display: "↖", gamepadDisplay: "↖" },
      { name: "Up", display: "↑", gamepadDisplay: "↑" },
      { name: "Up+Right", display: "↗", gamepadDisplay: "↗" },
      { name: "Right", display: "→", gamepadDisplay: "→" },
      { name: "Right+Down", display: "↘", gamepadDisplay: "↘" },
      { name: "Down", display: "↓", gamepadDisplay: "↓" },
      { name: "Down+Left", display: "↙", gamepadDisplay: "↙" },
      { name: "Low Punch", display: "J", gamepadDisplay: "A/X" },
      { name: "Medium Punch", display: "K", gamepadDisplay: "B/◯" },
      { name: "High Punch", display: "L", gamepadDisplay: "RB/R1" },
      { name: "Low Kick", display: "U", gamepadDisplay: "X/□" },
      { name: "Medium Kick", display: "I", gamepadDisplay: "Y/△" },
      { name: "High Kick", display: "O", gamepadDisplay: "LB/L1" },
      {
        name: "Low Punch+Low Kick",
        display: "J + U",
        gamepadDisplay: "A/X + X/□",
      },
      {
        name: "Medium Punch+Medium Kick",
        display: "K + I",
        gamepadDisplay: "B/◯ + Y/△",
      },
      {
        name: "High Punch+High Kick",
        display: "L + O",
        gamepadDisplay: "RB/R1 + LB/L1",
      },
    ];

    this.actions = {};
    this.idxToMove.forEach((move, idx) => {
      let key = move.name.toUpperCase().replace(/[ +\-]/g, "_");
      this.actions[key] = idx;
    });
    this.actions.SUPER_ART = 18;
    this.actions.COMBO = 19;

    this.difficultyLabels = [
      "",
      "Very Easy",
      "Easy",
      "Medium",
      "Hard",
      "Very Hard",
      "Expert",
      "Master",
      "Extreme",
    ];
    this.numOutfitsPerCharacter = 6;
    this.maxInputHistory = 20; // roughly max length of move sequence

    // ux (ms)
    this.animationDuration = 600;
    this.comboTimeout = 500;
    this.transitionMinDisplayTime = 3000;
    this.coinSoundDuration = 1000;
    this.capcomSoundDuration = 6000;

    this.volume = 0.5; // 0-1
    // relative to this.volume
    this.selectVolume = 0.2;
    this.startSoundVolume = 0.2;
    this.gameplayMusicVolume = 0.2;
    this.transitionSoundVolume = 0.2;
    this.winLoseSoundVolume = 0.2;

    // ui
    this.staticImages = {
      CAPCOM: "/capcom.svg",
      MODAL: "/modal.svg",
      MUTE: "/icons/mute.svg",
      UNMUTE: "/icons/unmute.svg",
      HUMAN: "/icons/human.png",
      LLM: "/icons/llm.png",
    };
    this.screens = {
      COIN: "coin",
      SPLASH: "splash",
      SETTINGS: "settings",
      LOADING: "loading",
      GAME: "game",
      WIN: "win",
      ERROR: "error",
    };
    this.buttons = [
      "start-game-btn",
      "play-again-btn",
      "error-back-btn",
      "p1-selected-portrait",
      "p2-selected-portrait",
    ];
    this.hoverElements = [
      "super-art-select-p1",
      "super-art-select-p2",
      "difficulty-slider",
      "modal-link",
    ];

    // audio  (suffix = .mp3 added later)
    this.soundFiles = {
      HOVER: "hover",
      CLICK: "click",
      COIN: "coin",
      CAPCOM: "capcom",
      SELECT: "select",
      TRANSITION: "transition",
      START: "start",
      WIN: "win",
      LOSE: "lose",
      CONTINUE: "continue",
      GAMEPAD_CONNECT: "gamepad-connect",
      GAMEPAD_DISCONNECT: "gamepad-disconnect",
    };
    this.gameplayMusicFiles = [
      "alex,ken",
      "chun-li",
      "dudley",
      "elena",
      "gouki",
      "hugo",
      "ibuki",
      "makoto",
      "necro,twelve",
      "q",
      "remy",
      "ryu",
      "sean,oro",
      "urien",
      "yun,yang",
    ];
    this.gameplayMusicMap = {};
    this.gameplayMusicFiles.forEach((entry) => {
      entry.split(",").forEach((name) => {
        const formattedName = name
          .trim()
          .split("-")
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join("-");
        this.gameplayMusicMap[formattedName] = entry;
      });
    });
  }

  async preloadAllAssets() {
    const imagePromises = [];

    const preloadImage = (src) => {
      const asset = new Image();
      asset.src = src;
      return new Promise((resolve) => {
        asset.onload = resolve;
        asset.onerror = resolve;
      });
    };

    this.characters.forEach((character) => {
      imagePromises.push(
        preloadImage(`/portraits/${character.toLowerCase()}.png`)
      );
    });

    Object.entries(this.staticImages).forEach(([, src]) => {
      imagePromises.push(preloadImage(src));
    });

    await Promise.all([
      AudioManager.preloadSounds(this.soundFiles, this.gameplayMusicMap),
      ...imagePromises,
    ]);
  }

  initializeGamepadManager() {
    GamepadManager.init({
      onStatusChange: (connected) => {
        WebSocketManager.send("gamepad_status", { connected });
        this.updateControlsDisplay();
        this.updateCombosDisplay(this.currentCharacter);
        this.updateSuperArtsDisplay(this.currentCharacter);
      },
      onInput: (state) => {
        this.processGamepadInput(state);
      },
      onUIAction: (inputX, inputY, buttons) => {
        this.handleGamepadUIAction(inputX, inputY, buttons);
      },
    });

    GamepadManager.setUIActive(true);
  }

  initializeWebSocketManager() {
    WebSocketManager.init({
      onMessage: (event) => this.handleWebSocketMessage(event),
    });
  }

  // init ui

  initializeUI() {
    // in the order that user sees them
    this.initializeCoinScreen();
    this.showScreen(this.screens.COIN);
    this.initializeSplashScreen();
    this.setupPlayerToggle();
    this.initializeCharacterGrid();
    this.initializeOutfitGrid(null);
    this.loadExtraMovesDisplay();
    this.initializeDifficultySlider();
    this.updateControlsDisplay();
  }

  initializeCoinScreen() {
    const coinBtn = document.getElementById("insert-coin-btn");
    if (coinBtn) {
      coinBtn.addEventListener("click", () => {
        coinBtn.disabled = true;

        coinBtn.classList.remove("animate-coin-shine");
        coinBtn.classList.add("animate-coin-insert");

        AudioManager.playSound(this.soundFiles.COIN);

        setTimeout(() => {
          this.transitionToSplash();
        }, this.coinSoundDuration);
      });

      coinBtn.addEventListener("mouseenter", () => {
        AudioManager.playSound(this.soundFiles.HOVER);
      });
    }
  }

  initializeSplashScreen() {
    const splashScreen = document.getElementById("splash-screen");
    if (!splashScreen) return;

    splashScreen.addEventListener("click", (e) => {
      if (splashScreen.classList.contains("hidden")) return;

      if (this.capcomTimeout) {
        clearTimeout(this.capcomTimeout);
        this.capcomTimeout = null;
      }

      if (AudioManager.sounds[this.soundFiles.CAPCOM]) {
        AudioManager.sounds[this.soundFiles.CAPCOM].pause();
        AudioManager.sounds[this.soundFiles.CAPCOM].currentTime = 0;
      }

      this.showScreen(this.screens.SETTINGS);
    });
  }

  transitionToSplash() {
    if (!document.getElementById("coin-screen").classList.contains("hidden")) {
      this.showScreen(this.screens.SPLASH);
      AudioManager.playSound(this.soundFiles.CAPCOM);

      this.capcomTimeout = setTimeout(() => {
        this.capcomTimeout = null;
        this.showScreen(this.screens.SETTINGS);
      }, this.capcomSoundDuration);
    }
  }

  setupPlayerToggle() {
    const playerToggle = document.getElementById("player-toggle");
    if (playerToggle) {
      playerToggle.addEventListener("click", () => {
        this.gameState.humanVsLlm = !this.gameState.humanVsLlm;

        const playerIcon = document.getElementById("player-icon");
        if (this.gameState.humanVsLlm) {
          playerIcon.src = this.staticImages.HUMAN;
        } else {
          playerIcon.src = this.staticImages.LLM;
        }

        const p1Label = document.querySelector("#p1-selection-box h2");
        const p2Label = document.querySelector("#p2-selection-box h2");

        if (p1Label) {
          p1Label.textContent = this.gameState.humanVsLlm ? "YOU" : "LLM 1";
        }
        if (p2Label) {
          p2Label.textContent = this.gameState.humanVsLlm ? "LLM" : "LLM 2";
        }

        AudioManager.playSound(this.soundFiles.CLICK);
      });

      playerToggle.addEventListener("mouseenter", () => {
        AudioManager.playSound(this.soundFiles.HOVER);
      });
    }
  }

  initializeCharacterGrid() {
    const gridContainer = document.getElementById("character-grid");
    gridContainer.innerHTML = "";

    this.characters.forEach((character, index) => {
      const portrait = this.createPortrait(character, index);
      gridContainer.appendChild(portrait);
    });

    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    const p2SuperArt = document.getElementById("super-art-select-p2");
    if (p2SuperArt) {
      p2SuperArt.addEventListener("change", () =>
        AudioManager.playSound(this.soundFiles.CLICK)
      );
    }
  }

  initializeDifficultySlider() {
    const slider = document.getElementById("difficulty-slider");
    const label = document.getElementById("difficulty-label");

    slider.addEventListener("input", (e) => {
      const value = parseInt(e.target.value);
      this.gameState.difficulty = value;
      label.textContent = this.difficultyLabels[value];
      AudioManager.playSound(this.soundFiles.CLICK);
    });
  }

  async loadExtraMovesDisplay() {
    const elements = {
      combosLoading: document.getElementById("combos-loading"),
      superArtsLoading: document.getElementById("super-arts-loading"),
      combosList: document.getElementById("combos-list"),
      superArtsList: document.getElementById("super-arts-list"),
    };

    try {
      const response = await fetch("/api/extra-moves");
      const data = await response.json();
      this.combos = data.combos;
      this.specialMoves = data.special_moves;

      this.preprocessMoves();
      this.updateCombosDisplay(this.currentCharacter);
      this.updateSuperArtsDisplay(this.currentCharacter);

      const superArtSelect = document.getElementById("super-art-select-p1");
      this.gameState.player1.superArt = parseInt(superArtSelect.value);

      superArtSelect.addEventListener("change", () => {
        this.gameState.player1.superArt = parseInt(superArtSelect.value);
        this.updateSuperArtsDisplay(this.currentCharacter);
        this.preprocessMoves();
        AudioManager.playSound(this.soundFiles.CLICK);
      });

      elements.combosLoading.classList.add("hidden");
      elements.superArtsLoading.classList.add("hidden");
    } catch (error) {
      console.error("Failed to load combos:", error);
      elements.combosLoading.classList.add("hidden");
      elements.superArtsLoading.classList.add("hidden");
      elements.combosList.innerHTML =
        '<p class="text-sf-red">Failed to load combos</p>';
      elements.superArtsList.innerHTML =
        '<p class="text-sf-red">Failed to load super arts</p>';
    }
  }

  // init event listeners

  initializeEventListeners() {
    [...this.buttons, ...this.hoverElements].forEach((elemId) => {
      const elem = document.getElementById(elemId);
      if (elem) {
        elem.addEventListener("mouseenter", () =>
          AudioManager.playSound(this.soundFiles.HOVER)
        );
      }
    });

    document.getElementById("start-game-btn").addEventListener("click", () => {
      AudioManager.playSound(this.soundFiles.CLICK);
      this.startGame();
    });
    document.getElementById("play-again-btn").addEventListener("click", () => {
      AudioManager.playSound(this.soundFiles.CLICK);
      this.resetSelections();
      this.showScreen(this.screens.SETTINGS);
    });
    document.getElementById("error-back-btn").addEventListener("click", () => {
      AudioManager.playSound(this.soundFiles.CLICK);
      this.showScreen(this.screens.SETTINGS);
    });

    const handleKeyEvent = (e, isDown) => {
      if (!this.gameState.loaded || !this.gameState.humanVsLlm) return;

      this.keyState[e.code] = isDown;
      const action = this.getActionFromKeys();

      WebSocketManager.send("player_action", {
        action,
      });

      if (action !== this.actions.NO_MOVE) {
        this.inputHistory.push({ action, time: Date.now() });

        if (this.inputHistory.length > this.maxInputHistory) {
          this.inputHistory.shift();
        }

        const detectedMove = this.detectExtra();
        if (detectedMove) {
          WebSocketManager.send("player_action", {
            action: detectedMove.type === "super_art" ? 18 : 19,
            [detectedMove.type === "super_art" ? "super_art" : "combo"]:
              detectedMove.name,
          });
        }
      }

      e.preventDefault();
    };

    document.addEventListener("keydown", (e) => handleKeyEvent(e, true));
    document.addEventListener("keyup", (e) => handleKeyEvent(e, false));

    ["p1", "p2"].forEach((player) => {
      document
        .getElementById(`${player}-selected-portrait`)
        .addEventListener("click", () => {
          this.switchActivePlayer(player);
          AudioManager.playSound(this.soundFiles.CLICK);
        });
    });
  }

  // gamepad support

  handleGamepadUIAction(inputX, inputY, buttons) {
    this.updateGamepadSections();

    const currentScreen = this.getCurrentScreen();
    if (currentScreen === this.screens.SPLASH && buttons.a) {
      const splashScreen = document.getElementById("splash-screen");
      if (splashScreen) {
        splashScreen.click();
      }
      return;
    }

    if (!this.gamepadUIState.sections.length) return;

    if (buttons.lb) {
      this.changeGamepadSection(-1);
      return;
    } else if (buttons.rb) {
      this.changeGamepadSection(1);
      return;
    }

    if (buttons.a) {
      this.handleGamepadSelect();
      return;
    }

    if (inputX !== 0 || inputY !== 0) {
      this.handleGamepadNavigation(inputX, inputY);
    }
  }

  updateGamepadSections(forceUpdate = false) {
    const currentScreen = this.getCurrentScreen();
    if (!forceUpdate && currentScreen === this.gamepadUIState.currentScreen)
      return;

    const preservePosition =
      forceUpdate && currentScreen === this.gamepadUIState.currentScreen;
    const oldSection = preservePosition
      ? this.gamepadUIState.currentSection
      : 0;
    const oldElement = preservePosition
      ? this.gamepadUIState.currentElement
      : 0;

    this.gamepadUIState.currentScreen = currentScreen;
    this.gamepadUIState.currentSection = 0;
    this.gamepadUIState.currentElement = 0;
    this.gamepadUIState.sections = [];

    switch (currentScreen) {
      case this.screens.COIN:
        this.gamepadUIState.sections = [
          { elements: this.getVisibleHeaderElements() },
          { elements: ["#insert-coin-btn"] },
        ];
        break;
      case this.screens.SPLASH:
        this.gamepadUIState.sections = [];
        break;
      case this.screens.SETTINGS:
        this.gamepadUIState.sections = [
          { elements: ["#modal-link", "#player-toggle", "#mute-toggle"] },
          { elements: ["#p1-selected-portrait", "#p2-selected-portrait"] },
          { elements: this.getCharacterGridElements(), grid: true, cols: 5 },
          { elements: this.getOutfitElements(), grid: true, cols: 1 },
          { elements: ["#super-art-select-p1"], controls: true },
          { elements: ["#super-art-select-p2"], controls: true },
          { elements: ["#difficulty-slider"], controls: true },
          { elements: ["#start-game-btn"] },
        ];
        break;
      case this.screens.WIN:
        this.gamepadUIState.sections = [
          { elements: this.getVisibleHeaderElements() },
          { elements: ["#play-again-btn"] },
        ];
        break;
      case this.screens.ERROR:
        this.gamepadUIState.sections = [
          { elements: this.getVisibleHeaderElements() },
          { elements: ["#error-back-btn"] },
        ];
        break;
      case this.screens.LOADING:
        this.gamepadUIState.sections = [
          { elements: this.getVisibleHeaderElements() },
        ];
        break;
      case this.screens.GAME:
        this.gamepadUIState.sections = [];
        break;
    }

    this.gamepadUIState.sections = this.gamepadUIState.sections.filter(
      (section) => section.elements && section.elements.length > 0
    );

    switch (currentScreen) {
      case this.screens.COIN:
        this.gamepadUIState.currentSection =
          this.gamepadUIState.sections.length > 1 ? 1 : 0;
        break;
      case this.screens.SPLASH:
        this.gamepadUIState.currentSection =
          this.gamepadUIState.sections.length > 1 ? 1 : 0;
        break;
      case this.screens.SETTINGS:
        if (this.gamepadUIState.sections.length > 1) {
          this.gamepadUIState.currentSection = 1;
        }
        break;
      case this.screens.WIN:
        this.gamepadUIState.currentSection =
          this.gamepadUIState.sections.length > 1 ? 1 : 0;
        break;
      case this.screens.ERROR:
        this.gamepadUIState.currentSection =
          this.gamepadUIState.sections.length > 1 ? 1 : 0;
        break;
    }

    if (preservePosition) {
      if (oldSection < this.gamepadUIState.sections.length) {
        this.gamepadUIState.currentSection = oldSection;
        const section = this.gamepadUIState.sections[oldSection];
        if (
          section &&
          section.elements &&
          oldElement < section.elements.length
        ) {
          this.gamepadUIState.currentElement = oldElement;
        }
      }
    }

    this.updateGamepadHover();
  }

  getCharacterGridElements() {
    const portraits = document.querySelectorAll("#character-grid > div");
    return Array.from(portraits).map(
      (el) => `#${el.id || this.generateElementId(el)}`
    );
  }

  getOutfitElements() {
    const outfits = document.querySelectorAll("#outfit-grid > div");
    return Array.from(outfits).map(
      (el) => `#${el.id || this.generateElementId(el)}`
    );
  }

  getVisibleHeaderElements() {
    const elements = [];

    const header = document.getElementById("game-header");
    if (header && !header.classList.contains("hidden")) {
      elements.push("#modal-link");
    }

    const playerToggle = document.getElementById("player-toggle");

    if (playerToggle && !playerToggle.classList.contains("hidden")) {
      elements.push("#player-toggle");
    }

    elements.push("#mute-toggle");

    return elements;
  }

  generateElementId(element) {
    const id = `gamepad-el-${Math.random().toString(36).substr(2, 9)}`;
    element.id = id;
    return id;
  }

  changeGamepadSection(direction) {
    const numSections = this.gamepadUIState.sections.length;
    if (numSections === 0) return;

    this.gamepadUIState.currentSection =
      (this.gamepadUIState.currentSection + direction + numSections) %
      numSections;
    this.gamepadUIState.currentElement = 0;

    this.updateGamepadHover();
    AudioManager.playSound(this.soundFiles.HOVER);
  }

  handleGamepadNavigation(inputX, inputY) {
    const section =
      this.gamepadUIState.sections[this.gamepadUIState.currentSection];
    if (!section || !section.elements.length) return;

    if (section.grid) {
      this.navigateGrid(inputX, inputY, section);
    } else if (section.controls) {
      this.navigateControls(inputX, inputY, section);
    } else {
      this.navigateList(inputX, inputY, section);
    }

    this.updateGamepadHover();
    AudioManager.playSound(this.soundFiles.HOVER);
  }

  navigateGrid(inputX, inputY, section) {
    const cols = section.cols || 1;
    const rows = Math.ceil(section.elements.length / cols);
    const currentRow = Math.floor(this.gamepadUIState.currentElement / cols);
    const currentCol = this.gamepadUIState.currentElement % cols;

    let newRow = currentRow;
    let newCol = currentCol;

    if (inputY < 0) newRow = Math.max(0, currentRow - 1);
    else if (inputY > 0) newRow = Math.min(rows - 1, currentRow + 1);

    if (inputX < 0) newCol = Math.max(0, currentCol - 1);
    else if (inputX > 0) newCol = Math.min(cols - 1, currentCol + 1);

    const newIndex = newRow * cols + newCol;
    if (newIndex < section.elements.length) {
      this.gamepadUIState.currentElement = newIndex;
    }
  }

  navigateControls(inputX, inputY, section) {
    const currentEl = document.querySelector(
      section.elements[this.gamepadUIState.currentElement]
    );

    if (
      currentEl &&
      (currentEl.tagName === "INPUT" || currentEl.tagName === "SELECT")
    ) {
      if (currentEl.type === "range") {
        const step = parseFloat(currentEl.step);
        const min = parseFloat(currentEl.min);
        const max = parseFloat(currentEl.max);
        const current = parseFloat(currentEl.value);

        if (inputX < 0) {
          currentEl.value = Math.max(min, current - step);
          currentEl.dispatchEvent(new Event("input", { bubbles: true }));
        } else if (inputX > 0) {
          currentEl.value = Math.min(max, current + step);
          currentEl.dispatchEvent(new Event("input", { bubbles: true }));
        }
      } else if (currentEl.tagName === "SELECT") {
        const options = currentEl.options;
        const current = currentEl.selectedIndex;

        if (inputX < 0) {
          currentEl.selectedIndex = Math.max(0, current - 1);
          currentEl.dispatchEvent(new Event("change", { bubbles: true }));
        } else if (inputX > 0) {
          currentEl.selectedIndex = Math.min(options.length - 1, current + 1);
          currentEl.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    }

    const isSlider =
      currentEl && currentEl.tagName === "INPUT" && currentEl.type === "range";

    if (inputY !== 0) {
      this.navigateList(0, inputY, section);
    } else if (inputX !== 0 && section.elements.length > 1) {
      if (!isSlider) {
        this.navigateList(inputX, 0, section);
      }
    }
  }

  navigateList(inputX, inputY, section) {
    if (inputY < 0 || inputX < 0) {
      this.gamepadUIState.currentElement = Math.max(
        0,
        this.gamepadUIState.currentElement - 1
      );
    } else if (inputY > 0 || inputX > 0) {
      this.gamepadUIState.currentElement = Math.min(
        section.elements.length - 1,
        this.gamepadUIState.currentElement + 1
      );
    }
  }

  handleGamepadSelect() {
    const section =
      this.gamepadUIState.sections[this.gamepadUIState.currentSection];
    if (!section) return;

    const elementSelector =
      section.elements[this.gamepadUIState.currentElement];
    const element = document.querySelector(elementSelector);

    if (element) {
      element.click();
      AudioManager.playSound(this.soundFiles.CLICK);
    }
  }

  updateGamepadHover() {
    document.querySelectorAll(".gamepad-hover").forEach((el) => {
      el.classList.remove("gamepad-hover");
    });

    if (!GamepadManager.isConnected()) {
      return;
    }

    const section =
      this.gamepadUIState.sections[this.gamepadUIState.currentSection];
    if (section && section.elements[this.gamepadUIState.currentElement]) {
      const element = document.querySelector(
        section.elements[this.gamepadUIState.currentElement]
      );
      if (element) {
        element.classList.add("gamepad-hover");
        element.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }

  getCurrentScreen() {
    for (const [, screenId] of Object.entries(this.screens)) {
      const el = document.getElementById(`${screenId}-screen`);
      if (el && !el.classList.contains("hidden")) {
        return screenId;
      }
    }
    return null;
  }

  processGamepadInput(currentState) {
    const directions = {
      left: currentState.axes.left.x < -0.5 || currentState.buttons[14],
      right: currentState.axes.left.x > 0.5 || currentState.buttons[15],
      up: currentState.axes.left.y < -0.5 || currentState.buttons[12],
      down: currentState.axes.left.y > 0.5 || currentState.buttons[13],
    };

    const attacks = {
      LP: currentState.buttons[0],
      MP: currentState.buttons[1],
      LK: currentState.buttons[2],
      MK: currentState.buttons[3],
      HK: currentState.buttons[4],
      HP: currentState.buttons[5],
    };

    let action = this.actions.NO_MOVE;

    if (attacks.LP && attacks.LK) {
      action = this.actions.LOW_PUNCH_LOW_KICK;
    } else if (attacks.MP && attacks.MK) {
      action = this.actions.MEDIUM_PUNCH_MEDIUM_KICK;
    } else if (attacks.HP && attacks.HK) {
      action = this.actions.HIGH_PUNCH_HIGH_KICK;
    } else if (attacks.HP) {
      action = this.actions.HIGH_PUNCH;
    } else if (attacks.MP) {
      action = this.actions.MEDIUM_PUNCH;
    } else if (attacks.LP) {
      action = this.actions.LOW_PUNCH;
    } else if (attacks.HK) {
      action = this.actions.HIGH_KICK;
    } else if (attacks.MK) {
      action = this.actions.MEDIUM_KICK;
    } else if (attacks.LK) {
      action = this.actions.LOW_KICK;
    } else if (directions.left && directions.up) {
      action = this.actions.LEFT_UP;
    } else if (directions.right && directions.up) {
      action = this.actions.UP_RIGHT;
    } else if (directions.left && directions.down) {
      action = this.actions.DOWN_LEFT;
    } else if (directions.right && directions.down) {
      action = this.actions.RIGHT_DOWN;
    } else if (directions.left) {
      action = this.actions.LEFT;
    } else if (directions.right) {
      action = this.actions.RIGHT;
    } else if (directions.up) {
      action = this.actions.UP;
    } else if (directions.down) {
      action = this.actions.DOWN;
    }

    WebSocketManager.send("player_action", { action });

    if (action !== this.actions.NO_MOVE) {
      this.inputHistory.push({ action, time: Date.now() });

      if (this.inputHistory.length > this.maxInputHistory) {
        this.inputHistory.shift();
      }

      const detectedMove = this.detectExtra();
      if (detectedMove) {
        WebSocketManager.send("player_action", {
          action: detectedMove.type === "super_art" ? 18 : 19,
          [detectedMove.type === "super_art" ? "super_art" : "combo"]:
            detectedMove.name,
        });
      }
    }
  }

  // start game

  startGame() {
    const { p1, p2 } = this.characterGrid;

    if (!p1.selected || !p2.selected) {
      if (this.gameState.humanVsLlm) {
        alert(
          "Both you and the LLM must have characters selected before starting!"
        );
      } else {
        alert(
          "Both LLM 1 and LLM 2 must have characters selected before starting!"
        );
      }
      return;
    }

    Object.assign(this.gameState.player1, {
      character: p1.character,
      outfit: p1.outfit,
      superArt: parseInt(document.getElementById("super-art-select-p1").value),
    });

    Object.assign(this.gameState.player2, {
      character: p2.character,
      outfit: p2.outfit,
      superArt: parseInt(document.getElementById("super-art-select-p2").value),
    });

    this.gameState.difficulty = parseInt(
      document.getElementById("difficulty-slider").value
    );

    AudioManager.play(this.soundFiles.START, {
      volume: this.startSoundVolume,
      trackAs: "effect",
    });

    setTimeout(() => {
      this.resetGameState();
      this.showScreen(this.screens.LOADING);
      document.getElementById("loading-status").textContent =
        "Starting game...";
      WebSocketManager.send("start_game", {
        difficulty: this.gameState.difficulty,
        humanVsLlm: this.gameState.humanVsLlm,
        player1: this.gameState.player1,
        player2: this.gameState.player2,
        gamepadConnected: GamepadManager.isConnected(),
      });
    }, 10); //  delay to allow sound to play first
  }

  resetGameState() {
    this.gameState.loaded = false;
    this.gameState.serverReady = false;
    this.gameState.firstFrameReceived = false;
    this.gameState.inTransition = false;
    this.gameState.transitionStartTime = null;
    this.gameState.readyToHideTransition = false;
    this.keyState = {};
    this.inputHistory = [];

    const status = document.getElementById("canvas-loading-status");
    status.textContent = "Loading game...";

    const overlay = document.getElementById("canvas-loading-overlay");
    overlay.classList.remove("hidden");

    const canvas = document.getElementById("game-canvas");
    canvas.classList.add("hidden");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // init ws

  async handleWebSocketMessage(event) {
    if (event.data instanceof Blob) {
      this.handleFrameData(event.data);
      return;
    }

    const message = JSON.parse(event.data);
    if (message.type === "game_state") {
      this.handleGameState(message.data);
    } else if (message.type === "transition") {
      this.handleTransition(message.data);
    }
  }

  handleFrameData(blob) {
    const overlay = document.getElementById("canvas-loading-overlay");

    if (!this.gameState.firstFrameReceived) {
      this.gameState.firstFrameReceived = true;
      overlay.classList.add("hidden");
      const canvas = document.getElementById("game-canvas");
      canvas.classList.remove("hidden");
    }

    if (this.gameState.inTransition) {
      this.gameState.readyToHideTransition = true;

      const elapsedTime = Date.now() - this.gameState.transitionStartTime;
      if (elapsedTime >= this.transitionMinDisplayTime) {
        this.hideTransitionOverlay();
      } else {
        const remainingTime = this.transitionMinDisplayTime - elapsedTime;
        setTimeout(() => {
          if (
            this.gameState.readyToHideTransition &&
            this.gameState.inTransition
          ) {
            this.hideTransitionOverlay();
          }
        }, remainingTime);
      }
    }

    const canvas = document.getElementById("game-canvas");
    const ctx = canvas.getContext("2d");
    const url = URL.createObjectURL(blob);
    const img = new Image();

    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }

  handleGameState(data) {
    console.log("Game state:", data.status);
    const startButton = document.getElementById("start-game-btn");

    if (!this.gameState.serverReady) {
      this.gameState.serverReady = true;
      startButton.disabled = false;
      startButton.textContent = "START GAME";
      startButton.classList.remove("opacity-50");
      console.log("Server ready");
    }

    switch (data.status) {
      case "initializing":
        document.getElementById("loading-status").textContent =
          "Starting game...";
        break;
      case "running":
        this.gameState.loaded = true;
        this.showScreen(this.screens.GAME);
        GamepadManager.setUIActive(!this.gameState.humanVsLlm);
        AudioManager.play(this.gameState.player1.character, {
          volume: this.gameplayMusicVolume,
          loop: true,
          trackAs: "select",
        });
        break;
      case "finished":
        this.gameState.loaded = false;
        GamepadManager.setUIActive(true);

        AudioManager.stopTrack("select");

        const winner = data.winner || "Unknown";
        let displayWinner = winner;

        document.getElementById(
          "winner-text"
        ).textContent = `Winner: ${displayWinner}`;

        const winSound =
          !this.gameState.humanVsLlm || winner === "YOU"
            ? this.soundFiles.WIN
            : this.soundFiles.LOSE;

        AudioManager.play(winSound, {
          volume: this.winLoseSoundVolume,
          trackAs: "winLose",
          onEnd: () => {
            if (
              !document
                .getElementById("win-screen")
                .classList.contains("hidden")
            ) {
              AudioManager.play(this.soundFiles.CONTINUE, {
                volume: this.selectVolume,
                loop: true,
                trackAs: "select",
              });
            }
          },
        });

        this.showScreen(this.screens.WIN);
        break;
      case "error":
        this.gameState.loaded = false;
        AudioManager.stopTrack("select");
        this.showError(data.error || "Unknown game error");
        break;
    }
  }

  handleTransition(data) {
    this.gameState.inTransition = true;
    this.gameState.transitionStartTime = Date.now();
    this.gameState.readyToHideTransition = false;

    AudioManager.stopTrack("select");
    AudioManager.play(this.soundFiles.TRANSITION, {
      volume: this.transitionSoundVolume,
      trackAs: "transition",
    });

    const status = document.getElementById("canvas-loading-status");

    let message = "";
    if (data.transition_type === "round") {
      message = "Loading next round...";
    } else if (data.transition_type === "game") {
      message = "Determining winner...";
    }
    status.textContent = message;

    const overlay = document.getElementById("canvas-loading-overlay");
    overlay.classList.remove("hidden");

    const canvas = document.getElementById("game-canvas");
    canvas.classList.add("hidden");

    const header = document.getElementById("game-header");
    if (header) {
      header.classList.remove("hidden");
    }

    setTimeout(() => {
      if (this.gameState.readyToHideTransition && this.gameState.inTransition) {
        this.hideTransitionOverlay();
      }
    }, this.transitionMinDisplayTime);
  }

  hideTransitionOverlay() {
    this.gameState.inTransition = false;
    this.gameState.transitionStartTime = null;
    this.gameState.readyToHideTransition = false;

    AudioManager.stopTrack("transition");

    if (
      this.gameState.loaded &&
      !document.getElementById("game-screen").classList.contains("hidden")
    ) {
      AudioManager.play(this.gameState.player1.character, {
        volume: this.gameplayMusicVolume,
        loop: true,
        trackAs: "select",
      });

      const header = document.getElementById("game-header");
      if (header) {
        header.classList.add("hidden");
      }
    }

    const canvas = document.getElementById("game-canvas");
    canvas.classList.remove("hidden");

    const overlay = document.getElementById("canvas-loading-overlay");
    overlay.classList.add("hidden");
  }

  // helper fns
  // input handling

  preprocessMoves() {
    this.movesByLength = {};

    if (!this.currentCharacter || !this.specialMoves || !this.combos) return;

    const characterMoves = this.specialMoves[this.currentCharacter];
    const characterCombos = this.combos[this.currentCharacter];
    const selectedSuperArt = this.gameState.player1.superArt;

    if (characterMoves) {
      this.addMovesToLength(characterMoves, selectedSuperArt, "super_art");
    }

    if (characterCombos) {
      for (const [comboName, comboData] of Object.entries(characterCombos)) {
        const seq = comboData[this.playerDirection];
        this.addMoveToLength(seq, "combo", comboName);
      }
    }

    this.sortMovesByPriority();
  }

  addMovesToLength(moves, selectedSuperArt, moveType) {
    for (const [moveKey, moveData] of Object.entries(moves)) {
      if (this.isSuperArtMove(moveKey, selectedSuperArt)) {
        const seq = moveData[this.playerDirection];
        this.addMoveToLength(seq, moveType, moveKey);
      }
    }
  }

  isSuperArtMove(moveKey, selectedSuperArt) {
    return (
      moveKey.startsWith(`${selectedSuperArt} `) ||
      (moveKey.startsWith("Max") &&
        (moveKey.startsWith(`Max-${selectedSuperArt} `) ||
          moveKey.startsWith("Max ")))
    );
  }

  addMoveToLength(sequence, type, name) {
    if (!this.movesByLength[sequence.length]) {
      this.movesByLength[sequence.length] = [];
    }
    this.movesByLength[sequence.length].push({ type, name, sequence });
  }

  sortMovesByPriority() {
    for (const length in this.movesByLength) {
      this.movesByLength[length].sort((a, b) =>
        a.type === "super_art" && b.type === "combo"
          ? -1
          : a.type === "combo" && b.type === "super_art"
          ? 1
          : 0
      );
    }
  }

  getActionFromKeys() {
    const attacks = {
      LP: this.keyState["KeyJ"],
      MP: this.keyState["KeyK"],
      HP: this.keyState["KeyL"],
      LK: this.keyState["KeyU"],
      MK: this.keyState["KeyI"],
      HK: this.keyState["KeyO"],
    };

    if (attacks.LP && attacks.LK) return this.actions.LOW_PUNCH_LOW_KICK;
    if (attacks.MP && attacks.MK) return this.actions.MEDIUM_PUNCH_MEDIUM_KICK;
    if (attacks.HP && attacks.HK) return this.actions.HIGH_PUNCH_HIGH_KICK;

    if (attacks.HP) return this.actions.HIGH_PUNCH;
    if (attacks.MP) return this.actions.MEDIUM_PUNCH;
    if (attacks.LP) return this.actions.LOW_PUNCH;
    if (attacks.HK) return this.actions.HIGH_KICK;
    if (attacks.MK) return this.actions.MEDIUM_KICK;
    if (attacks.LK) return this.actions.LOW_KICK;

    const directions = {
      left: this.keyState["KeyA"] || this.keyState["ArrowLeft"],
      right: this.keyState["KeyD"] || this.keyState["ArrowRight"],
      up: this.keyState["KeyW"] || this.keyState["ArrowUp"],
      down: this.keyState["KeyS"] || this.keyState["ArrowDown"],
    };

    if (directions.left && directions.up) return this.actions.LEFT_UP;
    if (directions.right && directions.up) return this.actions.UP_RIGHT;
    if (directions.left && directions.down) return this.actions.DOWN_LEFT;
    if (directions.right && directions.down) return this.actions.RIGHT_DOWN;

    if (directions.left) return this.actions.LEFT;
    if (directions.right) return this.actions.RIGHT;
    if (directions.up) return this.actions.UP;
    if (directions.down) return this.actions.DOWN;

    return this.actions.NO_MOVE;
  }

  detectExtra() {
    const currentTime = Date.now();

    this.inputHistory = this.inputHistory.filter(
      (input) => currentTime - input.time <= this.comboTimeout
    );

    if (this.inputHistory.length < 2) return null;

    for (let len = this.inputHistory.length; len >= 2; len--) {
      const match = this.findMoveMatch(len);
      if (match) {
        this.inputHistory = [];
        return match;
      }
    }

    return null;
  }

  findMoveMatch(sequenceLength) {
    const moves = this.movesByLength[sequenceLength];
    if (!moves) return null;

    const startIndex = this.inputHistory.length - sequenceLength;

    for (const move of moves) {
      if (this.isSequenceMatch(move.sequence, startIndex)) {
        return { type: move.type, name: move.name };
      }
    }

    return null;
  }

  isSequenceMatch(sequence, startIndex) {
    for (let i = 0; i < sequence.length; i++) {
      if (this.inputHistory[startIndex + i].action !== sequence[i]) {
        return false;
      }
    }
    return true;
  }

  // ui

  showScreen(screenId) {
    Object.values(this.screens).forEach((screen) => {
      const el = document.getElementById(`${screen}-screen`);
      if (el) {
        el.classList.toggle("hidden", screen !== screenId);
      }
    });

    const isLoading = screenId === this.screens.LOADING;
    const hideAll = isLoading && !this.assetsLoaded;

    const header = document.getElementById("game-header");
    if (header) {
      const hideHeader =
        screenId === this.screens.SPLASH ||
        screenId === this.screens.GAME ||
        hideAll;
      header.classList.toggle("hidden", hideHeader);
    }

    const playerToggle = document.getElementById("player-toggle");
    if (playerToggle) {
      const showPlayerToggle = screenId === this.screens.SETTINGS;
      playerToggle.classList.toggle("hidden", !showPlayerToggle);
    }

    const muteButton = document.getElementById("mute-toggle");
    if (muteButton) {
      muteButton.classList.toggle("hidden", hideAll);
    }

    const gamepadStatus = document.getElementById("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.toggle("hidden", hideAll);
    }

    const gamepadHelp = document.getElementById("gamepad-help");
    if (gamepadHelp) {
      const hideGamepadHelp =
        !GamepadManager.isConnected() ||
        screenId === this.screens.LOADING ||
        screenId === this.screens.GAME;
      gamepadHelp.classList.toggle("hidden", hideGamepadHelp);
    }

    if (screenId === this.screens.SETTINGS) {
      AudioManager.play(this.soundFiles.SELECT, {
        volume: this.selectVolume,
        loop: true,
        trackAs: "select",
      });
      AudioManager.stopTrack("winLose");
    } else {
      AudioManager.stopTrack("select");
      if (screenId !== this.screens.WIN) {
        AudioManager.stopTrack("winLose");
      }
    }

    if (screenId === this.screens.COIN) {
      const coinBtn = document.getElementById("insert-coin-btn");
      if (coinBtn) {
        coinBtn.disabled = false;
        coinBtn.classList.remove("animate-coin-insert");
        coinBtn.classList.add("animate-coin-shine");
      }
    }

    if (GamepadManager.isConnected()) {
      this.gamepadUIState.currentScreen = null;
      this.updateGamepadSections();
    }
  }

  showError(message) {
    document.getElementById("error-details").textContent =
      new Date().toLocaleString() + "\n" + message;
    this.showScreen(this.screens.ERROR);
  }

  // character move display

  updateControlsDisplay() {
    const controls = {
      "movement-display": GamepadManager.isConnected()
        ? "Left Stick / D-Pad"
        : "WASD / Arrow Keys",
      "lp-display": GamepadManager.isConnected() ? "A/X" : "J",
      "mp-display": GamepadManager.isConnected() ? "B/◯" : "K",
      "hp-display": GamepadManager.isConnected() ? "RB/R1" : "L",
      "lk-display": GamepadManager.isConnected() ? "X/□" : "U",
      "mk-display": GamepadManager.isConnected() ? "Y/△" : "I",
      "hk-display": GamepadManager.isConnected() ? "LB/L1" : "O",
      "lplk-display": GamepadManager.isConnected() ? "A/X + X/□" : "J + U",
      "mpmk-display": GamepadManager.isConnected() ? "B/◯ + Y/△" : "K + I",
      "hphk-display": GamepadManager.isConnected() ? "RB/R1 + LB/L1" : "L + O",
    };

    Object.entries(controls).forEach(([id, text]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = text;
      }
    });
  }

  updateCombosDisplay(character) {
    const combosList = document.getElementById("combos-list");

    if (!character || !this.combos || !this.combos[character]) {
      combosList.innerHTML =
        '<p class="text-sf-beige-dark">Select a character to see combos</p>';
      return;
    }

    const combos = this.combos[character];

    const moves = Object.entries(combos).map(([name, data]) => ({
      name,
      sequence: data[this.playerDirection],
    }));

    combosList.innerHTML = this.generateMovesHTML(moves);
  }

  updateSuperArtsDisplay(character) {
    const superArtsList = document.getElementById("super-arts-list");
    const selectedSuperArt = document.getElementById(
      "super-art-select-p1"
    ).value;

    if (!character || !this.specialMoves || !this.specialMoves[character]) {
      superArtsList.innerHTML =
        '<p class="text-sf-beige-dark">Select a character to see super arts</p>';
      return;
    }

    const characterMoves = this.specialMoves[character];
    const moves = [];

    for (const [moveKey, moveData] of Object.entries(characterMoves)) {
      if (moveKey.startsWith(`${selectedSuperArt} `)) {
        moves.push({
          name: this.getSpecialMoveDisplayName(moveKey),
          sequence: moveData[this.playerDirection],
        });
        break;
      }
    }

    for (const [moveKey, moveData] of Object.entries(characterMoves)) {
      if (typeof moveKey === "string" && moveKey.startsWith("Max")) {
        if (
          moveKey.startsWith(`Max-${selectedSuperArt} `) ||
          moveKey.startsWith("Max ")
        ) {
          moves.push({
            name: this.getSpecialMoveDisplayName(moveKey),
            sequence: moveData[this.playerDirection],
          });
        }
      }
    }

    superArtsList.innerHTML = this.generateMovesHTML(moves);
  }

  generateMovesHTML(moves) {
    const moveElements = moves
      .map(
        (move) => `
            <p>${move.name}:</p>
            <div class="flex items-center gap-2 flex-wrap justify-center mb-4">
                ${this.getExtraElements(move.sequence)}
            </div>
        `
      )
      .join("");

    return `<div class="text-center flex flex-col justify-center items-center gap-4">${moveElements}</div>`;
  }

  getExtraElements(sequence) {
    return sequence
      .map((action, index) => {
        const move = this.idxToMove[action];
        const symbol = GamepadManager.isConnected()
          ? move.gamepadDisplay
          : move.display;
        const isLast = index === sequence.length - 1;
        return `
                <span class="control-key">${symbol}</span>
                ${!isLast ? "<span>+</span>" : ""}
            `;
      })
      .join("");
  }

  getSpecialMoveDisplayName(fullKey) {
    if (fullKey.match(/^\d+ /)) {
      // format: "1 Messatsu Gou Hadou" -> "Messatsu Gou Hadou"
      return fullKey.substring(2);
    } else if (fullKey.startsWith("Max-")) {
      // format: "Max-1 Messatsu Gou Hadou" -> "Max Messatsu Gou Hadou"
      const parts = fullKey.split(" ");
      return "Max " + parts.slice(1).join(" ");
    }
    return fullKey;
  }

  // character/outfit display

  switchActivePlayer(player) {
    this.characterGrid.activePlayer = player;
    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    const selectedCharacter = this.characterGrid[player].character;
    if (selectedCharacter) {
      this.initializeOutfitGrid(selectedCharacter);
    } else {
      const gridContainer = document.getElementById("outfit-grid");
      const indicator = document.getElementById("outfit-player-indicator");

      gridContainer.innerHTML = "";
      indicator.textContent = "Select a character to see outfits";
    }
    this.updateGamepadSections(true);
  }

  updatePlayerBoxes() {
    const p1Portrait = document.getElementById("p1-selected-portrait");
    const p2Portrait = document.getElementById("p2-selected-portrait");
    const activeColor = this.getPlayerColor(this.characterGrid.activePlayer);

    p1Portrait.className = `portrait-box border-${
      this.characterGrid.activePlayer === "p1" ? activeColor : "transparent"
    }`;
    p2Portrait.className = `portrait-box border-${
      this.characterGrid.activePlayer === "p2" ? activeColor : "transparent"
    }`;
  }

  updateCharacterBorders() {
    const portraits = document.querySelectorAll("#character-grid > div");

    portraits.forEach((el) => {
      el.classList.remove("border-sf-red", "border-sf-blue");
      el.classList.add("border-transparent");
    });

    ["p1", "p2"].forEach((player) => {
      if (this.characterGrid[player].character) {
        const selected = Array.from(portraits).find(
          (p) => p.dataset.character === this.characterGrid[player].character
        );
        if (selected) {
          selected.classList.remove("border-transparent");
          selected.classList.add(`border-${this.getPlayerColor(player)}`);
        }
      }
    });
  }

  selectCharacter(player, character) {
    if (!character) return;

    const portraits = document.querySelectorAll("#character-grid > div");
    const selectedPortrait = Array.from(portraits).find(
      (p) => p.dataset.character === character
    );
    if (!selectedPortrait) return;

    selectedPortrait.classList.add("animate-character-flash");

    setTimeout(() => {
      selectedPortrait.classList.remove("animate-character-flash");

      this.characterGrid[player].selected = true;
      this.characterGrid[player].character = character;
      this.characterGrid[player].outfit = 1;

      if (player === "p1") {
        this.currentCharacter = character;
        this.updateCombosDisplay(character);
        this.updateSuperArtsDisplay(character);
        this.preprocessMoves();
      }

      this.updatePlayerPortrait(player, character);
      this.updateCharacterBorders();
      this.initializeOutfitGrid(character);
      this.updateGamepadSections(true);
    }, this.animationDuration);
  }

  updatePlayerPortrait(player, character) {
    const portraitImg = document.querySelector(
      `#${player}-selected-portrait img`
    );
    const nameEl = document.getElementById(`${player}-selected-name`);
    const portraitBox = document.getElementById(`${player}-selected-portrait`);

    const existingPlaceholder = portraitBox.querySelector(
      ".portrait-placeholder"
    );
    if (existingPlaceholder) existingPlaceholder.remove();

    const placeholder = document.createElement("div");
    placeholder.className =
      "portrait-placeholder absolute inset-0 loading-placeholder rounded-lg";
    portraitBox.appendChild(placeholder);

    portraitImg.classList.add("opacity-0");
    portraitImg.src = `/portraits/${character.toLowerCase()}.png`;
    portraitImg.classList.remove("hidden");
    nameEl.textContent = character;

    const loadHandler = () => {
      portraitImg.classList.remove("opacity-0");
      portraitImg.classList.add(
        "opacity-100",
        "transition-opacity",
        "duration-300"
      );
      const ph = portraitBox.querySelector(".portrait-placeholder");
      if (ph) ph.remove();
    };

    const errorHandler = () => {
      portraitImg.classList.remove("opacity-0");
      portraitImg.classList.add("opacity-100");
      const ph = portraitBox.querySelector(".portrait-placeholder");
      if (ph)
        ph.innerHTML =
          '<div class="flex items-center justify-center h-full text-sf-red">?</div>';
    };

    portraitImg.addEventListener("load", loadHandler, { once: true });
    portraitImg.addEventListener("error", errorHandler, { once: true });
  }

  selectOutfit(player, outfitIndex) {
    const outfitNum = outfitIndex + 1; // 1-based for display

    const outfits = document.querySelectorAll("#outfit-grid > div");
    const selectedOutfit = outfits[outfitIndex];
    if (!selectedOutfit) return;

    selectedOutfit.classList.add("animate-character-flash");

    setTimeout(() => {
      selectedOutfit.classList.remove("animate-character-flash");
      this.characterGrid[player].outfit = outfitNum;
      this.updateOutfitBorders();
    }, this.animationDuration);
  }

  updateOutfitBorders() {
    const outfits = document.querySelectorAll("#outfit-grid > div");
    const activePlayer = this.characterGrid.activePlayer;
    const selectedOutfit = this.characterGrid[activePlayer].outfit;
    const borderColor = `border-${this.getPlayerColor(activePlayer)}`;

    outfits.forEach((el, index) => {
      el.classList.remove("border-sf-red", "border-sf-blue");
      if (selectedOutfit && selectedOutfit === index + 1) {
        el.classList.remove("border-transparent");
        el.classList.add(borderColor);
      } else {
        el.classList.add("border-transparent");
      }
    });
  }

  initializeOutfitGrid(character) {
    const gridContainer = document.getElementById("outfit-grid");
    const indicator = document.getElementById("outfit-player-indicator");

    if (!character) {
      gridContainer.innerHTML = "";
      indicator.textContent = "Select a character to see outfits";
      return;
    }

    const activePlayer = this.characterGrid.activePlayer;
    const colorClass = `text-${this.getPlayerColor(activePlayer)}`;

    let playerText = "";
    if (!this.gameState.humanVsLlm) {
      playerText = activePlayer === "p1" ? "LLM 1" : "LLM 2";
    } else {
      playerText = activePlayer === "p1" ? "YOU" : "LLM";
    }

    indicator.innerHTML = `<span class="${colorClass}">${playerText}</span> - ${character} Outfits`;

    gridContainer.innerHTML = "";

    for (let i = 0; i < this.numOutfitsPerCharacter; i++) {
      const outfit = this.createOutfitBox(character, i);
      gridContainer.appendChild(outfit);
    }

    this.updateOutfitBorders();
  }

  getPlayerColor(player) {
    return player === "p1" ? "sf-red" : "sf-blue";
  }

  resetSelections() {
    this.characterGrid = {
      activePlayer: "p1",
      p1: { selected: false, character: null, outfit: 1 },
      p2: { selected: false, character: null, outfit: 1 },
    };

    this.currentCharacter = null;

    const p1Img = document.querySelector("#p1-selected-portrait img");
    const p2Img = document.querySelector("#p2-selected-portrait img");

    p1Img.src = "";
    p1Img.classList.add("hidden");
    p2Img.src = "";
    p2Img.classList.add("hidden");

    document.getElementById("p1-selected-name").textContent = "-";
    document.getElementById("p2-selected-name").textContent = "-";

    this.gameState.player1 = { character: null, outfit: 1, superArt: 1 };
    this.gameState.player2 = { character: null, outfit: 1, superArt: 1 };
    this.gameState.difficulty = 1;

    document.getElementById("super-art-select-p1").value = "1";
    document.getElementById("super-art-select-p2").value = "1";

    document.getElementById("combos-list").innerHTML = "";
    document.getElementById("super-arts-list").innerHTML = "";

    document.getElementById("difficulty-slider").value = "1";
    document.getElementById("difficulty-label").textContent = "Very Easy";

    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    this.initializeOutfitGrid(null);
    this.updateGamepadSections(true);
  }

  // ui element creation

  createSelectable(type, params) {
    const { character, index, imageSrc, imageAlt, labelText, onClick } = params;

    const isPortrait = type === "portrait";
    const element = this.createImageBox({
      className: isPortrait
        ? "relative w-full aspect-square bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200"
        : "relative size-24 bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200 mx-auto",
      imageSrc,
      imageAlt,
      imageClassName: isPortrait
        ? "relative size-full object-contain rounded-lg"
        : "relative size-full object-contain bg-sf-dark rounded-lg",
    });

    if (isPortrait) {
      element.dataset.character = character;
      element.dataset.index = index;
    } else {
      element.dataset.outfit = index;
    }

    const label = document.createElement("div");
    label.className =
      "absolute bottom-0 left-0 right-0 p-1 text-center font-bold text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg";
    label.textContent = labelText;
    element.appendChild(label);

    element.addEventListener("mouseenter", () => {
      if (
        !element.classList.contains("border-sf-red") &&
        !element.classList.contains("border-sf-blue")
      ) {
        element.classList.remove("border-transparent");
        const currentBorderColor = `border-${this.getPlayerColor(
          this.characterGrid.activePlayer
        )}`;
        element.classList.add(currentBorderColor);
        AudioManager.playSound(this.soundFiles.HOVER);
      }
    });

    element.addEventListener("mouseleave", () => {
      const isSelected = isPortrait
        ? this.characterGrid[this.characterGrid.activePlayer].character ===
          character
        : this.characterGrid[this.characterGrid.activePlayer].outfit ===
          index + 1;

      if (!isSelected) {
        element.classList.remove("border-sf-red", "border-sf-blue");
        element.classList.add("border-transparent");
      }

      if (isPortrait) this.updateCharacterBorders();
    });

    element.addEventListener("click", () => {
      onClick();
      AudioManager.playSound(this.soundFiles.CLICK);
    });

    return element;
  }

  createOutfitBox(character, index) {
    const outfit = this.createSelectable("outfit", {
      character,
      index,
      imageSrc: `/outfits/${character}/${index}.png`,
      imageAlt: `Outfit ${index + 1}`,
      labelText: `${index + 1}`,
      onClick: () => this.selectOutfit(this.characterGrid.activePlayer, index),
    });

    if (!outfit.id) {
      outfit.id = `outfit-${character.toLowerCase()}-${index}`;
    }

    return outfit;
  }

  createPortrait(character, index) {
    const portrait = this.createSelectable("portrait", {
      character,
      index,
      imageSrc: `/portraits/${character.toLowerCase()}.png`,
      imageAlt: character,
      labelText: character,
      onClick: () =>
        this.selectCharacter(this.characterGrid.activePlayer, character),
    });

    if (!portrait.id) {
      portrait.id = `character-portrait-${character.toLowerCase()}`;
    }

    return portrait;
  }

  createImageBox({ className, imageSrc, imageAlt, imageClassName }) {
    const box = document.createElement("div");
    box.className = className;

    const placeholder = document.createElement("div");
    placeholder.className = "absolute inset-0 loading-placeholder rounded-lg";
    box.appendChild(placeholder);

    const img = document.createElement("img");
    img.src = imageSrc;
    img.alt = imageAlt;
    img.className =
      imageClassName + " opacity-0 transition-opacity duration-300";

    img.addEventListener(
      "load",
      () => {
        img.classList.remove("opacity-0");
        img.classList.add("opacity-100");
        placeholder.remove();
      },
      { once: true }
    );

    img.addEventListener(
      "error",
      () => {
        img.classList.remove("opacity-0");
        img.classList.add("opacity-100");
        placeholder.innerHTML =
          '<div class="flex items-center justify-center h-full text-sf-red">?</div>';
      },
      { once: true }
    );

    box.appendChild(img);
    return box;
  }

  cleanup() {
    GamepadManager.stopPolling();
    WebSocketManager.close();

    if (this.capcomTimeout) {
      clearTimeout(this.capcomTimeout);
      this.capcomTimeout = null;
    }

    AudioManager.stopAll();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new StreetFighterGame();
});
