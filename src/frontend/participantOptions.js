export const PARTICIPANT_SPECS = {
  human: {
    label: "YOU",
    kind: "human",
    logo: "/logos/human.webp",
    seats: ["P1"],
  },
  cpu: {
    label: "CPU",
    kind: "cpu",
    logo: "/logos/cpu.webp",
    seats: ["P2"],
  },
  qwen35_9b: {
    label: "QWEN3.5-9B",
    kind: "model",
    logo: "/logos/qwen.webp",
    seats: ["P1", "P2"],
  },
  gemma4_31b: {
    label: "GEMMA4-31B",
    kind: "model",
    logo: "/logos/google.webp",
    seats: ["P1", "P2"],
  },
  ministral3_14b: {
    label: "MINISTRAL3-14B",
    kind: "model",
    logo: "/logos/mistral.webp",
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

export const isHumanParticipant = (participant) =>
  PARTICIPANT_SPECS[participant]?.kind === "human";

export const isCpuParticipant = (participant) =>
  PARTICIPANT_SPECS[participant]?.kind === "cpu";

export const isModelParticipant = (participant) =>
  PARTICIPANT_SPECS[participant]?.kind === "model";

export const getHumanSeat = (state) => {
  if (isHumanParticipant(state.player1Participant)) return "P1";
  if (isHumanParticipant(state.player2Participant)) return "P2";
  return null;
};

export const hasHumanParticipant = (state) => getHumanSeat(state) !== null;

export const getParticipantsForSeat = (seat) =>
  Object.entries(PARTICIPANT_SPECS)
    .filter(([, spec]) => spec.seats.includes(seat))
    .map(([participant, spec]) => ({ participant, ...spec }));
