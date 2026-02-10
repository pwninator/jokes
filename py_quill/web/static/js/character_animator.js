// This implementation must strictly conform to:
// `py_quill/common/character_animator_spec.md`.
// Keep runtime semantics aligned with the canonical spec.

const IDENTITY_TRANSFORM = Object.freeze({
  translate_x: 0,
  translate_y: 0,
  scale_x: 1,
  scale_y: 1,
});

function cloneTransform(transform) {
  return {
    translate_x: Number(transform.translate_x),
    translate_y: Number(transform.translate_y),
    scale_x: Number(transform.scale_x),
    scale_y: Number(transform.scale_y),
  };
}

function normalizeTransform(transform) {
  if (!transform) {
    return cloneTransform(IDENTITY_TRANSFORM);
  }
  return {
    translate_x: Number(transform.translate_x ?? 0),
    translate_y: Number(transform.translate_y ?? 0),
    scale_x: Number(transform.scale_x ?? 1),
    scale_y: Number(transform.scale_y ?? 1),
  };
}

function lerp(start, end, progress) {
  return start + ((end - start) * progress);
}

function sortedByStart(events) {
  return [...events].sort((left, right) => {
    const leftStart = Number(left.start_time);
    const rightStart = Number(right.start_time);
    if (leftStart === rightStart) {
      return Number(left.end_time) - Number(right.end_time);
    }
    return leftStart - rightStart;
  });
}

function asNumber(value) {
  return Number(value ?? 0);
}

function toBrowserUrl(uri) {
  if (!uri) {
    return uri;
  }
  const raw = String(uri).trim();
  if (!raw) {
    return raw;
  }
  if (raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('data:')) {
    return raw;
  }
  if (!raw.startsWith('gs://')) {
    return raw;
  }

  const gcsPath = raw.slice('gs://'.length);
  const slashIndex = gcsPath.indexOf('/');
  if (slashIndex === -1) {
    return `https://${gcsPath}`;
  }
  const bucket = gcsPath.slice(0, slashIndex);
  const objectPath = gcsPath.slice(slashIndex + 1);

  // Custom-domain buckets (e.g. images.quillsstorybook.com) are directly hostable.
  if (bucket.includes('.')) {
    return `https://${bucket}/${objectPath}`;
  }
  return `https://storage.googleapis.com/${bucket}/${objectPath}`;
}

export class CharacterAnimator {
  /**
   * @param {Object} sequenceData - JSON export of PosableCharacterSequence
   * @param {Object} domElements - Map of DOM elements { head, mouth, leftEye, rightEye, leftHand, rightHand }
   * @param {Object} characterDefinition - JSON export of PosableCharacterDef containing image URIs
   */
  constructor(sequenceData, domElements, characterDefinition) {
    this.sequenceData = sequenceData || {};
    this.domElements = domElements || {};
    this.characterDefinition = this._normalizeCharacterDefinition(characterDefinition || {});
    this.timeline = null;
    this.audioCache = new Map();
    this.activeSounds = new Set();
    this._soundByEventKey = new Map();
    this._sortedTrackCache = new Map();
    this._gsap = null;
    this._validateSequenceForSpec();
  }

  _normalizeCharacterDefinition(definition) {
    const normalized = { ...definition };
    Object.keys(normalized).forEach((field) => {
      if (field.endsWith('_gcs_uri')) {
        normalized[field] = toBrowserUrl(normalized[field]);
      }
    });
    return normalized;
  }

  /**
   * Returns the canonical duration defined by the max `end_time` of all tracks.
   * @returns {number}
   */
  durationSec() {
    let maxEndTime = 0;
    const trackNames = this._trackNames();
    trackNames.forEach((trackName) => {
      const track = this._track(trackName);
      track.forEach((event) => {
        maxEndTime = Math.max(maxEndTime, asNumber(event.end_time));
      });
    });
    return maxEndTime;
  }

  /**
   * Random-access pose sampling at an arbitrary timestamp.
   * @param {number} timeSec
   * @returns {Object}
   */
  samplePoseAtTime(timeSec) {
    const t = asNumber(timeSec);
    return {
      left_eye_open: this._sampleBooleanTrack('sequence_left_eye_open', t, true),
      right_eye_open: this._sampleBooleanTrack('sequence_right_eye_open', t, true),
      mouth_state: this._sampleMouthTrack(t),
      left_hand_visible: this._sampleBooleanTrack('sequence_left_hand_visible', t, true),
      right_hand_visible: this._sampleBooleanTrack('sequence_right_hand_visible', t, true),
      left_hand_transform: this._sampleTransformTrack('sequence_left_hand_transform', t),
      right_hand_transform: this._sampleTransformTrack('sequence_right_hand_transform', t),
      head_transform: this._sampleTransformTrack('sequence_head_transform', t),
    };
  }

