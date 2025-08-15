import { byId } from "./utils.js";

export const WebSocketManager = {
  socket: null,
  onMessage: null,

  init(callbacks = {}) {
    this.onMessage = callbacks.onMessage || (() => {});

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.socket = new WebSocket(wsUrl);
    const startButton = byId("start-game-btn");

    this.socket.onopen = () => console.log("Connected to server");

    this.socket.onclose = () => {
      console.log("Disconnected from server");
      if (startButton && !startButton.textContent.includes("START GAME")) {
        startButton.textContent = "Connection Lost";
        startButton.disabled = true;
        startButton.classList.add("opacity-50");
      }
    };

    this.socket.onerror = (event) => {
      console.error("WebSocket connection error", event);
      if (startButton && !startButton.textContent.includes("START GAME")) {
        startButton.textContent = "Connection Error";
        startButton.disabled = true;
        startButton.classList.add("opacity-50");
      }
    };

    this.socket.onmessage = (event) => this.onMessage(event);

    startButton.disabled = true;
    startButton.classList.add("opacity-50");
  },

  send(type, data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(
          JSON.stringify({
            type: type,
            data: data,
          })
        );
      } catch (e) {
        console.error("websocket send fail", e);
      }
    }
  },

  close() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  },
};
