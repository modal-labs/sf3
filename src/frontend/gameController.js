import { byId, setText } from "./utils.js";
import { GameState } from "./gameState.js";
import { ScreenManager } from "./screenManager.js";
import { WebSocketManager } from "./webSocketManager.js";
import { AudioManager } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { SOUND_KEYS } from "./constants.js";
import { setCanvasSize } from "./app.js";

const createGameController = () => {
  const startGame = () => {
    const state = GameState.get();

    const difficultySlider = byId("difficulty-slider");
    const difficultyValue = parseInt(difficultySlider?.value || 2);
    const difficultyMap = ["basic", "advanced", "expert"];

    const gameConfig = {
      humanVsLlm: state.humanVsLlm,
      player1: {
        character: state.characterGrid.p1.character,
        outfit: state.characterGrid.p1.outfit,
        superArt: parseInt(byId("super-art-select-p1")?.value || 1),
      },
      player2: {
        character: state.characterGrid.p2.character,
        outfit: state.characterGrid.p2.outfit,
        superArt: parseInt(byId("super-art-select-p2")?.value || 1),
      },
      gamepadConnected: GamepadManager.isConnected(),
      difficulty: difficultyMap[difficultyValue],
    };

    GameState.update({
      player1: gameConfig.player1,
      player2: gameConfig.player2,
    });

    AudioManager.play(SOUND_KEYS.START, {
      volume: 0.2,
      trackAs: "effect",
    });

    setTimeout(() => {
      resetGameState();
      ScreenManager.showScreen(ScreenManager.screens.LOADING);
      setText("loading-status", "Starting game...");
      WebSocketManager.send("start_game", gameConfig);
    }, 10);
  };

  const resetGameState = () => {
    GameState.resetGameState();

    const status = byId("canvas-loading-status");
    if (status) status.textContent = "Loading game...";

    const overlay = byId("canvas-loading-overlay");
    if (overlay) overlay.classList.remove("hidden");

    const canvas = byId("game-canvas");
    if (canvas) {
      canvas.classList.add("hidden");
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  const handleWebSocketMessage = async (event) => {
    if (event.data instanceof Blob) {
      handleFrameData(event.data);
      return;
    }

    const message = JSON.parse(event.data);
    if (message.type === "game_state") {
      handleGameState(message.data);
    } else if (message.type === "transition") {
      handleTransition(message.data);
    }
  };

  const handleFrameData = (blob) => {
    const state = GameState.get();
    const overlay = byId("canvas-loading-overlay");

    if (!state.firstFrameReceived) {
      GameState.update({ firstFrameReceived: true });
      if (overlay) overlay.classList.add("hidden");
      const canvas = byId("game-canvas");
      if (canvas) canvas.classList.remove("hidden");
    }

    if (state.inTransition) {
      ScreenManager.checkTransitionReady();
    }

    renderFrame(blob);
  };

  const renderFrame = (blob) => {
    const canvas = byId("game-canvas");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const url = URL.createObjectURL(blob);
    const img = new Image();

    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
    };
    img.src = url;
  };

  const handleGameState = (data) => {
    console.log("Game state:", data.status);
    const startButton = byId("start-game-btn");

    if (!GameState.get().serverReady) {
      GameState.update({ serverReady: true });
      if (startButton) {
        startButton.disabled = false;
        startButton.textContent = "START GAME";
        startButton.classList.remove("opacity-50");
      }
      console.log("Server ready");
    }

    switch (data.status) {
      case "initializing":
        setText("loading-status", "Starting game...");
        break;

      case "running":
        GameState.update({ loaded: true });
        setCanvasSize();
        ScreenManager.showScreen(ScreenManager.screens.GAME);
        GamepadManager.setUIActive(!GameState.get().humanVsLlm);

        const character = GameState.get().player1.character;
        if (character) {
          AudioManager.play(character, {
            volume: 0.2,
            loop: true,
            trackAs: "select",
          });
        }
        break;

      case "finished":
        handleGameFinished(data.winner);
        break;

      case "error":
        GameState.update({ loaded: false });
        AudioManager.stopTrack("select");
        ScreenManager.showError(data.error || "Unknown game error");
        break;
    }
  };

  const handleGameFinished = (winner) => {
    GameState.update({ loaded: false });
    GamepadManager.setUIActive(true);
    AudioManager.stopTrack("select");

    const displayWinner = winner || "Unknown";
    ScreenManager.showWinScreen(displayWinner);
  };

  const handleTransition = (data) => {
    let message = "";
    if (data.transition_type === "round") {
      message = "Loading next round...";
    } else if (data.transition_type === "game") {
      message = "Determining winner...";
    }

    ScreenManager.showTransition(message);
  };

  const init = () => {
    WebSocketManager.init({
      onMessage: handleWebSocketMessage,
    });

    const startBtn = byId("start-game-btn");
    if (startBtn) {
      startBtn.addEventListener("click", () => {
        AudioManager.playSound(SOUND_KEYS.CLICK);
        startGame();
      });
    }

    const playAgainBtn = byId("play-again-btn");
    if (playAgainBtn) {
      playAgainBtn.addEventListener("click", () => {
        AudioManager.playSound(SOUND_KEYS.CLICK);
        ScreenManager.showScreen(ScreenManager.screens.SETTINGS);
      });
    }

    const errorBackBtn = byId("error-back-btn");
    if (errorBackBtn) {
      errorBackBtn.addEventListener("click", () => {
        AudioManager.playSound(SOUND_KEYS.CLICK);
        ScreenManager.showScreen(ScreenManager.screens.SETTINGS);
      });
    }
  };

  const cleanup = () => {
    WebSocketManager.close();
  };

  return {
    init,
    startGame,
    cleanup,
  };
};

export const GameController = createGameController();