  /**
   * Returns sound events whose `start_time` falls in the given interval.
   * @param {number} startSec
   * @param {number} endSec
   * @param {Object} options
   * @param {boolean} options.includeStart
   * @param {boolean} options.includeEnd
   * @returns {Object[]}
   */
  soundEventsBetween(startSec, endSec, { includeStart = true, includeEnd = false } = {}) {
    const start = asNumber(startSec);
    const end = asNumber(endSec);
    return this._track('sequence_sound_events').filter((event) => {
      const eventStart = asNumber(event.start_time);
      const startOk = includeStart ? eventStart >= start : eventStart > start;
      const endOk = includeEnd ? eventStart <= end : eventStart < end;
      return startOk && endOk;
    });
  }

  /**
   * Preloads audio and images and initializes GSAP timeline.
   * @returns {Promise<void>}
   */
  async init() {
    this._gsap = await this._loadGsap();
    await Promise.all([
      this._preloadAudio(),
      this._preloadImages(),
    ]);
    this._buildTimeline();
  }

  async _loadGsap() {
    if (this._gsap) {
      return this._gsap;
    }
    if (typeof window !== 'undefined' && window.gsap) {
      this._gsap = window.gsap;
      return this._gsap;
    }
    const gsapModule = await import('https://cdn.skypack.dev/gsap');
    this._gsap = gsapModule.default || gsapModule.gsap || gsapModule;
    return this._gsap;
  }

  _trackNames() {
    return [
      'sequence_left_eye_open',
      'sequence_right_eye_open',
      'sequence_mouth_state',
      'sequence_left_hand_visible',
      'sequence_right_hand_visible',
      'sequence_left_hand_transform',
      'sequence_right_hand_transform',
      'sequence_head_transform',
      'sequence_sound_events',
    ];
  }

  _track(trackName) {
    if (this._sortedTrackCache.has(trackName)) {
      return this._sortedTrackCache.get(trackName);
    }
    const events = this.sequenceData[trackName] || [];
    const sorted = sortedByStart(events);
    this._sortedTrackCache.set(trackName, sorted);
    return sorted;
  }

  _sampleBooleanTrack(trackName, timeSec, defaultValue) {
    const track = this._track(trackName);
    for (let eventIndex = 0; eventIndex < track.length; eventIndex += 1) {
      const event = track[eventIndex];
      const start = asNumber(event.start_time);
      const end = asNumber(event.end_time);
      if (timeSec >= start && timeSec <= end) {
        return Boolean(event.value);
      }
    }
    return defaultValue;
  }

  _sampleMouthTrack(timeSec) {
    const track = this._track('sequence_mouth_state');
    for (let eventIndex = 0; eventIndex < track.length; eventIndex += 1) {
      const event = track[eventIndex];
      const start = asNumber(event.start_time);
      const end = asNumber(event.end_time);
      if (timeSec >= start && timeSec <= end) {
        return event.mouth_state || 'CLOSED';
      }
    }
    return 'CLOSED';
  }

  _sampleTransformTrack(trackName, timeSec) {
    const track = this._track(trackName);
    if (track.length === 0) {
      return cloneTransform(IDENTITY_TRANSFORM);
    }

    let previousTarget = cloneTransform(IDENTITY_TRANSFORM);

    for (let eventIndex = 0; eventIndex < track.length; eventIndex += 1) {
      const event = track[eventIndex];
      const start = asNumber(event.start_time);
      const end = asNumber(event.end_time);
      const target = normalizeTransform(event.target_transform);

      if (timeSec < start) {
        return previousTarget;
      }

      if (timeSec <= end) {
        if (end <= start) {
          return target;
        }
        const progress = (timeSec - start) / (end - start);
        return {
          translate_x: lerp(previousTarget.translate_x, target.translate_x, progress),
          translate_y: lerp(previousTarget.translate_y, target.translate_y, progress),
          scale_x: lerp(previousTarget.scale_x, target.scale_x, progress),
          scale_y: lerp(previousTarget.scale_y, target.scale_y, progress),
        };
      }

      previousTarget = target;
    }

    return previousTarget;
  }

  /**
   * Updates the sequence data and rebuilds the timeline.
   * @param {Object} newSequenceData
   */
  async updateSequence(newSequenceData) {
    this.sequenceData = newSequenceData;
    // Start preloading any new audio
    this._preloadAudio();
    // Rebuild timeline immediately
    this._buildTimeline();
  }

