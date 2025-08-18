import { byId, $, $$ } from "./utils.js";
import { GameState } from "./gameState.js";
import { AudioManager } from "./audioManager.js";
import { UIFactory } from "./uiFactory.js";
import { GamepadUINavigator } from "./gamepadUINavigator.js";
import { SOUND_KEYS } from "./constants.js";

const createCharacterSelectionManager = () => {
  const numOutfitsPerCharacter = 6;
  const animationDuration = 600;

  let onPortraitHover = null;
  let onPortraitLeave = null;

  const initCharacterGrid = (characters) => {
    const gridContainer = byId("character-grid");
    if (!gridContainer) return;

    gridContainer.innerHTML = "";

    const state = GameState.get();

    onPortraitHover = (character, imageSrc) => {
      const player = state.characterGrid.activePlayer;
      const previewBox = byId(`${player}-selected-portrait`);
      const previewImg = previewBox?.querySelector("img");

      if (previewImg && state.characterGrid[player].character !== character) {
        previewImg.src = imageSrc;
        previewImg.classList.remove("hidden", "opacity-100");
        previewImg.classList.add("opacity-80", "object-contain");
        const nameEl = byId(`${player}-selected-name`);
        if (nameEl) nameEl.textContent = character;
      }
    };

    onPortraitLeave = (character) => {
      updateCharacterBorders();
      const state = GameState.get();
      const player = state.characterGrid.activePlayer;
      const selectedChar = state.characterGrid[player].character;

      if (selectedChar !== character) {
        const previewBox = byId(`${player}-selected-portrait`);
        const previewImg = previewBox?.querySelector("img");
        const nameEl = byId(`${player}-selected-name`);

        if (selectedChar) {
          if (previewImg) {
            previewImg.src = `/portraits/${selectedChar.toLowerCase()}.png`;
            previewImg.classList.remove("hidden", "opacity-80");
            previewImg.classList.add("opacity-100", "object-contain");
          }
          if (nameEl) nameEl.textContent = selectedChar;
        } else {
          if (previewImg) {
            previewImg.classList.add("hidden");
            previewImg.classList.remove("opacity-80");
          }
          if (nameEl) nameEl.textContent = "-";
        }
      }
    };

    // attach callbacks to state for UIFactory access
    state.characterGrid.onPortraitHover = onPortraitHover;
    state.characterGrid.onPortraitLeave = onPortraitLeave;

    characters.forEach((character, index) => {
      const portrait = UIFactory.createPortrait(
        character,
        index,
        state,
        (player, char) => selectCharacter(player, char)
      );
      gridContainer.appendChild(portrait);
    });

    updatePlayerBoxes();
    updateCharacterBorders();
  };

  const selectCharacter = (player, character) => {
    if (!character) return;

    const portraits = $$("#character-grid > div");
    const selectedPortrait = Array.from(portraits).find(
      (p) => p.dataset.character === character
    );
    if (!selectedPortrait) return;

    selectedPortrait.classList.add("animate-character-flash");

    setTimeout(() => {
      selectedPortrait.classList.remove("animate-character-flash");

      const state = GameState.get();
      const previousCharacter = state.characterGrid[player].character;
      const shouldResetOutfit = previousCharacter !== character;

      if (player === "p1") {
        GameState.setPlayer1Character(
          character,
          shouldResetOutfit ? 1 : state.characterGrid.p1.outfit
        );
      } else {
        GameState.setPlayer2Character(
          character,
          shouldResetOutfit ? 1 : state.characterGrid.p2.outfit
        );
      }

      updatePlayerPortrait(player, character);
      updateCharacterBorders();

      if (player === state.characterGrid.activePlayer) {
        initOutfitGrid(character);
      }

      setTimeout(() => {
        const event = new CustomEvent("characterSelectionChanged");
        window.dispatchEvent(event);
      }, 0);
    }, animationDuration);
  };

  const updatePlayerPortrait = (player, character) => {
    const portraitImg = $(`#${player}-selected-portrait img`);
    const nameEl = byId(`${player}-selected-name`);
    const portraitBox = byId(`${player}-selected-portrait`);

    const existingPlaceholder = portraitBox.querySelector(
      ".portrait-placeholder"
    );
    if (existingPlaceholder) existingPlaceholder.remove();

    const placeholder = document.createElement("div");
    placeholder.className =
      "portrait-placeholder absolute inset-0 loading-placeholder rounded-lg";
    portraitBox.appendChild(placeholder);

    portraitImg.classList.add("opacity-0");
    portraitImg.src = `/portraits/${character.toLowerCase()}.png`;
    portraitImg.classList.remove("hidden", "opacity-80");
    portraitImg.classList.add("object-contain", "opacity-100");
    nameEl.textContent = character;

    const loadHandler = () => {
      portraitImg.classList.remove("opacity-0");
      portraitImg.classList.add(
        "opacity-100",
        "transition-opacity",
        "duration-300"
      );
      const ph = portraitBox.querySelector(".portrait-placeholder");
      if (ph) ph.remove();
    };

    const errorHandler = () => {
      portraitImg.classList.remove("opacity-0");
      portraitImg.classList.add("opacity-100");
      const ph = portraitBox.querySelector(".portrait-placeholder");
      if (ph)
        ph.innerHTML =
          '<div class="flex items-center justify-center h-full text-sf-red">?</div>';
    };

    portraitImg.addEventListener("load", loadHandler, { once: true });
    portraitImg.addEventListener("error", errorHandler, { once: true });
  };

  const updateCharacterBorders = () => {
    const portraits = $$("#character-grid > div");
    const state = GameState.get();

    portraits.forEach((el) => {
      el.classList.remove("border-sf-red", "border-sf-blue", "border-sf-green");
      el.classList.add("border-transparent");
    });

    const p1Character = state.characterGrid.p1.character;
    const p2Character = state.characterGrid.p2.character;
    const sameCharacter = p1Character === p2Character && p1Character !== null;

    if (sameCharacter) {
      const selected = Array.from(portraits).find(
        (p) => p.dataset.character === p1Character
      );
      if (selected) {
        selected.classList.remove("border-transparent");
        selected.classList.add("border-sf-green");
      }
    } else {
      ["p1", "p2"].forEach((player) => {
        const char = state.characterGrid[player].character;
        if (char) {
          const selected = Array.from(portraits).find(
            (p) => p.dataset.character === char
          );
          if (selected) {
            selected.classList.remove("border-transparent");
            selected.classList.add(`border-${getPlayerColor(player)}`);
          }
        }
      });
    }
  };

  const updatePlayerBoxes = () => {
    const state = GameState.get();
    const p1Portrait = byId("p1-selected-portrait");
    const p2Portrait = byId("p2-selected-portrait");
    const activeColor = getPlayerColor(state.characterGrid.activePlayer);

    if (p1Portrait) {
      p1Portrait.className = `portrait-box border-${
        state.characterGrid.activePlayer === "p1" ? activeColor : "transparent"
      }`;
    }
    if (p2Portrait) {
      p2Portrait.className = `portrait-box border-${
        state.characterGrid.activePlayer === "p2" ? activeColor : "transparent"
      }`;
    }
  };

  const switchActivePlayer = (player) => {
    GameState.switchActivePlayer(player);
    updatePlayerBoxes();
    updateCharacterBorders();

    const state = GameState.get();
    const selectedCharacter = state.characterGrid[player].character;
    if (selectedCharacter) {
      initOutfitGrid(selectedCharacter);
    } else {
      const gridContainer = byId("outfit-grid");
      const indicator = byId("outfit-player-indicator");

      if (gridContainer) gridContainer.innerHTML = "";
      if (indicator)
        indicator.textContent = "Select a character to see outfits";
    }
    GamepadUINavigator.updateGamepadSections(true);
  };

  const initOutfitGrid = (character) => {
    const gridContainer = byId("outfit-grid");
    const indicator = byId("outfit-player-indicator");

    if (!character) {
      if (gridContainer) gridContainer.innerHTML = "";
      if (indicator)
        indicator.textContent = "Select a character to see outfits";
      return;
    }

    const state = GameState.get();
    const activePlayer = state.characterGrid.activePlayer;
    const colorClass = `text-${getPlayerColor(activePlayer)}`;

    let playerText = "";
    if (!state.humanVsLlm) {
      playerText = activePlayer === "p1" ? "LLM 1" : "LLM 2";
    } else {
      playerText = activePlayer === "p1" ? "YOU" : "LLM";
    }

    if (indicator) {
      indicator.innerHTML = `<span class="${colorClass}">${playerText}</span> - ${character} Outfits`;
    }

    if (gridContainer) {
      gridContainer.innerHTML = "";

      for (let i = 0; i < numOutfitsPerCharacter; i++) {
        const outfit = UIFactory.createOutfitBox(
          character,
          i,
          state,
          (player, index) => selectOutfit(player, index)
        );
        gridContainer.appendChild(outfit);
      }
    }

    updateOutfitBorders();
  };

  const selectOutfit = (player, outfitIndex) => {
    const outfitNum = outfitIndex + 1; // 1-based
    const outfits = $$("#outfit-grid > div");
    const selectedOutfit = outfits[outfitIndex];
    if (!selectedOutfit) return;

    selectedOutfit.classList.add("animate-character-flash");

    setTimeout(() => {
      selectedOutfit.classList.remove("animate-character-flash");
      GameState.updateProperty(`characterGrid.${player}.outfit`, outfitNum);
      updateOutfitBorders();
    }, animationDuration);
  };

  const updateOutfitBorders = () => {
    const outfits = $$("#outfit-grid > div");
    const state = GameState.get();
    const activePlayer = state.characterGrid.activePlayer;
    const inactivePlayer = activePlayer === "p1" ? "p2" : "p1";

    const sameCharacter =
      state.characterGrid.p1.character === state.characterGrid.p2.character &&
      state.characterGrid.p1.character !== null;

    outfits.forEach((el, index) => {
      el.classList.remove(
        "border-sf-red",
        "border-sf-blue",
        "border-sf-green",
        "border-transparent"
      );

      const outfitNum = index + 1;
      const p1Selected = state.characterGrid.p1.outfit === outfitNum;
      const p2Selected = state.characterGrid.p2.outfit === outfitNum;

      if (sameCharacter && p1Selected && p2Selected) {
        el.classList.add("border-sf-green");
      } else if (state.characterGrid[activePlayer].outfit === outfitNum) {
        el.classList.add(`border-${getPlayerColor(activePlayer)}`);
      } else if (
        sameCharacter &&
        state.characterGrid[inactivePlayer].outfit === outfitNum
      ) {
        el.classList.add(`border-${getPlayerColor(inactivePlayer)}`);
      } else {
        el.classList.add("border-transparent");
      }
    });
  };

  const getPlayerColor = (player) => {
    return player === "p1" ? "sf-blue" : "sf-red";
  };

  const setupPlayerBoxListeners = () => {
    ["p1", "p2"].forEach((player) => {
      const box = byId(`${player}-selected-portrait`);
      if (box) {
        box.addEventListener("click", () => {
          switchActivePlayer(player);
          AudioManager.playSound(SOUND_KEYS.CLICK);
        });
      }
    });
  };

  return {
    initCharacterGrid,
    selectCharacter,
    switchActivePlayer,
    updateCharacterBorders,
    updatePlayerBoxes,
    updateOutfitBorders,
    initOutfitGrid,
    setupPlayerBoxListeners,
  };
};

export const CharacterSelectionManager = createCharacterSelectionManager();
