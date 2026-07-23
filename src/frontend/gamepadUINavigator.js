import { byId, $, $$ } from "./utils.js";
import { GameState } from "./gameState.js";
import { AudioManager } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { isHumanParticipant } from "./participantOptions.js";
import { SOUND_KEYS } from "./constants.js";

const lobbySelectors = {
  start: "#start-game-btn",
  help: "#controls-help",
  mute: "#mute-toggle",
};

let lastLobbyColumn = "P1";

const getLobbyFocusGraph = () => ({
  start: byId("start-game-btn"),
  help: byId("controls-help"),
  mute: byId("mute-toggle"),
  columns: {
    P1: Array.from(
      document.querySelectorAll('[data-participant-seat="P1"]')
    ),
    P2: Array.from(
      document.querySelectorAll('[data-participant-seat="P2"]')
    ),
  },
});

export const getLobbyNavigationTarget = (current, direction) => {
  if (!current) return null;

  const { start, help, mute, columns } = getLobbyFocusGraph();
  if (!start || columns.P1.length === 0 || columns.P2.length === 0) {
    return null;
  }

  if (current === start) {
    if (direction === "up") return mute;
    if (direction === "right") return columns.P2[0];
    if (direction === "left" || direction === "down") return columns.P1[0];
    return null;
  }

  for (const column of ["P1", "P2"]) {
    const row = columns[column].indexOf(current);
    if (row < 0) continue;

    lastLobbyColumn = column;
    if (direction === "up") {
      return row === 0 ? start : columns[column][row - 1];
    }
    if (direction === "down") {
      return row === columns[column].length - 1
        ? help
        : columns[column][row + 1];
    }
    if (direction === "left" || direction === "right") {
      const otherColumn = column === "P1" ? "P2" : "P1";
      lastLobbyColumn = otherColumn;
      return columns[otherColumn][
        Math.min(row, columns[otherColumn].length - 1)
      ];
    }
    return null;
  }

  if (current === help) {
    if (direction === "up") return columns[lastLobbyColumn].at(-1);
    if (direction === "down") return mute;
    return null;
  }

  if (current === mute) {
    if (direction === "up") return help;
    if (direction === "down") return start;
    return null;
  }

  return null;
};

export const directionFromAxes = (inputX, inputY) =>
  inputY < 0
    ? "up"
    : inputY > 0
      ? "down"
      : inputX < 0
        ? "left"
        : inputX > 0
          ? "right"
          : null;

