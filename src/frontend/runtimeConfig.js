const getGameplayBaseUrl = () => {
  const baseUrl = window.__SF3_CONFIG__?.gameplayBaseUrl?.trim() || "";
  return baseUrl.replace(/\/+$/, "");
};

const SCHEME_PREFIX = /^[a-zA-Z][a-zA-Z\d+.-]*:\/\//;

const getParsedGameplayBaseUrl = () => {
  const baseUrl = getGameplayBaseUrl();
  if (!baseUrl) return null;

  const normalizedBaseUrl = SCHEME_PREFIX.test(baseUrl)
    ? baseUrl
    : `${window.location.protocol}//${baseUrl.replace(/^\/+/, "")}`;

  try {
    return new URL(normalizedBaseUrl);
  } catch {
    return null;
  }
};

export const gameplayUrl = (path) => {
  const baseUrl = getParsedGameplayBaseUrl();
  return baseUrl ? new URL(path, baseUrl).toString() : path;
};

export const gameplayWebSocketUrl = () => {
  const url = new URL(gameplayUrl("/ws"), window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.search = "";
  url.hash = "";
  return url.toString();
};
