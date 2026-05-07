import { byId, setText } from "./utils.js";
import { GameState } from "./gameState.js";
import { ScreenManager } from "./screenManager.js";
import { WebRtcManager } from "./webRtcManager.js";
import { AudioManager } from "./audioManager.js";
import { GamepadManager } from "./gamepadManager.js";
import { isHumanParticipant } from "./participantOptions.js";
import { SOUND_KEYS } from "./constants.js";
import { setCanvasSize } from "./app.js";

const createGameController = () => {
  const remoteVideo = document.createElement("video");
  remoteVideo.autoplay = true;
  remoteVideo.muted = true;
  remoteVideo.playsInline = true;
  let renderFrameHandle = null;
  let videoFrameHandle = null;
  let lastPresentedFrames = 0;
  let nextFreshPresentedFrame = 1;

  const startGame = () => {
    const state = GameState.get();

    const difficultySlider = byId("difficulty-slider");
    const difficultyValue = parseInt(difficultySlider?.value || 2);
    const difficultyMap = ["basic", "advanced", "expert"];

    const gameConfig = {
      player1Participant: state.player1Participant,
      player2Participant: state.player2Participant,
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
      WebRtcManager.send("start_game", gameConfig);
    }, 10);
  };

  const resetGameState = () => {
    GameState.resetGameState();
    nextFreshPresentedFrame = lastPresentedFrames + 1;

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

  const cancelVideoFrameObserver = () => {
    if (
      videoFrameHandle !== null &&
      typeof remoteVideo.cancelVideoFrameCallback === "function"
    ) {
      remoteVideo.cancelVideoFrameCallback(videoFrameHandle);
      videoFrameHandle = null;
    }
  };

  const scheduleVideoFrameObserver = () => {
    if (typeof remoteVideo.requestVideoFrameCallback !== "function") {
      return;
    }

    videoFrameHandle = remoteVideo.requestVideoFrameCallback((_, metadata) => {
      lastPresentedFrames = metadata.presentedFrames;
      if (metadata.presentedFrames >= nextFreshPresentedFrame) {
        handleFrameData();
      }
      scheduleVideoFrameObserver();
    });
  };

  const handleTransportMessage = (raw) => {
    const message = JSON.parse(raw);
    if (message.type === "game_state") {
      handleGameState(message.data);
    } else if (message.type === "transition") {
      handleTransition(message.data);
    }
  };

  const handleFrameData = () => {
    const state = GameState.get();
    if (
      typeof remoteVideo.requestVideoFrameCallback === "function" &&
      lastPresentedFrames < nextFreshPresentedFrame
    ) {
      return;
    }

    if (!state.loaded) {
      return;
    }

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
  };

  const renderVideoFrame = () => {
    const canvas = byId("game-canvas");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (remoteVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(remoteVideo, 0, 0, canvas.width, canvas.height);
      if (typeof remoteVideo.requestVideoFrameCallback !== "function") {
        handleFrameData();
      }
    }
    renderFrameHandle = requestAnimationFrame(renderVideoFrame);
  };

  const restartVideoRendering = () => {
    if (renderFrameHandle !== null) {
      cancelAnimationFrame(renderFrameHandle);
      renderFrameHandle = null;
    }
    cancelVideoFrameObserver();
    remoteVideo.play().catch(() => { });
    scheduleVideoFrameObserver();
    renderFrameHandle = requestAnimationFrame(renderVideoFrame);
  };

  const handleRemoteStream = (stream) => {
    remoteVideo.srcObject = stream;
    remoteVideo.onloadedmetadata = restartVideoRendering;
  };

  const handleGameState = (data) => {
    const startButton = byId("start-game-btn");

    if (!GameState.get().serverReady) {
      GameState.update({ serverReady: true });
      if (startButton) {
        startButton.disabled = false;
        startButton.textContent = "START GAME";
        startButton.classList.remove("opacity-50");
      }
    }

    switch (data.status) {
      case "initializing":
        setText("loading-status", "Starting game...");
        break;

      case "running":
        GameState.update({ loaded: true });
        setCanvasSize();
        ScreenManager.showScreen(ScreenManager.screens.GAME);
        restartVideoRendering();
        GamepadManager.setUIActive(
          !isHumanParticipant(GameState.get().player1Participant)
        );

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
    if (data.transition_type === "round") {
      const message = "Loading next round...";
      ScreenManager.showTransition(message);
    }
  };

  const init = () => {
    WebRtcManager.init({
      onMessage: handleTransportMessage,
      onRemoteStream: handleRemoteStream,
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
    if (renderFrameHandle !== null) {
      cancelAnimationFrame(renderFrameHandle);
      renderFrameHandle = null;
    }
    cancelVideoFrameObserver();
    WebRtcManager.close();
  };

  return {
    init,
    startGame,
    cleanup,
  };
};

export const GameController = createGameController();
