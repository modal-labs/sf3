import { byId } from "./utils.js";
import { GameState } from "./gameState.js";
import { AudioManager } from "./audioManager.js";
import { AssetLoader } from "./assetLoader.js";
import { GamepadManager } from "./gamepadManager.js";
import { InputController } from "./inputController.js";
import { MovesDisplay } from "./movesEngine.js";
import { GamepadUINavigator } from "./gamepadUINavigator.js";
import {
  getParticipantLabel,
  getParticipantsForSeat,
  isCpuParticipant,
  isHumanParticipant,
} from "./participantOptions.js";
import { SOUND_KEYS } from "./constants.js";

const DIFFICULTY_MODES = {
  model: {
    stateKey: "modelDifficulty",
    min: 0,
    max: 2,
    defaultValue: 2,
    labels: ["Basic", "Advanced", "Expert"],
    descriptions: [
      "No combos or super arts",
      "Combos enabled, no super arts",
      "All moves available",
    ],
    descriptionColors: ["text-sf-green", "text-sf-blue", "text-sf-red"],
  },
  cpu: {
    stateKey: "cpuDifficulty",
    min: 1,
    max: 8,
    defaultValue: 8,
    labels: ["1", "CPU", "8"],
    descriptionFor: (value) => `Arcade CPU level ${value} of 8`,
    descriptionColors: ["text-sf-beige"],
  },
};

