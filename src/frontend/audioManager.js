import { byId } from "./utils.js";
import { SOUND_KEYS } from "./constants.js";

const trackSlots = {
  phase: "phaseSound",
};

const gestureEvents = ["click", "touchend", "keydown"];

export const AudioManager = {
  sounds: {},
  soundSources: {},
  pendingPlaybacks: new Map(),
  enabled: true,
  volume: 0.5,
  effectSound: null,
  phaseSound: null,
  isMobile: /iPhone|iPad|iPod|Android/i.test(navigator.userAgent),
  gestureListenersInstalled: false,

  init() {
    this.enabled = localStorage.getItem("audioEnabled") !== "false";
    this.setupMuteButton();
    this.setupGestureListeners();
  },

  soundUrl(relativePath) {
    return `/sounds/${relativePath
      .split("/")
      .map(encodeURIComponent)
      .join("/")}`;
  },

  async preloadSounds(soundFiles, gameplayMusicMap) {
    Object.entries(soundFiles).forEach(([key, relativePath]) => {
      this.soundSources[key] = this.soundUrl(relativePath);
    });

    Object.entries(gameplayMusicMap).forEach(([key, relativePath]) => {
      this.soundSources[key] = this.soundUrl(relativePath);
    });

    if (this.isMobile) {
      return;
    }

    const promises = Object.keys(soundFiles).map((key) => {
      const asset = this.getOrCreateSound(key);
      asset.preload = "auto";
      if (asset.readyState >= 2) return Promise.resolve();

      const ready = new Promise((resolve) => {
        const resolveOnce = () => {
          clearTimeout(timeout);
          resolve();
        };
        const timeout = setTimeout(resolveOnce, 5000);
        asset.addEventListener("loadeddata", resolveOnce, { once: true });
        asset.addEventListener("canplaythrough", resolveOnce, { once: true });
        asset.addEventListener("error", resolveOnce, { once: true });
      });
      return ready;
    });

    Object.keys(gameplayMusicMap).forEach((key) => {
      this.getOrCreateSound(key);
    });

    await Promise.all(promises);
  },

  getOrCreateSound(soundName) {
    if (this.sounds[soundName]) return this.sounds[soundName];

    const source = this.soundSources[soundName];
    if (!source) return null;

    const existingName = Object.keys(this.sounds).find(
      (name) => this.soundSources[name] === source
    );
    if (existingName) {
      this.sounds[soundName] = this.sounds[existingName];
      return this.sounds[soundName];
    }

    const sound = new Audio();
    sound.volume = this.volume;
    sound.muted = !this.enabled;
    const isUiSound = Object.values(SOUND_KEYS).includes(soundName);
    sound.preload = this.isMobile || !isUiSound ? "none" : "auto";
    sound.src = source;
    sound.addEventListener("play", () => {
      this.enforceChannelOwnership(sound);
    });
    this.sounds[soundName] = sound;
    return sound;
  },

  setupGestureListeners() {
    if (this.gestureListenersInstalled) return;

    gestureEvents.forEach((eventName) => {
      window.addEventListener(eventName, () => {
        this.retryPendingPlaybacks();
      });
    });
    this.gestureListenersInstalled = true;
  },

  retryPendingPlaybacks() {
    const requests = Array.from(this.pendingPlaybacks.values());
    this.pendingPlaybacks.clear();

    requests.forEach((request) => {
      if (request.kind === "play") {
        this.play(request.soundName, request.options);
      } else if (request.kind === "resume") {
        this.resumeTrack(request.trackType);
      }
    });
  },

  removePlaybackListeners(sound) {
    if (sound._activeEndHandler) {
      sound.removeEventListener("ended", sound._activeEndHandler);
      delete sound._activeEndHandler;
    }
    if (sound._activeErrorHandler) {
      sound.removeEventListener("error", sound._activeErrorHandler);
      delete sound._activeErrorHandler;
    }
  },

  cleanupPlaybackAttempt(sound, soundProp, onEndHandler, onErrorHandler) {
    if (
      sound._activeEndHandler !== onEndHandler ||
      sound._activeErrorHandler !== onErrorHandler
    ) {
      return false;
    }

    this.removePlaybackListeners(sound);
    if (soundProp) {
      if (this[soundProp] === sound) this[soundProp] = null;
    } else {
      if (this.effectSound === sound) this.effectSound = null;
    }
    delete sound._volumeMultiplier;
    delete sound._channel;
    return true;
  },

  enforceChannelOwnership(sound) {
    const ownsPhase = sound._channel === "phase" && this.phaseSound === sound;
    const ownsEffect = sound._channel === "effect" && this.effectSound === sound;
    if (!ownsPhase && !ownsEffect) {
      sound.pause();
    }
  },

  stopEffect() {
    this.pendingPlaybacks.delete("effect");
    const sound = this.effectSound;
    if (!sound) return;

    sound.pause();
    sound.currentTime = 0;
    sound.loop = false;
    this.removePlaybackListeners(sound);
    delete sound._volumeMultiplier;
    delete sound._channel;
    this.effectSound = null;
  },

  play(soundName, options = {}) {
    const {
      volume = 1,
      loop = false,
      trackAs = "effect",
      onEnd = null,
      onError = null,
    } = options;
    const sound = this.getOrCreateSound(soundName);

    if (!sound) {
      console.warn(`No sound found for: ${soundName}`);
      return false;
    }

    const soundProp = trackSlots[trackAs];
    const pendingKey = soundProp ? `track:${trackAs}` : "effect";
    if (soundProp) {
      this.stopTrack(trackAs);
    } else {
      this.stopEffect();
    }

    this.removePlaybackListeners(sound);

    sound.currentTime = 0;
    sound.loop = loop;
    sound.volume = this.enabled ? this.volume * volume : 0;
    sound.muted = !this.enabled;
    sound._volumeMultiplier = volume;

    if (soundProp) {
      this[soundProp] = sound;
      sound._channel = "phase";
    } else {
      this.effectSound = sound;
      sound._channel = "effect";
    }

    const onEndHandler = () => {
      if (
        !this.cleanupPlaybackAttempt(
          sound,
          soundProp,
          onEndHandler,
          onErrorHandler
        )
      ) {
        return;
      }
      if (onEnd) onEnd();
    };
    const onErrorHandler = (error) => {
      if (
        !this.cleanupPlaybackAttempt(
          sound,
          soundProp,
          onEndHandler,
          onErrorHandler
        )
      ) {
        return;
      }
      const playbackError = sound.error || error;
      console.warn(`Failed to play sound: ${soundName}`, playbackError);
      if (onError) onError(playbackError);
    };

    sound._activeEndHandler = onEndHandler;
    sound._activeErrorHandler = onErrorHandler;
    sound.addEventListener("ended", onEndHandler, { once: true });
    sound.addEventListener("error", onErrorHandler, { once: true });

    sound.play().catch((error) => {
      if (error.name !== "NotAllowedError") {
        console.warn(`Failed to play sound: ${soundName}`, error);
      }
      if (
        !this.cleanupPlaybackAttempt(
          sound,
          soundProp,
          onEndHandler,
          onErrorHandler
        )
      ) {
        return;
      }

      if (error.name === "NotAllowedError") {
        this.pendingPlaybacks.set(pendingKey, {
          kind: "play",
          soundName,
          options,
        });
        return;
      }

      if (onError) onError(error);
    });
    return true;
  },

  playPhase(soundName, options = {}) {
    const sound = this.getOrCreateSound(soundName);
    if (!sound) {
      console.warn(`No sound found for: ${soundName}`);
      return false;
    }

    const { volume = 1, loop = true } = options;
    if (this.phaseSound === sound) {
      sound.loop = loop;
      sound._volumeMultiplier = volume;
      sound.volume = this.enabled ? this.volume * volume : 0;
      sound.muted = !this.enabled;
      if (sound.paused) {
        return this.resumeTrack("phase");
      }
      return true;
    }

    return this.play(soundName, {
      ...options,
      loop,
      trackAs: "phase",
    });
  },

  playSound(soundName) {
    this.play(soundName, { trackAs: "effect" });
  },

  stopTrack(trackType) {
    const soundProp = trackSlots[trackType];
    if (!soundProp) return;
    this.pendingPlaybacks.delete(`track:${trackType}`);
    const sound = this[soundProp];

    if (sound) {
      sound.pause();
      sound.currentTime = 0;
      sound.loop = false;
      this.removePlaybackListeners(sound);
      delete sound._volumeMultiplier;
      delete sound._channel;
      this[soundProp] = null;
    }
  },

  pauseTrack(trackType) {
    const soundProp = trackSlots[trackType];
    if (!soundProp) return;
    this.pendingPlaybacks.delete(`track:${trackType}`);
    const sound = this[soundProp];
    if (sound) {
      sound.pause();
    }
  },

  resumeTrack(trackType) {
    const soundProp = trackSlots[trackType];
    if (!soundProp) return false;
    const sound = this[soundProp];
    if (!sound) return false;
    const pendingKey = `track:${trackType}`;
    this.pendingPlaybacks.delete(pendingKey);
    if (!sound.paused) return true;

    const multiplier = sound._volumeMultiplier ?? 1;
    sound.volume = this.enabled ? this.volume * multiplier : 0;
    sound.muted = !this.enabled;
    sound.play().catch((error) => {
      if (error.name === "NotAllowedError") {
        if (this[soundProp] === sound) {
          this.pendingPlaybacks.set(pendingKey, {
            kind: "resume",
            trackType,
          });
        }
        return;
      }

      console.warn(`Failed to resume ${trackType} track`, error);
    });
    return true;
  },

  stopAll() {
    Object.keys(trackSlots).forEach((trackType) => {
      this.stopTrack(trackType);
    });
    this.stopEffect();
    this.pendingPlaybacks.clear();
  },

  toggleMute() {
    this.enabled = !this.enabled;
    localStorage.setItem("audioEnabled", this.enabled);
    this.updateMuteButton();

    Object.values(trackSlots).forEach((soundProp) => {
      const sound = this[soundProp];
      if (!sound) return;
      const multiplier = sound._volumeMultiplier ?? 1;
      sound.volume = this.enabled ? this.volume * multiplier : 0;
      sound.muted = !this.enabled;
    });

    if (this.effectSound) {
      const sound = this.effectSound;
      const multiplier = sound._volumeMultiplier ?? 1;
      sound.volume = this.enabled ? this.volume * multiplier : 0;
      sound.muted = !this.enabled;
    }
  },

  setupMuteButton() {
    const muteButton = byId("mute-toggle");
    if (muteButton) {
      muteButton.addEventListener("click", () => {
        this.toggleMute();
        this.playSound(SOUND_KEYS.CLICK);
      });

      muteButton.addEventListener("mouseenter", () => {
        this.playSound(SOUND_KEYS.HOVER);
      });
    }

    this.updateMuteButton();
  },

  updateMuteButton() {
    const muteIcon = byId("mute-icon");
    if (muteIcon) {
      muteIcon.src = this.enabled ? "/icons/unmute.svg" : "/icons/mute.svg";
    }

    const muteButton = byId("mute-toggle");
    if (!muteButton) return;

    const enabledClasses = [
      "border-sf-green",
      "bg-sf-dark",
      "hover:bg-sf-darker",
      "hover:border-sf-green-dark",
    ];
    const disabledClasses = [
      "border-sf-gold",
      "bg-sf-darker",
      "hover:bg-sf-dark",
      "hover:border-sf-gold-dark",
    ];
    muteButton.classList.remove(...enabledClasses, ...disabledClasses);
    if (this.enabled) {
      muteButton.classList.add(...enabledClasses);
    } else {
      muteButton.classList.add(...disabledClasses);
    }
  },
};

export const playHover = () => AudioManager.playSound(SOUND_KEYS.HOVER);
export const playClick = () => AudioManager.playSound(SOUND_KEYS.CLICK);
