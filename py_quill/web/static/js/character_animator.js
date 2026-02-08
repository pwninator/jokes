import gsap from 'https://cdn.skypack.dev/gsap';

export class CharacterAnimator {
  /**
   * @param {Object} sequenceData - JSON export of PosableCharacterSequence
   * @param {Object} domElements - Map of DOM elements { head, mouth, leftEye, rightEye, leftHand, rightHand }
   * @param {Object} characterDefinition - JSON export of PosableCharacterDef containing image URIs
   */
  constructor(sequenceData, domElements, characterDefinition) {
    this.sequenceData = sequenceData;
    this.domElements = domElements;
    this.characterDefinition = characterDefinition;
    this.timeline = null;
    this.audioCache = new Map(); // Map<gcs_uri, AudioElement>
    this.activeSounds = new Set(); // Set<AudioElement> - currently playing sounds
  }

  /**
   * Preloads audio and images.
   * @returns {Promise<void>}
   */
  async init() {
    await Promise.all([
        this._preloadAudio(),
        this._preloadImages()
    ]);
    this._buildTimeline();
  }

  /**
   * Preloads all unique audio files referenced in the sequence.
   * @returns {Promise<void>}
   */
  async _preloadAudio() {
    const soundEvents = this.sequenceData.sequence_sound_events || [];
    const uniqueUris = new Set(soundEvents.map(e => e.gcs_uri).filter(uri => uri));

    const loadPromises = Array.from(uniqueUris).map(uri => {
      return new Promise((resolve) => {
        const audio = new Audio();
        audio.preload = 'auto';
        audio.src = uri;

        const onLoaded = () => {
          this.audioCache.set(uri, audio);
          resolve();
        };

        const onError = (e) => {
            console.warn(`Failed to load audio: ${uri}`, e);
            resolve(); // Resolve anyway to proceed
        };

        // 'canplaythrough' implies the browser thinks it can play the whole file
        audio.addEventListener('canplaythrough', onLoaded, { once: true });
        audio.addEventListener('error', onError, { once: true });

        // Fallback timeout
        setTimeout(() => {
            if (!this.audioCache.has(uri)) {
                // Check if it's actually ready but event missed (rare but possible)
                if (audio.readyState >= 3) {
                    this.audioCache.set(uri, audio);
                } else {
                    console.warn(`Audio load timed out: ${uri}`);
                }
                resolve();
            }
        }, 5000);
      });
    });

    await Promise.all(loadPromises);
  }

  /**
   * Preloads images to ensure smooth swapping.
   * @returns {Promise<void>}
   */
  async _preloadImages() {
      const def = this.characterDefinition;
      // Collect all potential image URIs
      const uris = [
          def.mouth_open_gcs_uri,
          def.mouth_closed_gcs_uri,
          def.mouth_o_gcs_uri,
          def.left_eye_open_gcs_uri,
          def.left_eye_closed_gcs_uri,
          def.right_eye_open_gcs_uri,
          def.right_eye_closed_gcs_uri
      ].filter(uri => uri);

      const uniqueUris = new Set(uris);
      const loadPromises = Array.from(uniqueUris).map(uri => {
          return new Promise((resolve) => {
              const img = new Image();
              img.src = uri;
              img.onload = () => resolve();
              img.onerror = () => resolve();
          });
      });
      await Promise.all(loadPromises);
  }

  /**
   * Constructs the GSAP timeline from the sequence data.
   */
  _buildTimeline() {
    if (this.timeline) {
      this.timeline.kill();
      this._stopAllSounds();
    }

    this.timeline = gsap.timeline({ paused: true });

    // --- Transforms ---
    this._addTransformTrack(this.domElements.head, this.sequenceData.sequence_head_transform);
    this._addTransformTrack(this.domElements.leftHand, this.sequenceData.sequence_left_hand_transform);
    this._addTransformTrack(this.domElements.rightHand, this.sequenceData.sequence_right_hand_transform);

    // --- Visibility / Discrete States ---
    this._addBooleanTrack(this.domElements.leftHand, this.sequenceData.sequence_left_hand_visible, 'autoAlpha');
    this._addBooleanTrack(this.domElements.rightHand, this.sequenceData.sequence_right_hand_visible, 'autoAlpha');

    // Eyes (swapping src)
    this._addImageSwapTrack(
        this.domElements.leftEye,
        this.sequenceData.sequence_left_eye_open,
        (isOpen) => isOpen ? this.characterDefinition.left_eye_open_gcs_uri : this.characterDefinition.left_eye_closed_gcs_uri
    );
    this._addImageSwapTrack(
        this.domElements.rightEye,
        this.sequenceData.sequence_right_eye_open,
        (isOpen) => isOpen ? this.characterDefinition.right_eye_open_gcs_uri : this.characterDefinition.right_eye_closed_gcs_uri
    );

    // Mouth (swapping src based on enum)
    this._addMouthTrack(this.domElements.mouth, this.sequenceData.sequence_mouth_state);

    // --- Audio ---
    this._addAudioTrack(this.sequenceData.sequence_sound_events);
  }

