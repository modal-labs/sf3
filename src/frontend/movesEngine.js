export const MovesEngine = {
  preprocessMoves(
    currentCharacter,
    specialMoves,
    combos,
    playerDirection,
    selectedSuperArt
  ) {
    const movesByLength = {};
    if (!currentCharacter || !specialMoves || !combos) return movesByLength;

    const characterMoves = specialMoves[currentCharacter];
    const characterCombos = combos[currentCharacter];

    const isSuperArtMove = (moveKey) =>
      moveKey.startsWith(`${selectedSuperArt} `) ||
      (moveKey.startsWith("Max") &&
        (moveKey.startsWith(`Max-${selectedSuperArt} `) ||
          moveKey.startsWith("Max ")));

    const addMoveToLength = (sequence, type, name) => {
      if (!sequence) return;
      const len = sequence.length;
      if (!movesByLength[len]) movesByLength[len] = [];
      movesByLength[len].push({ type, name, sequence });
    };

    if (characterMoves) {
      for (const [moveKey, moveData] of Object.entries(characterMoves)) {
        if (isSuperArtMove(moveKey)) {
          const seq = moveData[playerDirection];
          addMoveToLength(seq, "super_art", moveKey);
        }
      }
    }

    if (characterCombos) {
      for (const [comboName, comboData] of Object.entries(characterCombos)) {
        const seq = comboData[playerDirection];
        addMoveToLength(seq, "combo", comboName);
      }
    }

    for (const len in movesByLength) {
      movesByLength[len].sort((a, b) =>
        a.type === "super_art" && b.type === "combo"
          ? -1
          : a.type === "combo" && b.type === "super_art"
          ? 1
          : 0
      );
    }

    return movesByLength;
  },

  detectExtra(inputHistory, comboTimeout, movesByLength) {
    const now = Date.now();
    const recent = inputHistory.filter(
      (input) => now - input.time <= comboTimeout
    );
    if (recent.length < 2) return { match: null, history: recent };

    for (let len = recent.length; len >= 2; len--) {
      const moves = movesByLength[len];
      if (!moves) continue;
      const startIndex = recent.length - len;
      for (const move of moves) {
        let ok = true;
        for (let i = 0; i < len; i++) {
          if (recent[startIndex + i].action !== move.sequence[i]) {
            ok = false;
            break;
          }
        }
        if (ok)
          return { match: { type: move.type, name: move.name }, history: [] };
      }
    }
    return { match: null, history: recent };
  },
};

export const MovesDisplay = {
  getSpecialMoveDisplayName(fullKey) {
    if (/^\d+ /.test(fullKey)) return fullKey.substring(2);
    if (fullKey.startsWith("Max-")) {
      const parts = fullKey.split(" ");
      return "Max " + parts.slice(1).join(" ");
    }
    return fullKey;
  },

  getExtraElements(sequence, idxToMove, isGamepadConnected) {
    const buttons = sequence
      .map((action) => {
        const move = idxToMove[action];
        const symbol = isGamepadConnected ? move.gamepadDisplay : move.display;
        return `<span class="game-ctrl">${symbol}</span>`;
      })
      .join("");
    return `<div class="flex items-center flex-wrap gap-1">${buttons}</div>`;
  },

  generateMovesHTML(moves, idxToMove, isGamepadConnected) {
    const moveElements = moves
      .map(
        (move) => `
            <div class="flex justify-between items-center gap-4">
                ${this.getExtraElements(
                  move.sequence,
                  idxToMove,
                  isGamepadConnected
                )}
                <h3 class="text-sf-gold">${move.name}</h3>
            </div>
        `
      )
      .join("");
    return moveElements;
  },
};
