import { AudioManager } from "./audioManager.js";
import { SOUND_KEYS } from "./constants.js";

export const UIFactory = {
  // portrait or outfit
  createSelectable(type, params, gameState) {
    const { character, index, imageSrc, imageAlt, labelText, onClick } = params;

    const isPortrait = type === "portrait";
    const element = this.createImageBox({
      className: isPortrait
        ? "relative w-full aspect-square bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200"
        : "relative size-24 bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200 mx-auto",
      imageSrc,
      imageAlt,
      imageClassName: isPortrait
        ? "relative size-full object-contain rounded-lg p-1"
        : "relative size-full object-contain bg-sf-dark rounded-lg",
    });

    if (isPortrait) {
      element.dataset.character = character;
      element.dataset.index = index;
    } else {
      element.dataset.outfit = index;
    }

    const label = document.createElement("div");
    label.className =
      "absolute bottom-0 left-0 right-0 p-1 text-center font-bold text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg";
    label.textContent = labelText;
    element.appendChild(label);

    element.addEventListener("mouseenter", () => {
      const getPlayerColor = (player) =>
        player === "p1" ? "sf-red" : "sf-blue";

      if (
        !element.classList.contains("border-sf-red") &&
        !element.classList.contains("border-sf-blue")
      ) {
        element.classList.remove("border-transparent");
        const currentBorderColor = `border-${getPlayerColor(
          gameState.characterGrid.activePlayer
        )}`;
        element.classList.add(currentBorderColor);
        AudioManager.playSound(SOUND_KEYS.HOVER);

        if (isPortrait && gameState.onPortraitHover) {
          gameState.onPortraitHover(character, imageSrc);
        }
      }
    });

    element.addEventListener("mouseleave", () => {
      const isSelected = isPortrait
        ? gameState.characterGrid[gameState.characterGrid.activePlayer]
            .character === character
        : gameState.characterGrid[gameState.characterGrid.activePlayer]
            .outfit ===
          index + 1;

      if (!isSelected) {
        element.classList.remove("border-sf-red", "border-sf-blue");
        element.classList.add("border-transparent");
      }

      if (isPortrait && gameState.onPortraitLeave) {
        gameState.onPortraitLeave(character);
      }
    });

    element.addEventListener("click", () => {
      onClick();
      AudioManager.playSound(SOUND_KEYS.CLICK);
    });

    return element;
  },

  createOutfitBox(character, index, gameState, onSelect) {
    const outfit = this.createSelectable(
      "outfit",
      {
        character,
        index,
        imageSrc: `/outfits/${character}/${index}.png`,
        imageAlt: `Outfit ${index + 1}`,
        labelText: `${index + 1}`,
        onClick: () => onSelect(gameState.characterGrid.activePlayer, index),
      },
      gameState
    );

    if (!outfit.id) {
      outfit.id = `outfit-${character.toLowerCase()}-${index}`;
    }

    return outfit;
  },

  createPortrait(character, index, gameState, onSelect) {
    const portrait = this.createSelectable(
      "portrait",
      {
        character,
        index,
        imageSrc: `/portraits/${character.toLowerCase()}.png`,
        imageAlt: character,
        labelText: character,
        onClick: () =>
          onSelect(gameState.characterGrid.activePlayer, character),
      },
      gameState
    );

    if (!portrait.id) {
      portrait.id = `character-portrait-${character.toLowerCase()}`;
    }

    return portrait;
  },

  createImageBox({ className, imageSrc, imageAlt, imageClassName }) {
    const box = document.createElement("div");
    box.className = className;

    const placeholder = document.createElement("div");
    placeholder.className = "absolute inset-0 loading-placeholder rounded-lg";
    box.appendChild(placeholder);

    const img = document.createElement("img");
    img.src = imageSrc;
    img.alt = imageAlt;
    img.className =
      imageClassName + " opacity-0 transition-opacity duration-300";

    img.addEventListener(
      "load",
      () => {
        img.classList.remove("opacity-0");
        img.classList.add("opacity-100");
        placeholder.remove();
      },
      { once: true }
    );

    img.addEventListener(
      "error",
      () => {
        img.classList.remove("opacity-0");
        img.classList.add("opacity-100");
        placeholder.innerHTML =
          '<div class="flex items-center justify-center h-full text-sf-red">?</div>';
      },
      { once: true }
    );

    box.appendChild(img);
    return box;
  },
};
