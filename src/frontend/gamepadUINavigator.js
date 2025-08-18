import { byId, $, $$ } from "./utils.js";
import { GameState } from "./gameState.js";
import { AudioManager } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { SOUND_KEYS, GRID } from "./constants.js";

const createGamepadUINavigator = () => {
  const getCurrentSection = () => {
    const state = GameState.getGamepadUIState();
    const sections = state.sections || [];
    return sections[state.currentSection];
  };

  const announceHover = () => {
    updateGamepadHover();
    AudioManager.playSound(SOUND_KEYS.HOVER);
  };

  const moveCursor = (index) => {
    GameState.updateGamepadUIState({ currentElement: index });
    announceHover();
  };

  const stepCursor = (delta) => {
    const section = getCurrentSection();
    if (!section || !section.elements || !section.elements.length) return;
    const state = GameState.getGamepadUIState();
    const len = section.elements.length;
    const next = (state.currentElement + delta + len) % len;
    moveCursor(next);
  };

  const generateElementId = (element) => {
    const id = `gamepad-el-${Math.random().toString(36).substr(2, 9)}`;
    element.id = id;
    return id;
  };

  const getCharacterGridElements = () => {
    const portraits = $$("#character-grid > div");
    return Array.from(portraits).map(
      (el) => `#${el.id || generateElementId(el)}`
    );
  };

  const getOutfitElements = () => {
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
      (el) => `#${el.id || generateElementId(el)}`
    );
  };

  const getSimpleScreenElements = (mainButtons = []) => {
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

    const muteToggle = byId("mute-toggle");
    if (muteToggle && !muteToggle.classList.contains("hidden")) {
      elements.push("#mute-toggle");
    }

    return elements;
  };

  const findElementIndex = (selector, sectionIndex) => {
    const state = GameState.getGamepadUIState();
    if (state.sections[sectionIndex]) {
      const elements = state.sections[sectionIndex].elements;
      const index = elements.indexOf(selector);
      return index >= 0 ? index : 0;
    }
    return 0;
  };

  const updateGamepadSections = (forceUpdate = false) => {
    const currentScreen = GameState.getCurrentScreen();
    const currentUIState = GameState.getGamepadUIState();

    if (!forceUpdate && currentScreen === currentUIState.currentScreen) return;

    const preservePosition =
      forceUpdate && currentScreen === currentUIState.currentScreen;
    const oldSection = preservePosition ? currentUIState.currentSection : 0;
    const oldElement = preservePosition ? currentUIState.currentElement : 0;

    let sections = [];
    let lastSidePanelIndex = currentUIState.lastSidePanelIndex;

    if (currentScreen !== "settings") {
      lastSidePanelIndex = -1;
    }

    switch (currentScreen) {
      case "coin":
        sections = [
          { elements: getSimpleScreenElements(["#insert-coin-btn"]) },
        ];
        break;
      case "splash":
        sections = [];
        break;
      case "settings":
        const settingsElements = [];

        settingsElements.push("#start-game-btn");
        settingsElements.push("#p1-selected-portrait");
        settingsElements.push("#p2-selected-portrait");

        const characterGridElements = getCharacterGridElements();
        settingsElements.push(...characterGridElements);

        settingsElements.push("#toggle-options-btn");

        const controlsHelp = byId("controls-help");
        if (controlsHelp && !controlsHelp.classList.contains("hidden")) {
          settingsElements.push("#controls-help");
        }

        const playerToggle = byId("player-toggle");
        if (playerToggle && !playerToggle.classList.contains("hidden")) {
          settingsElements.push("#player-toggle");
        }

        const muteToggle = byId("mute-toggle");
        if (muteToggle && !muteToggle.classList.contains("hidden")) {
          settingsElements.push("#mute-toggle");
        }

        const optionsPanel = byId("options-panel");
        if (optionsPanel && !optionsPanel.classList.contains("hidden")) {
          settingsElements.push("#super-art-select-p1");
          settingsElements.push("#super-art-select-p2");

          const outfitElements = getOutfitElements();
          settingsElements.push(...outfitElements);
        }

        sections = [
          {
            elements: settingsElements,
            name: "settings",
            special: "settings-linear",
          },
        ];
        break;
      case "win":
        const gameState = GameState.get();
        if (!gameState.humanVsLlm) {
          const winElements = ["#play-again-btn"];
          const muteToggle = byId("mute-toggle");
          if (muteToggle && !muteToggle.classList.contains("hidden")) {
            winElements.push("#mute-toggle");
          }
          sections = [
            {
              elements: winElements,
              name: "win-controls",
            },
          ];
        } else {
          sections = [
            { elements: getSimpleScreenElements(["#play-again-btn"]) },
          ];
        }
        break;
      case "error":
        const errorState = GameState.get();
        if (!errorState.humanVsLlm) {
          const errorElements = ["#error-back-btn"];
          const muteToggle = byId("mute-toggle");
          if (muteToggle && !muteToggle.classList.contains("hidden")) {
            errorElements.push("#mute-toggle");
          }
          sections = [
            {
              elements: errorElements,
              name: "error-controls",
            },
          ];
        } else {
          sections = [
            { elements: getSimpleScreenElements(["#error-back-btn"]) },
          ];
        }
        break;
      case "loading":
        const loadingState = GameState.get();
        if (!loadingState.humanVsLlm) {
          const loadingElements = [];
          const muteToggle = byId("mute-toggle");
          if (muteToggle && !muteToggle.classList.contains("hidden")) {
            loadingElements.push("#mute-toggle");
          }
          sections =
            loadingElements.length > 0
              ? [{ elements: loadingElements, name: "loading-controls" }]
              : [];
        } else {
          sections = [{ elements: getSimpleScreenElements([]) }];
        }
        break;
      case "game":
        const gameplayState = GameState.get();
        if (!gameplayState.humanVsLlm) {
          const gameElements = [];
          const muteToggle = byId("mute-toggle");
          if (muteToggle && !muteToggle.classList.contains("hidden")) {
            gameElements.push("#mute-toggle");
          }
          sections =
            gameElements.length > 0
              ? [{ elements: gameElements, name: "game-controls" }]
              : [];
        } else {
          sections = [];
        }
        break;
    }

    const helpOverlay = byId("help-overlay");
    if (helpOverlay && !helpOverlay.classList.contains("hidden")) {
      sections = [{ elements: ["#help-overlay-close"] }];
      GameState.updateGamepadUIState({
        currentScreen: "HELP",
        sections: sections.filter((s) => s.elements && s.elements.length > 0),
        currentSection: 0,
        currentElement: 0,
        lastSidePanelIndex,
      });
      updateGamepadHover();
      return;
    }

    sections = sections.filter(
      (section) => section.elements && section.elements.length > 0
    );

    let currentSection = 0;
    let currentElement = 0;

    switch (currentScreen) {
      case "coin":
        currentElement = findElementIndex("#insert-coin-btn", 0);
        break;
      case "splash":
        break;
      case "settings":
      case "win":
      case "error":
      case "loading":
        currentElement = 0;
        break;
    }

    if (preservePosition && currentScreen === "settings") {
      const section = sections[0];
      if (section && section.elements && oldElement < section.elements.length) {
        currentElement = oldElement;
      }
    } else if (preservePosition) {
      if (oldSection < sections.length) {
        currentSection = oldSection;
        const section = sections[oldSection];
        if (
          section &&
          section.elements &&
          oldElement < section.elements.length
        ) {
          currentElement = oldElement;
        }
      }
    }

    GameState.updateGamepadUIState({
      currentScreen,
      sections,
      currentSection,
      currentElement,
      lastSidePanelIndex,
    });

    updateGamepadHover();
  };

  const navigateSettingsLinear = (inputX, inputY, section) => {
    const state = GameState.getGamepadUIState();
    const currentEl = section.elements[state.currentElement];

    const startBtnIdx = 0;
    const p1BoxIdx = 1;
    const p2BoxIdx = 2;
    const characterStartIdx = 3;
    const characterEndIdx = characterStartIdx + 19;
    const toggleOptionsIdx = section.elements.indexOf("#toggle-options-btn");
    const controlsHelpIdx = section.elements.indexOf("#controls-help");
    const playerToggleIdx = section.elements.indexOf("#player-toggle");
    const muteToggleIdx = section.elements.indexOf("#mute-toggle");
    const superArtP1Idx = section.elements.indexOf("#super-art-select-p1");
    const superArtP2Idx = section.elements.indexOf("#super-art-select-p2");

    const onStartBtn = state.currentElement === startBtnIdx;
    const onPlayerBox =
      state.currentElement === p1BoxIdx || state.currentElement === p2BoxIdx;
    const onCharacterGrid =
      state.currentElement >= characterStartIdx &&
      state.currentElement < characterEndIdx;
    const onToggleOptions = state.currentElement === toggleOptionsIdx;
    const onSidePanel =
      currentEl === "#controls-help" ||
      currentEl === "#player-toggle" ||
      currentEl === "#mute-toggle";
    const onSuperArt =
      state.currentElement === superArtP1Idx ||
      state.currentElement === superArtP2Idx;
    const onOutfits = currentEl && currentEl.includes("outfit-");

    if (onStartBtn) {
      if (inputY > 0) moveCursor(p1BoxIdx);
      else if (inputY < 0) {
        const firstOutfitIdx = section.elements.findIndex((el) =>
          el.includes("outfit-")
        );
        if (firstOutfitIdx >= 0) {
          moveCursor(firstOutfitIdx + 2);
        } else {
          moveCursor(toggleOptionsIdx);
        }
      }
    } else if (onPlayerBox) {
      if (inputX !== 0) {
        moveCursor(inputX > 0 ? p2BoxIdx : p1BoxIdx);
      } else if (inputY > 0) {
        const targetCol = state.currentElement === p2BoxIdx ? 5 : 4;
        moveCursor(characterStartIdx + targetCol);
      } else if (inputY < 0) {
        moveCursor(startBtnIdx);
      }
    } else if (onCharacterGrid) {
      const gridIndex = state.currentElement - characterStartIdx;
      const cols = GRID.COLS;
      const currentRow = Math.floor(gridIndex / cols);
      const currentCol = gridIndex % cols;

      if (inputY < 0) {
        if (currentRow === 0) {
          moveCursor(currentCol < 5 ? p1BoxIdx : p2BoxIdx);
        } else {
          const newIndex =
            characterStartIdx + (currentRow - 1) * cols + currentCol;
          if (newIndex < characterEndIdx) moveCursor(newIndex);
        }
      } else if (inputY > 0) {
        if (currentRow === 1 || gridIndex >= 9) {
          moveCursor(toggleOptionsIdx);
        } else {
          const newCol = Math.min(currentCol, 8);
          const newIndex = characterStartIdx + cols + newCol;
          if (newIndex < characterEndIdx) moveCursor(newIndex);
        }
      } else if (inputX !== 0) {
        const maxCol = currentRow === 1 ? 8 : 9;
        let newCol = currentCol + inputX;
        if (newCol < 0) newCol = maxCol;
        else if (newCol > maxCol) newCol = 0;
        const newIndex = characterStartIdx + currentRow * cols + newCol;
        if (newIndex < characterEndIdx) moveCursor(newIndex);
      }
    } else if (onToggleOptions) {
      if (inputY < 0) {
        moveCursor(characterEndIdx - 5);
      } else if (inputY > 0) {
        if (superArtP1Idx >= 0) {
          moveCursor(superArtP1Idx);
        } else {
          moveCursor(startBtnIdx);
        }
      } else if (inputX !== 0) {
        const sidePanelElements = [
          controlsHelpIdx,
          playerToggleIdx,
          muteToggleIdx,
        ].filter((idx) => idx >= 0);

        if (sidePanelElements.length > 0) {
          const lastIndex = state.lastSidePanelIndex;
          if (lastIndex >= 0 && sidePanelElements.includes(lastIndex)) {
            moveCursor(lastIndex);
          } else {
            moveCursor(sidePanelElements[0]);
          }
        }
      }
    } else if (onSidePanel) {
      GameState.updateGamepadUIState({
        lastSidePanelIndex: state.currentElement,
      });

      if (inputX !== 0) {
        moveCursor(toggleOptionsIdx);
      } else if (inputY !== 0) {
        const sidePanelElements = [
          controlsHelpIdx,
          playerToggleIdx,
          muteToggleIdx,
        ].filter((idx) => idx >= 0);
        const currentSidePanelIdx = sidePanelElements.indexOf(
          state.currentElement
        );

        if (currentSidePanelIdx >= 0) {
          let newIdx = currentSidePanelIdx + inputY;
          if (newIdx < 0) newIdx = sidePanelElements.length - 1;
          else if (newIdx >= sidePanelElements.length) newIdx = 0;
          const newElement = sidePanelElements[newIdx];
          moveCursor(newElement);
          GameState.updateGamepadUIState({
            lastSidePanelIndex: newElement,
          });
        }
      }
    } else if (onSuperArt) {
      if (inputX !== 0) {
        moveCursor(inputX > 0 ? superArtP2Idx : superArtP1Idx);
      } else if (inputY < 0) {
        moveCursor(toggleOptionsIdx);
      } else if (inputY > 0) {
        const firstOutfitIdx = section.elements.findIndex((el) =>
          el.includes("outfit-")
        );
        if (firstOutfitIdx >= 0) {
          const targetOutfit = state.currentElement === superArtP2Idx ? 3 : 2;
          moveCursor(firstOutfitIdx + targetOutfit);
        } else {
          moveCursor(startBtnIdx);
        }
      }
    } else if (onOutfits) {
      const outfitStartIdx = section.elements.findIndex((el) =>
        el.includes("outfit-")
      );
      const outfitCount = 6;
      const outfitIndex = state.currentElement - outfitStartIdx;

      if (inputX !== 0) {
        let newOutfitIdx = outfitIndex + inputX;
        if (newOutfitIdx < 0) newOutfitIdx = outfitCount - 1;
        else if (newOutfitIdx >= outfitCount) newOutfitIdx = 0;
        moveCursor(outfitStartIdx + newOutfitIdx);
      } else if (inputY < 0) {
        const targetSuperArt =
          outfitIndex === 3 ? superArtP2Idx : superArtP1Idx;
        moveCursor(targetSuperArt);
      } else if (inputY > 0) {
        moveCursor(startBtnIdx);
      }
    }
  };

  const handleGamepadNavigation = (inputX, inputY) => {
    const section = getCurrentSection();
    if (!section || !section.elements.length) return;

    const currentScreen = GameState.getCurrentScreen();

    if (currentScreen !== "settings") {
      if (inputY !== 0) {
        stepCursor(inputY);
      } else if (inputX !== 0) {
        stepCursor(inputX);
      }
      return;
    }

    if (section.special === "settings-linear") {
      navigateSettingsLinear(inputX, inputY, section);
    } else {
      if (inputY !== 0) {
        stepCursor(inputY);
      } else if (inputX !== 0) {
        stepCursor(inputX);
      }
    }
  };

  const handleGamepadSelect = () => {
    const state = GameState.getGamepadUIState();
    const section = state.sections[state.currentSection];
    if (!section) return;

    const elementSelector = section.elements[state.currentElement];
    const element = $(elementSelector);

    if (element && !element.classList.contains("hidden")) {
      if (element.tagName === "SELECT") {
        const currentIndex = element.selectedIndex;
        const nextIndex = (currentIndex + 1) % element.options.length;
        element.selectedIndex = nextIndex;
        element.dispatchEvent(new Event("change"));
        AudioManager.playSound(SOUND_KEYS.CLICK);
      } else {
        element.click();
      }
    }
  };

  const updateGamepadHover = () => {
    const previousHovered = $(".gamepad-hover");
    const wasCharacter = previousHovered?.dataset?.character;

    $$(".gamepad-hover").forEach((el) => {
      el.classList.remove("gamepad-hover");
    });

    const gameState = GameState.get();
    if (wasCharacter && gameState.characterGrid?.onPortraitLeave) {
      gameState.characterGrid.onPortraitLeave(wasCharacter);
    }

    ["p1", "p2"].forEach((player) => {
      const selectedChar = gameState.characterGrid[player].character;
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

    const state = GameState.getGamepadUIState();
    const section = state.sections[state.currentSection];
    if (section && section.elements[state.currentElement]) {
      const element = $(section.elements[state.currentElement]);
      if (element && !element.classList.contains("hidden")) {
        element.classList.add("gamepad-hover");
        element.scrollIntoView({ behavior: "smooth", block: "nearest" });

        if (
          element.dataset.character &&
          gameState.characterGrid?.onPortraitHover
        ) {
          const character = element.dataset.character;
          const imageSrc = `/portraits/${character.toLowerCase()}.png`;
          gameState.characterGrid.onPortraitHover(character, imageSrc);
        }
      }
    }
  };

  const handleGamepadUIAction = (inputX, inputY, buttons) => {
    updateGamepadSections();

    const currentScreen = GameState.getCurrentScreen();
    if (currentScreen === "splash" && buttons.a) {
      const splashScreen = byId("splash-screen");
      if (splashScreen) {
        splashScreen.click();
      }
      return;
    }

    const state = GameState.getGamepadUIState();
    if (!state.sections.length) return;

    if (buttons.a) {
      handleGamepadSelect();
      return;
    }

    if (inputX !== 0 || inputY !== 0) {
      handleGamepadNavigation(inputX, inputY);
    }
  };

  const init = () => {
    GameState.subscribe((changeType) => {
      if (changeType === "screenChange") {
        updateGamepadSections();
      }
    });

    GamepadManager.onUIAction = handleGamepadUIAction;
  };

  return {
    init,
    updateGamepadSections,
    updateGamepadHover,
    handleGamepadUIAction,
  };
};

export const GamepadUINavigator = createGamepadUINavigator();
