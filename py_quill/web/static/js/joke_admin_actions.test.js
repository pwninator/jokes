const assert = require('node:assert/strict');
const test = require('node:test');

const {
  FakeDocument,
  FakeElement,
  append,
  createDeferred,
  createFetchMock,
  createFetchResponse,
} = require('./test_utils.js');
const {
  applyJokeDataToPayload,
  buildModifyRequestData,
  buildOptimisticPayload,
  formatThumbUrl,
  initJokeAdminActions,
  parseEditPayload,
} = require('./joke_admin_actions.js');

function buildModalRoot(id, backdropAttr) {
  const modal = new FakeElement({ id, className: 'admin-modal' });
  modal.setAttribute('aria-hidden', 'true');
  const backdrop = append(modal, new FakeElement({ className: 'admin-modal__backdrop' }));
  backdrop.setAttribute(backdropAttr, '');
  append(modal, new FakeElement({ className: 'admin-modal__dialog' }));
  return { modal, backdrop };
}

function buildEnvironment() {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const originalNode = global.Node;

  const root = new FakeElement({ tagName: 'body' });
  const document = new FakeDocument(root);
  const fetchMock = createFetchMock();

  global.Node = { ELEMENT_NODE: 1 };
  global.window = { __jokeAdminActionsInitialized: false };
  global.document = document;
  global.fetch = fetchMock;

  const editModalBundle = buildModalRoot('admin-edit-joke-modal', 'data-admin-edit-joke-backdrop');
  const regenerateModalBundle = buildModalRoot('admin-regenerate-modal', 'data-admin-regenerate-backdrop');
  const modifyModalBundle = buildModalRoot('admin-modify-joke-modal', 'data-admin-modify-joke-backdrop');
  const sceneIdeasModalBundle = buildModalRoot('admin-scene-ideas-modal', 'data-admin-scene-ideas-backdrop');

  append(root, editModalBundle.modal);
  append(root, regenerateModalBundle.modal);
  append(root, modifyModalBundle.modal);
  append(root, sceneIdeasModalBundle.modal);

  const editForm = append(editModalBundle.modal, new FakeElement({ id: 'admin-edit-joke-form', tagName: 'form' }));
  const editJokeId = append(editForm, new FakeElement({ id: 'admin-edit-joke-id', tagName: 'input' }));
  const editSetup = append(editForm, new FakeElement({ id: 'admin-edit-joke-setup', tagName: 'input' }));
  const editPunchline = append(editForm, new FakeElement({ id: 'admin-edit-joke-punchline', tagName: 'input' }));
  const editSeasonal = append(editForm, new FakeElement({ id: 'admin-edit-joke-seasonal', tagName: 'input' }));
  const editTags = append(editForm, new FakeElement({ id: 'admin-edit-joke-tags', tagName: 'input' }));
  const editSetupDesc = append(editForm, new FakeElement({ id: 'admin-edit-joke-setup-image-description', tagName: 'textarea' }));
  const editPunchlineDesc = append(editForm, new FakeElement({ id: 'admin-edit-joke-punchline-image-description', tagName: 'textarea' }));
  const editSetupImages = append(editForm, new FakeElement({ id: 'admin-edit-joke-setup-images' }));
  const editPunchlineImages = append(editForm, new FakeElement({ id: 'admin-edit-joke-punchline-images' }));
  append(editForm, new FakeElement({ id: 'admin-edit-joke-cancel-button', tagName: 'button' }));
  const editRegenerateButton = append(editForm, new FakeElement({ id: 'admin-edit-joke-regenerate-button', tagName: 'button' }));
  const editSceneIdeasButton = append(editForm, new FakeElement({ id: 'admin-edit-joke-scene-ideas-button', tagName: 'button' }));

  const regenerateForm = append(regenerateModalBundle.modal, new FakeElement({ id: 'admin-regenerate-form', tagName: 'form' }));
  const regenerateJokeId = append(regenerateForm, new FakeElement({ id: 'admin-regenerate-joke-id', tagName: 'input' }));
  const regenerateQuality = append(regenerateForm, new FakeElement({ id: 'admin-regenerate-quality', tagName: 'select' }));
  append(regenerateForm, new FakeElement({ id: 'admin-regenerate-cancel-button', tagName: 'button' }));

  const modifyForm = append(modifyModalBundle.modal, new FakeElement({ id: 'admin-modify-joke-form', tagName: 'form' }));
  const modifyJokeId = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-id', tagName: 'input' }));
  const modifySetupInstruction = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-instruction', tagName: 'textarea' }));
  const modifyPunchlineInstruction = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-instruction', tagName: 'textarea' }));
  const modifySetupPreview = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-preview', tagName: 'img' }));
  const modifyPunchlinePreview = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-preview', tagName: 'img' }));
  const modifySetupPlaceholder = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-placeholder' }));
  const modifyPunchlinePlaceholder = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-placeholder' }));
  append(modifyForm, new FakeElement({ id: 'admin-modify-joke-cancel-button', tagName: 'button' }));

  const sceneIdeasForm = append(sceneIdeasModalBundle.modal, new FakeElement({ id: 'admin-scene-ideas-form', tagName: 'form' }));
  const sceneIdeasSetup = append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-setup', tagName: 'textarea' }));
  const sceneIdeasPunchline = append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-punchline', tagName: 'textarea' }));
  append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-cancel-button', tagName: 'button' }));
  append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-generate-button', tagName: 'button' }));

  const card = append(root, new FakeElement({ className: 'joke-card', tagName: 'article' }));
  card.setAttribute('data-joke-id', 'joke-1');
  card.dataset.selectable = 'true';
  card.style.setProperty('--joke-card-max-width', '600px');

  const setupSlide = append(card, new FakeElement({ className: 'joke-slide' }));
  const setupMedia = append(setupSlide, new FakeElement({ className: 'joke-slide-media' }));
  const setupImg = append(setupMedia, new FakeElement({ tagName: 'img' }));
  setupImg.setAttribute('src', 'https://example.com/setup-old.png');
  setupImg.setAttribute('width', '600');

  const punchlineSlide = append(card, new FakeElement({ className: 'joke-slide' }));
  punchlineSlide.setAttribute('id', 'joke-1-punchline');
  const punchlineMedia = append(punchlineSlide, new FakeElement({ className: 'joke-slide-media' }));
  const punchlineImg = append(punchlineMedia, new FakeElement({ tagName: 'img' }));
  punchlineImg.setAttribute('src', 'https://example.com/punchline-old.png');
  punchlineImg.setAttribute('width', '600');

  const revealButton = append(card, new FakeElement({ tagName: 'button' }));
  revealButton.setAttribute('data-role', 'reveal');
  revealButton.setAttribute('data-label-show', 'Reveal Punchline');
  revealButton.setAttribute('data-label-hide', 'Back to Setup');
  revealButton.setAttribute('aria-expanded', 'false');
  revealButton.textContent = 'Reveal Punchline';

  const payload = {
    joke_id: 'joke-1',
    setup_text: 'Old setup',
    punchline_text: 'Old punchline',
    setup_image_url: 'https://example.com/setup-old.png',
    punchline_image_url: 'https://example.com/punchline-old.png',
    setup_images: [{ url: 'https://example.com/setup-old.png', thumb_url: 'https://example.com/setup-thumb.png' }],
    punchline_images: [{ url: 'https://example.com/punchline-old.png', thumb_url: 'https://example.com/punch-thumb.png' }],
  };

  const editButton = append(card, new FakeElement({ className: 'joke-edit-button', tagName: 'button' }));
  editButton.setAttribute('data-joke-data', JSON.stringify(payload));

  const regenerateButton = append(card, new FakeElement({ className: 'joke-regenerate-button', tagName: 'button' }));
  regenerateButton.setAttribute('data-joke-id', 'joke-1');

  const modifyButton = append(card, new FakeElement({ className: 'joke-modify-button', tagName: 'button' }));
  modifyButton.setAttribute('data-joke-id', 'joke-1');
  modifyButton.setAttribute('data-joke-data', JSON.stringify(payload));
  const modifyIcon = append(modifyButton, new FakeElement({ tagName: 'span' }));
  modifyIcon.textContent = 'paint';

  return {
    cleanup() {
      global.window = originalWindow;
      global.document = originalDocument;
      global.fetch = originalFetch;
      global.Node = originalNode;
    },
    document,
    fetchMock,
    elements: {
      card,
      editButton,
      editForm,
      editJokeId,
      editSetup,
      editPunchline,
      editSeasonal,
      editTags,
      editSetupDesc,
      editPunchlineDesc,
      editSetupImages,
      editPunchlineImages,
      editRegenerateButton,
      editSceneIdeasButton,
      regenerateButton,
      regenerateForm,
      regenerateJokeId,
      regenerateQuality,
      modifyModal: modifyModalBundle.modal,
      modifyForm,
      modifyIcon,
      modifyJokeId,
      modifySetupInstruction,
      modifyPunchlineInstruction,
      modifySetupPreview,
      modifyPunchlinePreview,
      modifySetupPlaceholder,
      modifyPunchlinePlaceholder,
      sceneIdeasForm,
      sceneIdeasSetup,
      sceneIdeasPunchline,
      revealButton,
      setupMedia,
      punchlineMedia,
    },
  };
}