const createGamepadUINavigator = () => {
  const getCurrentSection = () => {
    const state = GameState.getGamepadUIState();
    const sections = state.sections || [];
    return sections[state.currentSection];
  };

  const getElementPosition = (element) => {
    if (!(element instanceof Element) || !element.id) return null;

    const selector = `#${element.id}`;
    const { sections } = GameState.getGamepadUIState();
    for (let section = 0; section < sections.length; section++) {
      const elementIndex = sections[section].elements.indexOf(selector);
      if (elementIndex >= 0) {
        return { section, element: elementIndex };
      }
    }
    return null;
  };

  const focusNavigationElement = (element, playSound = true) => {
    if (!(element instanceof Element)) return false;

    let position = getElementPosition(element);
    if (!position) {
      updateGamepadSections(true);
      position = getElementPosition(element);
    }
    if (position) {
      GameState.updateGamepadUIState({
        currentSection: position.section,
        currentElement: position.element,
      });
    }

    element.focus({ preventScroll: true });
    element.scrollIntoView({ behavior: "smooth", block: "nearest" });
    updateGamepadHover();
    if (playSound) AudioManager.playSound(SOUND_KEYS.HOVER);
    return true;
  };

  const resolveLobbyCursor = () => {
    const active =
      document.activeElement instanceof Element
        ? document.activeElement.closest("button")
        : null;
    if (active) {
      const { start, help, mute, columns } = getLobbyFocusGraph();
      const inGraph =
        active === start ||
        active === help ||
        active === mute ||
        columns.P1.includes(active) ||
        columns.P2.includes(active);
      if (inGraph) return active;
    }

    const state = GameState.getGamepadUIState();
    const section = state.sections[state.currentSection];
    return section ? $(section.elements[state.currentElement]) : null;
  };

  const navigateLobbyDirection = (direction) => {
    if (!direction) return false;
    const current = resolveLobbyCursor();
    const target = getLobbyNavigationTarget(current, direction);
    if (!target || target === current) return false;
    return focusNavigationElement(target);
  };

  const moveCursor = (index) => {
    const section = getCurrentSection();
    if (!section) return;
    const target = $(section.elements[index]);
    if (target) focusNavigationElement(target);
  };

  const stepCursor = (delta) => {
    const section = getCurrentSection();
    if (!section || !section.elements || !section.elements.length) return;
    const state = GameState.getGamepadUIState();
    const len = section.elements.length;
    const next = (state.currentElement + delta + len) % len;
    moveCursor(next);
  };

  const getSimpleScreenElements = (mainButtons = []) => {
    const elements = [];

    elements.push(...mainButtons);

    const controlsHelp = byId("controls-help");
    if (controlsHelp && !controlsHelp.classList.contains("hidden")) {
      elements.push("#controls-help");
    }

    const muteToggle = byId("mute-toggle");
    if (muteToggle && !muteToggle.classList.contains("hidden")) {
      elements.push("#mute-toggle");
    }

    return elements;
  };

  const updateGamepadSections = (forceUpdate = false) => {
    const currentScreen = GameState.getCurrentScreen();
    const currentUIState = GameState.getGamepadUIState();

    if (!forceUpdate && currentScreen === currentUIState.currentScreen) return;

    const preservePosition =
      forceUpdate && currentScreen === currentUIState.currentScreen;
    const oldSection = preservePosition ? currentUIState.currentSection : 0;
    const oldElement = preservePosition ? currentUIState.currentElement : 0;

    let oldElementSelector = null;
    if (preservePosition && currentUIState.sections[oldSection]) {
      const oldSectionData = currentUIState.sections[oldSection];
      if (
        oldSectionData &&
        oldSectionData.elements &&
        oldSectionData.elements[oldElement]
      ) {
        oldElementSelector = oldSectionData.elements[oldElement];
      }
    }

    let sections = [];

    switch (currentScreen) {
      case "lobby": {
        const p1Elements = Array.from(
          document.querySelectorAll('[data-participant-seat="P1"]')
        ).map(({ id }) => `#${id}`);
        const p2Elements = Array.from(
          document.querySelectorAll('[data-participant-seat="P2"]')
        ).map(({ id }) => `#${id}`);
        const sideElements = getSimpleScreenElements([]);
        sections = [
          {
            elements: ["#start-game-btn"],
            name: "lobby-start",
          },
          { elements: p1Elements, name: "lobby-p1" },
          { elements: p2Elements, name: "lobby-p2" },
          { elements: sideElements, name: "lobby-side" },
        ];
        break;
      }
      case "error":
        const errorState = GameState.get();
        if (!isHumanParticipant(errorState.player1Participant)) {
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
        if (!isHumanParticipant(loadingState.player1Participant)) {
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
        const gameElements = [];
        const playAgain = byId("play-again-controls");
        if (playAgain && !playAgain.classList.contains("hidden")) {
          gameElements.push("#play-again-btn");
        }
        gameElements.push(...getSimpleScreenElements([]));
        sections =
          gameElements.length > 0
            ? [{ elements: gameElements, name: "game-controls" }]
            : [];
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
      });
      const closeButton = byId("help-overlay-close");
      if (closeButton) {
        focusNavigationElement(closeButton, false);
      } else {
        updateGamepadHover();
      }
      return;
    }

    sections = sections.filter(
      (section) => section.elements && section.elements.length > 0
    );

    let currentSection = 0;
    let currentElement = 0;

    if (preservePosition && oldElementSelector) {
      for (let sIdx = 0; sIdx < sections.length; sIdx++) {
        const section = sections[sIdx];
        if (section && section.elements) {
          const elementIdx = section.elements.indexOf(oldElementSelector);
          if (elementIdx >= 0) {
            currentSection = sIdx;
            currentElement = elementIdx;
            break;
          }
        }
      }

      if (
        currentElement === 0 &&
        currentSection === 0 &&
        oldSection < sections.length
      ) {
        currentSection = oldSection;
        const section = sections[oldSection];
        if (oldElement < section.elements.length) {
          currentElement = oldElement;
        }
      }
    } else if (preservePosition) {
      if (oldSection < sections.length) {
        currentSection = oldSection;
        const section = sections[oldSection];
        if (oldElement < section.elements.length) {
          currentElement = oldElement;
        }
      }
    }

    GameState.updateGamepadUIState({
      currentScreen,
      sections,
      currentSection,
      currentElement,
    });

    updateGamepadHover();
  };

  const handleGamepadNavigation = (inputX, inputY) => {
    const active =
      document.activeElement instanceof Element
        ? document.activeElement.closest("button")
        : null;
    const activePosition = getElementPosition(active);
    if (activePosition) {
      GameState.updateGamepadUIState({
        currentSection: activePosition.section,
        currentElement: activePosition.element,
      });
    }

    const section = getCurrentSection();
    if (!section || !section.elements.length) return;

    const currentScreen = GameState.getCurrentScreen();

    if (currentScreen !== "lobby") {
      const state = GameState.getGamepadUIState();
      const currentSelector = section.elements[state.currentElement];
      if (
        inputX !== 0 &&
        [lobbySelectors.help, lobbySelectors.mute].includes(currentSelector)
      ) {
        return;
      }
      if (inputY !== 0) {
        stepCursor(inputY);
      } else if (inputX !== 0) {
        stepCursor(inputX);
      }
      return;
    }

    navigateLobbyDirection(directionFromAxes(inputX, inputY));
  };

  const handleGamepadSelect = () => {
    const active =
      document.activeElement instanceof Element
        ? document.activeElement.closest("button")
        : null;
    const activePosition = getElementPosition(active);
    if (activePosition) {
      GameState.updateGamepadUIState({
        currentSection: activePosition.section,
        currentElement: activePosition.element,
      });
    }

    const state = GameState.getGamepadUIState();
    const section = state.sections[state.currentSection];
    if (!section) return;

    const elementSelector = section.elements[state.currentElement];
    const element = $(elementSelector);

    if (
      element &&
      !element.classList.contains("hidden") &&
      !element.disabled
    ) {
      element.click();
    }
  };

  const updateGamepadHover = () => {
    $$(".gamepad-hover").forEach((el) => {
      el.classList.remove("gamepad-hover");
    });

    if (!GamepadManager.isConnected() || !GamepadManager.uiActive) {
      return;
    }

    const state = GameState.getGamepadUIState();
    const section = state.sections[state.currentSection];
    if (section && section.elements[state.currentElement]) {
      const element = $(section.elements[state.currentElement]);
      if (element && !element.classList.contains("hidden")) {
        element.classList.add("gamepad-hover");
        element.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  };

  const handleGamepadUIAction = (inputX, inputY, buttons) => {
    updateGamepadSections();

    const currentScreen = GameState.getCurrentScreen();
    if (currentScreen === "lobby" && buttons.start) {
      document.dispatchEvent(new Event("gameStartRequest"));
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

    document.addEventListener("focusin", (event) => {
      const target =
        event.target instanceof Element ? event.target.closest("button") : null;
      const position = getElementPosition(target);
      if (!position) return;
      GameState.updateGamepadUIState({
        currentSection: position.section,
        currentElement: position.element,
      });
      updateGamepadHover();
    });

    GamepadManager.onUIAction = handleGamepadUIAction;
  };

  const restoreNavPosition = (position) => {
    if (position && position.element !== undefined) {
      GameState.updateGamepadUIState({
        currentSection: position.section || 0,
        currentElement: position.element,
      });
      const section = getCurrentSection();
      const target = section ? $(section.elements[position.element]) : null;
      if (target) {
        focusNavigationElement(target, false);
      } else {
        updateGamepadHover();
      }
    }
  };

  return {
    init,
    updateGamepadSections,
    updateGamepadHover,
    handleGamepadUIAction,
    handleDirectionalNavigation: handleGamepadNavigation,
    navigateLobbyDirection,
    restoreNavPosition,
  };
};

export const GamepadUINavigator = createGamepadUINavigator();