const createUIController = () => {
  const populateParticipantSelect = (select, seat) => {
    select.innerHTML = "";
    getParticipantsForSeat(seat).forEach(({ participant, label }) => {
      const option = document.createElement("option");
      option.value = participant;
      option.textContent = label;
      select.appendChild(option);
    });
  };

  const getActiveDifficultyMode = () => {
    const state = GameState.get();
    return isCpuParticipant(state.player2Participant) ? "cpu" : "model";
  };

  const syncDifficultySlider = () => {
    const slider = byId("difficulty-slider");
    const description = byId("difficulty-description");
    const labelMin = byId("difficulty-label-min");
    const labelMid = byId("difficulty-label-mid");
    const labelMax = byId("difficulty-label-max");
    if (!slider || !description || !labelMin || !labelMid || !labelMax) return;

    const modeKey = getActiveDifficultyMode();
    const mode = DIFFICULTY_MODES[modeKey];
    const state = GameState.get();
    const value = state[mode.stateKey] ?? mode.defaultValue;

    slider.min = String(mode.min);
    slider.max = String(mode.max);
    slider.value = String(value);
    labelMin.textContent = mode.labels[0];
    labelMid.textContent = mode.labels[1];
    labelMax.textContent = mode.labels[2];

    if (mode.descriptions) {
      description.textContent = mode.descriptions[value];
    } else {
      description.textContent = mode.descriptionFor(value);
    }

    description.classList.remove(
      "text-sf-green",
      "text-sf-blue",
      "text-sf-red",
      "text-sf-beige"
    );
    const color =
      mode.descriptionColors[value] ??
      mode.descriptionColors[mode.descriptionColors.length - 1];
    description.classList.add(color);
  };

  const syncParticipantUI = () => {
    const state = GameState.get();
    const p1Select = byId("participant-select-p1");
    const p2Select = byId("participant-select-p2");
    const p1Label = byId("participant-label-p1");
    const p2Label = byId("participant-label-p2");

    if (p1Select) p1Select.value = state.player1Participant;
    if (p2Select) p2Select.value = state.player2Participant;
    if (p1Label) p1Label.textContent = getParticipantLabel(state.player1Participant);
    if (p2Label) p2Label.textContent = getParticipantLabel(state.player2Participant);
    syncDifficultySlider();
  };

  const setupParticipantSelectors = () => {
    const p1Select = byId("participant-select-p1");
    const p2Select = byId("participant-select-p2");
    if (!p1Select || !p2Select) return;

    populateParticipantSelect(p1Select, "P1");
    populateParticipantSelect(p2Select, "P2");

    p1Select.addEventListener("change", () => {
      GameState.setPlayer1Participant(p1Select.value);
      updateHelpIconVisibility();
      AudioManager.playSound(SOUND_KEYS.CLICK);
      GamepadUINavigator.updateGamepadSections(true);
    });
    p2Select.addEventListener("change", () => {
      GameState.setPlayer2Participant(p2Select.value);
      AudioManager.playSound(SOUND_KEYS.CLICK);
      GamepadUINavigator.updateGamepadSections(true);
    });

    syncParticipantUI();
  };

  const setupDifficultySlider = () => {
    const slider = byId("difficulty-slider");
    if (!slider) return;

    const onInput = () => {
      const mode = DIFFICULTY_MODES[getActiveDifficultyMode()];
      const value = parseInt(slider.value, 10);
      GameState.updateProperty(mode.stateKey, value);
      syncDifficultySlider();
    };

    slider.addEventListener("input", onInput);
    slider.addEventListener("change", () => {
      AudioManager.playSound(SOUND_KEYS.CLICK);
    });
    slider.addEventListener("mouseenter", () => {
      AudioManager.playSound(SOUND_KEYS.HOVER);
    });

    syncDifficultySlider();
  };

  const setupOptionsPanel = () => {
    const optionsToggle = byId("toggle-options-btn");
    const optionsPanel = byId("options-panel");

    if (optionsToggle && optionsPanel) {
      optionsToggle.addEventListener("click", () => {
        const isHidden = optionsPanel.classList.contains("hidden");
        optionsPanel.classList.toggle("hidden", !isHidden);
        optionsToggle.textContent = isHidden ? "HIDE OPTIONS" : "SHOW OPTIONS";
        AudioManager.playSound(SOUND_KEYS.CLICK);
        GamepadUINavigator.updateGamepadSections(true);
      });
    }

    setupDifficultySlider();

    const superArtP1 = byId("super-art-select-p1");
    const superArtP2 = byId("super-art-select-p2");

    if (superArtP1) {
      GameState.updateProperty("player1.superArt", parseInt(superArtP1.value));
      superArtP1.addEventListener("change", () => {
        GameState.updateProperty(
          "player1.superArt",
          parseInt(superArtP1.value)
        );
        updateSuperArtsDisplay();
        AudioManager.playSound(SOUND_KEYS.CLICK);
      });
    }

    if (superArtP2) {
      GameState.updateProperty("player2.superArt", parseInt(superArtP2.value));
      superArtP2.addEventListener("change", () => {
        GameState.updateProperty(
          "player2.superArt",
          parseInt(superArtP2.value)
        );
        AudioManager.playSound(SOUND_KEYS.CLICK);
      });
    }
  };

  const setupHelpOverlay = () => {
    const helpButton = byId("controls-help");
    const overlay = byId("help-overlay");
    const closeBtn = byId("help-overlay-close");

    if (!helpButton || !overlay || !closeBtn) return;

    let savedNavPosition = null;

    const openOverlay = () => {
      const navState = GameState.getGamepadUIState();
      savedNavPosition = {
        section: navState.currentSection,
        element: navState.currentElement,
      };

      overlay.classList.remove("hidden");
      updateControlsDisplay();
      updateGamepadNavVisibility();

      const currentScreen = GameState.getCurrentScreen();
      const hideExtraMoves =
        currentScreen === "coin" || currentScreen === "splash";

      const combosSection = byId("combos-section");
      const superArtsSection = byId("super-arts-section");

      if (combosSection?.parentElement?.parentElement) {
        combosSection.parentElement.parentElement.classList.toggle(
          "hidden",
          hideExtraMoves
        );
      }
      if (superArtsSection?.parentElement) {
        superArtsSection.parentElement.classList.toggle(
          "hidden",
          hideExtraMoves
        );
      }

      AudioManager.playSound(SOUND_KEYS.CLICK);
      GamepadManager.setUIActive(true);
      GamepadUINavigator.updateGamepadSections(true);
    };

    const closeOverlay = () => {
      overlay.classList.add("hidden");
      AudioManager.playSound(SOUND_KEYS.CLICK);
      GamepadManager.setUIActive(true);
      GamepadUINavigator.updateGamepadSections(true);

      if (savedNavPosition) {
        GamepadUINavigator.restoreNavPosition(savedNavPosition);
        savedNavPosition = null;
      }
    };

    helpButton.addEventListener("click", openOverlay);
    closeBtn.addEventListener("click", closeOverlay);
  };

  const updateControlsDisplay = () => {
    const onPad = GamepadManager.isConnected();
    const controls = {
      "movement-display": onPad ? "Left Stick / D-Pad" : "WASD / Arrow Keys",
      "lp-display": onPad ? "A" : "J",
      "mp-display": onPad ? "B" : "K",
      "hp-display": onPad ? "RB" : "L",
      "lk-display": onPad ? "X" : "U",
      "mk-display": onPad ? "Y" : "I",
      "hk-display": onPad ? "LB" : "O",
      "lplk-display": onPad ? "A + X" : "J + U",
      "mpmk-display": onPad ? "B + Y" : "K + I",
      "hphk-display": onPad ? "RB + LB" : "L + O",
      "pause-display": onPad ? "Esc / Click / Start/Menu" : "Esc / Click",
    };

    Object.entries(controls).forEach(([id, text]) => {
      const element = byId(id);
      if (element) element.textContent = text;
    });
  };

  const updateCombosDisplay = (character) => {
    const combosList = byId("combos-list");
    if (!combosList) return;

    if (!character || !InputController.getCombos()[character]) {
      combosList.innerHTML =
        '<p class="text-sf-beige-dark">Select a character to see combos</p>';
      return;
    }

    const state = GameState.get();
    const combos = InputController.getCombos()[character];

    const moves = Object.entries(combos).map(([name, data]) => ({
      name,
      sequence: data[state.playerDirection],
    }));

    combosList.innerHTML = MovesDisplay.generateMovesHTML(
      moves,
      InputController.idxToMove,
      GamepadManager.isConnected()
    );
  };

  const updateSuperArtsDisplay = (character) => {
    const superArtsList = byId("super-arts-list");
    if (!superArtsList) return;

    const state = GameState.get();
    character = character || state.currentCharacter;

    if (!character || !InputController.getSpecialMoves()[character]) {
      superArtsList.innerHTML =
        '<p class="text-sf-beige-dark">Select a character to see super arts</p>';
      return;
    }

    const selectedEl = byId(
      state.characterGrid.activePlayer === "p1"
        ? "super-art-select-p1"
        : "super-art-select-p2"
    );
    const selectedSuperArt = selectedEl ? selectedEl.value : "1";

    const characterMoves = InputController.getSpecialMoves()[character];
    const moves = [];

    for (const [moveKey, moveData] of Object.entries(characterMoves)) {
      if (moveKey.startsWith(`${selectedSuperArt} `)) {
        moves.push({
          name: MovesDisplay.getSpecialMoveDisplayName(moveKey),
          sequence: moveData[state.playerDirection],
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
            sequence: moveData[state.playerDirection],
          });
        }
      }
    }

    superArtsList.innerHTML = MovesDisplay.generateMovesHTML(
      moves,
      InputController.idxToMove,
      GamepadManager.isConnected()
    );
  };

  const updateHelpIconVisibility = (screenId) => {
    const controlsHelp = byId("controls-help");
    if (!controlsHelp) return;

    const state = GameState.get();
    if (!isHumanParticipant(state.player1Participant)) {
      controlsHelp.classList.add("hidden");
      return;
    }

    const currentScreen = screenId || state.currentScreen;
    const isLoading = currentScreen === "loading";
    const hideAll = isLoading && !state.assetsLoaded;
    const isEarlyScreen =
      currentScreen === "coin" || currentScreen === "splash";
    const isGameplay = currentScreen === "game";
    const isMinimalScreen =
      currentScreen === "win" ||
      currentScreen === "error" ||
      (currentScreen === "loading" && state.assetsLoaded);

    controlsHelp.classList.toggle(
      "hidden",
      hideAll || isEarlyScreen || isGameplay || isMinimalScreen
    );
  };

  const updateGamepadNavVisibility = () => {
    const gamepadNavSection = byId("gamepad-nav-section");
    if (gamepadNavSection) {
      const showGamepadNav = GamepadManager.isConnected();
      gamepadNavSection.classList.toggle("hidden", !showGamepadNav);
    }
  };

  const loadExtraMovesDisplay = async () => {
    const elements = {
      combosLoading: byId("combos-loading"),
      superArtsLoading: byId("super-arts-loading"),
      combosList: byId("combos-list"),
      superArtsList: byId("super-arts-list"),
    };

    if (!elements.combosLoading || !elements.superArtsLoading) return;

    try {
      const data = await AssetLoader.loadExtraMoves();

      InputController.setExtraMoves(data.combos, data.specialMoves);

      const state = GameState.get();
      updateCombosDisplay(state.currentCharacter);
      updateSuperArtsDisplay(state.currentCharacter);

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
  };

  const setupHoverSounds = () => {
    const buttons = [
      "start-game-btn",
      "play-again-btn",
      "error-back-btn",
      "p1-selected-portrait",
      "p2-selected-portrait",
      "participant-select-p1",
      "participant-select-p2",
      "super-art-select",
      "toggle-options-btn",
      "help-overlay-close",
      "controls-help",
      "modal-link",
    ];

    buttons.forEach((elemId) => {
      const elem = byId(elemId);
      if (elem) {
        elem.addEventListener("mouseenter", () =>
          AudioManager.playSound(SOUND_KEYS.HOVER)
        );
      }
    });
  };

  const init = () => {
    setupParticipantSelectors();
    setupOptionsPanel();
    setupHelpOverlay();
    setupHoverSounds();
    loadExtraMovesDisplay();

    GameState.subscribe((changeType, data) => {
      if (changeType === "gameModeChange") {
        syncParticipantUI();
      }
      if (changeType === "playerCharacterChange" && data.player === "p1") {
        updateCombosDisplay(data.character);
        updateSuperArtsDisplay(data.character);

        GameState.updateProperty("currentCharacter", data.character);
      }
    });
  };

  return {
    init,
    updateControlsDisplay,
    updateCombosDisplay,
    updateSuperArtsDisplay,
    updateHelpIconVisibility,
    updateGamepadNavVisibility,
  };
};

export const UIController = createUIController();
