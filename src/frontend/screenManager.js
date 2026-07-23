import { byId, show, hide } from "./utils.js";
import { GameState } from "./gameState.js";

const createScreenManager = () => {
  const screens = {
    LOBBY: "lobby",
    LOADING: "loading",
    GAME: "game",
    ERROR: "error",
  };

  const hideAllScreens = () => {
    Object.values(screens).forEach((screen) => {
      const el = byId(`${screen}-screen`);
      if (el) hide(el);
    });
  };

  const updateUIVisibility = (screenId) => {
    const state = GameState.get();
    const isLoading = screenId === screens.LOADING;
    const hideAll = isLoading && !state.assetsLoaded;
    const hideSideControls = screenId === screens.GAME || hideAll;

    const header = byId("game-header");
    if (header) {
      const hideHeader = screenId === screens.GAME || hideAll;
      header.classList.toggle("hidden", hideHeader);
    }

    const muteButton = byId("mute-toggle");
    if (muteButton) {
      muteButton.classList.toggle("hidden", hideSideControls);
    }

    const gamepadStatus = byId("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.toggle("hidden", hideSideControls);
    }

    updateHelpIconVisibility(screenId);
  };

  const updateHelpIconVisibility = (screenId) => {
    const controlsHelp = byId("controls-help");
    if (!controlsHelp) return;

    const state = GameState.get();
    const isLoading = screenId === screens.LOADING;
    const hideAll = isLoading && !state.assetsLoaded;
    controlsHelp.classList.toggle(
      "hidden",
      screenId === screens.GAME || hideAll
    );
  };

  const showScreen = (screenId) => {
    hideAllScreens();

    const screenEl = byId(`${screenId}-screen`);
    if (screenEl) show(screenEl);

    GameState.setCurrentScreen(screenId);
    updateUIVisibility(screenId);

    // Always invalidate so keyboard and gamepad rebuild the same focus sections.
    GameState.updateGamepadUIState({ currentScreen: null });
  };

  const showError = (message) => {
    const errorDetails = byId("error-details");
    if (errorDetails) {
      errorDetails.textContent = new Date().toLocaleString() + "\n" + message;
    }
    showScreen(screens.ERROR);
  };

  return {
    screens,
    showScreen,
    showError,
    refreshVisibility: () => updateUIVisibility(GameState.getCurrentScreen()),
  };
};

export const ScreenManager = createScreenManager();
