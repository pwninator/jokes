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
  buildRegenerateAllRequestData,
  buildStateRequestData,
  buildOptimisticPayload,
  formatThumbUrl,
  getReachableStateOptions,
  initJokeAdminActions,
  isFutureDailyPayload,
  parseEditPayload,
  updateCardFromPayload,
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
  const alerts = [];
  global.window = {
    __jokeAdminActionsInitialized: false,
    alert(message) {
      alerts.push(message);
    },
  };
  global.document = document;
  global.fetch = fetchMock;

  const editModalBundle = buildModalRoot('admin-edit-joke-modal', 'data-admin-edit-joke-backdrop');
  const regenerateAllModalBundle = buildModalRoot('admin-regenerate-all-modal', 'data-admin-regenerate-all-backdrop');
  const regenerateModalBundle = buildModalRoot('admin-regenerate-modal', 'data-admin-regenerate-backdrop');
  const modifyModalBundle = buildModalRoot('admin-modify-joke-modal', 'data-admin-modify-joke-backdrop');
  const stateModalBundle = buildModalRoot('admin-state-joke-modal', 'data-admin-state-joke-backdrop');
  const sceneIdeasModalBundle = buildModalRoot('admin-scene-ideas-modal', 'data-admin-scene-ideas-backdrop');

  append(root, editModalBundle.modal);
  append(root, regenerateAllModalBundle.modal);
  append(root, regenerateModalBundle.modal);
  append(root, modifyModalBundle.modal);
  append(root, stateModalBundle.modal);
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
  const editRegenerateAllButton = append(editModalBundle.modal, new FakeElement({ id: 'admin-edit-joke-regenerate-all-button', tagName: 'button' }));
  const editSceneIdeasButton = append(editForm, new FakeElement({ id: 'admin-edit-joke-scene-ideas-button', tagName: 'button' }));

  const regenerateAllForm = append(regenerateAllModalBundle.modal, new FakeElement({ id: 'admin-regenerate-all-form', tagName: 'form' }));
  append(regenerateAllForm, new FakeElement({ id: 'admin-regenerate-all-cancel-button', tagName: 'button' }));
  const regenerateAllSubmitButton = append(regenerateAllForm, new FakeElement({ id: 'admin-regenerate-all-submit-button', tagName: 'button' }));

  const regenerateJokeId = append(regenerateModalBundle.modal, new FakeElement({ id: 'admin-regenerate-joke-id', tagName: 'input' }));
  const regenerateModelButtonA = append(regenerateModalBundle.modal, new FakeElement({ tagName: 'button' }));
  regenerateModelButtonA.setAttribute('data-admin-regenerate-model-button', 'true');
  regenerateModelButtonA.setAttribute('data-image-quality', 'medium_mini');
  const regenerateModelButtonB = append(regenerateModalBundle.modal, new FakeElement({ tagName: 'button' }));
  regenerateModelButtonB.setAttribute('data-admin-regenerate-model-button', 'true');
  regenerateModelButtonB.setAttribute('data-image-quality', 'high');

  const modifyForm = append(modifyModalBundle.modal, new FakeElement({ id: 'admin-modify-joke-form', tagName: 'form' }));
  const modifyJokeId = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-id', tagName: 'input' }));
  const modifySetupInstruction = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-instruction', tagName: 'textarea' }));
  const modifyPunchlineInstruction = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-instruction', tagName: 'textarea' }));
  const modifySetupPreview = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-preview', tagName: 'img' }));
  const modifyPunchlinePreview = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-preview', tagName: 'img' }));
  const modifySetupPlaceholder = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-placeholder' }));
  const modifyPunchlinePlaceholder = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-placeholder' }));
  append(modifyForm, new FakeElement({ id: 'admin-modify-joke-cancel-button', tagName: 'button' }));

  const stateForm = append(stateModalBundle.modal, new FakeElement({ id: 'admin-state-joke-form', tagName: 'form' }));
  const stateJokeId = append(stateForm, new FakeElement({ id: 'admin-state-joke-id', tagName: 'input' }));
  const stateNewState = append(stateForm, new FakeElement({ id: 'admin-state-joke-new-state', tagName: 'input' }));
  const stateOptions = append(stateForm, new FakeElement({ id: 'admin-state-joke-options' }));
  append(stateForm, new FakeElement({ id: 'admin-state-joke-cancel-button', tagName: 'button' }));
  append(stateForm, new FakeElement({ id: 'admin-state-joke-submit-button', tagName: 'button' }));

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
    state: 'APPROVED',
    public_timestamp: null,
    setup_text: 'Old setup',
    punchline_text: 'Old punchline',
    setup_image_url: 'https://example.com/setup-old.png',
    punchline_image_url: 'https://example.com/punchline-old.png',
    setup_images: [{ url: 'https://example.com/setup-old.png', thumb_url: 'https://example.com/setup-thumb.png' }],
    punchline_images: [{ url: 'https://example.com/punchline-old.png', thumb_url: 'https://example.com/punch-thumb.png' }],
  };

  const editButton = append(card, new FakeElement({ className: 'joke-edit-button', tagName: 'button' }));
  editButton.setAttribute('data-joke-data', JSON.stringify(payload));

  const stateButton = append(card, new FakeElement({
    className: 'joke-state-badge joke-state-badge--button joke-state-approved',
    tagName: 'button',
  }));
  stateButton.setAttribute('data-joke-state-button', 'true');
  stateButton.setAttribute('data-joke-data', JSON.stringify(payload));
  stateButton.textContent = 'Approved';

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
    alerts,
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
      editRegenerateAllButton,
      editSceneIdeasButton,
      regenerateModal: regenerateModalBundle.modal,
      regenerateAllModal: regenerateAllModalBundle.modal,
      regenerateAllForm,
      regenerateAllSubmitButton,
      regenerateButton,
      regenerateJokeId,
      regenerateModelButtonA,
      regenerateModelButtonB,
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
      stateModal: stateModalBundle.modal,
      stateForm,
      stateButton,
      stateJokeId,
      stateNewState,
      stateOptions,
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

