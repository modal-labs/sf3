import { AudioManager } from "./audioManager.js";
import { GameState } from "./gameState.js";
import { setText } from "./utils.js";

const createAssetLoader = () => {
  const characters = [
    "Alex",
    "Chun-Li",
    "Dudley",
    "Elena",
    "Gouki",
    "Hugo",
    "Ibuki",
    "Ken",
    "Makoto",
    "Necro",
    "Oro",
    "Q",
    "Remy",
    "Ryu",
    "Sean",
    "Twelve",
    "Urien",
    "Yang",
    "Yun",
  ];

  const staticImages = {
    CAPCOM: "/capcom.svg",
    MODAL: "/modal.svg",
    MUTE: "/icons/mute.svg",
    UNMUTE: "/icons/unmute.svg",
    HUMAN: "/icons/human.png",
    LLM: "/icons/llm.png",
    HELP: "/icons/help.png",
    CLOSE: "/icons/close.png",
    GAMEPAD: "/icons/gamepad.png",
  };

  const soundFiles = {
    HOVER: "hover",
    CLICK: "click",
    COIN: "coin",
    CAPCOM: "capcom",
    SELECT: "select",
    TRANSITION: "transition",
    START: "start",
    WIN: "win",
    LOSE: "lose",
    CONTINUE: "continue",
    GAMEPAD_CONNECT: "gamepad-connect",
    GAMEPAD_DISCONNECT: "gamepad-disconnect",
  };

  const gameplayMusicFiles = [
    "alex,ken",
    "chun-li",
    "dudley",
    "elena",
    "gouki",
    "hugo",
    "ibuki",
    "makoto",
    "necro,twelve",
    "q",
    "remy",
    "ryu",
    "sean,oro",
    "urien",
    "yun,yang",
  ];

  const buildGameplayMusicMap = () => {
    const map = {};
    gameplayMusicFiles.forEach((entry) => {
      entry.split(",").forEach((name) => {
        const formattedName = name
          .trim()
          .split("-")
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join("-");
        map[formattedName] = entry;
      });
    });
    return map;
  };

  const preloadImage = (src) => {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = resolve;
      img.onerror = resolve;
      img.src = src;
    });
  };

  const loadAllAssets = async () => {
    setText("loading-status", "Loading assets...");

    const imagePromises = [];

    characters.forEach((character) => {
      imagePromises.push(
        preloadImage(`/portraits/${character.toLowerCase()}.png`)
      );
    });

    Object.values(staticImages).forEach((src) => {
      imagePromises.push(preloadImage(src));
    });

    const gameplayMusicMap = buildGameplayMusicMap();

    await Promise.all([
      AudioManager.preloadSounds(soundFiles, gameplayMusicMap),
      ...imagePromises,
    ]);

    GameState.update({ assetsLoaded: true });
    setText("loading-status", "Connecting to server...");
  };

  const loadExtraMoves = async () => {
    try {
      const response = await fetch("/api/extra-moves");
      const data = await response.json();
      return {
        combos: data.combos || {},
        specialMoves: data.special_moves || {},
      };
    } catch (error) {
      console.error("Failed to load extra moves:", error);
      return {
        combos: {},
        specialMoves: {},
      };
    }
  };

  return {
    characters,
    staticImages,
    soundFiles,
    gameplayMusicMap: buildGameplayMusicMap(),
    loadAllAssets,
    loadExtraMoves,
  };
};

export const AssetLoader = createAssetLoader();
