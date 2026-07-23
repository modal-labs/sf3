const createGameState = () => {
  let state = {
    player1Participant: "human",
    player2Participant: "qwen35_9b",
    loaded: false,
    acceptsInput: false,
    serverReady: false,
    firstFrameReceived: false,
    assetsLoaded: false,

    player1: {
      character: null,
      outfit: 1,
      superArt: 1,
    },
    player2: {
      character: null,
      outfit: 1,
      superArt: 1,
    },

    currentCharacter: null,
    playerDirection: "right",

    gamePhase: "connecting",
    currentScreen: null,

    keyState: {},

    gamepadUIState: {
      currentScreen: null,
      currentSection: 0,
      currentElement: 0,
      sections: [],
    },
  };

  const listeners = new Set();

  const notifyListeners = (changeType, data) => {
    listeners.forEach((listener) => {
      listener(changeType, data, state);
    });
  };

  return {
    get() {
      return { ...state };
    },

    update(updates) {
      state = { ...state, ...updates };
      notifyListeners("update", updates);
    },

    setCurrentScreen(screen) {
      const previousScreen = state.currentScreen;
      state.currentScreen = screen;
      notifyListeners("screenChange", { from: previousScreen, to: screen });
    },

    getCurrentScreen() {
      return state.currentScreen;
    },

    setKeyState(key, pressed) {
      state.keyState[key] = pressed;
    },

    getKeyState() {
      return { ...state.keyState };
    },

    setPlayer1Participant(participant) {
      state.player1Participant = participant;
      notifyListeners("gameModeChange", {
        player1Participant: state.player1Participant,
        player2Participant: state.player2Participant,
      });
    },

    setPlayer2Participant(participant) {
      state.player2Participant = participant;
      notifyListeners("gameModeChange", {
        player1Participant: state.player1Participant,
        player2Participant: state.player2Participant,
      });
    },

    updateGamepadUIState(updates) {
      state.gamepadUIState = { ...state.gamepadUIState, ...updates };
      notifyListeners("gamepadUIUpdate", updates);
    },

    getGamepadUIState() {
      return { ...state.gamepadUIState };
    },

    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
};

export const GameState = createGameState();
