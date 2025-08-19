import { AudioManager } from "./audioManager.js";
import { SOUND_KEYS } from "./constants.js";

export const UIFactory = {
  // portrait or outfit
  createSelectable(type, params, gameState) {
    const { character, index, imageSrc, imageAlt, labelText, onClick } = params;

    const isPortrait = type === "portrait";
    const element = this.createImageBox({
      className: isPortrait
        ? "relative size-16 lg:size-20 aspect-square bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200"
        : "relative size-16 lg:size-20 bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200 mx-auto",
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
      "absolute bottom-0 left-0 right-0 p-0.5 lg:p-1 text-center font-bold text-xs lg:text-sm text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg";
    label.textContent = labelText;
    element.appendChild(label);

    element.addEventListener("mouseenter", () => {
      const getPlayerColor = (player) =>
        player === "p1" ? "sf-blue" : "sf-red";

      const isSelectedByP1 =
        isPortrait && gameState.characterGrid.p1.character === character;
      const isSelectedByP2 =
        isPortrait && gameState.characterGrid.p2.character === character;

      if (isPortrait) {
        if (!isSelectedByP1 && !isSelectedByP2) {
          element.classList.remove("border-transparent");
          const currentBorderColor = `border-${getPlayerColor(
            gameState.characterGrid.activePlayer
          )}`;
          element.classList.add(currentBorderColor);
        }
      } else {
        if (
          !element.classList.contains("border-sf-red") &&
          !element.classList.contains("border-sf-blue") &&
          !element.classList.contains("border-sf-green")
        ) {
          element.classList.remove("border-transparent");
          const currentBorderColor = `border-${getPlayerColor(
            gameState.characterGrid.activePlayer
          )}`;
          element.classList.add(currentBorderColor);
        }
      }

      AudioManager.playSound(SOUND_KEYS.HOVER);

      if (
        isPortrait &&
        gameState.characterGrid &&
        gameState.characterGrid.onPortraitHover
      ) {
        gameState.characterGrid.onPortraitHover(character, imageSrc);
      }
    });

    element.addEventListener("mouseleave", () => {
      const isSelectedByP1 = isPortrait
        ? gameState.characterGrid.p1.character === character
        : gameState.characterGrid.p1.outfit === index + 1;

      const isSelectedByP2 = isPortrait
        ? gameState.characterGrid.p2.character === character
        : gameState.characterGrid.p2.outfit === index + 1;

      if (!isSelectedByP1 && !isSelectedByP2) {
        element.classList.remove(
          "border-sf-red",
          "border-sf-blue",
          "border-sf-green"
        );
        element.classList.add("border-transparent");
      } else if (isPortrait) {
        element.classList.remove(
          "border-sf-red",
          "border-sf-blue",
          "border-sf-green",
          "border-transparent"
        );
        if (isSelectedByP1 && isSelectedByP2) {
          element.classList.add("border-sf-green");
        } else if (isSelectedByP1) {
          element.classList.add("border-sf-blue");
        } else if (isSelectedByP2) {
          element.classList.add("border-sf-red");
        }
      } else {
        const sameCharacter =
          gameState.characterGrid.p1.character ===
          gameState.characterGrid.p2.character;
        element.classList.remove(
          "border-sf-red",
          "border-sf-blue",
          "border-sf-green",
          "border-transparent"
        );

        if (sameCharacter && isSelectedByP1 && isSelectedByP2) {
          element.classList.add("border-sf-green");
        } else if (isSelectedByP1) {
          element.classList.add("border-sf-blue");
        } else if (isSelectedByP2) {
          element.classList.add("border-sf-red");
        } else {
          element.classList.add("border-transparent");
        }
      }

      if (
        isPortrait &&
        gameState.characterGrid &&
        gameState.characterGrid.onPortraitLeave
      ) {
        gameState.characterGrid.onPortraitLeave(character);
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
