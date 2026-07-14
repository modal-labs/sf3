export const PARTICIPANT_LABELS = {
  human: "YOU",
  qwen36_35ba3b_fp8: "QWEN3.6-35B",
  gemma4_31b: "GEMMA4-31B",
  ministral3_14b: "MINISTRAL3-14B",
};

export const getParticipantLabel = (participant) =>
  PARTICIPANT_LABELS[participant] || participant;

export const getWinnerLabel = (participant, player, opponentParticipant) => {
  const label = getParticipantLabel(participant);
  return participant === opponentParticipant
    ? `${label} (${player.toUpperCase()})`
    : label;
};

export const isHumanParticipant = (participant) => participant === "human";
