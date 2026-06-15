import { byId } from "./utils.js";
import { gameplayWebSocketUrl } from "./runtimeConfig.js";

const iceServerTimeoutMs = 3000;
const fallbackIceServers = [{ urls: "stun:stun.l.google.com:19302" }];

export const WebRtcManager = {
  ws: null,
  peer: null,
  dataChannel: null,
  onMessage: null,
  onRemoteStream: null,
  onDisconnect: null,
  peerId: "",
  turnResolver: null,
  hasStarted: false,
  pendingMessages: [],
  pendingRemoteStream: null,
  pendingOutbound: [],

  init(callbacks = {}) {
    this.onMessage = callbacks.onMessage || null;
    this.onRemoteStream = callbacks.onRemoteStream || null;
    this.onDisconnect = callbacks.onDisconnect || null;

    if (this.onMessage && this.pendingMessages.length > 0) {
      const messages = [...this.pendingMessages];
      this.pendingMessages = [];
      messages.forEach((raw) => this.onMessage?.(raw));
    }

    if (this.onRemoteStream && this.pendingRemoteStream) {
      this.onRemoteStream(this.pendingRemoteStream);
      this.pendingRemoteStream = null;
    }

    if (this.hasStarted) {
      return;
    }

    const startButton = byId("start-game-btn");
    if (startButton) {
      startButton.disabled = true;
      startButton.classList.add("opacity-50");
    }

    this.hasStarted = true;
    this.connect();
  },

  async connect() {
    try {
      this.peerId = this.generateShortId();
      await this.openSignalingSocket();
      const iceServers = await this.getIceServers();
      this.peer = new RTCPeerConnection({ iceServers });
      this.peer.addTransceiver("video", { direction: "recvonly" });

      this.peer.onicecandidate = (event) => {
        if (!event.candidate || !event.candidate.candidate) {
          return;
        }
        this.sendSignal({
          type: "ice_candidate",
          candidate: {
            candidate_sdp: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex,
          },
          peer_id: this.peerId,
        });
      };

      this.peer.ontrack = (event) => {
        const stream =
          event.streams[0] ||
          (event.track ? new MediaStream([event.track]) : null);
        if (!stream) {
          return;
        }
        if (this.onRemoteStream) {
          this.onRemoteStream(stream);
          return;
        }
        this.pendingRemoteStream = stream;
      };

      this.peer.onconnectionstatechange = () => {
        const state = this.peer?.connectionState;
        if (state === "failed" || state === "disconnected" || state === "closed") {
          this.handleDisconnect("Game connection lost.");
        }
      };

      this.dataChannel = this.peer.createDataChannel("game_control");
      this.dataChannel.onopen = () => {
        this.flushPendingOutbound();
      };
      this.dataChannel.onmessage = (event) => {
        const raw = String(event.data);
        if (this.onMessage) {
          this.onMessage(raw);
          return;
        }
        this.pendingMessages.push(raw);
      };
      this.dataChannel.onclose = () => {
        this.handleDisconnect("Game data channel closed.");
      };
      this.flushPendingOutbound();

      const offer = await this.peer.createOffer();
      await this.peer.setLocalDescription(offer);
      this.sendSignal({
        type: offer.type,
        sdp: offer.sdp || "",
        peer_id: this.peerId,
      });
    } catch (error) {
      console.error("WebRTC connect error", error);
      this.handleDisconnect("Connection Error");
      this.hasStarted = false;
    }
  },

  async openSignalingSocket() {
    const wsUrl = `${gameplayWebSocketUrl()}/${this.peerId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      this.handleSignalingMessage(String(event.data));
    };
    this.ws.onclose = () => {
      if (!this.peer || this.peer.connectionState !== "connected") {
        this.handleDisconnect("Signaling connection lost.");
      }
    };
    this.ws.onerror = () => {
      this.handleDisconnect("Connection Error");
    };

    await new Promise((resolve, reject) => {
      const ws = this.ws;
      if (!ws) {
        reject(new Error("websocket missing"));
        return;
      }

      const onOpen = () => {
        ws.removeEventListener("error", onError);
        resolve();
      };
      const onError = () => {
        ws.removeEventListener("open", onOpen);
        reject(new Error("signaling websocket error"));
      };

      ws.addEventListener("open", onOpen, { once: true });
      ws.addEventListener("error", onError, { once: true });
    });
  },

  async getIceServers() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return fallbackIceServers;
    }

    const iceServerPromise = new Promise((resolve) => {
      this.turnResolver = resolve;
    });
    this.sendSignal({ type: "get_turn_servers", peer_id: this.peerId });

    try {
      return await Promise.race([
        iceServerPromise,
        new Promise((resolve) =>
          setTimeout(() => resolve(fallbackIceServers), iceServerTimeoutMs)
        ),
      ]);
    } catch {
      return fallbackIceServers;
    } finally {
      this.turnResolver = null;
    }
  },

  async handleSignalingMessage(raw) {
    let message;
    try {
      message = JSON.parse(raw);
    } catch {
      return;
    }

    if (message.type === "turn_servers" && message.ice_servers && this.turnResolver) {
      this.turnResolver(message.ice_servers);
      return;
    }

    if (message.type === "answer" && this.peer && message.sdp) {
      await this.peer.setRemoteDescription(
        new RTCSessionDescription({ type: "answer", sdp: message.sdp })
      );
      return;
    }

    if (message.type === "ice_candidate" && this.peer && message.candidate) {
      await this.peer.addIceCandidate(
        new RTCIceCandidate({
          candidate: message.candidate.candidate_sdp,
          sdpMid: message.candidate.sdpMid,
          sdpMLineIndex: message.candidate.sdpMLineIndex,
        })
      );
    }
  },

  sendSignal(message) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify(message));
  },

  send(type, data) {
    const payload = JSON.stringify({ type, data });
    if (!this.dataChannel || this.dataChannel.readyState !== "open") {
      this.pendingOutbound.push(payload);
      return;
    }
    this.dataChannel.send(payload);
  },

  flushPendingOutbound() {
    if (!this.dataChannel || this.dataChannel.readyState !== "open") {
      return;
    }
    while (this.pendingOutbound.length > 0) {
      const payload = this.pendingOutbound.shift();
      if (payload) {
        this.dataChannel.send(payload);
      }
    }
  },

  close() {
    this.onDisconnect = null;
    if (this.dataChannel) {
      this.dataChannel.close();
      this.dataChannel = null;
    }
    if (this.peer) {
      this.peer.close();
      this.peer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.turnResolver = null;
    this.hasStarted = false;
    this.pendingMessages = [];
    this.pendingRemoteStream = null;
    this.pendingOutbound = [];
  },

  handleDisconnect(message) {
    this.updateStartButton("Connection Lost");
    this.onDisconnect?.(message);
  },

  updateStartButton(text) {
    const startButton = byId("start-game-btn");
    if (!startButton || startButton.textContent?.includes("START GAME")) {
      return;
    }
    startButton.textContent = text;
    startButton.disabled = true;
    startButton.classList.add("opacity-50");
  },

  generateShortId() {
    const chars =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let result = "";
    for (let i = 0; i < 22; i += 1) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  },
};