test('buildRegenerateAllRequestData sends text only when it changed', () => {
  assert.deepEqual(
    buildRegenerateAllRequestData(
      {
        jokeId: 'joke-1',
        setupText: 'Old setup',
        punchlineText: 'Old punchline',
      },
      {
        setup_text: ' Old setup ',
        punchline_text: 'Old punchline',
      },
    ),
    {
      joke_id: 'joke-1',
      regenerate_scene_ideas: true,
      generate_descriptions: true,
      populate_images: true,
    },
  );

  assert.deepEqual(
    buildRegenerateAllRequestData(
      {
        jokeId: 'joke-1',
        setupText: 'New setup',
        punchlineText: 'Old punchline',
      },
      {
        setup_text: 'Old setup',
        punchline_text: 'Old punchline',
      },
    ),
    {
      joke_id: 'joke-1',
      setup_text: 'New setup',
      regenerate_scene_ideas: true,
      generate_descriptions: true,
      populate_images: true,
    },
  );
});

test('buildStateRequestData builds the joke_state payload', () => {
  assert.deepEqual(buildStateRequestData('joke-1', 'PUBLISHED'), {
    op: 'joke_state',
    joke_id: 'joke-1',
    new_state: 'PUBLISHED',
  });
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

test('reachable state options exclude unknown draft and locked daily', () => {
  assert.deepEqual(getReachableStateOptions({ state: 'APPROVED' }), [
    'UNREVIEWED',
    'REJECTED',
    'PUBLISHED',
    'DAILY',
  ]);
  assert.equal(
    isFutureDailyPayload({ state: 'DAILY', public_timestamp: '2000-01-01T00:00:00Z' }),
    false,
  );
  assert.deepEqual(
    getReachableStateOptions({ state: 'DAILY', public_timestamp: '2000-01-01T00:00:00Z' }),
    [],
  );
  assert.deepEqual(getReachableStateOptions({ state: 'DRAFT' }), []);
  assert.deepEqual(getReachableStateOptions({ state: 'UNKNOWN' }), []);
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

test('state button opens modal with only reachable states', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    await env.document.dispatch('click', { target: env.elements.stateButton });

    assert.equal(env.elements.stateModal.classList.contains('admin-modal--open'), true);
    assert.equal(env.elements.stateJokeId.value, 'joke-1');
    assert.deepEqual(
      env.elements.stateOptions.children.map((child) => child.textContent),
      ['Unreviewed', 'Rejected', 'Published', 'Daily'],
    );
  } finally {
    env.cleanup();
  }
});

test('state button for draft still opens modal with empty options', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    env.elements.stateButton.setAttribute('data-joke-data', JSON.stringify({
      joke_id: 'joke-1',
      state: 'DRAFT',
      public_timestamp: null,
    }));
    env.elements.stateButton.textContent = 'Draft';

    await env.document.dispatch('click', { target: env.elements.stateButton });

    assert.equal(env.elements.stateModal.classList.contains('admin-modal--open'), true);
    assert.equal(env.elements.stateJokeId.value, 'joke-1');
    assert.equal(env.elements.stateOptions.children.length, 0);
  } finally {
    env.cleanup();
  }
});

