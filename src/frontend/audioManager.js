import { byId } from "./utils.js";
import { SOUND_KEYS } from "./constants.js";

export const AudioManager = {
  sounds: {},
  enabled: true,
  volume: 0.5,
  currentEffects: [],
  selectSound: null,
  transitionSound: null,
  winLoseSound: null,
  isMobile: /iPhone|iPad|iPod|Android/i.test(navigator.userAgent),

  init() {
    if (this.isMobile) {
      this.enabled = false;
      return;
    }

    this.enabled = localStorage.getItem("audioEnabled") !== "false";
    this.setupMuteButton();
  },

  async preloadSounds(soundFiles, gameplayMusicMap) {
    if (this.isMobile) {
      return;
    }

    Object.entries(soundFiles).forEach(([, filename]) => {
      const asset = new Audio(`/sounds/${filename}.mp3`);
      asset.volume = this.volume;
      asset.preload = "auto";
      this.sounds[filename] = asset;
    });

    Object.entries(gameplayMusicMap).forEach(([key, filename]) => {
      const asset = new Audio(`/sounds/gameplay/${filename}.mp3`);
      asset.volume = this.volume;
      asset.preload = "auto";
      this.sounds[key] = asset;
    });

    const promises = [];
    Object.values(this.sounds).forEach((asset) => {
      promises.push(
        new Promise((resolve) => {
          asset.addEventListener("canplaythrough", resolve, { once: true });
          asset.addEventListener("error", resolve, { once: true });
        })
      );
    });

    await Promise.all(promises);
  },

  play(soundName, options = {}) {
    if (this.isMobile) {
      return;
    }

    const {
      volume = 1,
      loop = false,
      trackAs = "effect",
      onEnd = null,
    } = options;

    const sound = this.sounds[soundName];

    if (!sound) {
      console.warn(`No sound found for: ${soundName}`);
      return;
    }

    if (trackAs === "select") this.stopTrack("select");
    else if (trackAs === "transition") this.stopTrack("transition");
    else if (trackAs === "winLose") this.stopTrack("winLose");

    sound.currentTime = 0;
    sound.loop = loop;
    sound.volume = this.enabled ? this.volume * volume : 0;

    if (trackAs === "select") {
      this.selectSound = sound;
    } else if (trackAs === "transition") {
      this.transitionSound = sound;
    } else if (trackAs === "winLose") {
      this.winLoseSound = sound;
    } else {
      sound._volumeMultiplier = volume;
      this.currentEffects.push(sound);
    }

    const onEndHandler = () => {
      if (trackAs === "effect") {
        const index = this.currentEffects.indexOf(sound);
        if (index > -1) this.currentEffects.splice(index, 1);
        delete sound._volumeMultiplier;
      } else if (trackAs === "winLose") {
        this.winLoseSound = null;
      }

      if (onEnd) onEnd();
      sound.removeEventListener("ended", onEndHandler);
    };

    if (trackAs === "effect" || trackAs === "winLose" || onEnd) {
      sound.addEventListener("ended", onEndHandler);
    }

    sound.play().catch((error) => {
      console.warn(`Failed to play sound: ${soundName}`, error);
      if (trackAs === "effect") {
        const index = this.currentEffects.indexOf(sound);
        if (index > -1) this.currentEffects.splice(index, 1);
        delete sound._volumeMultiplier;
      } else if (trackAs === "winLose") {
        this.winLoseSound = null;
      }
      if (trackAs === "effect" || trackAs === "winLose" || onEnd) {
        sound.removeEventListener("ended", onEndHandler);
      }
    });
  },

  playSound(soundName) {
    this.play(soundName, { trackAs: "effect" });
  },

  stopTrack(trackType) {
    if (this.isMobile) return;
    const trackMap = {
      select: "selectSound",
      winLose: "winLoseSound",
      transition: "transitionSound",
    };

    const soundProp = trackMap[trackType];
    const sound = this[soundProp];

    if (sound) {
      sound.pause();
      sound.currentTime = 0;
      sound.loop = false;
      this[soundProp] = null;
    }
  },

  stopAll() {
    if (this.isMobile) return;

    this.stopTrack("select");
    this.stopTrack("winLose");
    this.stopTrack("transition");

    this.currentEffects.forEach((sound) => {
      sound.pause();
      sound.currentTime = 0;
    });
    this.currentEffects = [];
  },

  toggleMute() {
    if (this.isMobile) return;
    this.enabled = !this.enabled;
    localStorage.setItem("audioEnabled", this.enabled);

    const muteIcon = byId("mute-icon");
    if (muteIcon) {
      muteIcon.src = this.enabled ? "/icons/unmute.svg" : "/icons/mute.svg";
    }

    const muteButton = byId("mute-toggle");
    if (muteButton) {
      if (this.enabled) {
        muteButton.classList.remove(
          "border-sf-gold",
          "bg-sf-darker",
          "hover:bg-sf-dark",
          "hover:border-sf-gold-dark"
        );
        muteButton.classList.add(
          "border-sf-green",
          "bg-sf-dark",
          "hover:bg-sf-darker",
          "hover:border-sf-green-dark"
        );
      } else {
        muteButton.classList.remove(
          "border-sf-green",
          "bg-sf-dark",
          "hover:bg-sf-darker",
          "hover:border-sf-green-dark"
        );
        muteButton.classList.add(
          "border-sf-gold",
          "bg-sf-darker",
          "hover:bg-sf-dark",
          "hover:border-sf-gold-dark"
        );
      }
    }

    if (this.selectSound) {
      this.selectSound.volume = this.enabled ? this.volume * 0.2 : 0;
    }

    if (this.transitionSound) {
      this.transitionSound.volume = this.enabled ? this.volume * 0.2 : 0;
    }

    if (this.winLoseSound) {
      this.winLoseSound.volume = this.enabled ? this.volume * 0.2 : 0;
    }

    this.currentEffects.forEach((sound) => {
      const multiplier = sound._volumeMultiplier || 1;
      sound.volume = this.enabled ? this.volume * multiplier : 0;
    });
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

      const muteIcon = byId("mute-icon");
      if (muteIcon) {
        muteIcon.src = this.enabled ? "/icons/unmute.svg" : "/icons/mute.svg";
      }

      if (this.enabled) {
        muteButton.classList.remove("border-sf-gold", "bg-sf-darker");
        muteButton.classList.add("border-sf-green", "bg-sf-dark");
      } else {
        muteButton.classList.remove("border-sf-green", "bg-sf-dark");
        muteButton.classList.add("border-sf-gold", "bg-sf-darker");
      }
    }
  },
};

export const playHover = () => AudioManager.playSound(SOUND_KEYS.HOVER);
export const playClick = () => AudioManager.playSound(SOUND_KEYS.CLICK);
