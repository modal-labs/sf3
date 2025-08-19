import { byId, $ } from "./utils.js";
import { GameState } from "./gameState.js";
import { AudioManager } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { InputController } from "./inputController.js";
import { MovesDisplay } from "./movesEngine.js";
import { GamepadUINavigator } from "./gamepadUINavigator.js";
import { SOUND_KEYS } from "./constants.js";

const createUIController = () => {
  const setupPlayerToggle = () => {
    const playerToggle = byId("player-toggle");
    if (!playerToggle) return;

    playerToggle.addEventListener("click", () => {
      const isHumanVsLlm = GameState.toggleGameMode();

      const playerIcon = byId("player-icon");
      if (playerIcon) {
        playerIcon.src = isHumanVsLlm ? "/icons/human.png" : "/icons/llm.png";
      }

      const p1Label = $("#p1-selection-box h2");
      const p2Label = $("#p2-selection-box h2");

      if (p1Label) {
        p1Label.textContent = isHumanVsLlm ? "YOU" : "LLM 1";
      }
      if (p2Label) {
        p2Label.textContent = isHumanVsLlm ? "LLM" : "LLM 2";
      }

      updateHelpIconVisibility();
      AudioManager.playSound(SOUND_KEYS.CLICK);
      GamepadUINavigator.updateGamepadSections(true);
    });

    playerToggle.addEventListener("mouseenter", () => {
      AudioManager.playSound(SOUND_KEYS.HOVER);
    });
  };

  const setupDifficultySlider = () => {
    const slider = byId("difficulty-slider");
    const description = byId("difficulty-description");

    if (!slider || !description) return;

    const descriptions = [
      "No combos or super arts",
      "Combos enabled, no super arts",
      "All moves available",
    ];

    const updateDescription = () => {
      const value = parseInt(slider.value);
      description.textContent = descriptions[value];

      description.classList.remove(
        "text-sf-green",
        "text-sf-blue",
        "text-sf-red"
      );
      if (value === 0) description.classList.add("text-sf-green");
      else if (value === 1) description.classList.add("text-sf-blue");
      else description.classList.add("text-sf-red");
    };

    slider.addEventListener("input", updateDescription);
    slider.addEventListener("change", () => {
      AudioManager.playSound(SOUND_KEYS.CLICK);
    });

    slider.addEventListener("mouseenter", () => {
      AudioManager.playSound(SOUND_KEYS.HOVER);
    });

    updateDescription();
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

        const state = GameState.get();
        InputController.updateMovesList(
          state.currentCharacter,
          state.playerDirection,
          parseInt(superArtP1.value)
        );
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
    if (!state.humanVsLlm) {
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
      const response = await fetch("/api/extra-moves");
      const data = await response.json();

      InputController.setExtraMoves(data.combos, data.special_moves);

      const state = GameState.get();
      InputController.updateMovesList(
        state.currentCharacter,
        state.playerDirection,
        state.player1.superArt
      );

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
    setupPlayerToggle();
    setupOptionsPanel();
    setupHelpOverlay();
    setupHoverSounds();
    loadExtraMovesDisplay();

    GameState.subscribe((changeType, data) => {
      if (changeType === "playerCharacterChange" && data.player === "p1") {
        updateCombosDisplay(data.character);
        updateSuperArtsDisplay(data.character);

        const state = GameState.get();
        GameState.updateProperty("currentCharacter", data.character);
        InputController.updateMovesList(
          data.character,
          state.playerDirection,
          state.player1.superArt
        );
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
