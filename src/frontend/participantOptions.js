export const PARTICIPANT_SPECS = {
  human: { label: "YOU", kind: "human", seats: ["P1"] },
  cpu: { label: "CPU", kind: "cpu", seats: ["P2"] },
  qwen35_9b: { label: "QWEN3.5-9B", kind: "model", seats: ["P1", "P2"] },
  gemma4_31b: { label: "GEMMA4-31B", kind: "model", seats: ["P1", "P2"] },
  ministral3_14b: {
    label: "MINISTRAL3-14B",
    kind: "model",
    seats: ["P1", "P2"],
  },
};

export const PARTICIPANT_LABELS = Object.fromEntries(
  Object.entries(PARTICIPANT_SPECS).map(([participant, spec]) => [
    participant,
    spec.label,
  ])
);

export const getParticipantLabel = (participant) =>
  PARTICIPANT_LABELS[participant] || participant;

export const getWinnerLabel = (participant, player, opponentParticipant) => {
  const label = getParticipantLabel(participant);
  return participant === opponentParticipant
    ? `${label} (${player.toUpperCase()})`
    : label;
};

export const isHumanParticipant = (participant) =>
  PARTICIPANT_SPECS[participant]?.kind === "human";

export const isCpuParticipant = (participant) =>
  PARTICIPANT_SPECS[participant]?.kind === "cpu";

export const getParticipantsForSeat = (seat) =>
  Object.entries(PARTICIPANT_SPECS)
    .filter(([, spec]) => spec.seats.includes(seat))
    .map(([participant, spec]) => ({ participant, ...spec }));
