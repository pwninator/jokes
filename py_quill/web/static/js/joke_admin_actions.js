(function () {
  function initJokeAdminActions(options) {
    if (window.__jokeAdminActionsInitialized) {
      return;
    }

    const config = options || {};
    if (!config.jokeCreationUrl) {
      throw new Error('jokeCreationUrl is required for initJokeAdminActions');
    }
    const jokeCreationUrl = config.jokeCreationUrl;

    const editModal = document.getElementById('admin-edit-joke-modal');
    const editModalBackdrop = document.querySelector('[data-admin-edit-joke-backdrop]');
    const editForm = document.getElementById('admin-edit-joke-form');
    const editCancelButton = document.getElementById('admin-edit-joke-cancel-button');
    const editJokeIdInput = document.getElementById('admin-edit-joke-id');
    const editSetupInput = document.getElementById('admin-edit-joke-setup');
    const editPunchlineInput = document.getElementById('admin-edit-joke-punchline');
    const editSeasonalInput = document.getElementById('admin-edit-joke-seasonal');
    const editTagsInput = document.getElementById('admin-edit-joke-tags');
    const editSetupImageDescriptionInput = document.getElementById('admin-edit-joke-setup-image-description');
    const editPunchlineImageDescriptionInput = document.getElementById('admin-edit-joke-punchline-image-description');
    const editSetupImagesGrid = document.getElementById('admin-edit-joke-setup-images');
    const editPunchlineImagesGrid = document.getElementById('admin-edit-joke-punchline-images');
    const editRegenerateButton = document.getElementById('admin-edit-joke-regenerate-button');
    const editSceneIdeasButton = document.getElementById('admin-edit-joke-scene-ideas-button');

    const regenerateModal = document.getElementById('admin-regenerate-modal');
    const regenerateModalBackdrop = document.querySelector('[data-admin-regenerate-backdrop]');
    const regenerateForm = document.getElementById('admin-regenerate-form');
    const regenerateCancelButton = document.getElementById('admin-regenerate-cancel-button');
    const regenerateJokeIdInput = document.getElementById('admin-regenerate-joke-id');
    const regenerateQualityInput = document.getElementById('admin-regenerate-quality');

    const sceneIdeasModal = document.getElementById('admin-scene-ideas-modal');
    const sceneIdeasModalBackdrop = document.querySelector('[data-admin-scene-ideas-backdrop]');
    const sceneIdeasForm = document.getElementById('admin-scene-ideas-form');
    const sceneIdeasCancelButton = document.getElementById('admin-scene-ideas-cancel-button');
    const sceneIdeasSetupInput = document.getElementById('admin-scene-ideas-setup');
    const sceneIdeasPunchlineInput = document.getElementById('admin-scene-ideas-punchline');
    const sceneIdeasGenerateButton = document.getElementById('admin-scene-ideas-generate-button');

    if (!editModal || !regenerateModal || !sceneIdeasModal) {
      return;
    }

    window.__jokeAdminActionsInitialized = true;

    let activeEditCard = null;
    let selectedSetupImageUrl = null;
    let selectedPunchlineImageUrl = null;
    let activeEditPayload = null;

    function isEditModalOpen() {
      return Boolean(editModal && editModal.classList.contains('admin-modal--open'));
    }

    function isSceneIdeasModalOpen() {
      return Boolean(sceneIdeasModal && sceneIdeasModal.classList.contains('admin-modal--open'));
    }

    function isRegenerateModalOpen() {
      return Boolean(regenerateModal && regenerateModal.classList.contains('admin-modal--open'));
    }

    function openRegenerateModal() {
      if (!regenerateModal) {
        return;
      }
      regenerateModal.classList.add('admin-modal--open');
      regenerateModal.setAttribute('aria-hidden', 'false');
      if (regenerateQualityInput) {
        regenerateQualityInput.focus();
      }
    }

    function closeRegenerateModal() {
      if (!regenerateModal) {
        return;
      }
      regenerateModal.classList.remove('admin-modal--open');
      regenerateModal.setAttribute('aria-hidden', 'true');
    }

    function openEditModal() {
      if (!editModal) {
        return;
      }
      editModal.classList.add('admin-modal--open');
      editModal.setAttribute('aria-hidden', 'false');
      if (editSetupInput) {
        editSetupInput.focus();
      }
    }

    function closeEditModal() {
      if (!editModal) {
        return;
      }
      editModal.classList.remove('admin-modal--open');
      editModal.setAttribute('aria-hidden', 'true');
    }

    function openSceneIdeasModal() {
      if (!sceneIdeasModal || !activeEditPayload) {
        return;
      }
      setValue(sceneIdeasSetupInput, activeEditPayload.setup_scene_idea);
      setValue(sceneIdeasPunchlineInput, activeEditPayload.punchline_scene_idea);
      sceneIdeasModal.classList.add('admin-modal--open');
      sceneIdeasModal.setAttribute('aria-hidden', 'false');
      if (sceneIdeasSetupInput) {
        sceneIdeasSetupInput.focus();
      }
    }

    function closeSceneIdeasModal() {
      if (!sceneIdeasModal) {
        return;
      }
      sceneIdeasModal.classList.remove('admin-modal--open');
      sceneIdeasModal.setAttribute('aria-hidden', 'true');
    }

    function setSceneIdeasLocked(isLocked) {
      const locked = Boolean(isLocked);
      if (sceneIdeasSetupInput) {
        sceneIdeasSetupInput.disabled = locked;
      }
      if (sceneIdeasPunchlineInput) {
        sceneIdeasPunchlineInput.disabled = locked;
      }
      if (sceneIdeasCancelButton) {
        sceneIdeasCancelButton.disabled = locked;
      }
      if (sceneIdeasGenerateButton) {
        sceneIdeasGenerateButton.disabled = locked;
        sceneIdeasGenerateButton.textContent = locked ? 'Generating...' : 'Generate Image Descriptions';
      }
    }

    function getRevealButtonLabel(button) {
      if (!button) {
        return 'Reveal Punchline';
      }
      const expanded = button.getAttribute('aria-expanded') === 'true';
      const labelAttribute = expanded ? 'data-label-hide' : 'data-label-show';
      return button.getAttribute(labelAttribute) || 'Reveal Punchline';
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
      revealButton.textContent = 'Generating...';
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

    function handleEditCancel() {
      if (isSceneIdeasModalOpen()) {
        closeSceneIdeasModal();
      }
      closeEditModal();
      activeEditCard = null;
      activeEditPayload = null;
    }

    function setValue(input, value) {
      if (!input) {
        return;
      }
      input.value = (value === null || value === undefined) ? '' : String(value);
    }

    function parseEditPayload(rawValue) {
      const raw = rawValue || '{}';
      let payload = {};
      try {
        payload = JSON.parse(raw);
      } catch (e) {
        try {
          const decoder = document.createElement('textarea');
          decoder.innerHTML = raw;
          const decoded = decoder.value || '{}';
          payload = JSON.parse(decoded);
        } catch (_inner) {
          console.warn('Failed to parse edit payload', { raw }); // eslint-disable-line no-console
          payload = {};
        }
      }
      return payload;
    }

    function getEditPayloadFromCard(card) {
      if (!card) {
        return {};
      }
      const editButton = card.querySelector('.joke-edit-button');
      if (!editButton) {
        return {};
      }
      return parseEditPayload(editButton.getAttribute('data-joke-data'));
    }

    function renderImageGrid(container, images, selectedUrl, onSelect) {
      if (!container) {
        return;
      }
      container.innerHTML = '';
      if (!images || !Array.isArray(images) || images.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'muted';
        empty.textContent = 'No images found.';
        container.appendChild(empty);
        return;
      }

      images.forEach((image, index) => {
        if (!image || !image.url) {
          return;
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'admin-modal__image-option' + (image.url === selectedUrl ? ' admin-modal__image-option--selected' : '');
        button.dataset.imageUrl = image.url;

        const img = document.createElement('img');
        img.src = image.thumb_url || image.url;
        img.alt = `Image ${index + 1}`;
        img.loading = 'lazy';

        button.appendChild(img);
        button.addEventListener('click', () => {
          onSelect(image.url);
        });

        container.appendChild(button);
      });
    }

    function dedupeKeepOrder(values) {
      const seen = new Set();
      const result = [];
      (values || []).forEach((value) => {
        if (!value) {
          return;
        }
        if (seen.has(value)) {
          return;
        }
        seen.add(value);
        result.push(value);
      });
      return result;
    }

    function formatThumbUrl(url, width) {
      if (!url || typeof url !== 'string') {
        return url;
      }
      const prefix = 'https://images.quillsstorybook.com/cdn-cgi/image/';
      if (!url.startsWith(prefix)) {
        return url;
      }
      const remainder = url.slice(prefix.length);
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
      params.width = String(width || 180);
      const newParamsStr = Object.keys(params).map((k) => `${k}=${params[k]}`).join(',');
      return `${prefix}${newParamsStr}/${objectPath}`;
    }

    function getCardImageSize(card) {
      if (!card) {
        return 600;
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
      return 600;
    }

    function formatCardImageUrl(url, card) {
      if (!url) {
        return url;
      }
      return formatThumbUrl(url, getCardImageSize(card));
    }

    function extractImageUrls(images) {
      return (images || []).map((image) => image && image.url).filter(Boolean);
    }

    function buildImagesForGrid(primaryUrl, allUrls) {
      const urls = dedupeKeepOrder([primaryUrl, ...(allUrls || [])]);
      return urls.map((url) => ({
        url,
        thumb_url: formatThumbUrl(url, 180),
      }));
    }

    function updateEditButtonPayload(card, payload) {
      if (!card || !payload) {
        return;
      }
      const editButton = card.querySelector('.joke-edit-button');
      if (!editButton) {
        return;
      }
      editButton.setAttribute('data-joke-data', JSON.stringify(payload));
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
      } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'joke-slide-placeholder text-button';
        placeholder.textContent = placeholderText;
        media.appendChild(placeholder);
      }
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

      setSlideMedia(setupSlide, setupUrl, payload.setup_text, 'Illustration baking...', size);
      setSlideMedia(punchlineSlide, punchlineUrl, payload.punchline_text, 'Punchline ready to read!', size);

      if (card.dataset.selectable === 'true') {
        if (setupUrl) {
          card.dataset.setupUrl = setupUrl;
        } else {
          card.removeAttribute('data-setup-url');
        }
      }

      updateEditButtonPayload(card, payload);
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

      const setupUrls = extractImageUrls(payload.setup_images);
      const punchlineUrls = extractImageUrls(payload.punchline_images);
      payload.setup_images = buildImagesForGrid(payload.setup_image_url, setupUrls);
      payload.punchline_images = buildImagesForGrid(payload.punchline_image_url, punchlineUrls);
      return payload;
    }

    function applyJokeDataToPayload(basePayload, jokeData) {
      if (!jokeData) {
        return basePayload;
      }
      const payload = { ...(basePayload || {}) };
      payload.joke_id = jokeData.key || jokeData.joke_id || payload.joke_id || '';

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
        if (Array.isArray(jokeData.tags)) {
          payload.tags = jokeData.tags.filter(Boolean).join(', ');
        } else {
          payload.tags = jokeData.tags ? String(jokeData.tags) : '';
        }
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
      const setupUrls = Array.isArray(jokeData.all_setup_image_urls)
        ? jokeData.all_setup_image_urls
        : extractImageUrls(payload.setup_images);
      const punchlineUrls = Array.isArray(jokeData.all_punchline_image_urls)
        ? jokeData.all_punchline_image_urls
        : extractImageUrls(payload.punchline_images);
      payload.setup_image_url = setupUrl;
      payload.punchline_image_url = punchlineUrl;
      payload.setup_images = buildImagesForGrid(setupUrl, setupUrls);
      payload.punchline_images = buildImagesForGrid(punchlineUrl, punchlineUrls);
      return payload;
    }

    function selectSetupImage(url) {
      selectedSetupImageUrl = url;
      if (!activeEditPayload) {
        return;
      }
      renderImageGrid(editSetupImagesGrid, activeEditPayload.setup_images, selectedSetupImageUrl, selectSetupImage);
    }

    function selectPunchlineImage(url) {
      selectedPunchlineImageUrl = url;
      if (!activeEditPayload) {
        return;
      }
      renderImageGrid(editPunchlineImagesGrid, activeEditPayload.punchline_images, selectedPunchlineImageUrl, selectPunchlineImage);
    }

    if (regenerateCancelButton) {
      regenerateCancelButton.addEventListener('click', () => {
        closeRegenerateModal();
      });
    }

    if (regenerateModalBackdrop) {
      regenerateModalBackdrop.addEventListener('click', () => {
        closeRegenerateModal();
      });
    }

    if (editCancelButton) {
      editCancelButton.addEventListener('click', () => {
        handleEditCancel();
      });
    }

    if (editModalBackdrop) {
      editModalBackdrop.addEventListener('click', () => {
        handleEditCancel();
      });
    }

    if (editSceneIdeasButton) {
      editSceneIdeasButton.addEventListener('click', () => {
        openSceneIdeasModal();
      });
    }

    if (sceneIdeasCancelButton) {
      sceneIdeasCancelButton.addEventListener('click', () => {
        closeSceneIdeasModal();
      });
    }

    if (sceneIdeasModalBackdrop) {
      sceneIdeasModalBackdrop.addEventListener('click', () => {
        closeSceneIdeasModal();
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        if (isSceneIdeasModalOpen()) {
          closeSceneIdeasModal();
          return;
        }
        if (isEditModalOpen()) {
          handleEditCancel();
          return;
        }
        if (isRegenerateModalOpen()) {
          closeRegenerateModal();
          return;
        }
      }
    });

    if (regenerateForm) {
      regenerateForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        if (!regenerateJokeIdInput || !regenerateQualityInput) {
          return;
        }

        const jokeId = regenerateJokeIdInput.value;
        const quality = regenerateQualityInput.value;
        const card = document.querySelector(`.joke-card[data-joke-id="${jokeId}"]`);

        const payload = {
          data: {
            joke_id: jokeId,
            image_quality: quality,
            populate_images: true,
          },
        };

        closeRegenerateModal();

        if (card) {
          setCardGenerating(card);
        }

        try {
          const response = await fetch(jokeCreationUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(payload),
          });

          let json = null;
          try {
            json = await response.json();
          } catch (_e) {
            json = null;
          }

          // If the backend returns the updated joke payload, refresh the card in-place.
          const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
          if (response.ok && jokeData && card) {
            const basePayload = getEditPayloadFromCard(card);
            const refreshedPayload = applyJokeDataToPayload(basePayload, jokeData);
            updateCardFromPayload(card, refreshedPayload);
          }
          if (!response.ok) {
            console.warn('regenerate images request failed', response.status); // eslint-disable-line no-console
          }
        } catch (err) {
          console.warn('regenerate images request failed', err); // eslint-disable-line no-console
        } finally {
          if (card) {
            setCardIdle(card);
          }
        }
      });
    }

    document.addEventListener('click', (event) => {
      const regenerateButton = event.target.closest('.joke-regenerate-button');
      if (regenerateButton) {
        const jokeId = regenerateButton.getAttribute('data-joke-id');
        if (jokeId) {
          setValue(regenerateJokeIdInput, jokeId);
          openRegenerateModal();
        }
        return;
      }

      const editButton = event.target.closest('.joke-edit-button');
      if (!editButton) {
        return;
      }

      const card = editButton.closest('.joke-card');
      const payload = parseEditPayload(editButton.getAttribute('data-joke-data'));

      activeEditCard = card;
      activeEditPayload = payload;

      setValue(editJokeIdInput, payload.joke_id || payload.jokeId || '');
      setValue(editSetupInput, payload.setup_text);
      setValue(editPunchlineInput, payload.punchline_text);
      setValue(editSeasonalInput, payload.seasonal);
      setValue(editTagsInput, payload.tags);
      setValue(editSetupImageDescriptionInput, payload.setup_image_description);
      setValue(editPunchlineImageDescriptionInput, payload.punchline_image_description);

      selectedSetupImageUrl = payload.setup_image_url || null;
      selectedPunchlineImageUrl = payload.punchline_image_url || null;

      if (!selectedSetupImageUrl && payload.setup_images && payload.setup_images.length) {
        selectedSetupImageUrl = payload.setup_images[0].url;
      }
      if (!selectedPunchlineImageUrl && payload.punchline_images && payload.punchline_images.length) {
        selectedPunchlineImageUrl = payload.punchline_images[0].url;
      }

      renderImageGrid(editSetupImagesGrid, payload.setup_images, selectedSetupImageUrl, selectSetupImage);
      renderImageGrid(editPunchlineImagesGrid, payload.punchline_images, selectedPunchlineImageUrl, selectPunchlineImage);

      openEditModal();
    });

    async function generateImageDescriptionsFromSceneIdeas() {
      if (!activeEditPayload || !editJokeIdInput) {
        return;
      }
      if (!sceneIdeasSetupInput || !sceneIdeasPunchlineInput) {
        return;
      }

      const setupSceneIdea = sceneIdeasSetupInput.value.trim();
      const punchlineSceneIdea = sceneIdeasPunchlineInput.value.trim();

      setSceneIdeasLocked(true);

      const requestPayload = {
        data: {
          joke_id: editJokeIdInput.value,
          setup_scene_idea: setupSceneIdea,
          punchline_scene_idea: punchlineSceneIdea,
          generate_descriptions: true,
        },
      };

      try {
        const resp = await fetch(jokeCreationUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify(requestPayload),
        });

        let json = null;
        try {
          json = await resp.json();
        } catch (_e) {
          json = null;
        }

        const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
        if (!resp.ok || !jokeData) {
          console.warn('Generate image descriptions failed', { status: resp.status, json }); // eslint-disable-line no-console
          return;
        }

        activeEditPayload.setup_scene_idea = setupSceneIdea;
        activeEditPayload.punchline_scene_idea = punchlineSceneIdea;

        activeEditPayload.setup_image_description = jokeData.setup_image_description;
        activeEditPayload.punchline_image_description = jokeData.punchline_image_description;
        setValue(editSetupImageDescriptionInput, jokeData.setup_image_description);
        setValue(editPunchlineImageDescriptionInput, jokeData.punchline_image_description);

        if (jokeData.all_setup_image_urls || jokeData.setup_image_url) {
          activeEditPayload.setup_images = buildImagesForGrid(jokeData.setup_image_url, jokeData.all_setup_image_urls);
          activeEditPayload.setup_image_url = jokeData.setup_image_url;
          selectedSetupImageUrl = jokeData.setup_image_url || (activeEditPayload.setup_images[0] ? activeEditPayload.setup_images[0].url : selectedSetupImageUrl);
          renderImageGrid(editSetupImagesGrid, activeEditPayload.setup_images, selectedSetupImageUrl, selectSetupImage);
        }

        if (jokeData.all_punchline_image_urls || jokeData.punchline_image_url) {
          activeEditPayload.punchline_images = buildImagesForGrid(jokeData.punchline_image_url, jokeData.all_punchline_image_urls);
          activeEditPayload.punchline_image_url = jokeData.punchline_image_url;
          selectedPunchlineImageUrl = jokeData.punchline_image_url || (activeEditPayload.punchline_images[0] ? activeEditPayload.punchline_images[0].url : selectedPunchlineImageUrl);
          renderImageGrid(editPunchlineImagesGrid, activeEditPayload.punchline_images, selectedPunchlineImageUrl, selectPunchlineImage);
        }

        closeSceneIdeasModal();
      } catch (err) {
        console.warn('Generate image descriptions request failed', err); // eslint-disable-line no-console
      } finally {
        setSceneIdeasLocked(false);
      }
    }

    async function sendEditRequest(populateImages) {
      if (!editJokeIdInput || !editSetupInput || !editPunchlineInput) {
        return;
      }

      if (!editSetupInput.checkValidity() || !editPunchlineInput.checkValidity()) {
        if (editForm && typeof editForm.reportValidity === 'function') {
          editForm.reportValidity();
        }
        return;
      }

      const setupText = editSetupInput.value.trim();
      const punchlineText = editPunchlineInput.value.trim();
      if (!setupText || !punchlineText) {
        if (editForm && typeof editForm.reportValidity === 'function') {
          editForm.reportValidity();
        }
        return;
      }

      const payload = {
        data: {
          joke_id: editJokeIdInput.value,
          setup_text: setupText,
          punchline_text: punchlineText,
          seasonal: editSeasonalInput ? editSeasonalInput.value.trim() : '',
          tags: editTagsInput ? editTagsInput.value.trim() : '',
          setup_image_description: (editSetupImageDescriptionInput && editSetupImageDescriptionInput.value) ? editSetupImageDescriptionInput.value.trim() : '',
          punchline_image_description: (editPunchlineImageDescriptionInput && editPunchlineImageDescriptionInput.value) ? editPunchlineImageDescriptionInput.value.trim() : '',
          setup_image_url: selectedSetupImageUrl,
          punchline_image_url: selectedPunchlineImageUrl,
          populate_images: Boolean(populateImages),
        },
      };

      const jokeId = editJokeIdInput.value;
      const card = activeEditCard || document.querySelector(`.joke-card[data-joke-id="${jokeId}"]`);
      const basePayload = activeEditPayload || getEditPayloadFromCard(card);
      const optimisticPayload = buildOptimisticPayload(basePayload, {
        jokeId,
        setupText,
        punchlineText,
        seasonal: editSeasonalInput ? editSeasonalInput.value.trim() : '',
        tags: editTagsInput ? editTagsInput.value.trim() : '',
        setupImageDescription: (editSetupImageDescriptionInput && editSetupImageDescriptionInput.value)
          ? editSetupImageDescriptionInput.value.trim()
          : '',
        punchlineImageDescription: (editPunchlineImageDescriptionInput && editPunchlineImageDescriptionInput.value)
          ? editPunchlineImageDescriptionInput.value.trim()
          : '',
        setupImageUrl: selectedSetupImageUrl,
        punchlineImageUrl: selectedPunchlineImageUrl,
      });
      if (card) {
        updateCardFromPayload(card, optimisticPayload);
      }

      closeEditModal();
      if (card) {
        setCardGenerating(card);
      }
      activeEditCard = null;
      activeEditPayload = null;

      try {
        const response = await fetch(jokeCreationUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify(payload),
        });
        if (populateImages) {
          let json = null;
          try {
            json = await response.json();
          } catch (_e) {
            json = null;
          }

          const jokeData = json && json.data && json.data.joke_data ? json.data.joke_data : null;
          if (response.ok && jokeData) {
            const refreshedPayload = applyJokeDataToPayload(optimisticPayload, jokeData);
            if (card) {
              updateCardFromPayload(card, refreshedPayload);
            }
            if (isEditModalOpen() && activeEditCard
                && activeEditCard.getAttribute('data-joke-id') === jokeId) {
              activeEditPayload = refreshedPayload;
              selectedSetupImageUrl = refreshedPayload.setup_image_url || null;
              selectedPunchlineImageUrl = refreshedPayload.punchline_image_url || null;
              renderImageGrid(editSetupImagesGrid, refreshedPayload.setup_images,
                selectedSetupImageUrl, selectSetupImage);
              renderImageGrid(editPunchlineImagesGrid, refreshedPayload.punchline_images,
                selectedPunchlineImageUrl, selectPunchlineImage);
            }
          }
        }
        if (!response.ok) {
          console.warn('joke_creation_process request failed', response.status); // eslint-disable-line no-console
        }
      } catch (err) {
        console.warn('joke_creation_process request failed', err); // eslint-disable-line no-console
      } finally {
        if (card) {
          setCardIdle(card);
        }
      }
    }

    if (editForm) {
      editForm.addEventListener('submit', (event) => {
        event.preventDefault();
        sendEditRequest(false);
      });
    }

    if (editRegenerateButton) {
      editRegenerateButton.addEventListener('click', () => {
        sendEditRequest(true);
      });
    }

    if (sceneIdeasForm) {
      sceneIdeasForm.addEventListener('submit', (event) => {
        event.preventDefault();
        generateImageDescriptionsFromSceneIdeas();
      });
    }
  }

  window.initJokeAdminActions = initJokeAdminActions;
})();