  /**
   * Preloads all unique audio files referenced in the sequence.
   * @returns {Promise<void>}
   */
  async _preloadAudio() {
    const soundEvents = this._track('sequence_sound_events');
    const uniqueUris = new Set(
      soundEvents
        .map((event) => toBrowserUrl(event.gcs_uri))
        .filter((uri) => uri),
    );

    const loadPromises = Array.from(uniqueUris).map((uri) => new Promise((resolve) => {
      const audio = new Audio();
      audio.preload = 'auto';
      audio.src = uri;

      const onLoaded = () => {
        this.audioCache.set(uri, audio);
        resolve();
      };

      const onError = (error) => {
        console.warn(`Failed to load audio: ${uri}`, error);
        resolve();
      };

      audio.addEventListener('canplaythrough', onLoaded, { once: true });
      audio.addEventListener('error', onError, { once: true });

      setTimeout(() => {
        if (!this.audioCache.has(uri)) {
          if (audio.readyState >= 3) {
            this.audioCache.set(uri, audio);
          } else {
            console.warn(`Audio load timed out: ${uri}`);
          }
          resolve();
        }
      }, 5000);
    }));

    await Promise.all(loadPromises);
  }

  /**
   * Preloads images to ensure smooth swapping.
   * @returns {Promise<void>}
   */
  async _preloadImages() {
    const definition = this.characterDefinition;
    const uris = [
      definition.mouth_open_gcs_uri,
      definition.mouth_closed_gcs_uri,
      definition.mouth_o_gcs_uri,
      definition.left_eye_open_gcs_uri,
      definition.left_eye_closed_gcs_uri,
      definition.right_eye_open_gcs_uri,
      definition.right_eye_closed_gcs_uri,
    ].filter((uri) => uri);

    const uniqueUris = new Set(uris);
    const loadPromises = Array.from(uniqueUris).map((uri) => new Promise((resolve) => {
      const image = new Image();
      image.src = uri;
      image.onload = () => resolve();
      image.onerror = () => resolve();
    }));

    await Promise.all(loadPromises);
  }

  /**
   * Constructs the GSAP timeline from the sequence data.
   */
  _buildTimeline() {
    if (!this._gsap) {
      throw new Error('GSAP runtime not loaded. Call init() before play/seek.');
    }
    if (this.timeline) {
      this.timeline.kill();
      this._stopAllSounds();
    }

    this.timeline = this._gsap.timeline({ paused: true });

    this._addTransformTrack(this.domElements.head, this._track('sequence_head_transform'));
    this._addTransformTrack(this.domElements.leftHand, this._track('sequence_left_hand_transform'));
    this._addTransformTrack(this.domElements.rightHand, this._track('sequence_right_hand_transform'));

    this._addBooleanTrack(this.domElements.leftHand, this._track('sequence_left_hand_visible'), 'autoAlpha');
    this._addBooleanTrack(this.domElements.rightHand, this._track('sequence_right_hand_visible'), 'autoAlpha');

    this._addImageSwapTrack(
      this.domElements.leftEye,
      this._track('sequence_left_eye_open'),
      (isOpen) => (isOpen ? this.characterDefinition.left_eye_open_gcs_uri : this.characterDefinition.left_eye_closed_gcs_uri),
    );
    this._addImageSwapTrack(
      this.domElements.rightEye,
      this._track('sequence_right_eye_open'),
      (isOpen) => (isOpen ? this.characterDefinition.right_eye_open_gcs_uri : this.characterDefinition.right_eye_closed_gcs_uri),
    );

    this._addMouthTrack(this.domElements.mouth, this._track('sequence_mouth_state'));
    this._addAudioTrack(this._track('sequence_sound_events'));
  }

  _addTransformTrack(element, events) {
    if (!element || !events) {
      return;
    }
    events.forEach((event) => {
      const startTime = asNumber(event.start_time);
      const endTime = asNumber(event.end_time);
      const duration = Math.max(0, endTime - startTime);
      const target = normalizeTransform(event.target_transform);
      this.timeline.to(element, {
        x: target.translate_x,
        y: target.translate_y,
        scaleX: target.scale_x,
        scaleY: target.scale_y,
        duration: duration,
        ease: 'none',
      }, startTime);
    });
  }

  _addBooleanTrack(element, events, property) {
    if (!element || !events) {
      return;
    }
    events.forEach((event) => {
      this.timeline.set(element, {
        [property]: event.value ? 1 : 0,
      }, asNumber(event.start_time));
    });
  }

  _addImageSwapTrack(element, events, uriSelector) {
    if (!element || !events) {
      return;
    }
    events.forEach((event) => {
      const uri = uriSelector(Boolean(event.value));
      this.timeline.set(element, {
        attr: { src: uri },
      }, asNumber(event.start_time));
    });
  }

