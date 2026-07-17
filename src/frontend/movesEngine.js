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
