import { AssetLoader } from "./assetLoader.js";
import { AudioManager } from "./audioManager.js";
import { GameState } from "./gameState.js";
import { ScreenManager } from "./screenManager.js";
import { InputController } from "./inputController.js";
import { CharacterSelectionManager } from "./characterSelectionManager.js";
import { GameController } from "./gameController.js";
import { UIController } from "./uiController.js";
import { GamepadManager } from "./gamepadManager.js";
import { GamepadUINavigator } from "./gamepadUINavigator.js";
import { WebSocketManager } from "./webSocketManager.js";
import { byId } from "./utils.js";

export const setCanvasSize = () => {
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  const canvas = byId("game-canvas");
  if (canvas) {
    // original = 384x224
    if (isMobile) {
      // 1.5x scale for mobile
      canvas.width = 576;
      canvas.height = 336;
    } else {
      // 2x scale for desktop
      canvas.width = 768;
      canvas.height = 448;
    }
  }
};

const initApp = async () => {
  await AssetLoader.loadAllAssets();

  AudioManager.init();

  ScreenManager.initCoinScreen();
  ScreenManager.initSplashScreen();
  ScreenManager.showScreen(ScreenManager.screens.COIN);

  CharacterSelectionManager.initCharacterGrid(AssetLoader.characters);
  CharacterSelectionManager.selectCharacter("p1", "Ken");
  CharacterSelectionManager.selectCharacter("p2", "Ryu");
  CharacterSelectionManager.initOutfitGrid(null);
  CharacterSelectionManager.setupPlayerBoxListeners();

  GamepadManager.init({
    onStatusChange: (connected) => {
      WebSocketManager.send("gamepad_status", { connected });
      UIController.updateControlsDisplay();
      UIController.updateCombosDisplay(GameState.get().currentCharacter);
      UIController.updateSuperArtsDisplay(GameState.get().currentCharacter);
      UIController.updateHelpIconVisibility();
      UIController.updateGamepadNavVisibility();
      GamepadUINavigator.updateGamepadSections(true);

      const currentScreen = GameState.getCurrentScreen();
      if (currentScreen === "splash") {
        const muteButton = byId("mute-toggle");
        if (muteButton) {
          muteButton.classList.toggle("hidden", connected);
        }
      }
    },
    onInput: () => {}, // will be set by InputController
    onUIAction: () => {}, // will be set by GamepadUINavigator
  });

  GamepadManager.setUIActive(true);

  InputController.init();
  InputController.initGamepadInput();
  GameController.init();
  UIController.init();
  GamepadUINavigator.init();

  GameState.subscribe((changeType) => {
    if (changeType === "screenChange") {
      const state = GameState.get();
      if (state.currentScreen === "settings") {
        const activePlayer = state.characterGrid.activePlayer;
        const activeCharacter = state.characterGrid[activePlayer].character;

        CharacterSelectionManager.updatePlayerBoxes();
        CharacterSelectionManager.updateCharacterBorders();

        if (activeCharacter) {
          GameState.updateProperty("currentCharacter", activeCharacter);
          UIController.updateCombosDisplay(activeCharacter);
          UIController.updateSuperArtsDisplay(activeCharacter);
          CharacterSelectionManager.initOutfitGrid(activeCharacter);
        } else {
          CharacterSelectionManager.initOutfitGrid(null);
        }
      }
    }
  });

  window.addEventListener("beforeunload", () => {
    AudioManager.stopAll();
    ScreenManager.cleanup();
    GameController.cleanup();
  });

  window.addEventListener("characterSelectionChanged", () => {
    GamepadUINavigator.updateGamepadSections(true);
  });
};

document.addEventListener("DOMContentLoaded", () => {
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  let hasKeyboard = false;
  let hasGamepad = false;

  const checkMobileRequirements = () => {
    const isPortrait = window.innerHeight > window.innerWidth;
    const rotateScreen = byId("rotate-device");
    const requirementTitle = byId("requirement-title");
    const requirementText = byId("requirement-text");
    const requirementIcon = byId("requirement-icon");
    const inputIcons = byId("input-icons");

    if (rotateScreen && isMobile) {
      if (isPortrait) {
        rotateScreen.classList.remove("hidden");
        rotateScreen.classList.add("flex");
        requirementTitle.textContent = "Please Rotate Your Device";
        requirementText.textContent =
          "This game requires landscape orientation on mobile devices.";
        requirementIcon.classList.remove("hidden");
        inputIcons.classList.add("hidden");
        inputIcons.classList.remove("flex");
      } else if (!hasKeyboard && !hasGamepad) {
        rotateScreen.classList.remove("hidden");
        rotateScreen.classList.add("flex");
        requirementTitle.textContent = "Controller Required";
        requirementText.textContent =
          "Please connect a Bluetooth keyboard or gamepad to play on mobile.";
        requirementIcon.classList.add("hidden");
        inputIcons.classList.remove("hidden");
        inputIcons.classList.add("flex");
      } else {
        rotateScreen.classList.add("hidden");
        rotateScreen.classList.remove("flex");
      }
    } else if (rotateScreen) {
      rotateScreen.classList.add("hidden");
      rotateScreen.classList.remove("flex");
    }
  };

  window.addEventListener("keydown", () => {
    if (isMobile && !hasKeyboard) {
      hasKeyboard = true;
      checkMobileRequirements();
    }
  });

  window.addEventListener("gamepadStatusChange", (e) => {
    if (isMobile) {
      hasGamepad = e.detail.connected;
      checkMobileRequirements();
    }
  });

  setCanvasSize();
  checkMobileRequirements();
  window.addEventListener("orientationchange", checkMobileRequirements);
  window.addEventListener("resize", checkMobileRequirements);

  initApp();
});
