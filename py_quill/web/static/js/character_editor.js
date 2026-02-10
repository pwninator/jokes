export class CharacterEditor {
  constructor(container, sequenceData, onUpdate) {
    this.container = container;
    this.sequenceData = sequenceData || {};
    this.onUpdate = onUpdate;
    this.scale = 100; // pixels per second
    this.selectedEvent = null; // { trackName, index }
    this.trackConfig = [
      { name: 'sequence_head_transform', label: 'Head Transform', type: 'TRANSFORM' },
      { name: 'sequence_left_hand_transform', label: 'L Hand Transform', type: 'TRANSFORM' },
      { name: 'sequence_right_hand_transform', label: 'R Hand Transform', type: 'TRANSFORM' },
      { name: 'sequence_left_eye_open', label: 'L Eye Open', type: 'BOOLEAN' },
      { name: 'sequence_right_eye_open', label: 'R Eye Open', type: 'BOOLEAN' },
      { name: 'sequence_mouth_state', label: 'Mouth State', type: 'MOUTH' },
      { name: 'sequence_left_hand_visible', label: 'L Hand Visible', type: 'BOOLEAN' },
      { name: 'sequence_right_hand_visible', label: 'R Hand Visible', type: 'BOOLEAN' },
      { name: 'sequence_sound_events', label: 'Sound', type: 'SOUND' },
    ];

    this._ensureDataStructure();
    this._injectStyles();
    this._createModal();
    this.render();
  }

  destroy() {
    if (this.modalOverlay && this.modalOverlay.parentNode) {
      this.modalOverlay.parentNode.removeChild(this.modalOverlay);
    }
  }

  _ensureDataStructure() {
    this.trackConfig.forEach(track => {
      if (!this.sequenceData[track.name]) {
        this.sequenceData[track.name] = [];
      }
    });
  }

  _injectStyles() {
    const styleId = 'character-editor-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .editor-timeline {
        display: flex;
        flex-direction: column;
        border: 1px solid #ccc;
        overflow-x: auto;
        background: #fff;
        margin-top: 20px;
        padding-bottom: 20px;
      }
      .editor-track {
        display: flex;
        align-items: center;
        height: 40px;
        border-bottom: 1px solid #eee;
        position: relative;
        min-width: 1000px; /* Ensure scrolling */
      }
      .track-label {
        width: 150px;
        font-weight: bold;
        padding-left: 10px;
        flex-shrink: 0;
        background: #f9f9f9;
        border-right: 1px solid #ddd;
        position: sticky;
        left: 0;
        z-index: 10;
        height: 100%;
        display: flex;
        align-items: center;
      }
      .track-content {
        flex-grow: 1;
        position: relative;
        height: 100%;
        cursor: crosshair;
      }
      .event-block {
        position: absolute;
        height: 80%;
        top: 10%;
        background: #3498db;
        border-radius: 4px;
        cursor: pointer;
        opacity: 0.8;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 10px;
        overflow: hidden;
        white-space: nowrap;
        padding: 0 4px;
      }
      .event-block:hover {
        opacity: 1;
        background: #2980b9;
      }
      /* Modal Styles */
      .editor-modal-overlay {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.5);
        display: none;
        align-items: center;
        justify-content: center;
        z-index: 1000;
      }
      .editor-modal {
        background: white;
        padding: 20px;
        border-radius: 8px;
        width: 400px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      }
      .editor-modal h3 { margin-top: 0; }
      .form-group { margin-bottom: 12px; }
      .form-group label { display: block; margin-bottom: 4px; font-weight: 500; }
      .form-group input, .form-group select { width: 100%; padding: 6px; box-sizing: border-box; }
      .modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
      .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
      .btn-primary { background: #3498db; color: white; }
      .btn-danger { background: #e74c3c; color: white; }
      .btn-secondary { background: #95a5a6; color: white; }
    `;
    document.head.appendChild(style);
  }

  _createModal() {
    this.modalOverlay = document.createElement('div');
    this.modalOverlay.className = 'editor-modal-overlay';
    this.modalOverlay.innerHTML = `
      <div class="editor-modal">
        <h3 id="modal-title">Edit Event</h3>
        <div id="modal-content"></div>
        <div class="modal-actions">
          <button id="modal-delete" class="btn btn-danger">Delete</button>
          <button id="modal-cancel" class="btn btn-secondary">Cancel</button>
          <button id="modal-save" class="btn btn-primary">Save</button>
        </div>
      </div>
    `;
    document.body.appendChild(this.modalOverlay);

    this.modalOverlay.querySelector('#modal-cancel').onclick = () => this._closeModal();
    this.modalOverlay.querySelector('#modal-delete').onclick = () => this._deleteEvent();
    this.modalOverlay.querySelector('#modal-save').onclick = () => this._saveEvent();
  }

  render() {
    this.container.innerHTML = '';
    const timeline = document.createElement('div');
    timeline.className = 'editor-timeline';

    this.trackConfig.forEach(track => {
      const trackEl = document.createElement('div');
      trackEl.className = 'editor-track';

      const label = document.createElement('div');
      label.className = 'track-label';
      label.textContent = track.label;
      trackEl.appendChild(label);

      const content = document.createElement('div');
      content.className = 'track-content';
      content.onclick = (e) => {
        if (e.target === content) {
          const rect = content.getBoundingClientRect();
          const x = e.clientX - rect.left + content.scrollLeft; // Account for scroll
          const time = x / this.scale;
          this._openEventModal(track.name, null, time);
        }
      };

      const events = this.sequenceData[track.name] || [];
      events.forEach((event, index) => {
        const block = document.createElement('div');
        block.className = 'event-block';

        const startTime = event.start_time || 0;
        const endTime = event.end_time || (startTime + 0.1); // Default duration for visualization
        const duration = Math.max(0.1, endTime - startTime); // Min width

        block.style.left = `${startTime * this.scale}px`;
        block.style.width = `${duration * this.scale}px`;

        // Label content
        if (track.type === 'TRANSFORM') block.textContent = 'T';
        else if (track.type === 'BOOLEAN') block.textContent = event.value ? 'ON' : 'OFF';
        else if (track.type === 'MOUTH') block.textContent = event.mouth_state;
        else if (track.type === 'SOUND') block.textContent = '♫';

        block.onclick = (e) => {
          e.stopPropagation();
          this._openEventModal(track.name, index);
        };

        content.appendChild(block);
      });

      trackEl.appendChild(content);
      timeline.appendChild(trackEl);
    });

    this.container.appendChild(timeline);
  }

  _openEventModal(trackName, index, defaultTime = 0) {
    this.selectedEvent = { trackName, index };
    const track = this.trackConfig.find(t => t.name === trackName);
    const event = index !== null ? this.sequenceData[trackName][index] : { start_time: defaultTime };

    const content = this.modalOverlay.querySelector('#modal-content');
    content.innerHTML = '';

    // Common fields
    this._addInput(content, 'start_time', 'Start Time', event.start_time || 0, 'number', 0.01);
    this._addInput(content, 'end_time', 'End Time', event.end_time || '', 'number', 0.01);

    // Type specific fields
    if (track.type === 'TRANSFORM') {
        const t = event.target_transform || {};
        this._addInput(content, 'tx', 'Translate X', t.translate_x || 0, 'number');
        this._addInput(content, 'ty', 'Translate Y', t.translate_y || 0, 'number');
        this._addInput(content, 'sx', 'Scale X', t.scale_x !== undefined ? t.scale_x : 1, 'number', 0.1);
        this._addInput(content, 'sy', 'Scale Y', t.scale_y !== undefined ? t.scale_y : 1, 'number', 0.1);
    } else if (track.type === 'BOOLEAN') {
        this._addCheckbox(content, 'value', 'Value', event.value !== undefined ? event.value : true);
    } else if (track.type === 'MOUTH') {
        this._addSelect(content, 'mouth_state', 'Mouth State', ['OPEN', 'CLOSED', 'O'], event.mouth_state || 'CLOSED');
    } else if (track.type === 'SOUND') {
        this._addInput(content, 'gcs_uri', 'GCS URI', event.gcs_uri || '', 'text');
        this._addInput(content, 'volume', 'Volume', event.volume !== undefined ? event.volume : 1.0, 'number', 0.1);
    }

    this.modalOverlay.style.display = 'flex';
  }

  _addInput(parent, name, label, value, type = 'text', step = null) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const labelEl = document.createElement('label');
    labelEl.textContent = label;
    group.appendChild(labelEl);

    const input = document.createElement('input');
    input.name = name;
    input.type = type;
    if (value !== null && value !== undefined) {
        input.value = value;
    }
    if (step) input.step = step;
    group.appendChild(input);

    parent.appendChild(group);
  }

  _addCheckbox(parent, name, label, checked) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const labelEl = document.createElement('label');

    const input = document.createElement('input');
    input.name = name;
    input.type = 'checkbox';
    input.checked = !!checked;

    labelEl.appendChild(input);
    labelEl.appendChild(document.createTextNode(' ' + label));
    group.appendChild(labelEl);

    parent.appendChild(group);
  }

  _addSelect(parent, name, label, options, selected) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const labelEl = document.createElement('label');
    labelEl.textContent = label;
    group.appendChild(labelEl);

    const select = document.createElement('select');
    select.name = name;

    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        if (opt === selected) option.selected = true;
        select.appendChild(option);
    });

    group.appendChild(select);
    parent.appendChild(group);
  }

  _saveEvent() {
    const inputs = this.modalOverlay.querySelectorAll('#modal-content input, #modal-content select');
    const data = {};
    inputs.forEach(input => {
      if (input.type === 'checkbox') {
        data[input.name] = input.checked;
      } else if (input.type === 'number') {
        const val = parseFloat(input.value);
        data[input.name] = isNaN(val) ? 0 : val;
      } else {
        data[input.name] = input.value;
      }
    });

    // Special handling for end_time which can be null
    // We need to re-read the raw value for end_time because our loop above defaults NaN to 0
    // Actually, let's fix that logic.
    // Ideally we iterate and handle each field specifically, but loop is convenient.
    // Let's check the 'end_time' input specifically.
    const endTimeInput = this.modalOverlay.querySelector('input[name="end_time"]');
    let endTime = null;
    if (endTimeInput && endTimeInput.value.trim() !== '') {
        endTime = parseFloat(endTimeInput.value);
    }

    const trackName = this.selectedEvent.trackName;
    const track = this.trackConfig.find(t => t.name === trackName);

    const newEvent = {
        start_time: data.start_time,
        end_time: endTime,
    };

    if (track.type === 'TRANSFORM') {
        newEvent.target_transform = {
            translate_x: data.tx,
            translate_y: data.ty,
            scale_x: data.sx,
            scale_y: data.sy
        };
    } else if (track.type === 'BOOLEAN') {
        newEvent.value = data.value;
    } else if (track.type === 'MOUTH') {
        newEvent.mouth_state = data.mouth_state;
    } else if (track.type === 'SOUND') {
        newEvent.gcs_uri = data.gcs_uri;
        newEvent.volume = data.volume;
    }

    if (this.selectedEvent.index !== null) {
        this.sequenceData[trackName][this.selectedEvent.index] = newEvent;
    } else {
        this.sequenceData[trackName].push(newEvent);
    }

    // Sort events by start time
    this.sequenceData[trackName].sort((a, b) => a.start_time - b.start_time);

    this._closeModal();
    this.render();
    if (this.onUpdate) this.onUpdate(this.sequenceData);
  }

  _deleteEvent() {
    if (this.selectedEvent.index !== null) {
        const trackName = this.selectedEvent.trackName;
        this.sequenceData[trackName].splice(this.selectedEvent.index, 1);
        this.render();
        if (this.onUpdate) this.onUpdate(this.sequenceData);
    }
    this._closeModal();
  }

  _closeModal() {
    this.modalOverlay.style.display = 'none';
    this.selectedEvent = null;
  }
}
