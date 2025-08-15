import { byId, $, $$, setText } from "./utils.js";
import { SOUND_KEYS, GRID } from "./constants.js";
import { MovesEngine, MovesDisplay } from "./movesEngine.js";
import { AudioManager, playHover, playClick } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { WebSocketManager } from "./webSocketManager.js";
import { UIFactory } from "./uiFactory.js";

class StreetFighterGame {
  // init

  constructor() {
    this.initializeState();
    this.initializeConstants();
    this.preloadAllAssets().then(() => {
      this.assetsLoaded = true;
      setText("loading-status", "Connecting to server...");

      AudioManager.init();
      this.initializeUI();
      this.initializeEventListeners();
      this.initializeGamepadManager();
      this.initializeWebSocketManager();
    });

    window.addEventListener("beforeunload", () => this.cleanup());
  }

  initializeState() {
    this.assetsLoaded = false;
    this.capcomTimeout = null;

    this.gameState = {
      humanVsLlm: true,
      player1: { character: null, outfit: 1, superArt: 1 },
      player2: { character: null, outfit: 1, superArt: 1 },
      loaded: false,
      serverReady: false,
      firstFrameReceived: false,
      inTransition: false,
      transitionStartTime: null,
      readyToHideTransition: false,
    };

    this.keyState = {};
    this.inputHistory = [];
    this.movesByLength = {};
    this.combos = {};
    this.specialMoves = {};

    this.gamepadUIState = {
      currentScreen: null,
      currentSection: 0,
      currentElement: 0,
      sections: [],
    };

    this.currentCharacter = null;
    this.playerDirection = "right";
    this.characterGrid = {
      activePlayer: "p1",
      p1: { selected: false, character: "Ryu", outfit: 1 },
      p2: { selected: false, character: "Ken", outfit: 1 },
    };
  }

  initializeConstants() {
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

    this.numOutfitsPerCharacter = 6;
    this.maxInputHistory = 20;

    this.animationDuration = 600;
    this.comboTimeout = 500;
    this.transitionMinDisplayTime = 3000;
    this.coinSoundDuration = 1000;
    this.capcomSoundDuration = 6000;

    this.volume = 0.5;
    this.selectVolume = 0.2;
    this.startSoundVolume = 0.2;
    this.gameplayMusicVolume = 0.2;
    this.transitionSoundVolume = 0.2;
    this.winLoseSoundVolume = 0.2;

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
      "super-art-select",
      "toggle-options-btn",
      "help-overlay-close",
      "controls-help",
    ];
    this.hoverElements = ["modal-link"];

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
        this.updateHelpIconVisibility();
        this.updateGamepadNavVisibility();

        const currentScreen = this.getCurrentScreen();
        if (currentScreen === this.screens.SPLASH) {
          const muteButton = byId("mute-toggle");
          if (muteButton) {
            muteButton.classList.toggle("hidden", connected);
          }
        }
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

  initializeUI() {
    this.initializeCoinScreen();
    this.showScreen(this.screens.COIN);
    this.initializeSplashScreen();
    this.setupPlayerToggle();
    this.initializeCharacterGrid();
    this.selectCharacter("p1", "Ken");
    this.selectCharacter("p2", "Ryu");
    this.initializeOutfitGrid(null);
    this.initializeHelpOverlay();
    this.loadExtraMovesDisplay();
    this.updateControlsDisplay();
    this.updateHelpIconVisibility();
  }

  initializeCoinScreen() {
    const coinBtn = byId("insert-coin-btn");
    if (coinBtn) {
      coinBtn.addEventListener("click", () => {
        coinBtn.disabled = true;

        coinBtn.classList.remove("animate-coin-shine");
        coinBtn.classList.add("animate-coin-insert");

        AudioManager.playSound(SOUND_KEYS.COIN);

        setTimeout(() => {
          this.transitionToSplash();
        }, this.coinSoundDuration);
      });

      coinBtn.addEventListener("mouseenter", () => {
        playHover();
      });
    }
  }

  initializeSplashScreen() {
    const splashScreen = byId("splash-screen");
    if (!splashScreen) return;

    splashScreen.addEventListener("click", (e) => {
      if (splashScreen.classList.contains("hidden")) return;

      if (this.capcomTimeout) {
        clearTimeout(this.capcomTimeout);
        this.capcomTimeout = null;
      }

      if (AudioManager.sounds[SOUND_KEYS.CAPCOM]) {
        AudioManager.sounds[SOUND_KEYS.CAPCOM].pause();
        AudioManager.sounds[SOUND_KEYS.CAPCOM].currentTime = 0;
      }

      this.showScreen(this.screens.SETTINGS);
    });
  }

  initializeHelpOverlay() {
    const helpButton = byId("controls-help");
    const overlay = byId("help-overlay");
    const closeBtn = byId("help-overlay-close");
    if (helpButton && overlay && closeBtn) {
      const openOverlay = () => {
        overlay.classList.remove("hidden");

        this.updateControlsDisplay();
        this.updateGamepadNavVisibility();

        const currentScreen = this.getCurrentScreen();
        const hideExtraMoves =
          currentScreen === this.screens.COIN ||
          currentScreen === this.screens.SPLASH;

        const combosSection = byId("combos-section");
        const superArtsSection = byId("super-arts-section");

        if (
          combosSection &&
          combosSection.parentElement &&
          combosSection.parentElement.parentElement
        )
          combosSection.parentElement.parentElement.classList.toggle(
            "hidden",
            hideExtraMoves
          );
        if (superArtsSection && superArtsSection.parentElement)
          superArtsSection.parentElement.classList.toggle(
            "hidden",
            hideExtraMoves
          );

        playClick();
        GamepadManager.setUIActive(true);
        this.updateGamepadSections(true);
      };
      const closeOverlay = () => {
        overlay.classList.add("hidden");
        playClick();
        GamepadManager.setUIActive(true);
        this.updateGamepadSections(true);
      };
      helpButton.addEventListener("click", openOverlay);
      closeBtn.addEventListener("click", closeOverlay);
    }
  }