test('parseEditPayload decodes HTML-escaped JSON payloads', () => {
  const payload = parseEditPayload('{&quot;joke_id&quot;:&quot;joke-1&quot;,&quot;tags&quot;:&quot;cats&quot;}');
  assert.equal(payload.joke_id, 'joke-1');
  assert.equal(payload.tags, 'cats');
});

test('buildModifyRequestData includes only non-empty instructions', () => {
  assert.deepEqual(
    buildModifyRequestData('joke-1', 'make it sunnier', ''),
    {
      op: 'joke_image_modify',
      joke_id: 'joke-1',
      setup_instruction: 'make it sunnier',
    },
  );
});

test('buildOptimisticPayload refreshes image grids from selected urls', () => {
  const payload = buildOptimisticPayload(
    {
      joke_id: 'joke-1',
      setup_images: [{ url: 'https://example.com/setup-old.png' }],
      punchline_images: [{ url: 'https://example.com/punchline-old.png' }],
    },
    {
      jokeId: 'joke-1',
      setupText: 'Setup',
      punchlineText: 'Punchline',
      seasonal: '',
      tags: 'cats',
      setupImageDescription: '',
      punchlineImageDescription: '',
      setupImageUrl: 'https://example.com/setup-new.png',
      punchlineImageUrl: 'https://example.com/punchline-new.png',
    },
  );

  assert.deepEqual(
    payload.setup_images.map((image) => image.url),
    ['https://example.com/setup-new.png', 'https://example.com/setup-old.png'],
  );
  assert.deepEqual(
    payload.punchline_images.map((image) => image.url),
    ['https://example.com/punchline-new.png', 'https://example.com/punchline-old.png'],
  );
});

