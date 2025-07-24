class StreetFighterGame {
  // init

  constructor() {
    this.initializeState();
    this.initializeConstants();
    this.initializeAudio();
    this.showScreen(this.screens.LOADING);
    document.getElementById("loading-status").textContent = "Loading assets...";
    this.preloadAllAssets().then(() => {
      this.initializeUI();
      this.initializeEventListeners();
      this.initializeWebSocket();
    });
  }

  // init state

  initializeState() {
    // per session
    this.socket = null;

    // per game
    this.gameSettings = {
      difficulty: 1,
      player1: { character: "Ken", outfit: 1, superArt: 1 },
      player2: { character: "Ken", outfit: 1, superArt: 1 },
    };
    this.gameLoaded = false;
    this.serverReady = false;
    this.firstFrameReceived = false;
    this.inTransition = false;
    this.transitionStartTime = null;
    this.readyToHideTransition = false;

    // keys
    this.keyState = {};
    this.inputHistory = [];
    this.movesByLength = {};
    this.combos = {};
    this.specialMoves = {};

    // character select
    this.currentCharacter = "Ken";
    this.playerDirection = "right";
    this.characterGrid = {
      activePlayer: "p1",
      p1: { selected: false, character: null, outfit: null },
      p2: { selected: false, character: null, outfit: null },
    };
  }

  // init const

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
      { name: "No-Move", display: "" },
      { name: "Left", display: "←" },
      { name: "Left+Up", display: "↖" },
      { name: "Up", display: "↑" },
      { name: "Up+Right", display: "↗" },
      { name: "Right", display: "→" },
      { name: "Right+Down", display: "↘" },
      { name: "Down", display: "↓" },
      { name: "Down+Left", display: "↙" },
      { name: "Low Punch", display: "J" },
      { name: "Medium Punch", display: "K" },
      { name: "High Punch", display: "L" },
      { name: "Low Kick", display: "U" },
      { name: "Medium Kick", display: "I" },
      { name: "High Kick", display: "O" },
      { name: "Low Punch+Low Kick", display: "J + U" },
      { name: "Medium Punch+Medium Kick", display: "K + I" },
      { name: "High Punch+High Kick", display: "L + O" },
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

    // ux
    this.animationDuration = 600;
    this.comboTimeout = 500; // ms
    this.transitionMinDisplayTime = 3000; // ms
    this.coinSoundDuration = 1000;
    this.capcomSoundDuration = 6000; // ms

    this.volume = 0.5;
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

  // init audio

  initializeAudio() {
    this.audio = {
      sounds: {},
      enabled: localStorage.getItem("audioEnabled") === "true",
      volume: 0.5,
      selectSound: null,
      transitionSound: null,
      winLoseSound: null,
      currentEffects: [],
    };

    this.setupAudioPlayback();
    this.setupMuteButton();
  }

  async preloadAllAssets() {
    const totalAssets = [];

    Object.entries(this.soundFiles).forEach(([, filename]) => {
      // not using key since we get like `this.soundFiles.CLICK`
      const audio = new Audio(`/sounds/${filename}.mp3`);
      audio.volume = this.audio.volume;
      audio.preload = "auto";
      this.audio.sounds[filename] = audio;
      totalAssets.push(
        new Promise((resolve) => {
          audio.addEventListener("canplaythrough", resolve, { once: true });
          audio.addEventListener("error", resolve, { once: true });
        })
      );
    });

    Object.entries(this.gameplayMusicMap).forEach(([key, filename]) => {
      const audio = new Audio(`/sounds/gameplay/${filename}.mp3`);
      audio.volume = this.audio.volume;
      audio.preload = "auto";
      this.audio.sounds[key] = audio;
      totalAssets.push(
        new Promise((resolve) => {
          audio.addEventListener("canplaythrough", resolve, { once: true });
          audio.addEventListener("error", resolve, { once: true });
        })
      );
    });

    this.characters.forEach((character) => {
      const img = new Image();
      img.src = `/portraits/${character.toLowerCase()}.png`;
      totalAssets.push(
        new Promise((resolve) => {
          img.onload = resolve;
          img.onerror = resolve;
        })
      );
    });

    Object.entries(this.staticImages).forEach(([, src]) => {
      const img = new Image();
      img.src = src;
      totalAssets.push(
        new Promise((resolve) => {
          img.onload = resolve;
          img.onerror = resolve;
        })
      );
    });

    await Promise.all(totalAssets);
  }

  setupAudioPlayback() {
    this.playAudio = (soundName, options = {}) => {
      const {
        volume = 1,
        loop = false,
        trackAs = "effect",
        onEnd = null,
      } = options;

      const sound = this.audio.sounds[soundName];
      if (!sound) {
        console.warn(`No sound found for: ${soundName}`);
        return;
      }

      if (trackAs === "select") this.stopSelectSound();
      else if (trackAs === "transition") this.stopTransitionSound();
      else if (trackAs === "winLose") this.stopWinLoseSound();

      sound.currentTime = 0;
      sound.loop = loop;
      sound.volume = this.audio.enabled ? this.audio.volume * volume : 0;

      if (trackAs === "select") {
        this.audio.selectSound = sound;
      } else if (trackAs === "transition") {
        this.audio.transitionSound = sound;
      } else if (trackAs === "winLose") {
        this.audio.winLoseSound = sound;
      } else {
        sound._volumeMultiplier = volume;
        this.audio.currentEffects.push(sound);
      }

      const onEndHandler = () => {
        if (trackAs === "effect") {
          const index = this.audio.currentEffects.indexOf(sound);
          if (index > -1) this.audio.currentEffects.splice(index, 1);
          delete sound._volumeMultiplier;
        } else if (trackAs === "winLose") {
          this.audio.winLoseSound = null;
        }

        if (onEnd) onEnd();
        sound.removeEventListener("ended", onEndHandler);
      };

      if (trackAs === "effect" || trackAs === "winLose" || onEnd) {
        sound.addEventListener("ended", onEndHandler);
      }

      sound.play().catch(() => {
        if (trackAs === "effect") {
          const index = this.audio.currentEffects.indexOf(sound);
          if (index > -1) this.audio.currentEffects.splice(index, 1);
          delete sound._volumeMultiplier;
        } else if (trackAs === "winLose") {
          this.audio.winLoseSound = null;
        }
        if (trackAs === "effect" || trackAs === "winLose" || onEnd) {
          sound.removeEventListener("ended", onEndHandler);
        }
      });
    };

    this.playSound = (soundName) => {
      this.playAudio(soundName, { trackAs: "effect" });
    };

    this.playSelectSound = (soundName) => {
      this.playAudio(soundName, {
        volume: this.selectVolume,
        loop: true,
        trackAs: "select",
      });
    };

    this.playWinLoseSound = (soundName) => {
      this.playAudio(soundName, {
        volume: this.winLoseSoundVolume,
        trackAs: "winLose",
        onEnd: () => {
          if (
            !document.getElementById("win-screen").classList.contains("hidden")
          ) {
            this.playSelectSound(this.soundFiles.CONTINUE);
          }
        },
      });
    };

    this.playTransitionSound = () => {
      this.playAudio(this.soundFiles.TRANSITION, {
        volume: this.transitionSoundVolume,
        trackAs: "transition",
      });
    };

    this.playGameplayMusic = (character) => {
      this.playAudio(character, {
        volume: this.gameplayMusicVolume,
        loop: true,
        trackAs: "select",
      });
    };

    this.playStartSound = () => {
      this.playAudio(this.soundFiles.START, {
        volume: this.startSoundVolume,
        trackAs: "effect",
      });
    };

    this.stopSelectSound = () => {
      if (this.audio.selectSound) {
        this.audio.selectSound.pause();
        this.audio.selectSound.currentTime = 0;
        this.audio.selectSound.loop = false;
        this.audio.selectSound = null;
      }
    };

    this.stopWinLoseSound = () => {
      if (this.audio.winLoseSound) {
        this.audio.winLoseSound.pause();
        this.audio.winLoseSound.currentTime = 0;
        this.audio.winLoseSound = null;
      }
    };

    this.stopTransitionSound = () => {
      if (this.audio.transitionSound) {
        this.audio.transitionSound.pause();
        this.audio.transitionSound.currentTime = 0;
        this.audio.transitionSound = null;
      }
    };

    this.toggleMute = () => {
      this.audio.enabled = !this.audio.enabled;
      localStorage.setItem("audioEnabled", this.audio.enabled);

      const muteIcon = document.getElementById("mute-icon");
      if (muteIcon) {
        muteIcon.src = this.audio.enabled
          ? this.staticImages.UNMUTE
          : this.staticImages.MUTE;
      }

      if (this.audio.selectSound) {
        this.audio.selectSound.volume = this.audio.enabled
          ? this.audio.volume * this.selectVolume
          : 0;
      }

      if (this.audio.transitionSound) {
        this.audio.transitionSound.volume = this.audio.enabled
          ? this.audio.volume * this.transitionSoundVolume
          : 0;
      }

      if (this.audio.winLoseSound) {
        this.audio.winLoseSound.volume = this.audio.enabled
          ? this.audio.volume * this.winLoseSoundVolume
          : 0;
      }

      this.audio.currentEffects.forEach((sound) => {
        const multiplier = sound._volumeMultiplier || 1;
        sound.volume = this.audio.enabled ? this.audio.volume * multiplier : 0;
      });
    };
  }

  setupMuteButton() {
    const muteButton = document.getElementById("mute-toggle");
    if (muteButton) {
      muteButton.addEventListener("click", () => {
        this.toggleMute();
        this.playSound(this.soundFiles.CLICK);
      });

      muteButton.addEventListener("mouseenter", () => {
        this.playSound(this.soundFiles.HOVER);
      });

      const muteIcon = document.getElementById("mute-icon");
      if (muteIcon) {
        muteIcon.src = this.audio.enabled
          ? this.staticImages.UNMUTE
          : this.staticImages.MUTE;
      }
    }
  }

  // init ui

  initializeUI() {
    // in the order that user sees them
    this.initializeCoinScreen();
    this.showScreen(this.screens.COIN);
    this.initializeCharacterGrid();
    this.loadExtraMovesDisplay();
    this.initializeDifficultySlider();
  }

  initializeCoinScreen() {
    const coinBtn = document.getElementById("insert-coin-btn");
    if (coinBtn) {
      coinBtn.addEventListener("click", () => {
        coinBtn.disabled = true;

        coinBtn.classList.remove("animate-coin-shine");
        coinBtn.classList.add("animate-coin-insert");

        this.playSound(this.soundFiles.COIN);

        setTimeout(() => {
          this.transitionToSplash();
        }, this.coinSoundDuration);
      });

      coinBtn.addEventListener("mouseenter", () => {
        this.playSound(this.soundFiles.HOVER);
      });
    }
  }

  transitionToSplash() {
    if (
      document.getElementById("coin-screen").classList.contains("hidden") ===
      false
    ) {
      this.showScreen(this.screens.SPLASH);
      this.playSound(this.soundFiles.CAPCOM);

      setTimeout(() => {
        this.showScreen(this.screens.SETTINGS);
      }, this.capcomSoundDuration);
    }
  }

  initializeCharacterGrid() {
    const gridContainer = document.getElementById("character-grid");
    gridContainer.innerHTML = "";

    this.characters.forEach((character, index) => {
      const portrait = this.createPortrait(character, index, "character");
      gridContainer.appendChild(portrait);
    });

    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    const p2SuperArt = document.getElementById("super-art-select-p2");
    if (p2SuperArt) {
      p2SuperArt.addEventListener("change", () =>
        this.playSound(this.soundFiles.CLICK)
      );
    }
  }

  initializeDifficultySlider() {
    const slider = document.getElementById("difficulty-slider");
    const label = document.getElementById("difficulty-label");

    slider.addEventListener("input", (e) => {
      const value = parseInt(e.target.value);
      this.gameSettings.difficulty = value;
      label.textContent = this.difficultyLabels[value];
      this.playSound(this.soundFiles.CLICK);
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
      this.gameSettings.player1.superArt = parseInt(superArtSelect.value);

      superArtSelect.addEventListener("change", () => {
        this.gameSettings.player1.superArt = parseInt(superArtSelect.value);
        this.updateSuperArtsDisplay(this.currentCharacter);
        this.preprocessMoves();
        this.playSound(this.soundFiles.CLICK);
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
    this.buttons.forEach((btnId) => {
      const btn = document.getElementById(btnId);
      if (btn) {
        btn.addEventListener("mouseenter", () =>
          this.playSound(this.soundFiles.HOVER)
        );
      }
    });

    this.hoverElements.forEach((elemId) => {
      const elem = document.getElementById(elemId);
      if (elem) {
        elem.addEventListener("mouseenter", () =>
          this.playSound(this.soundFiles.HOVER)
        );
      }
    });

    document.getElementById("start-game-btn").addEventListener("click", () => {
      this.playSound(this.soundFiles.CLICK);
      this.startGame();
    });
    document.getElementById("play-again-btn").addEventListener("click", () => {
      this.playSound(this.soundFiles.CLICK);
      this.resetSelections();
      this.showScreen(this.screens.SETTINGS);
    });
    document.getElementById("error-back-btn").addEventListener("click", () => {
      this.playSound(this.soundFiles.CLICK);
      this.showScreen(this.screens.SETTINGS);
    });

    const handleKeyEvent = (e, isDown) => {
      if (!this.gameLoaded) return;

      this.keyState[e.code] = isDown;
      const action = this.getActionFromKeys();

      this.sendMessage("player_action", {
        action,
        move: this.idxToMove[action].name,
      });

      if (action !== this.actions.NO_MOVE) {
        this.inputHistory.push({ action, time: Date.now() });

        if (this.inputHistory.length > this.maxInputHistory) {
          this.inputHistory.shift();
        }

        const detectedMove = this.detectExtra();
        if (detectedMove) {
          this.sendMessage("player_action", {
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
          this.playSound(this.soundFiles.CLICK);
        });
    });
  }

  startGame() {
    const { p1, p2 } = this.characterGrid;

    if (!p1.selected || !p2.selected) {
      alert(
        "Both you and the LLM must have characters selected before starting!"
      );
      return;
    }

    if (!p1.outfit || !p2.outfit) {
      alert("Both you and the LLM must have outfits selected before starting!");
      return;
    }

    Object.assign(this.gameSettings.player1, {
      character: p1.character,
      outfit: p1.outfit,
      superArt: parseInt(document.getElementById("super-art-select-p1").value),
    });

    Object.assign(this.gameSettings.player2, {
      character: p2.character,
      outfit: p2.outfit,
      superArt: parseInt(document.getElementById("super-art-select-p2").value),
    });

    this.gameSettings.difficulty = parseInt(
      document.getElementById("difficulty-slider").value
    );

    this.playStartSound();

    setTimeout(() => {
      this.resetGameState();
      this.showScreen(this.screens.LOADING);
      document.getElementById("loading-status").textContent =
        "Starting game...";
      this.sendMessage("start_game", this.gameSettings);
    }, 10);
  }

  resetGameState() {
    this.gameLoaded = false;
    this.serverReady = false;
    this.firstFrameReceived = false;
    this.inTransition = false;
    this.transitionStartTime = null;
    this.readyToHideTransition = false;
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

  initializeWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.socket = new WebSocket(wsUrl);
    const startButton = document.getElementById("start-game-btn");

    this.socket.onopen = () => console.log("Connected to server");

    this.socket.onclose = () => {
      console.log("Disconnected from server");
      if (!this.serverReady) {
        startButton.textContent = "Connection Lost";
        startButton.disabled = true;
        startButton.classList.add("opacity-50");
      }
    };

    this.socket.onerror = (event) => {
      console.error("WebSocket connection error", event);
      this.showError("WebSocket connection error");
      if (!this.serverReady) {
        startButton.textContent = "Connection Error";
        startButton.disabled = true;
        startButton.classList.add("opacity-50");
      }
    };

    this.socket.onmessage = (event) => this.handleWebSocketMessage(event);

    startButton.disabled = true;
    startButton.classList.add("opacity-50");
  }

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

    if (!this.firstFrameReceived) {
      this.firstFrameReceived = true;
      overlay.classList.add("hidden");
      const canvas = document.getElementById("game-canvas");
      canvas.classList.remove("hidden");
    }

    if (this.inTransition) {
      this.readyToHideTransition = true;

      const elapsedTime = Date.now() - this.transitionStartTime;
      if (elapsedTime >= this.transitionMinDisplayTime) {
        this.hideTransitionOverlay();
      } else {
        const remainingTime = this.transitionMinDisplayTime - elapsedTime;
        setTimeout(() => {
          if (this.readyToHideTransition && this.inTransition) {
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

    if (!this.serverReady) {
      this.serverReady = true;
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
        this.gameLoaded = true;
        this.showScreen(this.screens.GAME);
        this.playGameplayMusic(this.gameSettings.player1.character);
        break;
      case "finished":
        this.gameLoaded = false;

        this.stopSelectSound();

        const winner = data.winner || "Unknown";
        document.getElementById(
          "winner-text"
        ).textContent = `Winner: ${winner}`;

        if (winner === "You") {
          this.playWinLoseSound(this.soundFiles.WIN);
        } else {
          this.playWinLoseSound(this.soundFiles.LOSE);
        }

        this.showScreen(this.screens.WIN);
        break;
      case "error":
        this.gameLoaded = false;
        this.stopSelectSound();
        this.showError(data.error || "Unknown game error");
        break;
    }
  }

  handleTransition(data) {
    this.inTransition = true;
    this.transitionStartTime = Date.now();
    this.readyToHideTransition = false;

    this.stopSelectSound();
    this.playTransitionSound();

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
      if (this.readyToHideTransition && this.inTransition) {
        this.hideTransitionOverlay();
      }
    }, this.transitionMinDisplayTime);
  }

  hideTransitionOverlay() {
    this.inTransition = false;
    this.transitionStartTime = null;
    this.readyToHideTransition = false;

    this.stopTransitionSound();

    if (
      this.gameLoaded &&
      document.getElementById("game-display").classList.contains("hidden") ===
        false
    ) {
      this.playGameplayMusic(this.gameSettings.player1.character);

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

  sendMessage(type, data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(
        JSON.stringify({
          type: type,
          data: data,
        })
      );
    }
  }

  // helper fns
  // input handling

  preprocessMoves() {
    this.movesByLength = {};

    if (!this.currentCharacter) return;

    const characterMoves = this.specialMoves[this.currentCharacter];
    const characterCombos = this.combos[this.currentCharacter];
    const selectedSuperArt = this.gameSettings.player1.superArt;

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
    const screens = [
      { id: "coin-screen", show: screenId === this.screens.COIN },
      { id: "splash-screen", show: screenId === this.screens.SPLASH },
      { id: "settings-screen", show: screenId === this.screens.SETTINGS },
      { id: "loading-screen", show: screenId === this.screens.LOADING },
      { id: "game-display", show: screenId === this.screens.GAME },
      { id: "win-screen", show: screenId === this.screens.WIN },
      { id: "error-screen", show: screenId === this.screens.ERROR },
    ];
    screens.forEach((screen) => {
      const el = document.getElementById(screen.id);
      if (el) {
        if (screen.show) {
          el.classList.remove("hidden");
        } else {
          el.classList.add("hidden");
        }
      }
    });

    const header = document.getElementById("game-header");
    if (header) {
      if (screenId === this.screens.GAME || screenId === this.screens.SPLASH) {
        header.classList.add("hidden");
      } else {
        header.classList.remove("hidden");
      }
    }

    if (screenId === this.screens.SETTINGS) {
      this.playSelectSound(this.soundFiles.SELECT);
      this.stopWinLoseSound();
    } else {
      this.stopSelectSound();
      if (screenId !== this.screens.WIN) {
        this.stopWinLoseSound();
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
  }

  showError(message) {
    document.getElementById("error-details").textContent =
      new Date().toLocaleString() + "\n" + message;
    this.showScreen(this.screens.ERROR);
  }

  // character move display

  updateCombosDisplay(character) {
    const combosList = document.getElementById("combos-list");
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
        const symbol = this.idxToMove[action].display;
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
      document.getElementById("outfit-selection").classList.add("hidden");
    }
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

      if (player === "p1") {
        this.currentCharacter = character;
        this.updateCombosDisplay(character);
        this.updateSuperArtsDisplay(character);
        this.preprocessMoves();
      }

      this.updatePlayerPortrait(player, character);
      this.updateCharacterBorders();
      this.initializeOutfitGrid(character);
      document.getElementById("outfit-selection").classList.remove("hidden");
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

    const activePlayer = this.characterGrid.activePlayer;
    const colorClass = `text-${this.getPlayerColor(activePlayer)}`;
    indicator.innerHTML = `<span class="${colorClass}">${this.getPlayerText(
      activePlayer
    )}</span> - ${character} Outfits`;

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

  getPlayerText(player) {
    return player === "p1" ? "You" : "LLM";
  }

  resetSelections() {
    this.characterGrid = {
      activePlayer: "p1",
      p1: { selected: false, character: null, outfit: null },
      p2: { selected: false, character: null, outfit: null },
    };

    this.currentCharacter = "Ken";

    const p1Img = document.querySelector("#p1-selected-portrait img");
    const p2Img = document.querySelector("#p2-selected-portrait img");

    p1Img.src = "";
    p1Img.classList.add("hidden");
    p2Img.src = "";
    p2Img.classList.add("hidden");

    document.getElementById("p1-selected-name").textContent = "-";
    document.getElementById("p2-selected-name").textContent = "-";

    document.getElementById("outfit-selection").classList.add("hidden");

    document.getElementById("super-art-select-p1").value = "1";
    document.getElementById("super-art-select-p2").value = "1";
    this.gameSettings.player1.superArt = 1;
    this.gameSettings.player2.superArt = 1;

    if (this.currentCharacter && this.combos && this.specialMoves) {
      this.updateCombosDisplay(this.currentCharacter);
      this.updateSuperArtsDisplay(this.currentCharacter);
      this.preprocessMoves();
    }

    document.getElementById("difficulty-slider").value = "1";
    document.getElementById("difficulty-label").textContent = "Very Easy";
    this.gameSettings.difficulty = 1;

    this.updatePlayerBoxes();
    this.updateCharacterBorders();
  }

  // ui element creation

  createOutfitBox(character, index) {
    const outfit = this.createImageBox({
      className:
        "relative size-24 bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200 mx-auto",
      imageSrc: `/outfits/${character}/${index}.png`,
      imageAlt: `Outfit ${index + 1}`,
      imageClassName: "relative size-full object-contain bg-sf-dark rounded-lg",
    });

    outfit.dataset.outfit = index;

    const label = document.createElement("div");
    label.className =
      "absolute bottom-0 left-0 right-0 p-1 text-center font-bold text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg";
    label.textContent = `${index + 1}`;
    outfit.appendChild(label);

    const borderColor = `border-${this.getPlayerColor(
      this.characterGrid.activePlayer
    )}`;

    outfit.addEventListener("mouseenter", () => {
      if (
        !outfit.classList.contains("border-sf-red") &&
        !outfit.classList.contains("border-sf-blue")
      ) {
        outfit.classList.remove("border-transparent");
        outfit.classList.add(borderColor);
        this.playSound(this.soundFiles.HOVER);
      }
    });

    outfit.addEventListener("mouseleave", () => {
      const activePlayer = this.characterGrid.activePlayer;
      const isSelected = this.characterGrid[activePlayer].outfit === index + 1;
      if (!isSelected) {
        outfit.classList.remove("border-sf-red", "border-sf-blue");
        outfit.classList.add("border-transparent");
      }
    });

    outfit.addEventListener("click", () => {
      this.selectOutfit(this.characterGrid.activePlayer, index);
      this.playSound(this.soundFiles.CLICK);
    });

    return outfit;
  }

  createPortrait(character, index, type) {
    const portrait = this.createImageBox({
      className:
        "relative w-full aspect-square bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200",
      imageSrc: `/portraits/${character.toLowerCase()}.png`,
      imageAlt: character,
      imageClassName: "relative w-full h-full object-contain rounded-lg",
    });

    portrait.dataset.character = character;
    portrait.dataset.index = index;

    const nameLabel = document.createElement("div");
    nameLabel.className =
      "absolute bottom-0 left-0 right-0 p-1 text-center font-bold text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg";
    nameLabel.textContent = character;
    portrait.appendChild(nameLabel);

    portrait.addEventListener("mouseenter", () => {
      if (type === "character") {
        const borderColor = `border-${this.getPlayerColor(
          this.characterGrid.activePlayer
        )}`;
        portrait.classList.remove("border-transparent");
        portrait.classList.add(borderColor);
        this.playSound(this.soundFiles.HOVER);
      }
    });

    portrait.addEventListener("mouseleave", () => {
      portrait.classList.remove("border-sf-red", "border-sf-blue");
      portrait.classList.add("border-transparent");
      this.updateCharacterBorders();
    });

    portrait.addEventListener("click", () => {
      this.selectCharacter(this.characterGrid.activePlayer, character);
      this.playSound(this.soundFiles.CLICK);
    });

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
}

document.addEventListener("DOMContentLoaded", () => {
  new StreetFighterGame();
});