test('state button for past daily still opens modal with empty options', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    env.elements.stateButton.setAttribute('data-joke-data', JSON.stringify({
      joke_id: 'joke-1',
      state: 'DAILY',
      public_timestamp: '2000-01-01T00:00:00Z',
    }));
    env.elements.stateButton.textContent = '2000-01-01';

    await env.document.dispatch('click', { target: env.elements.stateButton });

    assert.equal(env.elements.stateModal.classList.contains('admin-modal--open'), true);
    assert.equal(env.elements.stateJokeId.value, 'joke-1');
    assert.equal(env.elements.stateOptions.children.length, 0);
  } finally {
    env.cleanup();
  }
});

test('updateCardFromPayload keeps state badge interactive for non-mutable states', () => {
  const env = buildEnvironment();
  try {
    updateCardFromPayload(env.elements.card, {
      joke_id: 'joke-1',
      state: 'UNKNOWN',
      public_timestamp: null,
      setup_text: 'Setup text',
      punchline_text: 'Punchline text',
      setup_image_url: 'https://example.com/setup-unknown.png',
      punchline_image_url: 'https://example.com/punchline-unknown.png',
    });

    assert.equal(env.elements.stateButton.disabled, false);
    assert.equal(env.elements.stateButton.title, 'Change state');
    assert.equal(env.elements.stateButton.getAttribute('aria-label'), 'Change joke state');
  } finally {
    env.cleanup();
  }
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

test('state submit posts joke_state and updates the badge in place', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    const calendarSyncCalls = [];
    global.window.syncAdminJokesCalendarJokeState = (payload) => {
      calendarSyncCalls.push(payload);
    };
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    await env.document.dispatch('click', { target: env.elements.stateButton });
    await env.elements.stateOptions.children[2].dispatch('click');

    const deferred = createDeferred();
    env.fetchMock.enqueue(deferred.promise);

    const submitPromise = env.elements.stateForm.dispatch('submit');
    await Promise.resolve();

    assert.equal(env.elements.revealButton.disabled, true);
    assert.equal(env.elements.stateButton.textContent, 'Published');
    assert.deepEqual(JSON.parse(env.fetchMock.calls[0].options.body), {
      data: {
        op: 'joke_state',
        joke_id: 'joke-1',
        new_state: 'PUBLISHED',
      },
    });

    deferred.resolve(createFetchResponse({
      json: {
        data: {
          joke_data: {
            key: 'joke-1',
            state: 'DAILY',
            public_timestamp: '2099-03-05T00:00:00-08:00',
            is_public: false,
          },
        },
      },
    }));

    await submitPromise;
    await new Promise((resolve) => setImmediate(resolve));

    assert.equal(env.elements.stateModal.classList.contains('admin-modal--open'), false);
    assert.equal(env.elements.revealButton.disabled, false);
    assert.equal(env.elements.stateButton.textContent, '2099-03-05');
    assert.equal(env.elements.stateButton.classList.contains('joke-state-future-daily'), true);
    assert.equal(env.alerts.length, 0);
    assert.deepEqual(calendarSyncCalls, [{
      removeDate: null,
      addDate: '2099-03-05',
      entry: {
        joke_id: 'joke-1',
        setup_text: 'Old setup',
        thumbnail_url: 'https://example.com/setup-old.png',
      },
    }]);
  } finally {
    env.cleanup();
  }
});