  _addMouthTrack(element, events) {
    if (!element || !events) {
      return;
    }
    events.forEach((event) => {
      const state = event.mouth_state;
      let uri = this.characterDefinition.mouth_closed_gcs_uri;
      if (state === 'OPEN' || state === 'MouthState.OPEN') {
        uri = this.characterDefinition.mouth_open_gcs_uri;
      } else if (state === 'O' || state === 'MouthState.O') {
        uri = this.characterDefinition.mouth_o_gcs_uri;
      }

      this.timeline.set(element, {
        attr: { src: uri },
      }, asNumber(event.start_time));
    });
  }

  _addAudioTrack(events) {
    if (!events) {
      return;
    }
    events.forEach((event, index) => {
      const eventKey = this._eventKey(event, index);
      const audioUri = toBrowserUrl(event.gcs_uri);
      this.timeline.call(() => {
        this._playSound(eventKey, audioUri, event.volume);
      }, null, asNumber(event.start_time));
      this.timeline.call(() => {
        this._stopSoundByEventKey(eventKey);
      }, null, asNumber(event.end_time));
    });
  }

  _playSound(eventKey, uri, volume = 1.0) {
    const originalAudio = this.audioCache.get(uri);
    if (!originalAudio) {
      return;
    }

    this._stopSoundByEventKey(eventKey);
    const sound = originalAudio.cloneNode();
    sound.volume = volume;

    this.activeSounds.add(sound);
    this._soundByEventKey.set(eventKey, sound);

    sound.onended = () => {
      this.activeSounds.delete(sound);
      this._soundByEventKey.delete(eventKey);
    };

    sound.play().catch((error) => {
      console.warn('Audio play blocked or failed', error);
      this.activeSounds.delete(sound);
      this._soundByEventKey.delete(eventKey);
    });
  }

  _stopSoundByEventKey(eventKey) {
    const sound = this._soundByEventKey.get(eventKey);
    if (!sound) {
      return;
    }
    sound.pause();
    sound.currentTime = 0;
    this.activeSounds.delete(sound);
    this._soundByEventKey.delete(eventKey);
  }

  _stopAllSounds() {
    this.activeSounds.forEach((sound) => {
      sound.pause();
      sound.currentTime = 0;
    });
    this.activeSounds.clear();
    this._soundByEventKey.clear();
  }

  _pauseAllSounds() {
    this.activeSounds.forEach((sound) => sound.pause());
  }

  _resumeAllSounds() {
    this.activeSounds.forEach((sound) => sound.play().catch(() => {}));
  }

  play() {
    this.timeline?.play();
    this._resumeAllSounds();
  }

  pause() {
    this.timeline?.pause();
    this._pauseAllSounds();
  }

  seek(time) {
    this._stopAllSounds();
    this.timeline?.seek(time);
    this._syncAudioToTime(time);
  }

  _syncAudioToTime(time) {
    const soundEvents = this._track('sequence_sound_events');
    soundEvents.forEach((event, index) => {
      const audioUri = toBrowserUrl(event.gcs_uri);
      const audio = this.audioCache.get(audioUri);
      if (!audio || !audio.duration) {
        return;
      }

      const startTime = asNumber(event.start_time);
      const endTime = asNumber(event.end_time);
      if (time < startTime || time >= endTime) {
        return;
      }

      const offset = time - startTime;
      const eventKey = this._eventKey(event, index);
      this._stopSoundByEventKey(eventKey);

      const sound = audio.cloneNode();
      sound.volume = event.volume !== undefined ? event.volume : 1.0;
      sound.currentTime = offset;
      this.activeSounds.add(sound);
      this._soundByEventKey.set(eventKey, sound);
      sound.onended = () => {
        this.activeSounds.delete(sound);
        this._soundByEventKey.delete(eventKey);
      };

      if (!this.timeline?.paused()) {
        sound.play().catch(() => {});
      }
    });
  }

  _eventKey(event, index) {
    return `${index}:${event.gcs_uri}:${event.start_time}:${event.end_time}`;
  }

  _validateSequenceForSpec() {
    this._trackNames().forEach((trackName) => {
      const events = this.sequenceData[trackName] || [];
      if (!Array.isArray(events)) {
        throw new Error(`${trackName} must be an array`);
      }
      events.forEach((event, index) => {
        if (event.start_time === undefined || event.start_time === null) {
          throw new Error(`${trackName}[${index}] missing required start_time`);
        }
        if (event.end_time === undefined || event.end_time === null) {
          throw new Error(`${trackName}[${index}] missing required end_time`);
        }
        if (asNumber(event.end_time) < asNumber(event.start_time)) {
          throw new Error(`${trackName}[${index}] has end_time < start_time`);
        }
      });
    });
  }
}
