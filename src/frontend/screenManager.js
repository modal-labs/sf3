import { byId, show, hide } from "./utils.js";
import { AudioManager } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { GameState } from "./gameState.js";
import { SOUND_KEYS } from "./constants.js";

const createScreenManager = () => {
  const screens = {
    COIN: "coin",
    SPLASH: "splash",
    SETTINGS: "settings",
    LOADING: "loading",
    GAME: "game",
    WIN: "win",
    ERROR: "error",
  };

  const volumes = {
    select: 0.2,
    start: 0.2,
    gameplay: 0.2,
    transition: 0.2,
    winLose: 0.2,
  };

  const durations = {
    coin: 1000,
    capcom: 6000,
    animation: 600,
    transitionMinDisplay: 3000,
  };

  let capcomTimeout = null;
  let transitionTimeout = null;

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

    const header = byId("game-header");
    if (header) {
      const hideHeader =
        screenId === screens.SPLASH || screenId === screens.GAME || hideAll;
      header.classList.toggle("hidden", hideHeader);
    }

    const isGameplay = screenId === screens.GAME;
    const isMinimalScreen =
      screenId === screens.WIN ||
      screenId === screens.ERROR ||
      (screenId === screens.LOADING && state.assetsLoaded);

    const playerToggle = byId("player-toggle");
    if (playerToggle) {
      const showPlayerToggle = screenId === screens.SETTINGS;
      playerToggle.classList.toggle("hidden", !showPlayerToggle || isGameplay);
    }

    const muteButton = byId("mute-toggle");
    if (muteButton) {
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      const hideMute =
        isMobile ||
        hideAll ||
        (isGameplay && state.humanVsLlm) ||
        (isMinimalScreen && state.humanVsLlm) ||
        (screenId === screens.SPLASH && GamepadManager.isConnected());
      muteButton.classList.toggle("hidden", hideMute);
    }

    const gamepadStatus = byId("gamepad-status");
    if (gamepadStatus) {
      gamepadStatus.classList.toggle("hidden", hideAll);
    }

    updateHelpIconVisibility(screenId);
  };

  const updateHelpIconVisibility = (screenId) => {
    const controlsHelp = byId("controls-help");
    if (!controlsHelp) return;

    const state = GameState.get();
    if (!state.humanVsLlm) {
      hide(controlsHelp);
      return;
    }

    const isLoading = screenId === screens.LOADING;
    const hideAll = isLoading && !state.assetsLoaded;
    const isEarlyScreen =
      screenId === screens.COIN || screenId === screens.SPLASH;
    const isGameplay = screenId === screens.GAME;
    const isMinimalScreen =
      screenId === screens.WIN ||
      screenId === screens.ERROR ||
      (screenId === screens.LOADING && state.assetsLoaded);

    controlsHelp.classList.toggle(
      "hidden",
      hideAll || isEarlyScreen || isGameplay || isMinimalScreen
    );
  };

  const manageAudio = (screenId) => {
    if (screenId === screens.SETTINGS) {
      AudioManager.play(SOUND_KEYS.SELECT, {
        volume: volumes.select,
        loop: true,
        trackAs: "select",
      });
      AudioManager.stopTrack("winLose");
    } else {
      AudioManager.stopTrack("select");
      if (screenId !== screens.WIN) {
        AudioManager.stopTrack("winLose");
      }
    }
  };

  const resetCoinScreen = () => {
    const coinBtn = byId("insert-coin-btn");
    if (coinBtn) {
      coinBtn.disabled = false;
      coinBtn.classList.remove("animate-coin-insert");
      coinBtn.classList.add("animate-coin-shine");
    }
  };

  const showScreen = (screenId) => {
    hideAllScreens();

    const screenEl = byId(`${screenId}-screen`);
    if (screenEl) show(screenEl);

    GameState.setCurrentScreen(screenId);
    updateUIVisibility(screenId);
    manageAudio(screenId);

    if (screenId === screens.COIN) {
      resetCoinScreen();
    }

    if (GamepadManager.isConnected()) {
      GameState.updateGamepadUIState({ currentScreen: null });
    }
  };

  const transitionToSplash = () => {
    const coinScreen = byId("coin-screen");
    if (!coinScreen || coinScreen.classList.contains("hidden")) return;

    showScreen(screens.SPLASH);
    AudioManager.playSound(SOUND_KEYS.CAPCOM);

    capcomTimeout = setTimeout(() => {
      capcomTimeout = null;
      showScreen(screens.SETTINGS);
    }, durations.capcom);
  };

  const skipSplash = () => {
    if (capcomTimeout) {
      clearTimeout(capcomTimeout);
      capcomTimeout = null;
    }

    const capcomSound = AudioManager.sounds[SOUND_KEYS.CAPCOM];
    if (capcomSound) {
      capcomSound.pause();
      capcomSound.currentTime = 0;
    }

    showScreen(screens.SETTINGS);
  };

  const showTransition = (message) => {
    GameState.update({
      inTransition: true,
      transitionStartTime: Date.now(),
      readyToHideTransition: false,
    });

    AudioManager.stopTrack("select");
    AudioManager.play(SOUND_KEYS.TRANSITION, {
      volume: volumes.transition,
      trackAs: "transition",
    });

    const status = byId("canvas-loading-status");
    if (status) status.textContent = message;

    const overlay = byId("canvas-loading-overlay");
    const canvas = byId("game-canvas");

    if (overlay) show(overlay);
    if (canvas) hide(canvas);

    const header = byId("game-header");
    if (header) show(header);

    transitionTimeout = setTimeout(() => {
      const currentState = GameState.get();
      if (currentState.readyToHideTransition && currentState.inTransition) {
        hideTransition();
      }
    }, durations.transitionMinDisplay);
  };

  const hideTransition = () => {
    if (transitionTimeout) {
      clearTimeout(transitionTimeout);
      transitionTimeout = null;
    }

    GameState.update({
      inTransition: false,
      transitionStartTime: null,
      readyToHideTransition: false,
    });

    AudioManager.stopTrack("transition");

    const state = GameState.get();
    const gameScreen = byId("game-screen");

    if (
      state.loaded &&
      gameScreen &&
      !gameScreen.classList.contains("hidden")
    ) {
      const character = state.player1.character;
      if (character) {
        AudioManager.play(character, {
          volume: volumes.gameplay,
          loop: true,
          trackAs: "select",
        });
      }

      const header = byId("game-header");
      if (header) hide(header);
    }

    const canvas = byId("game-canvas");
    const overlay = byId("canvas-loading-overlay");

    if (canvas) show(canvas);
    if (overlay) hide(overlay);
  };

  const checkTransitionReady = () => {
    const state = GameState.get();
    if (!state.inTransition) return;

    GameState.update({ readyToHideTransition: true });

    const elapsedTime = Date.now() - state.transitionStartTime;
    if (elapsedTime >= durations.transitionMinDisplay) {
      hideTransition();
    }
  };

  const showWinScreen = (winner) => {
    const winnerEl = byId("winner-text");
    if (winnerEl) {
      winnerEl.textContent = `Winner: ${winner}`;
      winnerEl.classList.toggle(
        "text-sf-blue",
        winner === "YOU" || winner === "LLM 1" || winner === "P1"
      );
      winnerEl.classList.toggle(
        "text-sf-red",
        winner === "LLM" || winner === "LLM 2" || winner === "P2"
      );
    }

    const state = GameState.get();
    const winSound =
      !state.humanVsLlm || winner === "YOU" ? SOUND_KEYS.WIN : SOUND_KEYS.LOSE;

    AudioManager.play(winSound, {
      volume: volumes.winLose,
      trackAs: "winLose",
      onEnd: () => {
        const winScreen = byId("win-screen");
        if (winScreen && !winScreen.classList.contains("hidden")) {
          AudioManager.play(SOUND_KEYS.CONTINUE, {
            volume: volumes.select,
            loop: true,
            trackAs: "select",
          });
        }
      },
    });

    showScreen(screens.WIN);
  };

  const showError = (message) => {
    const errorDetails = byId("error-details");
    if (errorDetails) {
      errorDetails.textContent = new Date().toLocaleString() + "\n" + message;
    }
    showScreen(screens.ERROR);
  };

  const initCoinScreen = () => {
    const coinBtn = byId("insert-coin-btn");
    if (!coinBtn) return;

    const handleCoinInsert = () => {
      if (coinBtn.disabled) return;

      coinBtn.disabled = true;
      coinBtn.classList.remove("animate-coin-shine");
      coinBtn.classList.add("animate-coin-insert");

      AudioManager.playSound(SOUND_KEYS.COIN);

      setTimeout(() => {
        transitionToSplash();
      }, 1000);
    };

    coinBtn.addEventListener("click", handleCoinInsert);
    coinBtn.addEventListener("touchend", (e) => {
      e.preventDefault();
      handleCoinInsert();
    });

    coinBtn.addEventListener("mouseenter", () => {
      AudioManager.playSound(SOUND_KEYS.HOVER);
    });
  };

  const initSplashScreen = () => {
    const splashScreen = byId("splash-screen");
    if (!splashScreen) return;

    const handleSplashSkip = () => {
      if (splashScreen.classList.contains("hidden")) return;
      skipSplash();
    };

    splashScreen.addEventListener("click", handleSplashSkip);
    splashScreen.addEventListener("touchend", (e) => {
      e.preventDefault();
      handleSplashSkip();
    });
  };

  const cleanup = () => {
    if (capcomTimeout) {
      clearTimeout(capcomTimeout);
      capcomTimeout = null;
    }
    if (transitionTimeout) {
      clearTimeout(transitionTimeout);
      transitionTimeout = null;
    }
  };

  return {
    screens,
    showScreen,
    transitionToSplash,
    skipSplash,
    showTransition,
    hideTransition,
    checkTransitionReady,
    showWinScreen,
    showError,
    initCoinScreen,
    initSplashScreen,
    cleanup,
  };
};

export const ScreenManager = createScreenManager();