test('regenerate all button opens confirmation modal from edit dialog', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });

    await env.document.dispatch('click', { target: env.elements.editButton });
    await env.elements.editRegenerateAllButton.dispatch('click');

    assert.equal(env.elements.regenerateAllModal.classList.contains('admin-modal--open'), true);
    assert.equal(env.elements.regenerateAllSubmitButton.focused, true);
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

test('regenerate all confirmation omits unchanged text fields and refreshes the card', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });

    await env.document.dispatch('click', { target: env.elements.editButton });
    await env.elements.editRegenerateAllButton.dispatch('click');

    env.fetchMock.enqueue(createFetchResponse({
      json: {
        data: {
          joke_data: {
            key: 'joke-1',
            setup_text: 'Old setup',
            punchline_text: 'Old punchline',
            setup_image_url: 'https://example.com/setup-all.png',
            punchline_image_url: 'https://example.com/punchline-all.png',
            all_setup_image_urls: ['https://example.com/setup-all.png'],
            all_punchline_image_urls: ['https://example.com/punchline-all.png'],
          },
        },
      },
    }));

    await env.elements.regenerateAllForm.dispatch('submit');
    await new Promise((resolve) => setImmediate(resolve));

    assert.deepEqual(JSON.parse(env.fetchMock.calls[0].options.body), {
      data: {
        joke_id: 'joke-1',
        regenerate_scene_ideas: true,
        generate_descriptions: true,
        populate_images: true,
      },
    });
    assert.equal(env.elements.regenerateModal.classList.contains('admin-modal--open'), false);
    assert.equal(env.elements.setupMedia.querySelector('img').src, 'https://example.com/setup-all.png');
    assert.equal(env.elements.punchlineMedia.querySelector('img').src, 'https://example.com/punchline-all.png');
  } finally {
    env.cleanup();
  }
});

test('regenerate all confirmation sends only changed text fields', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });

    await env.document.dispatch('click', { target: env.elements.editButton });
    env.elements.editSetup.value = 'Updated setup';
    await env.elements.editRegenerateAllButton.dispatch('click');

    env.fetchMock.enqueue(createFetchResponse({
      json: {
        data: {
          joke_data: {
            key: 'joke-1',
            setup_text: 'Updated setup',
            punchline_text: 'Old punchline',
          },
        },
      },
    }));

    await env.elements.regenerateAllForm.dispatch('submit');
    await new Promise((resolve) => setImmediate(resolve));

    assert.deepEqual(JSON.parse(env.fetchMock.calls[0].options.body), {
      data: {
        joke_id: 'joke-1',
        setup_text: 'Updated setup',
        regenerate_scene_ideas: true,
        generate_descriptions: true,
        populate_images: true,
      },
    });
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
    assert.equal(env.elements.regenerateModelButtonA.focused, true);
  } finally {
    env.cleanup();
  }
});

test('regenerate model button sends request immediately and closes modal', { concurrency: false }, async () => {
  const env = buildEnvironment();
  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    await env.document.dispatch('click', { target: env.elements.regenerateButton });

    env.fetchMock.enqueue(createFetchResponse({
      json: {
        data: {
          joke_data: {
            key: 'joke-1',
            setup_text: 'Old setup',
            punchline_text: 'Old punchline',
            setup_image_url: 'https://example.com/setup-regenerated.png',
            punchline_image_url: 'https://example.com/punchline-regenerated.png',
            all_setup_image_urls: ['https://example.com/setup-regenerated.png'],
            all_punchline_image_urls: ['https://example.com/punchline-regenerated.png'],
          },
        },
      },
    }));

    await env.document.dispatch('click', { target: env.elements.regenerateModelButtonB });
    await new Promise((resolve) => setImmediate(resolve));

    assert.deepEqual(JSON.parse(env.fetchMock.calls[0].options.body), {
      data: {
        joke_id: 'joke-1',
        image_quality: 'high',
        populate_images: true,
      },
    });
    assert.equal(env.elements.regenerateAllModal.classList.contains('admin-modal--open'), false);
    assert.equal(env.elements.setupMedia.querySelector('img').src, 'https://example.com/setup-regenerated.png');
    assert.equal(env.elements.punchlineMedia.querySelector('img').src, 'https://example.com/punchline-regenerated.png');
  } finally {
    env.cleanup();
  }
});
