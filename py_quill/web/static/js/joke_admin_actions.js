(function (factory) {
  const exports = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exports;
  }
  if (typeof window !== 'undefined') {
    window.initJokeAdminActions = exports.initJokeAdminActions;
  }
}(function () {
  'use strict';

  const CARD_PLACEHOLDER_SETUP = 'Illustration baking...';
  const CARD_PLACEHOLDER_PUNCHLINE = 'Punchline ready to read!';
  const DEFAULT_CARD_IMAGE_SIZE = 600;
  const DEFAULT_GRID_IMAGE_WIDTH = 180;
  const DEFAULT_PREVIEW_IMAGE_WIDTH = 480;
  const DEFAULT_REVEAL_LABEL = 'Reveal Punchline';
  const GENERATING_LABEL = 'Generating...';
  const IMAGE_CDN_PREFIX = 'https://images.quillsstorybook.com/cdn-cgi/image/';
  const IMAGE_GRID_EMPTY_TEXT = 'No images found.';
  const ADMIN_MUTABLE_STATES = ['UNREVIEWED', 'APPROVED', 'REJECTED'];

  function getStateLabel(state) {
    switch (state) {
      case 'UNREVIEWED':
        return 'Unreviewed';
      case 'APPROVED':
        return 'Approved';
      case 'REJECTED':
        return 'Rejected';
      case 'PUBLISHED':
        return 'Published';
      case 'DAILY':
        return 'Daily';
      case 'DRAFT':
        return 'Draft';
      case 'UNKNOWN':
        return 'Unknown';
      default:
        return '';
    }
  }

  function extractDateLabel(value) {
    if (typeof value === 'string') {
      const match = value.match(/^(\d{4}-\d{2}-\d{2})/);
      if (match) {
        return match[1];
      }
    }
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 10) : '';
  }

  function isFutureDailyPayload(payload) {
    if (!payload || payload.state !== 'DAILY' || !payload.public_timestamp) {
      return false;
    }
    const date = new Date(payload.public_timestamp);
    return !Number.isNaN(date.getTime()) && date.getTime() > Date.now();
  }

  function getStateBadgeClass(payload) {
    if (!payload || !payload.state) {
      return '';
    }
    return isFutureDailyPayload(payload) ? 'future-daily' : String(payload.state).toLowerCase();
  }

  function getStateBadgeText(payload) {
    if (!payload || !payload.state) {
      return '';
    }
    if (payload.state === 'DAILY' && payload.public_timestamp) {
      return extractDateLabel(payload.public_timestamp) || 'Daily';
    }
    return getStateLabel(payload.state);
  }

  function getReachableStateOptions(payload) {
    const state = payload && payload.state ? String(payload.state) : '';
    if (ADMIN_MUTABLE_STATES.includes(state)) {
      return ['UNREVIEWED', 'APPROVED', 'REJECTED', 'PUBLISHED', 'DAILY']
        .filter((value) => value !== state);
    }
    if (state === 'PUBLISHED') {
      return ['APPROVED', 'UNREVIEWED', 'REJECTED', 'DAILY'];
    }
    if (state === 'DAILY' && isFutureDailyPayload(payload)) {
      return ['APPROVED', 'PUBLISHED', 'UNREVIEWED', 'REJECTED'];
    }
    return [];
  }

  function decodeHtmlEntities(value) {
    const raw = String(value || '');
    if (typeof document !== 'undefined' && document
        && typeof document.createElement === 'function') {
      const decoder = document.createElement('textarea');
      decoder.innerHTML = raw;
      return decoder.value || '';
    }
    return raw
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, '\'')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&');
  }

  function parseEditPayload(rawValue) {
    const raw = rawValue || '{}';
    try {
      return JSON.parse(raw);
    } catch (_error) {
      try {
        return JSON.parse(decodeHtmlEntities(raw) || '{}');
      } catch (_innerError) {
        console.warn('Failed to parse edit payload', { raw }); // eslint-disable-line no-console
        return {};
      }
    }
  }

  function dedupeKeepOrder(values) {
    const seen = new Set();
    const result = [];
    (values || []).forEach((value) => {
      if (!value || seen.has(value)) {
        return;
      }
      seen.add(value);
      result.push(value);
    });
    return result;
  }

  function formatThumbUrl(url, width) {
    if (!url || typeof url !== 'string' || !url.startsWith(IMAGE_CDN_PREFIX)) {
      return url;
    }
    const remainder = url.slice(IMAGE_CDN_PREFIX.length);
    const slashIndex = remainder.indexOf('/');
    if (slashIndex < 0) {
      return url;
    }
    const paramsStr = remainder.slice(0, slashIndex);
    const objectPath = remainder.slice(slashIndex + 1);
    const params = {};
    if (paramsStr) {
      paramsStr.split(',').forEach((part) => {
        const kv = part.split('=');
        if (kv.length === 2) {
          params[kv[0]] = kv[1];
        }
      });
    }
    params.width = String(width || DEFAULT_GRID_IMAGE_WIDTH);
    const newParamsStr = Object.keys(params).map((key) => `${key}=${params[key]}`).join(',');
    return `${IMAGE_CDN_PREFIX}${newParamsStr}/${objectPath}`;
  }

  function extractImageUrls(images) {
    return (images || []).map((image) => image && image.url).filter(Boolean);
  }

  function buildImagesForGrid(primaryUrl, allUrls) {
    return dedupeKeepOrder([primaryUrl, ...(allUrls || [])]).map((url) => ({
      url,
      thumb_url: formatThumbUrl(url, DEFAULT_GRID_IMAGE_WIDTH),
    }));
  }

  function applyJokeDataToPayload(basePayload, jokeData) {
    if (!jokeData) {
      return basePayload;
    }
    const payload = { ...(basePayload || {}) };
    payload.joke_id = jokeData.key || jokeData.joke_id || payload.joke_id || '';
    if (jokeData.state !== undefined) {
      payload.state = jokeData.state;
    }
    if (Object.prototype.hasOwnProperty.call(jokeData, 'public_timestamp')) {
      payload.public_timestamp = jokeData.public_timestamp;
    }
    if (jokeData.setup_text !== undefined) {
      payload.setup_text = jokeData.setup_text;
    }
    if (jokeData.punchline_text !== undefined) {
      payload.punchline_text = jokeData.punchline_text;
    }
    if (jokeData.seasonal !== undefined) {
      payload.seasonal = jokeData.seasonal;
    }
    if (Object.prototype.hasOwnProperty.call(jokeData, 'tags')) {
      payload.tags = Array.isArray(jokeData.tags)
        ? jokeData.tags.filter(Boolean).join(', ')
        : (jokeData.tags ? String(jokeData.tags) : '');
    }
    if (jokeData.setup_scene_idea !== undefined) {
      payload.setup_scene_idea = jokeData.setup_scene_idea;
    }
    if (jokeData.punchline_scene_idea !== undefined) {
      payload.punchline_scene_idea = jokeData.punchline_scene_idea;
    }
    if (jokeData.setup_image_description !== undefined) {
      payload.setup_image_description = jokeData.setup_image_description;
    }
    if (jokeData.punchline_image_description !== undefined) {
      payload.punchline_image_description = jokeData.punchline_image_description;
    }
    const setupUrl = jokeData.setup_image_url || payload.setup_image_url || '';
    const punchlineUrl = jokeData.punchline_image_url || payload.punchline_image_url || '';
    payload.setup_image_url = setupUrl;
    payload.punchline_image_url = punchlineUrl;
    payload.setup_images = buildImagesForGrid(
      setupUrl,
      Array.isArray(jokeData.all_setup_image_urls)
        ? jokeData.all_setup_image_urls
        : extractImageUrls(payload.setup_images),
    );
    payload.punchline_images = buildImagesForGrid(
      punchlineUrl,
      Array.isArray(jokeData.all_punchline_image_urls)
        ? jokeData.all_punchline_image_urls
        : extractImageUrls(payload.punchline_images),
    );
    return payload;
  }

  function buildOptimisticPayload(basePayload, values) {
    const payload = { ...(basePayload || {}) };
    payload.joke_id = values.jokeId || payload.joke_id || payload.jokeId || '';
    payload.setup_text = values.setupText;
    payload.punchline_text = values.punchlineText;
    payload.seasonal = values.seasonal;
    payload.tags = values.tags;
    payload.setup_image_description = values.setupImageDescription;
    payload.punchline_image_description = values.punchlineImageDescription;
    payload.setup_image_url = values.setupImageUrl;
    payload.punchline_image_url = values.punchlineImageUrl;
    payload.setup_images = buildImagesForGrid(
      payload.setup_image_url,
      extractImageUrls(payload.setup_images),
    );
    payload.punchline_images = buildImagesForGrid(
      payload.punchline_image_url,
      extractImageUrls(payload.punchline_images),
    );
    return payload;
  }

  function buildEditRequestData(formValues, populateImages) {
    return {
      joke_id: formValues.jokeId,
      setup_text: formValues.setupText,
      punchline_text: formValues.punchlineText,
      seasonal: formValues.seasonal,
      tags: formValues.tags,
      setup_image_description: formValues.setupImageDescription,
      punchline_image_description: formValues.punchlineImageDescription,
      setup_image_url: formValues.setupImageUrl,
      punchline_image_url: formValues.punchlineImageUrl,
      populate_images: Boolean(populateImages),
    };
  }

  function normalizeTextValue(value) {
    return value === null || value === undefined ? '' : String(value).trim();
  }

  function buildRegenerateAllRequestData(formValues, basePayload) {
    const payload = {
      joke_id: formValues.jokeId,
      regenerate_scene_ideas: true,
      generate_descriptions: true,
      populate_images: true,
    };

    if (formValues.setupText !== normalizeTextValue(basePayload && basePayload.setup_text)) {
      payload.setup_text = formValues.setupText;
    }
    if (formValues.punchlineText !== normalizeTextValue(basePayload && basePayload.punchline_text)) {
      payload.punchline_text = formValues.punchlineText;
    }

    return payload;
  }

  function buildModifyRequestData(jokeId, setupInstruction, punchlineInstruction) {
    const data = {
      op: 'joke_image_modify',
      joke_id: jokeId,
    };
    if (setupInstruction) {
      data.setup_instruction = setupInstruction;
    }
    if (punchlineInstruction) {
      data.punchline_instruction = punchlineInstruction;
    }
    return data;
  }

  function buildStateRequestData(jokeId, newState) {
    return {
      op: 'joke_state',
      joke_id: jokeId,
      new_state: newState,
    };
  }

  function buildCalendarEntryFromPayload(payload) {
    return {
      joke_id: payload.joke_id || payload.jokeId || '',
      setup_text: payload.setup_text || '',
      thumbnail_url: payload.setup_image_url || null,
    };
  }

  function syncDailyCalendarFromStateChange(previousPayload, nextPayload) {
    if (typeof window === 'undefined'
        || typeof window.syncAdminJokesCalendarJokeState !== 'function') {
      return;
    }

    const removeDate = isFutureDailyPayload(previousPayload)
      ? extractDateLabel(previousPayload.public_timestamp)
      : '';
    const addDate = isFutureDailyPayload(nextPayload)
      ? extractDateLabel(nextPayload.public_timestamp)
      : '';

    if (!removeDate && !addDate) {
      return;
    }

    window.syncAdminJokesCalendarJokeState({
      removeDate: removeDate || null,
      addDate: addDate || null,
      entry: addDate ? buildCalendarEntryFromPayload(nextPayload) : null,
    });
  }

  function getRevealButtonLabel(button) {
    if (!button) {
      return DEFAULT_REVEAL_LABEL;
    }
    const expanded = button.getAttribute('aria-expanded') === 'true';
    const labelAttr = expanded ? 'data-label-hide' : 'data-label-show';
    return button.getAttribute(labelAttr) || DEFAULT_REVEAL_LABEL;
  }

  function setValue(input, value) {
    if (!input) {
      return;
    }
    input.value = value === null || value === undefined ? '' : String(value);
  }

  function getEventTargetElement(event) {
    const elementNodeType = typeof Node !== 'undefined' ? Node.ELEMENT_NODE : 1;
    if (!event || !event.target) {
      return null;
    }
    if (event.target.nodeType === elementNodeType) {
      return event.target;
    }
    return event.target.parentElement || null;
  }

  function closestFromEvent(event, selector) {
    const element = getEventTargetElement(event);
    if (!element || typeof element.closest !== 'function') {
      return null;
    }
    return element.closest(selector);
  }

  function setPreviewImage(img, placeholder, imageUrl, altText) {
    if (!img || !placeholder) {
      return;
    }
    if (imageUrl) {
      img.src = formatThumbUrl(imageUrl, DEFAULT_PREVIEW_IMAGE_WIDTH) || imageUrl;
      img.alt = altText || '';
      img.classList.add('is-visible');
      placeholder.classList.add('is-hidden');
      return;
    }
    img.removeAttribute('src');
    img.alt = '';
    img.classList.remove('is-visible');
    placeholder.classList.remove('is-hidden');
  }

  function renderImageGrid(container, images, selectedUrl, onSelect) {
    if (!container) {
      return;
    }
    container.innerHTML = '';
    if (!Array.isArray(images) || images.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'muted';
      empty.textContent = IMAGE_GRID_EMPTY_TEXT;
      container.appendChild(empty);
      return;
    }
    images.forEach((image, index) => {
      if (!image || !image.url) {
        return;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = image.url === selectedUrl
        ? 'admin-modal__image-option admin-modal__image-option--selected'
        : 'admin-modal__image-option';
      button.dataset.imageUrl = image.url;
      const img = document.createElement('img');
      img.src = image.thumb_url || image.url;
      img.alt = `Image ${index + 1}`;
      img.loading = 'lazy';
      button.appendChild(img);
      button.addEventListener('click', () => onSelect(image.url));
      container.appendChild(button);
    });
  }

  function getCardImageSize(card) {
    if (!card) {
      return DEFAULT_CARD_IMAGE_SIZE;
    }
    const img = card.querySelector('.joke-slide img');
    if (img) {
      const widthValue = parseInt(img.getAttribute('width'), 10);
      if (!Number.isNaN(widthValue) && widthValue > 0) {
        return widthValue;
      }
    }
    const cssValue = card.style.getPropertyValue('--joke-card-max-width');
    if (cssValue) {
      const parsed = parseInt(cssValue, 10);
      if (!Number.isNaN(parsed) && parsed > 0) {
        return parsed;
      }
    }
    return DEFAULT_CARD_IMAGE_SIZE;
  }

  function formatCardImageUrl(url, card) {
    return url ? formatThumbUrl(url, getCardImageSize(card)) : url;
  }

  function updateCardAdminPayload(card, payload) {
    if (!card || !payload) {
      return;
    }
    ['.joke-edit-button', '.joke-modify-button', '[data-joke-state-button]'].forEach((selector) => {
      const element = card.querySelector(selector);
      if (element) {
        element.setAttribute('data-joke-data', JSON.stringify(payload));
      }
    });
  }

  function updateCardStateBadge(card, payload) {
    if (!card || !payload) {
      return;
    }
    const stateButton = card.querySelector('[data-joke-state-button]');
    if (!stateButton) {
      return;
    }
    const badgeClass = getStateBadgeClass(payload);
    stateButton.className = `joke-state-badge joke-state-badge--button joke-state-${badgeClass}`;
    stateButton.textContent = getStateBadgeText(payload);
    stateButton.disabled = false;
    stateButton.title = 'Change state';
    stateButton.setAttribute('aria-label', 'Change joke state');
  }

  function setSlideMedia(slide, imageUrl, altText, placeholderText, size) {
    if (!slide) {
      return;
    }
    const media = slide.querySelector('.joke-slide-media');
    if (!media) {
      return;
    }
    media.innerHTML = '';
    if (imageUrl) {
      const img = document.createElement('img');
      img.src = imageUrl;
      img.alt = altText || '';
      img.width = size;
      img.height = size;
      img.loading = 'lazy';
      media.appendChild(img);
      return;
    }
    const placeholder = document.createElement('div');
    placeholder.className = 'joke-slide-placeholder text-button';
    placeholder.textContent = placeholderText;
    media.appendChild(placeholder);
  }

  function updateCardFromPayload(card, payload) {
    if (!card || !payload) {
      return;
    }
    const size = getCardImageSize(card);
    const setupSlide = card.querySelector('.joke-slide');
    const punchlineSlide = card.querySelector('.joke-slide[id$="-punchline"]')
      || (card.querySelectorAll('.joke-slide')[1] || null);
    const setupUrl = formatCardImageUrl(payload.setup_image_url, card);
    const punchlineUrl = formatCardImageUrl(payload.punchline_image_url, card);
    setSlideMedia(setupSlide, setupUrl, payload.setup_text, CARD_PLACEHOLDER_SETUP, size);
    setSlideMedia(
      punchlineSlide,
      punchlineUrl,
      payload.punchline_text,
      CARD_PLACEHOLDER_PUNCHLINE,
      size,
    );
    if (card.dataset.selectable === 'true') {
      if (setupUrl) {
        card.dataset.setupUrl = setupUrl;
      } else {
        card.removeAttribute('data-setup-url');
      }
    }
    updateCardAdminPayload(card, payload);
    updateCardStateBadge(card, payload);
  }

  function setCardGenerating(card) {
    if (!card) {
      return;
    }
    const revealButton = card.querySelector('button[data-role="reveal"]');
    if (!revealButton) {
      return;
    }
    revealButton.classList.add('joke-reveal--generating');
    revealButton.disabled = true;
    revealButton.textContent = GENERATING_LABEL;
  }

  function setCardIdle(card) {
    if (!card) {
      return;
    }
    const revealButton = card.querySelector('button[data-role="reveal"]');
    if (!revealButton) {
      return;
    }
    revealButton.classList.remove('joke-reveal--generating');
    revealButton.disabled = false;
    revealButton.textContent = getRevealButtonLabel(revealButton);
  }

  function isModalOpen(modal) {
    return Boolean(modal && modal.classList.contains('admin-modal--open'));
  }

  function openModal(modal, focusTarget) {
    if (!modal) {
      return;
    }
    modal.classList.add('admin-modal--open');
    modal.setAttribute('aria-hidden', 'false');
    if (focusTarget) {
      focusTarget.focus();
    }
  }

  function closeModal(modal) {
    if (!modal) {
      return;
    }
    modal.classList.remove('admin-modal--open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function getEditPayloadFromCard(card) {
    if (!card) {
      return {};
    }
    const editButton = card.querySelector('.joke-edit-button');
    return editButton ? parseEditPayload(editButton.getAttribute('data-joke-data')) : {};
  }

  async function postJokeCreationRequest(jokeCreationUrl, payload) {
    const response = await fetch(jokeCreationUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    let json = null;
    try {
      json = await response.json();
    } catch (_error) {
      json = null;
    }
    return { response, json };
  }

  function initJokeAdminActions(options) {
    if (window.__jokeAdminActionsInitialized) {
      return;
    }

    const config = options || {};
    if (!config.jokeCreationUrl) {
      throw new Error('jokeCreationUrl is required for initJokeAdminActions');
    }
    const elements = {
      editModal: document.getElementById('admin-edit-joke-modal'),
      editModalBackdrop: document.querySelector('[data-admin-edit-joke-backdrop]'),
      editForm: document.getElementById('admin-edit-joke-form'),
      editCancelButton: document.getElementById('admin-edit-joke-cancel-button'),
      editJokeIdInput: document.getElementById('admin-edit-joke-id'),
      editSetupInput: document.getElementById('admin-edit-joke-setup'),
      editPunchlineInput: document.getElementById('admin-edit-joke-punchline'),
      editSeasonalInput: document.getElementById('admin-edit-joke-seasonal'),
      editTagsInput: document.getElementById('admin-edit-joke-tags'),
      editSetupImageDescriptionInput: document.getElementById('admin-edit-joke-setup-image-description'),
      editPunchlineImageDescriptionInput: document.getElementById('admin-edit-joke-punchline-image-description'),
      editSetupImagesGrid: document.getElementById('admin-edit-joke-setup-images'),
      editPunchlineImagesGrid: document.getElementById('admin-edit-joke-punchline-images'),
      editRegenerateButton: document.getElementById('admin-edit-joke-regenerate-button'),
      editRegenerateAllButton: document.getElementById('admin-edit-joke-regenerate-all-button'),
      editSceneIdeasButton: document.getElementById('admin-edit-joke-scene-ideas-button'),
      regenerateAllModal: document.getElementById('admin-regenerate-all-modal'),
      regenerateAllModalBackdrop: document.querySelector('[data-admin-regenerate-all-backdrop]'),
      regenerateAllForm: document.getElementById('admin-regenerate-all-form'),
      regenerateAllCancelButton: document.getElementById('admin-regenerate-all-cancel-button'),
      regenerateAllSubmitButton: document.getElementById('admin-regenerate-all-submit-button'),
      regenerateModal: document.getElementById('admin-regenerate-modal'),
      regenerateModalBackdrop: document.querySelector('[data-admin-regenerate-backdrop]'),
      regenerateJokeIdInput: document.getElementById('admin-regenerate-joke-id'),
      modifyModal: document.getElementById('admin-modify-joke-modal'),
      modifyModalBackdrop: document.querySelector('[data-admin-modify-joke-backdrop]'),
      modifyForm: document.getElementById('admin-modify-joke-form'),
      modifyCancelButton: document.getElementById('admin-modify-joke-cancel-button'),
      modifyJokeIdInput: document.getElementById('admin-modify-joke-id'),
      modifySetupInstructionInput: document.getElementById('admin-modify-joke-setup-instruction'),
      modifyPunchlineInstructionInput: document.getElementById('admin-modify-joke-punchline-instruction'),
      modifySetupPreview: document.getElementById('admin-modify-joke-setup-preview'),
      modifyPunchlinePreview: document.getElementById('admin-modify-joke-punchline-preview'),
      modifySetupPlaceholder: document.getElementById('admin-modify-joke-setup-placeholder'),
      modifyPunchlinePlaceholder: document.getElementById('admin-modify-joke-punchline-placeholder'),
      stateModal: document.getElementById('admin-state-joke-modal'),
      stateModalBackdrop: document.querySelector('[data-admin-state-joke-backdrop]'),
      stateForm: document.getElementById('admin-state-joke-form'),
      stateCancelButton: document.getElementById('admin-state-joke-cancel-button'),
      stateJokeIdInput: document.getElementById('admin-state-joke-id'),
      stateNewStateInput: document.getElementById('admin-state-joke-new-state'),
      stateOptions: document.getElementById('admin-state-joke-options'),
      sceneIdeasModal: document.getElementById('admin-scene-ideas-modal'),
      sceneIdeasModalBackdrop: document.querySelector('[data-admin-scene-ideas-backdrop]'),
      sceneIdeasForm: document.getElementById('admin-scene-ideas-form'),
      sceneIdeasCancelButton: document.getElementById('admin-scene-ideas-cancel-button'),
      sceneIdeasSetupInput: document.getElementById('admin-scene-ideas-setup'),
      sceneIdeasPunchlineInput: document.getElementById('admin-scene-ideas-punchline'),
      sceneIdeasGenerateButton: document.getElementById('admin-scene-ideas-generate-button'),
    };

    if (!elements.editModal || !elements.regenerateAllModal || !elements.regenerateModal
        || !elements.modifyModal || !elements.stateModal || !elements.sceneIdeasModal) {
      return;
    }

    window.__jokeAdminActionsInitialized = true;

    const state = {
      activeEditCard: null,
      activeEditPayload: null,
      activeModifyCard: null,
      activeModifyPayload: null,
      activeStateCard: null,
      activeStatePayload: null,
      selectedStateValue: '',
      selectedSetupImageUrl: null,
      selectedPunchlineImageUrl: null,
    };

    function handleEditCancel() {
      if (isModalOpen(elements.regenerateAllModal)) {
        closeModal(elements.regenerateAllModal);
      }
      if (isModalOpen(elements.sceneIdeasModal)) {
        closeModal(elements.sceneIdeasModal);
      }
      closeModal(elements.editModal);
      state.activeEditCard = null;
      state.activeEditPayload = null;
    }

    function validateEditForm() {
      if (!elements.editJokeIdInput || !elements.editSetupInput || !elements.editPunchlineInput) {
        return null;
      }
      if (!elements.editSetupInput.checkValidity()
          || !elements.editPunchlineInput.checkValidity()) {
        if (elements.editForm && typeof elements.editForm.reportValidity === 'function') {
          elements.editForm.reportValidity();
        }
        return null;
      }

      const formValues = readEditFormValues();
      if (!formValues.setupText || !formValues.punchlineText) {
        if (elements.editForm && typeof elements.editForm.reportValidity === 'function') {
          elements.editForm.reportValidity();
        }
        return null;
      }
      return formValues;
    }

    function handleModifyCancel() {
      closeModal(elements.modifyModal);
      state.activeModifyCard = null;
      state.activeModifyPayload = null;
    }

    function handleStateCancel() {
      closeModal(elements.stateModal);
      state.activeStateCard = null;
      state.activeStatePayload = null;
      state.selectedStateValue = '';
      setValue(elements.stateJokeIdInput, '');
      setValue(elements.stateNewStateInput, '');
      if (elements.stateOptions) {
        elements.stateOptions.innerHTML = '';
      }
    }

    function setSceneIdeasLocked(isLocked) {
      const locked = Boolean(isLocked);
      if (elements.sceneIdeasSetupInput) {
        elements.sceneIdeasSetupInput.disabled = locked;
      }
      if (elements.sceneIdeasPunchlineInput) {
        elements.sceneIdeasPunchlineInput.disabled = locked;
      }
      if (elements.sceneIdeasCancelButton) {
        elements.sceneIdeasCancelButton.disabled = locked;
      }
      if (elements.sceneIdeasGenerateButton) {
        elements.sceneIdeasGenerateButton.disabled = locked;
        elements.sceneIdeasGenerateButton.textContent = locked
          ? GENERATING_LABEL
          : 'Generate Image Descriptions';
      }
    }

    function getFirstRegenerateModelButton() {
      if (!elements.regenerateModal) {
        return null;
      }
      return elements.regenerateModal.querySelector('[data-admin-regenerate-model-button]');
    }

    function selectSetupImage(url) {
      state.selectedSetupImageUrl = url;
      if (!state.activeEditPayload) {
        return;
      }
      renderImageGrid(
        elements.editSetupImagesGrid,
        state.activeEditPayload.setup_images,
        state.selectedSetupImageUrl,
        selectSetupImage,
      );
    }

    function selectPunchlineImage(url) {
      state.selectedPunchlineImageUrl = url;
      if (!state.activeEditPayload) {
        return;
      }
      renderImageGrid(
        elements.editPunchlineImagesGrid,
        state.activeEditPayload.punchline_images,
        state.selectedPunchlineImageUrl,
        selectPunchlineImage,
      );
    }

    function populateEditModal(payload, card) {
      state.activeEditCard = card;
      state.activeEditPayload = payload;
      state.selectedSetupImageUrl = payload.setup_image_url || null;
      state.selectedPunchlineImageUrl = payload.punchline_image_url || null;

      if (!state.selectedSetupImageUrl && payload.setup_images && payload.setup_images.length) {
        state.selectedSetupImageUrl = payload.setup_images[0].url;
      }
      if (!state.selectedPunchlineImageUrl
          && payload.punchline_images && payload.punchline_images.length) {
        state.selectedPunchlineImageUrl = payload.punchline_images[0].url;
      }

      setValue(elements.editJokeIdInput, payload.joke_id || payload.jokeId || '');
      setValue(elements.editSetupInput, payload.setup_text);
      setValue(elements.editPunchlineInput, payload.punchline_text);
      setValue(elements.editSeasonalInput, payload.seasonal);
      setValue(elements.editTagsInput, payload.tags);
      setValue(elements.editSetupImageDescriptionInput, payload.setup_image_description);
      setValue(elements.editPunchlineImageDescriptionInput, payload.punchline_image_description);

      renderImageGrid(
        elements.editSetupImagesGrid,
        payload.setup_images,
        state.selectedSetupImageUrl,
        selectSetupImage,
      );
      renderImageGrid(
        elements.editPunchlineImagesGrid,
        payload.punchline_images,
        state.selectedPunchlineImageUrl,
        selectPunchlineImage,
      );
    }

    function populateModifyModal(payload, card) {
      state.activeModifyCard = card;
      state.activeModifyPayload = payload;

      setValue(elements.modifyJokeIdInput, payload.joke_id || payload.jokeId || '');
      setValue(elements.modifySetupInstructionInput, '');
      setValue(elements.modifyPunchlineInstructionInput, '');
      setPreviewImage(
        elements.modifySetupPreview,
        elements.modifySetupPlaceholder,
        payload.setup_image_url,
        payload.setup_text || 'Setup image',
      );
      setPreviewImage(
        elements.modifyPunchlinePreview,
        elements.modifyPunchlinePlaceholder,
        payload.punchline_image_url,
        payload.punchline_text || 'Punchline image',
      );
    }

    function renderStateOptions(payload) {
      if (!elements.stateOptions) {
        return;
      }
      const options = getReachableStateOptions(payload);
      elements.stateOptions.innerHTML = '';
      options.forEach((stateValue) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = state.selectedStateValue === stateValue
          ? `admin-modal__state-option admin-modal__state-option--selected joke-state-badge joke-state-${String(stateValue).toLowerCase()}`
          : `admin-modal__state-option joke-state-badge joke-state-${String(stateValue).toLowerCase()}`;
        button.textContent = getStateLabel(stateValue);
        button.setAttribute('data-state-value', stateValue);
        button.addEventListener('click', () => {
          state.selectedStateValue = stateValue;
          setValue(elements.stateNewStateInput, stateValue);
          renderStateOptions(payload);
        });
        elements.stateOptions.appendChild(button);
      });
    }

    function populateStateModal(payload, card) {
      state.activeStateCard = card;
      state.activeStatePayload = payload;
      state.selectedStateValue = '';
      setValue(elements.stateJokeIdInput, payload.joke_id || payload.jokeId || '');
      setValue(elements.stateNewStateInput, '');
      renderStateOptions(payload);
    }

    function readEditFormValues() {
      return {
        jokeId: elements.editJokeIdInput.value,
        setupText: elements.editSetupInput.value.trim(),
        punchlineText: elements.editPunchlineInput.value.trim(),
        seasonal: elements.editSeasonalInput ? elements.editSeasonalInput.value.trim() : '',
        tags: elements.editTagsInput ? elements.editTagsInput.value.trim() : '',
        setupImageDescription: elements.editSetupImageDescriptionInput
          ? elements.editSetupImageDescriptionInput.value.trim()
          : '',
        punchlineImageDescription: elements.editPunchlineImageDescriptionInput
          ? elements.editPunchlineImageDescriptionInput.value.trim()
          : '',
        setupImageUrl: state.selectedSetupImageUrl,
        punchlineImageUrl: state.selectedPunchlineImageUrl,
      };
    }

    async function sendEditRequest(populateImages) {
      const formValues = validateEditForm();
      if (!formValues) {
        return;
      }

      const payload = {
        data: buildEditRequestData(formValues, populateImages),
      };
      const card = state.activeEditCard
        || document.querySelector(`.joke-card[data-joke-id="${formValues.jokeId}"]`);
      const basePayload = state.activeEditPayload || getEditPayloadFromCard(card);
      const optimisticPayload = buildOptimisticPayload(basePayload, formValues);

      if (card) {
        updateCardFromPayload(card, optimisticPayload);
      }

      closeModal(elements.editModal);
      if (card) {
        setCardGenerating(card);
      }
      state.activeEditCard = null;
      state.activeEditPayload = null;

      try {
        const { response, json } = await postJokeCreationRequest(config.jokeCreationUrl, payload);
        if (populateImages) {
          const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
          if (response.ok && jokeData && card) {
            updateCardFromPayload(card, applyJokeDataToPayload(optimisticPayload, jokeData));
          }
        }
        if (!response.ok) {
          console.warn('joke_creation_process request failed', response.status); // eslint-disable-line no-console
        }
      } catch (error) {
        console.warn('joke_creation_process request failed', error); // eslint-disable-line no-console
      } finally {
        if (card) {
          setCardIdle(card);
        }
      }
    }

    async function sendRegenerateAllRequest() {
      const formValues = validateEditForm();
      if (!formValues) {
        return;
      }

      const card = state.activeEditCard
        || document.querySelector(`.joke-card[data-joke-id="${formValues.jokeId}"]`);
      const basePayload = state.activeEditPayload || getEditPayloadFromCard(card);
      const optimisticPayload = buildOptimisticPayload(basePayload, formValues);
      const payload = {
        data: buildRegenerateAllRequestData(formValues, basePayload),
      };

      if (card) {
        updateCardFromPayload(card, optimisticPayload);
      }

      closeModal(elements.regenerateAllModal);
      closeModal(elements.editModal);
      if (card) {
        setCardGenerating(card);
      }
      state.activeEditCard = null;
      state.activeEditPayload = null;

      try {
        const { response, json } = await postJokeCreationRequest(config.jokeCreationUrl, payload);
        const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
        if (response.ok && jokeData && card) {
          updateCardFromPayload(card, applyJokeDataToPayload(optimisticPayload, jokeData));
        }
        if (!response.ok) {
          console.warn('regenerate all request failed', response.status); // eslint-disable-line no-console
        }
      } catch (error) {
        console.warn('regenerate all request failed', error); // eslint-disable-line no-console
      } finally {
        if (card) {
          setCardIdle(card);
        }
      }
    }

    async function sendRegenerateRequest(imageQuality) {
      if (!elements.regenerateJokeIdInput) {
        return;
      }

      const jokeId = elements.regenerateJokeIdInput.value;
      if (!jokeId || !imageQuality) {
        return;
      }

      const card = document.querySelector(`.joke-card[data-joke-id="${jokeId}"]`);
      closeModal(elements.regenerateModal);
      if (card) {
        setCardGenerating(card);
      }

      try {
        const { response, json } = await postJokeCreationRequest(config.jokeCreationUrl, {
          data: {
            joke_id: jokeId,
            image_quality: imageQuality,
            populate_images: true,
          },
        });
        const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
        if (response.ok && jokeData && card) {
          updateCardFromPayload(
            card,
            applyJokeDataToPayload(getEditPayloadFromCard(card), jokeData),
          );
        }
        if (!response.ok) {
          console.warn('regenerate images request failed', response.status); // eslint-disable-line no-console
        }
      } catch (error) {
        console.warn('regenerate images request failed', error); // eslint-disable-line no-console
      } finally {
        if (card) {
          setCardIdle(card);
        }
      }
    }

    async function sendModifyRequest() {
      if (!elements.modifyJokeIdInput || !elements.modifySetupInstructionInput
          || !elements.modifyPunchlineInstructionInput) {
        return;
      }

      const jokeId = elements.modifyJokeIdInput.value;
      const setupInstruction = elements.modifySetupInstructionInput.value.trim();
      const punchlineInstruction = elements.modifyPunchlineInstructionInput.value.trim();
      if (!setupInstruction && !punchlineInstruction) {
        return;
      }

      const card = state.activeModifyCard
        || document.querySelector(`.joke-card[data-joke-id="${jokeId}"]`);
      const basePayload = state.activeModifyPayload || getEditPayloadFromCard(card);
      const payload = {
        data: buildModifyRequestData(jokeId, setupInstruction, punchlineInstruction),
      };

      handleModifyCancel();
      if (card) {
        setCardGenerating(card);
      }

      try {
        const { response, json } = await postJokeCreationRequest(config.jokeCreationUrl, payload);
        const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
        if (response.ok && jokeData && card) {
          updateCardFromPayload(card, applyJokeDataToPayload(basePayload, jokeData));
        }
        if (!response.ok) {
          console.warn('joke image modify request failed', response.status); // eslint-disable-line no-console
        }
      } catch (error) {
        console.warn('joke image modify request failed', error); // eslint-disable-line no-console
      } finally {
        if (card) {
          setCardIdle(card);
        }
      }
    }

    function showStateRequestError(message) {
      if (typeof window !== 'undefined' && typeof window.alert === 'function') {
        window.alert(message);
      }
    }

    async function sendStateRequest() {
      if (!elements.stateJokeIdInput || !elements.stateNewStateInput) {
        return;
      }

      const jokeId = elements.stateJokeIdInput.value;
      const newState = elements.stateNewStateInput.value;
      if (!jokeId || !newState) {
        return;
      }

      const card = state.activeStateCard
        || document.querySelector(`.joke-card[data-joke-id="${jokeId}"]`);
      const previousPayload = { ...(state.activeStatePayload || getEditPayloadFromCard(card)) };
      const optimisticPayload = {
        ...previousPayload,
        state: newState,
        public_timestamp: null,
      };

      handleStateCancel();
      if (card) {
        updateCardFromPayload(card, optimisticPayload);
        setCardGenerating(card);
      }

      try {
        const { response, json } = await postJokeCreationRequest(config.jokeCreationUrl, {
          data: buildStateRequestData(jokeId, newState),
        });
        const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
        if (response.ok && jokeData) {
          const nextPayload = applyJokeDataToPayload(optimisticPayload, jokeData);
          if (card) {
            updateCardFromPayload(card, nextPayload);
          }
          syncDailyCalendarFromStateChange(previousPayload, nextPayload);
          return;
        }
        if (card) {
          updateCardFromPayload(card, previousPayload);
        }
        showStateRequestError(
          (json && json.data && json.data.error) || 'Failed to update joke state.',
        );
      } catch (_error) {
        if (card) {
          updateCardFromPayload(card, previousPayload);
        }
        showStateRequestError('Failed to update joke state.');
      } finally {
        if (card) {
          setCardIdle(card);
        }
      }
    }

    async function generateImageDescriptionsFromSceneIdeas() {
      if (!state.activeEditPayload || !elements.editJokeIdInput
          || !elements.sceneIdeasSetupInput || !elements.sceneIdeasPunchlineInput) {
        return;
      }

      const setupSceneIdea = elements.sceneIdeasSetupInput.value.trim();
      const punchlineSceneIdea = elements.sceneIdeasPunchlineInput.value.trim();
      setSceneIdeasLocked(true);

      try {
        const { response, json } = await postJokeCreationRequest(config.jokeCreationUrl, {
          data: {
            joke_id: elements.editJokeIdInput.value,
            setup_scene_idea: setupSceneIdea,
            punchline_scene_idea: punchlineSceneIdea,
            generate_descriptions: true,
          },
        });

        const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
        if (!response.ok || !jokeData) {
          console.warn('Generate image descriptions failed', { // eslint-disable-line no-console
            status: response.status,
            json,
          });
          return;
        }

        state.activeEditPayload.setup_scene_idea = setupSceneIdea;
        state.activeEditPayload.punchline_scene_idea = punchlineSceneIdea;
        state.activeEditPayload.setup_image_description = jokeData.setup_image_description;
        state.activeEditPayload.punchline_image_description = jokeData.punchline_image_description;

        setValue(elements.editSetupImageDescriptionInput, jokeData.setup_image_description);
        setValue(
          elements.editPunchlineImageDescriptionInput,
          jokeData.punchline_image_description,
        );

        if (jokeData.all_setup_image_urls || jokeData.setup_image_url) {
          state.activeEditPayload.setup_images = buildImagesForGrid(
            jokeData.setup_image_url,
            jokeData.all_setup_image_urls,
          );
          state.activeEditPayload.setup_image_url = jokeData.setup_image_url;
          state.selectedSetupImageUrl = jokeData.setup_image_url
            || (state.activeEditPayload.setup_images[0]
              ? state.activeEditPayload.setup_images[0].url
              : state.selectedSetupImageUrl);
          renderImageGrid(
            elements.editSetupImagesGrid,
            state.activeEditPayload.setup_images,
            state.selectedSetupImageUrl,
            selectSetupImage,
          );
        }

        if (jokeData.all_punchline_image_urls || jokeData.punchline_image_url) {
          state.activeEditPayload.punchline_images = buildImagesForGrid(
            jokeData.punchline_image_url,
            jokeData.all_punchline_image_urls,
          );
          state.activeEditPayload.punchline_image_url = jokeData.punchline_image_url;
          state.selectedPunchlineImageUrl = jokeData.punchline_image_url
            || (state.activeEditPayload.punchline_images[0]
              ? state.activeEditPayload.punchline_images[0].url
              : state.selectedPunchlineImageUrl);
          renderImageGrid(
            elements.editPunchlineImagesGrid,
            state.activeEditPayload.punchline_images,
            state.selectedPunchlineImageUrl,
            selectPunchlineImage,
          );
        }

        closeModal(elements.sceneIdeasModal);
      } catch (error) {
        console.warn('Generate image descriptions request failed', error); // eslint-disable-line no-console
      } finally {
        setSceneIdeasLocked(false);
      }
    }

    if (elements.regenerateAllCancelButton) {
      elements.regenerateAllCancelButton.addEventListener('click', () => {
        closeModal(elements.regenerateAllModal);
      });
    }
    if (elements.regenerateAllModalBackdrop) {
      elements.regenerateAllModalBackdrop.addEventListener('click', () => {
        closeModal(elements.regenerateAllModal);
      });
    }
    if (elements.regenerateModalBackdrop) {
      elements.regenerateModalBackdrop.addEventListener('click', () => {
        closeModal(elements.regenerateModal);
      });
    }
    if (elements.modifyCancelButton) {
      elements.modifyCancelButton.addEventListener('click', handleModifyCancel);
    }
    if (elements.modifyModalBackdrop) {
      elements.modifyModalBackdrop.addEventListener('click', handleModifyCancel);
    }
    if (elements.stateCancelButton) {
      elements.stateCancelButton.addEventListener('click', handleStateCancel);
    }
    if (elements.stateModalBackdrop) {
      elements.stateModalBackdrop.addEventListener('click', handleStateCancel);
    }
    if (elements.editCancelButton) {
      elements.editCancelButton.addEventListener('click', handleEditCancel);
    }
    if (elements.editModalBackdrop) {
      elements.editModalBackdrop.addEventListener('click', handleEditCancel);
    }
    if (elements.editSceneIdeasButton) {
      elements.editSceneIdeasButton.addEventListener('click', () => {
        if (!state.activeEditPayload) {
          return;
        }
        setValue(elements.sceneIdeasSetupInput, state.activeEditPayload.setup_scene_idea);
        setValue(
          elements.sceneIdeasPunchlineInput,
          state.activeEditPayload.punchline_scene_idea,
        );
        openModal(elements.sceneIdeasModal, elements.sceneIdeasSetupInput);
      });
    }
    if (elements.sceneIdeasCancelButton) {
      elements.sceneIdeasCancelButton.addEventListener('click', () => {
        closeModal(elements.sceneIdeasModal);
      });
    }
    if (elements.sceneIdeasModalBackdrop) {
      elements.sceneIdeasModalBackdrop.addEventListener('click', () => {
        closeModal(elements.sceneIdeasModal);
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') {
        return;
      }
      if (isModalOpen(elements.regenerateAllModal)) {
        closeModal(elements.regenerateAllModal);
        return;
      }
      if (isModalOpen(elements.sceneIdeasModal)) {
        closeModal(elements.sceneIdeasModal);
        return;
      }
      if (isModalOpen(elements.editModal)) {
        handleEditCancel();
        return;
      }
      if (isModalOpen(elements.modifyModal)) {
        handleModifyCancel();
        return;
      }
      if (isModalOpen(elements.stateModal)) {
        handleStateCancel();
        return;
      }
      if (isModalOpen(elements.regenerateModal)) {
        closeModal(elements.regenerateModal);
      }
    });

    document.addEventListener('click', (event) => {
      const regenerateModelButton = closestFromEvent(event, '[data-admin-regenerate-model-button]');
      if (regenerateModelButton) {
        sendRegenerateRequest(regenerateModelButton.getAttribute('data-image-quality') || '');
        return;
      }

      const regenerateButton = closestFromEvent(event, '.joke-regenerate-button');
      if (regenerateButton) {
        const jokeId = regenerateButton.getAttribute('data-joke-id');
        if (jokeId) {
          setValue(elements.regenerateJokeIdInput, jokeId);
          openModal(elements.regenerateModal, getFirstRegenerateModelButton());
        }
        return;
      }

      const modifyButton = closestFromEvent(event, '.joke-modify-button');
      if (modifyButton) {
        populateModifyModal(
          parseEditPayload(modifyButton.getAttribute('data-joke-data')),
          modifyButton.closest('.joke-card'),
        );
        openModal(elements.modifyModal, elements.modifySetupInstructionInput);
        return;
      }

      const stateButton = closestFromEvent(event, '[data-joke-state-button]');
      if (stateButton && !stateButton.disabled) {
        const payload = parseEditPayload(stateButton.getAttribute('data-joke-data'));
        populateStateModal(payload, stateButton.closest('.joke-card'));
        openModal(elements.stateModal, elements.stateOptions);
        return;
      }

      const editButton = closestFromEvent(event, '.joke-edit-button');
      if (!editButton) {
        return;
      }

      populateEditModal(
        parseEditPayload(editButton.getAttribute('data-joke-data')),
        editButton.closest('.joke-card'),
      );
      openModal(elements.editModal, elements.editSetupInput);
    });

    if (elements.editForm) {
      elements.editForm.addEventListener('submit', (event) => {
        event.preventDefault();
        sendEditRequest(false);
      });
    }
    if (elements.editRegenerateButton) {
      elements.editRegenerateButton.addEventListener('click', () => {
        sendEditRequest(true);
      });
    }
    if (elements.editRegenerateAllButton) {
      elements.editRegenerateAllButton.addEventListener('click', () => {
        openModal(elements.regenerateAllModal, elements.regenerateAllSubmitButton);
      });
    }
    if (elements.regenerateAllForm) {
      elements.regenerateAllForm.addEventListener('submit', (event) => {
        event.preventDefault();
        sendRegenerateAllRequest();
      });
    }
    if (elements.sceneIdeasForm) {
      elements.sceneIdeasForm.addEventListener('submit', (event) => {
        event.preventDefault();
        generateImageDescriptionsFromSceneIdeas();
      });
    }
    if (elements.modifyForm) {
      elements.modifyForm.addEventListener('submit', (event) => {
        event.preventDefault();
        sendModifyRequest();
      });
    }
    if (elements.stateForm) {
      elements.stateForm.addEventListener('submit', (event) => {
        event.preventDefault();
        sendStateRequest();
      });
    }
  }

  return {
    applyJokeDataToPayload,
    buildEditRequestData,
    buildImagesForGrid,
    buildModifyRequestData,
    buildRegenerateAllRequestData,
    buildStateRequestData,
    buildOptimisticPayload,
    closestFromEvent,
    dedupeKeepOrder,
    extractImageUrls,
    formatThumbUrl,
    getReachableStateOptions,
    getRevealButtonLabel,
    getStateBadgeClass,
    getStateBadgeText,
    initJokeAdminActions,
    isFutureDailyPayload,
    parseEditPayload,
    updateCardFromPayload,
  };
}));