  transitionToSplash() {
    if (!byId("coin-screen").classList.contains("hidden")) {
      this.showScreen(this.screens.SPLASH);
      AudioManager.playSound(SOUND_KEYS.CAPCOM);

      this.capcomTimeout = setTimeout(() => {
        this.capcomTimeout = null;
        this.showScreen(this.screens.SETTINGS);
      }, this.capcomSoundDuration);
    }
  }

  setupPlayerToggle() {
    const playerToggle = byId("player-toggle");
    if (playerToggle) {
      playerToggle.addEventListener("click", () => {
        this.gameState.humanVsLlm = !this.gameState.humanVsLlm;

        const playerIcon = byId("player-icon");
        if (this.gameState.humanVsLlm) {
          playerIcon.src = this.staticImages.HUMAN;
        } else {
          playerIcon.src = this.staticImages.LLM;
        }

        const p1Label = $("#p1-selection-box h2");
        const p2Label = $("#p2-selection-box h2");

        if (p1Label) {
          p1Label.textContent = this.gameState.humanVsLlm ? "YOU" : "LLM 1";
        }
        if (p2Label) {
          p2Label.textContent = this.gameState.humanVsLlm ? "LLM" : "LLM 2";
        }

        this.updateHelpIconVisibility();

        const section = this.getCurrentSection();
        let selectedElement = null;
        if (
          section &&
          section.elements &&
          section.elements[this.gamepadUIState.currentElement]
        ) {
          selectedElement =
            section.elements[this.gamepadUIState.currentElement];
        }

        this.updateGamepadSections(true);

        if (selectedElement) {
          const newSection = this.getCurrentSection();
          if (newSection && newSection.elements) {
            const newIndex = newSection.elements.indexOf(selectedElement);
            if (newIndex >= 0) {
              this.gamepadUIState.currentElement = newIndex;
              this.updateGamepadHover();
            }
          }
        }

        playClick();
      });

      playerToggle.addEventListener("mouseenter", () => {
        playHover();
      });
    }
  }

  initializeCharacterGrid() {
    const gridContainer = byId("character-grid");
    gridContainer.innerHTML = "";

    this.characterGrid.onPortraitHover = (character, imageSrc) => {
      const player = this.characterGrid.activePlayer;
      const previewBox = byId(`${player}-selected-portrait`);
      const previewImg = previewBox?.querySelector("img");

      if (previewImg && this.characterGrid[player].character !== character) {
        previewImg.src = imageSrc;
        previewImg.classList.remove("hidden", "opacity-100");
        previewImg.classList.add("opacity-80", "object-contain");
        const nameEl = byId(`${player}-selected-name`);
        if (nameEl) nameEl.textContent = character;
      }
    };

    this.characterGrid.onPortraitLeave = (character) => {
      this.updateCharacterBorders();
      const player = this.characterGrid.activePlayer;
      const selectedChar = this.characterGrid[player].character;

      if (selectedChar !== character) {
        const previewBox = byId(`${player}-selected-portrait`);
        const previewImg = previewBox?.querySelector("img");
        const nameEl = byId(`${player}-selected-name`);

        if (selectedChar) {
          if (previewImg) {
            previewImg.src = `/portraits/${selectedChar.toLowerCase()}.png`;
            previewImg.classList.remove("hidden", "opacity-80");
            previewImg.classList.add("opacity-100", "object-contain");
          }
          if (nameEl) nameEl.textContent = selectedChar;
        } else {
          if (previewImg) {
            previewImg.classList.add("hidden");
            previewImg.classList.remove("opacity-80");
          }
          if (nameEl) nameEl.textContent = "-";
        }
      }
    };

    this.characters.forEach((character, index) => {
      const portrait = UIFactory.createPortrait(
        character,
        index,
        this,
        (player, char) => this.selectCharacter(player, char)
      );
      gridContainer.appendChild(portrait);
    });

    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    const optionsToggle = byId("toggle-options-btn");
    const optionsPanel = byId("options-panel");
    if (optionsToggle && optionsPanel) {
      optionsToggle.addEventListener("click", () => {
        const isHidden = optionsPanel.classList.contains("hidden");
        optionsPanel.classList.toggle("hidden", !isHidden);
        optionsToggle.textContent = isHidden ? "HIDE OPTIONS" : "SHOW OPTIONS";
        playClick();
        this.updateGamepadSections(true);
      });
    }
  }