  _addTransformTrack(element, events) {
    if (!element || !events) return;

    // Sort events by start_time
    events.sort((a, b) => a.start_time - b.start_time);

    events.forEach(event => {
        // Default to 0 duration (instant set) if end_time not provided
        let duration = 0;
        if (event.end_time !== undefined && event.end_time !== null) {
            duration = event.end_time - event.start_time;
        }

        // Ensure non-negative duration
        duration = Math.max(0, duration);

        const target = event.target_transform;

        this.timeline.to(element, {
            x: target.translate_x,
            y: target.translate_y,
            scaleX: target.scale_x,
            scaleY: target.scale_y,
            duration: duration,
            ease: "none"
        }, event.start_time);
    });
  }

  _addBooleanTrack(element, events, property) {
    if (!element || !events) return;
    events.forEach(event => {
       this.timeline.set(element, {
           [property]: event.value ? 1 : 0
       }, event.start_time);
    });
  }

  _addImageSwapTrack(element, events, uriSelector) {
      if (!element || !events) return;
      events.forEach(event => {
          const uri = uriSelector(event.value);
          this.timeline.set(element, {
              attr: { src: uri }
          }, event.start_time);
      });
  }

  _addMouthTrack(element, events) {
      if (!element || !events) return;
      events.forEach(event => {
          let uri;
          // Handle both string and enum-like inputs just in case
          const state = event.mouth_state;
          if (state === 'OPEN' || state === 'MouthState.OPEN') {
               uri = this.characterDefinition.mouth_open_gcs_uri;
          } else if (state === 'O' || state === 'MouthState.O') {
               uri = this.characterDefinition.mouth_o_gcs_uri;
          } else {
               uri = this.characterDefinition.mouth_closed_gcs_uri;
          }

          this.timeline.set(element, {
              attr: { src: uri }
          }, event.start_time);
      });
  }

  _addAudioTrack(events) {
      if (!events) return;
      events.forEach(event => {
          // We use a callback to play the sound
          this.timeline.call(() => {
              this._playSound(event.gcs_uri, event.volume);
          }, null, event.start_time);
      });
  }

  _playSound(uri, volume = 1.0) {
      const originalAudio = this.audioCache.get(uri);
      if (!originalAudio) return;

      // Clone to allow overlapping instances
      const sound = originalAudio.cloneNode();
      sound.volume = volume;

      this.activeSounds.add(sound);

      sound.onended = () => {
          this.activeSounds.delete(sound);
      };

      // Handle potential play errors (e.g. user gesture requirements)
      sound.play().catch(e => {
          console.warn("Audio play blocked or failed", e);
          this.activeSounds.delete(sound);
      });
  }

  _stopAllSounds() {
      this.activeSounds.forEach(sound => {
          sound.pause();
          sound.currentTime = 0;
      });
      this.activeSounds.clear();
  }

  _pauseAllSounds() {
      this.activeSounds.forEach(sound => sound.pause());
  }

  _resumeAllSounds() {
      this.activeSounds.forEach(sound => sound.play().catch(() => {}));
  }

  // --- Public Controls ---

  play() {
    this.timeline?.play();
    this._resumeAllSounds();
  }

  pause() {
    this.timeline?.pause();
    this._pauseAllSounds();
  }

  seek(time) {
    // 1. Stop all currently playing sounds to prevent chaos
    this._stopAllSounds();

    // 2. Move visual timeline
    this.timeline?.seek(time);

    // 3. (Optional) Check for sounds that should be playing at this timestamp
    // This is complex because we need to know the duration of each sound.
    // If 'audioCache' has loaded sounds, we know their duration.
    this._syncAudioToTime(time);
  }

  _syncAudioToTime(time) {
      if (!this.sequenceData.sequence_sound_events) return;

      this.sequenceData.sequence_sound_events.forEach(event => {
          const audio = this.audioCache.get(event.gcs_uri);
          if (!audio || !audio.duration) return; // Can't sync if not loaded

          const startTime = event.start_time;
          const endTime = startTime + audio.duration;

          // Check if 'time' is within the sound's window
          if (time >= startTime && time < endTime) {
              const offset = time - startTime;

              // Start this sound at the offset
              const sound = audio.cloneNode();
              sound.volume = event.volume !== undefined ? event.volume : 1.0;
              sound.currentTime = offset;

              this.activeSounds.add(sound);
              sound.onended = () => this.activeSounds.delete(sound);

              // Only play if timeline is not paused?
              // Usually seek() implies moving the playhead.
              // If the timeline is paused, we probably shouldn't play audio.
              if (!this.timeline.paused()) {
                  sound.play().catch(() => {});
              } else {
                  // If paused, just prep it? No, HTML5 Audio doesn't "prep" well in paused state
                  // without being part of the DOM or complex handling.
                  // We'll just ignore for now if paused, or play if playing.
              }
          }
      });
  }
}
