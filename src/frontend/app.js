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
        const defaultCharacter = state.characterGrid.p1.character || "Ken";
        GameState.updateProperty("currentCharacter", defaultCharacter);
        UIController.updateCombosDisplay(defaultCharacter);
        UIController.updateSuperArtsDisplay(defaultCharacter);
        CharacterSelectionManager.initOutfitGrid(defaultCharacter);
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

document.addEventListener("DOMContentLoaded", initApp);