test('applyJokeDataToPayload merges tag arrays and image urls', () => {
  const payload = applyJokeDataToPayload(
    {
      joke_id: 'joke-1',
      tags: '',
      setup_images: [{ url: 'https://example.com/setup-old.png' }],
      punchline_images: [{ url: 'https://example.com/punchline-old.png' }],
    },
    {
      key: 'joke-1',
      tags: ['cats', 'dogs'],
      setup_image_url: 'https://example.com/setup-new.png',
      punchline_image_url: 'https://example.com/punchline-new.png',
      all_setup_image_urls: ['https://example.com/setup-new.png', 'https://example.com/setup-old.png'],
      all_punchline_image_urls: ['https://example.com/punchline-new.png'],
    },
  );

  assert.equal(payload.tags, 'cats, dogs');
  assert.equal(payload.setup_image_url, 'https://example.com/setup-new.png');
  assert.deepEqual(
    payload.setup_images.map((image) => image.url),
    ['https://example.com/setup-new.png', 'https://example.com/setup-old.png'],
  );
});

test('formatThumbUrl preserves existing params and rewrites width', () => {
  assert.equal(
    formatThumbUrl(
      'https://images.quillsstorybook.com/cdn-cgi/image/fit=cover,width=180/example.png',
      480,
    ),
    'https://images.quillsstorybook.com/cdn-cgi/image/fit=cover,width=480/example.png',
  );
});

test('modify button opens modal from a non-element click target', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });

    await env.document.dispatch('click', {
      target: {
        nodeType: 3,
        parentElement: env.elements.modifyIcon,
      },
    });

    assert.equal(env.elements.modifyModal.classList.contains('admin-modal--open'), true);
    assert.equal(env.elements.modifyModal.getAttribute('aria-hidden'), 'false');
    assert.equal(env.elements.modifyJokeId.value, 'joke-1');
    assert.equal(env.elements.modifySetupPreview.src, 'https://example.com/setup-old.png');
    assert.equal(env.elements.modifyPunchlinePreview.src, 'https://example.com/punchline-old.png');
  } finally {
    env.cleanup();
  }
});