  async loadExtraMovesDisplay() {
    const elements = {
      combosLoading: byId("combos-loading"),
      superArtsLoading: byId("super-arts-loading"),
      combosList: byId("combos-list"),
      superArtsList: byId("super-arts-list"),
    };

    try {
      const response = await fetch("/api/extra-moves");
      const data = await response.json();
      this.combos = data.combos;
      this.specialMoves = data.special_moves;

      this.movesByLength = MovesEngine.preprocessMoves(
        this.currentCharacter,
        this.specialMoves,
        this.combos,
        this.playerDirection,
        this.gameState.player1.superArt
      );
      this.updateCombosDisplay(this.currentCharacter);
      this.updateSuperArtsDisplay(this.currentCharacter);

      const superArtP1 = byId("super-art-select-p1");
      const superArtP2 = byId("super-art-select-p2");
      if (superArtP1) {
        this.gameState.player1.superArt = parseInt(superArtP1.value);
        superArtP1.addEventListener("change", () => {
          this.gameState.player1.superArt = parseInt(superArtP1.value);
          this.updateSuperArtsDisplay(this.currentCharacter);
          this.movesByLength = MovesEngine.preprocessMoves(
            this.currentCharacter,
            this.specialMoves,
            this.combos,
            this.playerDirection,
            this.gameState.player1.superArt
          );
          playClick();
        });
      }
      if (superArtP2) {
        this.gameState.player2.superArt = parseInt(superArtP2.value);
        superArtP2.addEventListener("change", () => {
          this.gameState.player2.superArt = parseInt(superArtP2.value);
          playClick();
        });
      }

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

  initializeEventListeners() {
    [...this.buttons, ...this.hoverElements].forEach((elemId) => {
      const elem = byId(elemId);
      if (elem) {
        elem.addEventListener("mouseenter", () => playHover());
      }
    });

    byId("start-game-btn").addEventListener("click", () => {
      playClick();
      this.startGame();
    });
    byId("play-again-btn").addEventListener("click", () => {
      playClick();
      this.resetSelections();
      this.showScreen(this.screens.SETTINGS);
    });
    byId("error-back-btn").addEventListener("click", () => {
      playClick();
      this.showScreen(this.screens.SETTINGS);
    });

    const handleKeyEvent = (e, isDown) => {
      if (!this.gameState.loaded || !this.gameState.humanVsLlm) return;

      this.keyState[e.code] = isDown;
      const action = this.getActionFromKeys();
      this.handleActionFromInput(action);
      e.preventDefault();
    };

    document.addEventListener("keydown", (e) => handleKeyEvent(e, true));
    document.addEventListener("keyup", (e) => handleKeyEvent(e, false));

    ["p1", "p2"].forEach((player) => {
      byId(`${player}-selected-portrait`).addEventListener("click", () => {
        this.switchActivePlayer(player);
        playClick();
      });
    });
  }

  // input handlers

  handleGamepadUIAction(inputX, inputY, buttons) {
    this.updateGamepadSections();

    const currentScreen = this.getCurrentScreen();
    if (currentScreen === this.screens.SPLASH && buttons.a) {
      const splashScreen = byId("splash-screen");
      if (splashScreen) {
        splashScreen.click();
      }
      return;
    }

    if (!this.gamepadUIState.sections.length) return;

    if (currentScreen === this.screens.SETTINGS) {
      if (buttons.lb) {
        this.changeGamepadSection(-1);
        return;
      } else if (buttons.rb) {
        this.changeGamepadSection(1);
        return;
      }
    }

    if (buttons.a) {
      this.handleGamepadSelect();
      return;
    }

    if (inputX !== 0 || inputY !== 0) {
      this.handleGamepadNavigation(inputX, inputY);
    }
  }

  getCurrentSection() {
    return this.gamepadUIState.sections[this.gamepadUIState.currentSection];
  }

  announceHover() {
    this.updateGamepadHover();
    playHover();
  }

  moveCursor(index) {
    this.gamepadUIState.currentElement = index;
    this.announceHover();
  }

  stepCursor(delta) {
    const section = this.getCurrentSection();
    if (!section || !section.elements || !section.elements.length) return;
    const len = section.elements.length;
    const next = (this.gamepadUIState.currentElement + delta + len) % len;
    this.moveCursor(next);
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
          { elements: this.getSimpleScreenElements(["#insert-coin-btn"]) },
        ];
        break;
      case this.screens.SPLASH:
        this.gamepadUIState.sections = [];
        break;
      case this.screens.SETTINGS:
        const topNavElements = [];

        topNavElements.push("#start-game-btn");

        const controlsHelp = byId("controls-help");
        if (controlsHelp && !controlsHelp.classList.contains("hidden")) {
          topNavElements.push("#controls-help");
        }

        const playerToggle = byId("player-toggle");
        if (playerToggle && !playerToggle.classList.contains("hidden")) {
          topNavElements.push("#player-toggle");
        }

        topNavElements.push("#mute-toggle");

        const mainElements = [];

        mainElements.push("#p1-selected-portrait");
        mainElements.push("#p2-selected-portrait");

        const characterGridElements = this.getCharacterGridElements();
        mainElements.push(...characterGridElements);

        mainElements.push("#toggle-options-btn");

        const optionsPanel = byId("options-panel");
        if (optionsPanel && !optionsPanel.classList.contains("hidden")) {
          mainElements.push("#super-art-select-p1");
          mainElements.push("#super-art-select-p2");

          const outfitElements = this.getOutfitElements();
          mainElements.push(...outfitElements);
        }

        this.gamepadUIState.sections = [
          { elements: topNavElements, name: "top-nav" },
          {
            elements: mainElements,
            name: "main-area",
            special: "settings-main",
          },
        ];
        break;
      case this.screens.WIN:
        if (!this.gameState.humanVsLlm) {
          this.gamepadUIState.sections = [
            {
              elements: ["#play-again-btn", "#mute-toggle"],
              name: "win-controls",
            },
          ];
        } else {
          this.gamepadUIState.sections = [
            { elements: this.getSimpleScreenElements(["#play-again-btn"]) },
          ];
        }
        break;
      case this.screens.ERROR:
        if (!this.gameState.humanVsLlm) {
          this.gamepadUIState.sections = [
            {
              elements: ["#error-back-btn", "#mute-toggle"],
              name: "error-controls",
            },
          ];
        } else {
          this.gamepadUIState.sections = [
            { elements: this.getSimpleScreenElements(["#error-back-btn"]) },
          ];
        }
        break;
      case this.screens.LOADING:
        if (!this.gameState.humanVsLlm) {
          this.gamepadUIState.sections = [
            { elements: ["#mute-toggle"], name: "loading-controls" },
          ];
        } else {
          this.gamepadUIState.sections = [
            { elements: this.getSimpleScreenElements([]) },
          ];
        }
        break;
      case this.screens.GAME:
        if (!this.gameState.humanVsLlm) {
          this.gamepadUIState.sections = [
            { elements: ["#mute-toggle"], name: "game-controls" },
          ];
        } else {
          this.gamepadUIState.sections = [];
        }
        break;
    }

    const helpOverlay = byId("help-overlay");
    if (helpOverlay && !helpOverlay.classList.contains("hidden")) {
      this.gamepadUIState.currentScreen = "HELP";
      this.gamepadUIState.sections = [{ elements: ["#help-overlay-close"] }];
    }

    this.gamepadUIState.sections = this.gamepadUIState.sections.filter(
      (section) => section.elements && section.elements.length > 0
    );

    switch (currentScreen) {
      case this.screens.COIN:
        this.gamepadUIState.currentSection = 0;
        this.gamepadUIState.currentElement = this.findElementIndex(
          "#insert-coin-btn",
          0
        );
        break;
      case this.screens.SPLASH:
        this.gamepadUIState.currentSection = 0;
        break;
      case this.screens.SETTINGS:
        this.gamepadUIState.currentSection = 0;
        const topNavSection = this.gamepadUIState.sections[0];
        if (topNavSection && topNavSection.elements) {
          const startGameIdx =
            topNavSection.elements.indexOf("#start-game-btn");
          this.gamepadUIState.currentElement =
            startGameIdx >= 0 ? startGameIdx : 0;
        }
        break;
      case this.screens.WIN:
        this.gamepadUIState.currentSection = 0;
        this.gamepadUIState.currentElement = 0;
        break;
      case this.screens.ERROR:
        this.gamepadUIState.currentSection = 0;
        this.gamepadUIState.currentElement = 0;
        break;
      case this.screens.LOADING:
        this.gamepadUIState.currentSection = 0;
        this.gamepadUIState.currentElement = 0;
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
    const portraits = $$("#character-grid > div");
    return Array.from(portraits).map(
      (el) => `#${el.id || this.generateElementId(el)}`
    );
  }

  getOutfitElements() {
    const outfitPanel = byId("outfit-selection");
    const optionsPanel = byId("options-panel");
    if (
      !outfitPanel ||
      (optionsPanel && optionsPanel.classList.contains("hidden"))
    ) {
      return [];
    }
    const outfits = $$("#outfit-grid > div");
    return Array.from(outfits).map(
      (el) => `#${el.id || this.generateElementId(el)}`
    );
  }

  getSimpleScreenElements(mainButtons = []) {
    const elements = [];

    elements.push(...mainButtons);

    const controlsHelp = byId("controls-help");
    if (controlsHelp && !controlsHelp.classList.contains("hidden")) {
      elements.push("#controls-help");
    }

    const playerToggle = byId("player-toggle");
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

  findElementIndex(selector, sectionIndex) {
    if (this.gamepadUIState.sections[sectionIndex]) {
      const elements = this.gamepadUIState.sections[sectionIndex].elements;
      const index = elements.indexOf(selector);
      return index >= 0 ? index : 0;
    }
    return 0;
  }

  changeGamepadSection(direction) {
    const numSections = this.gamepadUIState.sections.length;
    if (numSections === 0) return;

    const currentScreen = this.getCurrentScreen();
    if (currentScreen === this.screens.SETTINGS && numSections > 1) {
      this.gamepadUIState.currentSection =
        (this.gamepadUIState.currentSection + direction + numSections) %
        numSections;

      if (this.gamepadUIState.currentSection === 0) {
        const startGameIdx =
          this.gamepadUIState.sections[0].elements.indexOf("#start-game-btn");
        this.gamepadUIState.currentElement =
          startGameIdx >= 0 ? startGameIdx : 0;
      } else {
        this.gamepadUIState.currentElement = 0;
      }
    }

    this.updateGamepadHover();
    AudioManager.playSound(SOUND_KEYS.HOVER);
  }

  handleGamepadNavigation(inputX, inputY) {
    const section = this.getCurrentSection();
    if (!section || !section.elements.length) return;

    const currentScreen = this.getCurrentScreen();

    if (currentScreen !== this.screens.SETTINGS) {
      if (inputY !== 0) this.stepCursor(inputY);
      return;
    }

    if (section.name === "top-nav") {
      if (inputY !== 0) this.stepCursor(inputY);
    } else if (section.special === "settings-main") {
      this.navigateSettingsMain(inputX, inputY, section);
    } else if (section.grid) {
      this.navigateGrid(inputX, inputY, section);
    } else if (section.controls) {
      this.navigateControls(inputX, inputY, section);
    } else {
      this.navigateList(inputX, inputY, section);
    }
  }

  navigateSettingsMain(inputX, inputY, section) {
    const onPlayerBox = this.gamepadUIState.currentElement < 2;
    const characterStartIdx = GRID.START;
    const characterEndIdx = GRID.START + GRID.COUNT;
    const onCharacterGrid =
      this.gamepadUIState.currentElement >= characterStartIdx &&
      this.gamepadUIState.currentElement < characterEndIdx;

    const superArtP1Idx = section.elements.indexOf("#super-art-select-p1");
    const superArtP2Idx = section.elements.indexOf("#super-art-select-p2");
    const onSuperArtSelect =
      superArtP1Idx >= 0 &&
      (this.gamepadUIState.currentElement === superArtP1Idx ||
        this.gamepadUIState.currentElement === superArtP2Idx);

    const outfitStartIdx = superArtP2Idx >= 0 ? superArtP2Idx + 1 : -1;
    const onOutfits =
      outfitStartIdx >= 0 &&
      this.gamepadUIState.currentElement >= outfitStartIdx &&
      section.elements[this.gamepadUIState.currentElement] &&
      section.elements[this.gamepadUIState.currentElement].includes("outfit-");

    if (onPlayerBox) {
      if (inputX !== 0) {
        this.moveCursor(inputX > 0 ? 1 : 0);
      }
      if (inputY > 0) {
        this.moveCursor(characterStartIdx);
      }
      if (inputY < 0) {
        this.moveCursor(section.elements.length - 1);
      }
    } else if (onCharacterGrid) {
      const gridIndex = this.gamepadUIState.currentElement - GRID.START;
      const cols = GRID.COLS;
      const currentRow = Math.floor(gridIndex / cols);
      const currentCol = gridIndex % cols;

      let newRow = currentRow;
      let newCol = currentCol;

      if (inputY < 0) {
        if (currentRow === 0) {
          this.moveCursor(currentCol < 5 ? 0 : 1);
          return;
        } else {
          newRow = currentRow - 1;
        }
      } else if (inputY > 0) {
        if (currentRow === 1 || gridIndex >= GRID.COLS) {
          this.moveCursor(characterEndIdx);
          return;
        } else {
          newRow = currentRow + 1;
        }
      }

      if (inputX < 0) {
        const maxCol = currentRow === 1 ? 8 : cols - 1;
        newCol = currentCol === 0 ? maxCol : currentCol - 1;
      } else if (inputX > 0) {
        const maxCol = currentRow === 1 ? 8 : cols - 1;
        newCol = currentCol === maxCol ? 0 : currentCol + 1;
      }

      const newGridIndex = newRow * cols + newCol;
      if (newGridIndex < 19) {
        this.moveCursor(characterStartIdx + newGridIndex);
      }
    } else if (onSuperArtSelect) {
      if (inputX !== 0) {
        this.moveCursor(inputX > 0 ? superArtP2Idx : superArtP1Idx);
      }
      if (inputY > 0) {
        this.moveCursor(superArtP2Idx + 1);
      }
      if (inputY < 0) {
        this.moveCursor(characterEndIdx);
      }
    } else if (onOutfits) {
      if (inputX !== 0) {
        const outfitEndIdx = section.elements.findIndex(
          (el, idx) => idx > outfitStartIdx && !el.includes("outfit-")
        );
        const lastOutfitIdx =
          outfitEndIdx > 0 ? outfitEndIdx - 1 : section.elements.length - 1;
        const numOutfits = lastOutfitIdx - outfitStartIdx + 1;

        const outfitIndex = this.gamepadUIState.currentElement - outfitStartIdx;
        const newOutfitIndex = (outfitIndex + inputX + numOutfits) % numOutfits;
        this.moveCursor(outfitStartIdx + newOutfitIndex);
      }
      if (inputY < 0) {
        this.moveCursor(superArtP1Idx);
      }
      if (inputY > 0) {
        this.moveCursor(0);
      }
    } else {
      if (inputX !== 0) {
        this.stepCursor(inputX);
      } else if (
        inputY < 0 &&
        this.gamepadUIState.currentElement === characterEndIdx
      ) {
        this.moveCursor(characterEndIdx - 1);
      } else if (inputY !== 0) {
        if (inputY > 0) {
          if (
            this.gamepadUIState.currentElement === characterEndIdx &&
            superArtP1Idx >= 0
          ) {
            this.moveCursor(superArtP1Idx);
          } else if (
            this.gamepadUIState.currentElement ===
            section.elements.length - 1
          ) {
            this.moveCursor(0);
          } else {
            this.moveCursor(this.gamepadUIState.currentElement + 1);
          }
        } else {
          if (this.gamepadUIState.currentElement === characterEndIdx) {
            this.moveCursor(characterEndIdx - 1);
          } else {
            const direction = -1;
            const numElements = section.elements.length;
            this.moveCursor(
              (this.gamepadUIState.currentElement + direction + numElements) %
                numElements
            );
          }
        }
      }
    }
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
    const currentEl = $(section.elements[this.gamepadUIState.currentElement]);

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
    const element = $(elementSelector);

    if (element) {
      if (element.tagName === "SELECT") {
        const currentIndex = element.selectedIndex;
        const nextIndex = (currentIndex + 1) % element.options.length;
        element.selectedIndex = nextIndex;
        element.dispatchEvent(new Event("change"));
        AudioManager.playSound(SOUND_KEYS.CLICK);
      } else {
        element.click();
        AudioManager.playSound(SOUND_KEYS.CLICK);
      }
    }
  }

  updateGamepadHover() {
    const previousHovered = $(".gamepad-hover");
    const wasCharacter = previousHovered?.dataset?.character;

    $$(".gamepad-hover").forEach((el) => {
      el.classList.remove("gamepad-hover");
    });

    if (
      wasCharacter &&
      this.characterGrid &&
      this.characterGrid.onPortraitLeave
    ) {
      this.characterGrid.onPortraitLeave(wasCharacter);
    }

    ["p1", "p2"].forEach((player) => {
      const selectedChar = this.characterGrid[player].character;
      const previewBox = byId(`${player}-selected-portrait`);
      const previewImg = previewBox?.querySelector("img");
      const nameEl = byId(`${player}-selected-name`);

      if (selectedChar) {
        if (previewImg) {
          previewImg.src = `/portraits/${selectedChar.toLowerCase()}.png`;
          previewImg.classList.remove("hidden", "opacity-80");
          previewImg.classList.add("opacity-100", "object-contain");
        }
        if (nameEl) nameEl.textContent = selectedChar;
      } else {
        if (previewImg) {
          previewImg.classList.add("hidden");
          previewImg.classList.remove("opacity-80", "opacity-100");
        }
        if (nameEl) nameEl.textContent = "-";
      }
    });

    if (!GamepadManager.isConnected()) {
      return;
    }

    const section =
      this.gamepadUIState.sections[this.gamepadUIState.currentSection];
    if (section && section.elements[this.gamepadUIState.currentElement]) {
      const element = $(section.elements[this.gamepadUIState.currentElement]);
      if (element) {
        element.classList.add("gamepad-hover");
        element.scrollIntoView({ behavior: "smooth", block: "nearest" });

        if (element.dataset.character) {
          // Trigger the same hover logic as mouse hover
          if (this.characterGrid && this.characterGrid.onPortraitHover) {
            const character = element.dataset.character;
            const imageSrc = `/portraits/${character.toLowerCase()}.png`;
            this.characterGrid.onPortraitHover(character, imageSrc);
          }
        }
      }
    }
  }

  getCurrentScreen() {
    for (const [, screenId] of Object.entries(this.screens)) {
      const el = byId(`${screenId}-screen`);
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

    this.handleActionFromInput(action);
  }

  startGame() {
    const { p1, p2 } = this.characterGrid;

    Object.assign(this.gameState.player1, {
      character: p1.character,
      outfit: p1.outfit,
      superArt: parseInt(byId("super-art-select-p1").value),
    });

    Object.assign(this.gameState.player2, {
      character: p2.character,
      outfit: p2.outfit,
      superArt: parseInt(byId("super-art-select-p2").value),
    });

    AudioManager.play(SOUND_KEYS.START, {
      volume: this.startSoundVolume,
      trackAs: "effect",
    });

    setTimeout(() => {
      this.resetGameState();
      this.showScreen(this.screens.LOADING);
      setText("loading-status", "Starting game...");
      WebSocketManager.send("start_game", {
        humanVsLlm: this.gameState.humanVsLlm,
        player1: this.gameState.player1,
        player2: this.gameState.player2,
        gamepadConnected: GamepadManager.isConnected(),
      });
    }, 10); //  delay to allow sound to play first
  }

  handleActionFromInput(action) {
    WebSocketManager.send("player_action", { action });

    if (action === this.actions.NO_MOVE) return;

    this.inputHistory.push({ action, time: Date.now() });

    if (this.inputHistory.length > this.maxInputHistory) {
      this.inputHistory.shift();
    }

    const { match, history } = MovesEngine.detectExtra(
      this.inputHistory,
      this.comboTimeout,
      this.movesByLength
    );
    this.inputHistory = history;
    if (match) {
      WebSocketManager.send("player_action", {
        action: match.type === "super_art" ? 18 : 19,
        [match.type === "super_art" ? "super_art" : "combo"]: match.name,
      });
    }
  }

  // ws

  resetGameState() {
    this.gameState.loaded = false;
    this.gameState.serverReady = false;
    this.gameState.firstFrameReceived = false;
    this.gameState.inTransition = false;
    this.gameState.transitionStartTime = null;
    this.gameState.readyToHideTransition = false;
    this.keyState = {};
    this.inputHistory = [];

    const status = byId("canvas-loading-status");
    status.textContent = "Loading game...";

    const overlay = byId("canvas-loading-overlay");
    overlay.classList.remove("hidden");

    const canvas = byId("game-canvas");
    canvas.classList.add("hidden");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
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
    const overlay = byId("canvas-loading-overlay");

    if (!this.gameState.firstFrameReceived) {
      this.gameState.firstFrameReceived = true;
      overlay.classList.add("hidden");
      const canvas = byId("game-canvas");
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

    const canvas = byId("game-canvas");
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
    const startButton = byId("start-game-btn");

    if (!this.gameState.serverReady) {
      this.gameState.serverReady = true;
      startButton.disabled = false;
      startButton.textContent = "START GAME";
      startButton.classList.remove("opacity-50");
      console.log("Server ready");
    }

    switch (data.status) {
      case "initializing":
        setText("loading-status", "Starting game...");
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

        const winnerEl = byId("winner-text");
        winnerEl.textContent = `Winner: ${displayWinner}`;
        winnerEl.classList.toggle(
          "text-sf-blue",
          winner === "YOU" || winner === "LLM 1" || winner === "P1"
        );
        winnerEl.classList.toggle(
          "text-sf-red",
          winner === "LLM" || winner === "LLM 2" || winner === "P2"
        );

        const winSound =
          !this.gameState.humanVsLlm || winner === "YOU"
            ? SOUND_KEYS.WIN
            : SOUND_KEYS.LOSE;

        AudioManager.play(winSound, {
          volume: this.winLoseSoundVolume,
          trackAs: "winLose",
          onEnd: () => {
            if (
              !document
                .getElementById("win-screen")
                .classList.contains("hidden")
            ) {
              AudioManager.play(SOUND_KEYS.CONTINUE, {
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
    AudioManager.play(SOUND_KEYS.TRANSITION, {
      volume: this.transitionSoundVolume,
      trackAs: "transition",
    });

    const status = byId("canvas-loading-status");

    let message = "";
    if (data.transition_type === "round") {
      message = "Loading next round...";
    } else if (data.transition_type === "game") {
      message = "Determining winner...";
    }
    status.textContent = message;

    const overlay = byId("canvas-loading-overlay");
    overlay.classList.remove("hidden");

    const canvas = byId("game-canvas");
    canvas.classList.add("hidden");

    const header = byId("game-header");
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
      !byId("game-screen").classList.contains("hidden")
    ) {
      AudioManager.play(this.gameState.player1.character, {
        volume: this.gameplayMusicVolume,
        loop: true,
        trackAs: "select",
      });

      const header = byId("game-header");
      if (header) {
        header.classList.add("hidden");
      }
    }

    const canvas = byId("game-canvas");
    canvas.classList.remove("hidden");

    const overlay = byId("canvas-loading-overlay");
    overlay.classList.add("hidden");
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

  // misc

  showScreen(screenId) {
    Object.values(this.screens).forEach((screen) => {
      const el = byId(`${screen}-screen`);
      if (el) {
        el.classList.toggle("hidden", screen !== screenId);
      }
    });

    const isLoading = screenId === this.screens.LOADING;
    const hideAll = isLoading && !this.assetsLoaded;

    const header = byId("game-header");
    if (header) {
      const hideHeader =
        screenId === this.screens.SPLASH ||
        screenId === this.screens.GAME ||
        hideAll;
      header.classList.toggle("hidden", hideHeader);
    }

    const isGameplay = screenId === this.screens.GAME;

    const isMinimalScreen =
      screenId === this.screens.WIN ||
      screenId === this.screens.ERROR ||
      (screenId === this.screens.LOADING && this.assetsLoaded);

    const playerToggle = byId("player-toggle");
    if (playerToggle) {
      const showPlayerToggle = screenId === this.screens.SETTINGS;
      playerToggle.classList.toggle("hidden", !showPlayerToggle || isGameplay);
    }

    const muteButton = byId("mute-toggle");
    if (muteButton) {
      const hideMute =
        hideAll ||
        (isGameplay && this.gameState.humanVsLlm) ||
        (isMinimalScreen && this.gameState.humanVsLlm) ||
        (screenId === this.screens.SPLASH && GamepadManager.isConnected());
      muteButton.classList.toggle("hidden", hideMute);
    }

    const gamepadStatus = byId("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.toggle("hidden", hideAll);
    }

    this.updateHelpIconVisibility(screenId);

    if (screenId === this.screens.SETTINGS) {
      AudioManager.play(SOUND_KEYS.SELECT, {
        volume: this.selectVolume,
        loop: true,
        trackAs: "select",
      });
      AudioManager.stopTrack("winLose");

      if (this.combos && this.specialMoves) {
        const defaultCharacter = this.characterGrid.p1.character || "Ken";
        this.currentCharacter = defaultCharacter;
        this.updateCombosDisplay(defaultCharacter);
        this.updateSuperArtsDisplay(defaultCharacter);
        this.initializeOutfitGrid(defaultCharacter);
      }
    } else {
      AudioManager.stopTrack("select");
      if (screenId !== this.screens.WIN) {
        AudioManager.stopTrack("winLose");
      }
    }

    if (screenId === this.screens.COIN) {
      const coinBtn = byId("insert-coin-btn");
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
    setText("error-details", new Date().toLocaleString() + "\n" + message);
    this.showScreen(this.screens.ERROR);
  }

  updateControlsDisplay() {
    const onPad = GamepadManager.isConnected();
    const controls = {
      "movement-display": onPad ? "Left Stick / D-Pad" : "WASD / Arrow Keys",
      "lp-display": onPad ? "A/X" : "J",
      "mp-display": onPad ? "B/◯" : "K",
      "hp-display": onPad ? "RB/R1" : "L",
      "lk-display": onPad ? "X/□" : "U",
      "mk-display": onPad ? "Y/△" : "I",
      "hk-display": onPad ? "LB/L1" : "O",
      "lplk-display": onPad ? "A/X + X/□" : "J + U",
      "mpmk-display": onPad ? "B/◯ + Y/△" : "K + I",
      "hphk-display": onPad ? "RB/R1 + LB/L1" : "L + O",
    };

    Object.entries(controls).forEach(([id, text]) => {
      const element = byId(id);
      if (element) element.textContent = text;
    });
  }

  updateCombosDisplay(character) {
    const combosList = byId("combos-list");

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

    combosList.innerHTML = MovesDisplay.generateMovesHTML(
      moves,
      this.idxToMove,
      GamepadManager.isConnected()
    );
  }

  updateSuperArtsDisplay(character) {
    const superArtsList = byId("super-arts-list");
    const selectedEl = byId(
      this.characterGrid.activePlayer === "p1"
        ? "super-art-select-p1"
        : "super-art-select-p2"
    );
    const selectedSuperArt = selectedEl ? selectedEl.value : "1";

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
          name: MovesDisplay.getSpecialMoveDisplayName(moveKey),
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
            name: MovesDisplay.getSpecialMoveDisplayName(moveKey),
            sequence: moveData[this.playerDirection],
          });
        }
      }
    }

    superArtsList.innerHTML = MovesDisplay.generateMovesHTML(
      moves,
      this.idxToMove,
      GamepadManager.isConnected()
    );
  }

  switchActivePlayer(player) {
    this.characterGrid.activePlayer = player;
    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    const selectedCharacter = this.characterGrid[player].character;
    if (selectedCharacter) {
      this.initializeOutfitGrid(selectedCharacter);
    } else {
      const gridContainer = byId("outfit-grid");
      const indicator = byId("outfit-player-indicator");

      gridContainer.innerHTML = "";
      indicator.textContent = "Select a character to see outfits";
    }
    this.updateGamepadSections(true);
  }

  updatePlayerBoxes() {
    const p1Portrait = byId("p1-selected-portrait");
    const p2Portrait = byId("p2-selected-portrait");
    const activeColor = this.getPlayerColor(this.characterGrid.activePlayer);

    p1Portrait.className = `portrait-box border-${
      this.characterGrid.activePlayer === "p1" ? activeColor : "transparent"
    }`;
    p2Portrait.className = `portrait-box border-${
      this.characterGrid.activePlayer === "p2" ? activeColor : "transparent"
    }`;
  }

  updateCharacterBorders() {
    const portraits = $$("#character-grid > div");

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

    const portraits = $$("#character-grid > div");
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
        this.movesByLength = MovesEngine.preprocessMoves(
          this.currentCharacter,
          this.specialMoves,
          this.combos,
          this.playerDirection,
          this.gameState.player1.superArt
        );
      }

      this.updatePlayerPortrait(player, character);
      this.updateCharacterBorders();
      this.initializeOutfitGrid(character);
      this.updateGamepadSections(true);
    }, this.animationDuration);
  }

  updatePlayerPortrait(player, character) {
    const portraitImg = $(`#${player}-selected-portrait img`);
    const nameEl = byId(`${player}-selected-name`);
    const portraitBox = byId(`${player}-selected-portrait`);

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
    portraitImg.classList.remove("hidden", "opacity-80");
    portraitImg.classList.add("object-contain", "opacity-100");
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

    const outfits = $$("#outfit-grid > div");
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
    const outfits = $$("#outfit-grid > div");
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
    const gridContainer = byId("outfit-grid");
    const indicator = byId("outfit-player-indicator");

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
      const outfit = UIFactory.createOutfitBox(
        character,
        i,
        this,
        (player, index) => this.selectOutfit(player, index)
      );
      gridContainer.appendChild(outfit);
    }

    this.updateOutfitBorders();
  }

  getPlayerColor(player) {
    return player === "p1" ? "sf-blue" : "sf-red";
  }

  resetSelections() {
    this.characterGrid = {
      activePlayer: "p1",
      p1: { selected: false, character: "Ryu", outfit: 1 },
      p2: { selected: false, character: "Ken", outfit: 1 },
    };

    this.currentCharacter = null;

    const p1Img = $("#p1-selected-portrait img");
    const p2Img = $("#p2-selected-portrait img");

    p1Img.src = "";
    p1Img.classList.add("hidden");
    p2Img.src = "";
    p2Img.classList.add("hidden");

    setText("p1-selected-name", "-");
    setText("p2-selected-name", "-");

    this.gameState.player1 = { character: null, outfit: 1, superArt: 1 };
    this.gameState.player2 = { character: null, outfit: 1, superArt: 1 };

    const sa1 = byId("super-art-select-p1");
    if (sa1) sa1.value = "1";
    const sa2 = byId("super-art-select-p2");
    if (sa2) sa2.value = "1";

    byId("combos-list").innerHTML = "";
    byId("super-arts-list").innerHTML = "";

    this.selectCharacter("p1", "Ken");
    this.selectCharacter("p2", "Ryu");
    this.updatePlayerBoxes();
    this.updateCharacterBorders();

    this.initializeOutfitGrid(null);
    this.updateGamepadSections(true);
  }

  updateHelpIconVisibility(screenId = null) {
    const controlsHelp = byId("controls-help");
    if (!controlsHelp) return;

    const currentScreen = screenId || this.getCurrentScreen();

    if (!this.gameState.humanVsLlm) {
      controlsHelp.classList.add("hidden");
      return;
    }

    const isLoading = currentScreen === this.screens.LOADING;
    const hideAll = isLoading && !this.assetsLoaded;

    const isEarlyScreen =
      currentScreen === this.screens.COIN ||
      currentScreen === this.screens.SPLASH;

    const isGameplay = currentScreen === this.screens.GAME;

    const isMinimalScreen =
      currentScreen === this.screens.WIN ||
      currentScreen === this.screens.ERROR ||
      (currentScreen === this.screens.LOADING && this.assetsLoaded);

    controlsHelp.classList.toggle(
      "hidden",
      hideAll || isEarlyScreen || isGameplay || isMinimalScreen
    );
  }

  updateGamepadNavVisibility() {
    const gamepadNavSection = byId("gamepad-nav-section");
    if (gamepadNavSection) {
      const showGamepadNav = GamepadManager.isConnected();
      gamepadNavSection.classList.toggle("hidden", !showGamepadNav);
    }
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
