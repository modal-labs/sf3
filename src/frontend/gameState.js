const createGameState = () => {
  let state = {
    // core game status
    humanVsLlm: true,
    loaded: false,
    serverReady: false,
    firstFrameReceived: false,
    assetsLoaded: false,

    inTransition: false,
    transitionStartTime: null,
    readyToHideTransition: false,

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

    characterGrid: {
      activePlayer: "p1",
      p1: { selected: false, character: "Ryu", outfit: 1 },
      p2: { selected: false, character: "Ken", outfit: 1 },
    },

    currentCharacter: null,
    playerDirection: "right",

    currentScreen: null,

    // input state
    keyState: {},
    inputHistory: [],

    // gamepad nav
    gamepadUIState: {
      currentScreen: null,
      currentSection: 0,
      currentElement: 0,
      sections: [],
      lastSidePanelIndex: -1,
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

    getProperty(path) {
      const keys = path.split(".");
      let value = state;
      for (const key of keys) {
        value = value[key];
        if (value === undefined) return undefined;
      }
      return value;
    },

    update(updates) {
      state = { ...state, ...updates };
      notifyListeners("update", updates);
    },

    updateProperty(path, value) {
      const keys = path.split(".");
      const lastKey = keys.pop();
      let target = state;

      for (const key of keys) {
        if (!target[key]) target[key] = {};
        target = target[key];
      }

      target[lastKey] = value;
      notifyListeners("propertyUpdate", { path, value });
    },

    resetGameState() {
      state.loaded = false;
      state.serverReady = false;
      state.firstFrameReceived = false;
      state.inTransition = false;
      state.transitionStartTime = null;
      state.readyToHideTransition = false;
      state.keyState = {};
      state.inputHistory = [];
      notifyListeners("reset", null);
    },

    setPlayer1Character(character, outfit = 1) {
      state.characterGrid.p1.character = character;
      state.characterGrid.p1.outfit = outfit;
      state.player1.character = character;
      state.player1.outfit = outfit;
      notifyListeners("playerCharacterChange", {
        player: "p1",
        character,
        outfit,
      });
    },

    setPlayer2Character(character, outfit = 1) {
      state.characterGrid.p2.character = character;
      state.characterGrid.p2.outfit = outfit;
      state.player2.character = character;
      state.player2.outfit = outfit;
      notifyListeners("playerCharacterChange", {
        player: "p2",
        character,
        outfit,
      });
    },

    switchActivePlayer(player) {
      state.characterGrid.activePlayer = player;
      notifyListeners("activePlayerChange", player);
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

    addInputToHistory(input) {
      state.inputHistory.push(input);
      if (state.inputHistory.length > 20) {
        // roughly length of longest combo
        state.inputHistory.shift();
      }
    },

    clearInputHistory() {
      state.inputHistory = [];
    },

    getInputHistory() {
      return [...state.inputHistory];
    },

    toggleGameMode() {
      state.humanVsLlm = !state.humanVsLlm;
      notifyListeners("gameModeChange", state.humanVsLlm);
      return state.humanVsLlm;
    },

    isHumanVsLlm() {
      return state.humanVsLlm;
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