test('modify submit posts joke_image_modify and updates the card in place', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    await env.document.dispatch('click', { target: env.elements.modifyIcon });

    env.elements.modifySetupInstruction.value = 'make it sunnier';
    env.elements.modifyPunchlineInstruction.value = 'add confetti';

    const deferred = createDeferred();
    env.fetchMock.enqueue(deferred.promise);

    const submitPromise = env.elements.modifyForm.dispatch('submit');
    await Promise.resolve();

    assert.equal(env.elements.revealButton.disabled, true);
    assert.equal(env.elements.revealButton.textContent, 'Generating...');
    assert.deepEqual(JSON.parse(env.fetchMock.calls[0].options.body), {
      data: {
        op: 'joke_image_modify',
        joke_id: 'joke-1',
        setup_instruction: 'make it sunnier',
        punchline_instruction: 'add confetti',
      },
    });

    deferred.resolve(createFetchResponse({
      json: {
        data: {
          joke_data: {
            key: 'joke-1',
            setup_text: 'Old setup',
            punchline_text: 'Old punchline',
            setup_image_url: 'https://example.com/setup-new.png',
            punchline_image_url: 'https://example.com/punchline-new.png',
            all_setup_image_urls: ['https://example.com/setup-new.png'],
            all_punchline_image_urls: ['https://example.com/punchline-new.png'],
          },
        },
      },
    }));

    await submitPromise;
    await new Promise((resolve) => setImmediate(resolve));

    assert.equal(env.elements.modifyModal.classList.contains('admin-modal--open'), false);
    assert.equal(env.elements.revealButton.disabled, false);
    assert.equal(env.elements.revealButton.textContent, 'Reveal Punchline');
    assert.equal(env.elements.setupMedia.querySelector('img').src, 'https://example.com/setup-new.png');
    assert.equal(env.elements.punchlineMedia.querySelector('img').src, 'https://example.com/punchline-new.png');
  } finally {
    env.cleanup();
  }
});

test('edit button populates modal and regenerate request refreshes the card', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });

    await env.document.dispatch('click', { target: env.elements.editButton });
    assert.equal(env.elements.editJokeId.value, 'joke-1');
    assert.equal(env.elements.editSetup.value, 'Old setup');
    assert.equal(env.elements.editPunchline.value, 'Old punchline');

    env.fetchMock.enqueue(createFetchResponse({
      json: {
        data: {
          joke_data: {
            key: 'joke-1',
            setup_text: 'Refreshed setup',
            punchline_text: 'Refreshed punchline',
            setup_image_url: 'https://example.com/setup-refreshed.png',
            punchline_image_url: 'https://example.com/punchline-refreshed.png',
            all_setup_image_urls: ['https://example.com/setup-refreshed.png'],
            all_punchline_image_urls: ['https://example.com/punchline-refreshed.png'],
          },
        },
      },
    }));

    await env.elements.editRegenerateButton.dispatch('click');
    await new Promise((resolve) => setImmediate(resolve));

    assert.deepEqual(JSON.parse(env.fetchMock.calls[0].options.body), {
      data: {
        joke_id: 'joke-1',
        setup_text: 'Old setup',
        punchline_text: 'Old punchline',
        seasonal: '',
        tags: '',
        setup_image_description: '',
        punchline_image_description: '',
        setup_image_url: 'https://example.com/setup-old.png',
        punchline_image_url: 'https://example.com/punchline-old.png',
        populate_images: true,
      },
    });
    assert.equal(env.elements.setupMedia.querySelector('img').src, 'https://example.com/setup-refreshed.png');
    assert.equal(env.elements.punchlineMedia.querySelector('img').src, 'https://example.com/punchline-refreshed.png');
  } finally {
    env.cleanup();
  }
});

test('regenerate button opens modal and stores joke id', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    await env.document.dispatch('click', { target: env.elements.regenerateButton });

    assert.equal(env.elements.regenerateJokeId.value, 'joke-1');
    assert.equal(env.elements.regenerateQuality.focused, true);
  } finally {
    env.cleanup();
  }
});
