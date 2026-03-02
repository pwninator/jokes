const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

class FakeClassList {
  constructor(initialTokens = []) {
    this._tokens = new Set(initialTokens.filter(Boolean));
  }

  add(...tokens) {
    tokens.forEach((token) => this._tokens.add(token));
  }

  remove(...tokens) {
    tokens.forEach((token) => this._tokens.delete(token));
  }

  contains(token) {
    return this._tokens.has(token);
  }

  toString() {
    return Array.from(this._tokens).join(' ');
  }
}

class FakeStyle {
  constructor() {
    this._values = new Map();
  }

  setProperty(name, value) {
    this._values.set(name, String(value));
  }

  getPropertyValue(name) {
    return this._values.get(name) || '';
  }
}

class FakeElement {
  constructor({ id = '', className = '', tagName = 'div', parent = null } = {}) {
    this.id = id;
    this.tagName = String(tagName).toUpperCase();
    this.nodeType = 1;
    this.parentNode = parent;
    this.parentElement = parent;
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.classList = new FakeClassList(className.split(/\s+/));
    this.listeners = new Map();
    this.style = new FakeStyle();
    this.value = '';
    this.textContent = '';
    this.disabled = false;
    this.hidden = false;
    this.src = '';
    this.alt = '';
    this.width = 0;
    this.height = 0;
    this.loading = '';
    this.type = '';
    this.focused = false;
    this._innerHTML = '';
  }

  get className() {
    return this.classList.toString();
  }

  set className(value) {
    this.classList = new FakeClassList(String(value).split(/\s+/));
    this.attributes.set('class', this.classList.toString());
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this.children = [];
  }

  appendChild(child) {
    child.parentNode = this;
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === 'src') {
      this.src = '';
    }
    if (name.startsWith('data-')) {
      const dataKey = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      delete this.dataset[dataKey];
    }
  }

  setAttribute(name, value) {
    const stringValue = String(value);
    this.attributes.set(name, stringValue);
    if (name === 'id') {
      this.id = stringValue;
      return;
    }
    if (name === 'class') {
      this.className = stringValue;
      return;
    }
    if (name === 'src') {
      this.src = stringValue;
      return;
    }
    if (name === 'alt') {
      this.alt = stringValue;
      return;
    }
    if (name === 'width') {
      this.width = Number(stringValue);
      return;
    }
    if (name === 'height') {
      this.height = Number(stringValue);
      return;
    }
    if (name.startsWith('data-')) {
      const dataKey = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      this.dataset[dataKey] = stringValue;
    }
  }

  getAttribute(name) {
    if (name === 'class') {
      return this.classList.toString();
    }
    if (name === 'src') {
      return this.src || null;
    }
    if (name === 'alt') {
      return this.alt || null;
    }
    return this.attributes.get(name) || null;
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type, event = {}) {
    const listeners = this.listeners.get(type) || [];
    const actualEvent = {
      target: this,
      currentTarget: this,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...event,
    };
    for (const listener of listeners) {
      // eslint-disable-next-line no-await-in-loop
      await listener(actualEvent);
    }
    return actualEvent;
  }

  focus() {
    this.focused = true;
  }

  checkValidity() {
    return true;
  }

  reportValidity() {
    return true;
  }

  closest(selector) {
    let current = this;
    while (current) {
      if (current.matches(selector)) {
        return current;
      }
      current = current.parentElement || null;
    }
    return null;
  }

  matches(selector) {
    const tagOnlyMatch = selector.match(/^[a-zA-Z]+$/);
    if (tagOnlyMatch) {
      return this.tagName === tagOnlyMatch[0].toUpperCase();
    }

    const classAttrMatch = selector.match(/^\.([a-zA-Z0-9_-]+)(\[.+\])?$/);
    if (classAttrMatch) {
      if (!this.classList.contains(classAttrMatch[1])) {
        return false;
      }
      return this._matchesAttributeSelector(classAttrMatch[2] || '');
    }

    const tagAttrMatch = selector.match(/^([a-zA-Z]+)(\[.+\])$/);
    if (tagAttrMatch) {
      if (this.tagName !== tagAttrMatch[1].toUpperCase()) {
        return false;
      }
      return this._matchesAttributeSelector(tagAttrMatch[2]);
    }

    if (selector.startsWith('[') && selector.endsWith(']')) {
      return this._matchesAttributeSelector(selector);
    }

    return false;
  }

  _matchesAttributeSelector(selector) {
    if (!selector) {
      return true;
    }

    const exactMatch = selector.match(/^\[([^=\]]+)="([^"]*)"\]$/);
    if (exactMatch) {
      const [, attrName, expected] = exactMatch;
      return (this.getAttribute(attrName) || '') === expected;
    }

    const suffixMatch = selector.match(/^\[([^=\]]+)\$="([^"]*)"\]$/);
    if (suffixMatch) {
      const [, attrName, expectedSuffix] = suffixMatch;
      return (this.getAttribute(attrName) || '').endsWith(expectedSuffix);
    }

    const presenceMatch = selector.match(/^\[([^=\]]+)\]$/);
    if (presenceMatch) {
      return this.getAttribute(presenceMatch[1]) !== null;
    }

    return false;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    if (selector.includes(' ')) {
      const [ancestorSelector, descendantSelector] = selector.split(/\s+(.+)/);
      const results = [];
      const ancestors = this.querySelectorAll(ancestorSelector);
      ancestors.forEach((ancestor) => {
        results.push(...ancestor.querySelectorAll(descendantSelector));
      });
      return results;
    }

    const results = [];
    this._collectDescendants((element) => element.matches(selector), results);
    return results;
  }

  _collectDescendants(predicate, results) {
    this.children.forEach((child) => {
      if (predicate(child)) {
        results.push(child);
      }
      child._collectDescendants(predicate, results);
    });
  }
}

class FakeDocument {
  constructor(root) {
    this.body = root;
    this.listeners = new Map();
  }

  getElementById(id) {
    return this._findElement((element) => element.id === id);
  }

  querySelector(selector) {
    return this.body.querySelector(selector);
  }

  querySelectorAll(selector) {
    return this.body.querySelectorAll(selector);
  }

  createElement(tagName) {
    return new FakeElement({ tagName });
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type, event = {}) {
    const listeners = this.listeners.get(type) || [];
    const actualEvent = {
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...event,
    };
    for (const listener of listeners) {
      // eslint-disable-next-line no-await-in-loop
      await listener(actualEvent);
    }
    return actualEvent;
  }

  _findElement(predicate) {
    const queue = [...this.body.children];
    while (queue.length) {
      const current = queue.shift();
      if (predicate(current)) {
        return current;
      }
      queue.push(...current.children);
    }
    return null;
  }
}

function createFetchResponse({ ok = true, status = 200, json = {} }) {
  return {
    ok,
    status,
    async json() {
      return json;
    },
  };
}

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function createFetchMock() {
  const calls = [];
  const queue = [];

  async function fetchMock(url, options = {}) {
    calls.push({ url: String(url), options });
    if (!queue.length) {
      throw new Error(`No mocked fetch response for ${url}`);
    }
    const next = queue.shift();
    if (next && typeof next.then === 'function') {
      return next;
    }
    return next;
  }

  fetchMock.calls = calls;
  fetchMock.enqueue = (response) => {
    queue.push(response);
  };
  return fetchMock;
}

function append(parent, child) {
  parent.appendChild(child);
  return child;
}

function buildModalRoot(id, backdropAttr) {
  const modal = new FakeElement({ id, className: 'admin-modal' });
  modal.setAttribute('aria-hidden', 'true');
  const backdrop = append(modal, new FakeElement({ className: 'admin-modal__backdrop' }));
  backdrop.setAttribute(backdropAttr, '');
  append(modal, new FakeElement({ className: 'admin-modal__dialog' }));
  return { modal, backdrop };
}

function buildEnvironment() {
  const root = new FakeElement({ tagName: 'body' });
  const document = new FakeDocument(root);
  const fetchMock = createFetchMock();

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
  const editCancelButton = append(editForm, new FakeElement({ id: 'admin-edit-joke-cancel-button', tagName: 'button' }));
  const editRegenerateButton = append(editForm, new FakeElement({ id: 'admin-edit-joke-regenerate-button', tagName: 'button' }));
  const editSceneIdeasButton = append(editForm, new FakeElement({ id: 'admin-edit-joke-scene-ideas-button', tagName: 'button' }));

  const regenerateForm = append(regenerateModalBundle.modal, new FakeElement({ id: 'admin-regenerate-form', tagName: 'form' }));
  const regenerateJokeId = append(regenerateForm, new FakeElement({ id: 'admin-regenerate-joke-id', tagName: 'input' }));
  const regenerateQuality = append(regenerateForm, new FakeElement({ id: 'admin-regenerate-quality', tagName: 'select' }));
  const regenerateCancelButton = append(regenerateForm, new FakeElement({ id: 'admin-regenerate-cancel-button', tagName: 'button' }));

  const modifyForm = append(modifyModalBundle.modal, new FakeElement({ id: 'admin-modify-joke-form', tagName: 'form' }));
  const modifyJokeId = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-id', tagName: 'input' }));
  const modifySetupInstruction = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-instruction', tagName: 'textarea' }));
  const modifyPunchlineInstruction = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-instruction', tagName: 'textarea' }));
  const modifySetupPreview = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-preview', tagName: 'img' }));
  const modifyPunchlinePreview = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-preview', tagName: 'img' }));
  const modifySetupPlaceholder = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-setup-placeholder' }));
  const modifyPunchlinePlaceholder = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-punchline-placeholder' }));
  const modifyCancelButton = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-cancel-button', tagName: 'button' }));
  const modifySubmitButton = append(modifyForm, new FakeElement({ id: 'admin-modify-joke-submit-button', tagName: 'button' }));

  const sceneIdeasForm = append(sceneIdeasModalBundle.modal, new FakeElement({ id: 'admin-scene-ideas-form', tagName: 'form' }));
  const sceneIdeasSetup = append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-setup', tagName: 'textarea' }));
  const sceneIdeasPunchline = append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-punchline', tagName: 'textarea' }));
  const sceneIdeasCancelButton = append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-cancel-button', tagName: 'button' }));
  const sceneIdeasGenerateButton = append(sceneIdeasForm, new FakeElement({ id: 'admin-scene-ideas-generate-button', tagName: 'button' }));

  const card = append(root, new FakeElement({ className: 'joke-card', tagName: 'article' }));
  card.setAttribute('data-joke-id', 'joke-1');
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

  const editPayload = {
    joke_id: 'joke-1',
    setup_text: 'Old setup',
    punchline_text: 'Old punchline',
    setup_image_url: 'https://example.com/setup-old.png',
    punchline_image_url: 'https://example.com/punchline-old.png',
    setup_images: [{ url: 'https://example.com/setup-old.png', thumb_url: 'https://example.com/setup-thumb.png' }],
    punchline_images: [{ url: 'https://example.com/punchline-old.png', thumb_url: 'https://example.com/punch-thumb.png' }],
  };

  const editButton = append(card, new FakeElement({ className: 'joke-edit-button', tagName: 'button' }));
  editButton.setAttribute('data-joke-data', JSON.stringify(editPayload));

  const modifyButton = append(card, new FakeElement({ className: 'joke-modify-button', tagName: 'button' }));
  modifyButton.setAttribute('data-joke-data', JSON.stringify(editPayload));
  modifyButton.setAttribute('data-joke-id', 'joke-1');
  const modifyIcon = append(modifyButton, new FakeElement({ tagName: 'span' }));
  modifyIcon.textContent = '🎨';

  const modulePath = path.resolve(__dirname, 'joke_admin_actions.js');
  const context = {
    Node: { ELEMENT_NODE: 1 },
    window: { __jokeAdminActionsInitialized: false },
    document,
    fetch: fetchMock,
    console,
  };
  context.globalThis = context;
  vm.runInNewContext(fs.readFileSync(modulePath, 'utf8'), context, {
    filename: modulePath,
  });

  return {
    cleanup() {
      context.window.__jokeAdminActionsInitialized = false;
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
      editCancelButton,
      editRegenerateButton,
      editSceneIdeasButton,
      regenerateForm,
      regenerateJokeId,
      regenerateQuality,
      regenerateCancelButton,
      modifyModal: modifyModalBundle.modal,
      modifyForm,
      modifyButton,
      modifyIcon,
      modifyJokeId,
      modifySetupInstruction,
      modifyPunchlineInstruction,
      modifySetupPreview,
      modifyPunchlinePreview,
      modifySetupPlaceholder,
      modifyPunchlinePlaceholder,
      modifyCancelButton,
      modifySubmitButton,
      sceneIdeasForm,
      sceneIdeasSetup,
      sceneIdeasPunchline,
      sceneIdeasCancelButton,
      sceneIdeasGenerateButton,
      revealButton,
      setupMedia,
      punchlineMedia,
    },
    initJokeAdminActions: context.window.initJokeAdminActions,
  };
}

test('modify button opens modal from a non-element click target and populates preview state', { concurrency: false }, async () => {
  const env = buildEnvironment();
  const { cleanup, elements, initJokeAdminActions } = env;

  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });

    const textNodeTarget = {
      nodeType: 3,
      parentElement: elements.modifyIcon,
    };

    await env.document.dispatch('click', { target: textNodeTarget });

    assert.equal(elements.modifyModal.classList.contains('admin-modal--open'), true);
    assert.equal(elements.modifyModal.getAttribute('aria-hidden'), 'false');
    assert.equal(elements.modifyJokeId.value, 'joke-1');
    assert.equal(elements.modifySetupInstruction.value, '');
    assert.equal(elements.modifyPunchlineInstruction.value, '');
    assert.equal(elements.modifySetupPreview.src, 'https://example.com/setup-old.png');
    assert.equal(elements.modifyPunchlinePreview.src, 'https://example.com/punchline-old.png');
    assert.equal(elements.modifySetupPreview.classList.contains('is-visible'), true);
    assert.equal(elements.modifyPunchlinePreview.classList.contains('is-visible'), true);
    assert.equal(elements.modifySetupPlaceholder.classList.contains('is-hidden'), true);
    assert.equal(elements.modifyPunchlinePlaceholder.classList.contains('is-hidden'), true);
  } finally {
    cleanup();
  }
});

test('modify submit posts joke_image_modify and updates the card in place', { concurrency: false }, async () => {
  const env = buildEnvironment();
  const { cleanup, elements, fetchMock, initJokeAdminActions } = env;

  try {
    initJokeAdminActions({ jokeCreationUrl: 'https://example.com/joke_creation_process' });
    await env.document.dispatch('click', { target: elements.modifyIcon });

    elements.modifySetupInstruction.value = 'make it sunnier';
    elements.modifyPunchlineInstruction.value = 'add confetti';

    const deferred = createDeferred();
    fetchMock.enqueue(deferred.promise);

    const submitPromise = elements.modifyForm.dispatch('submit');
    await Promise.resolve();

    assert.equal(elements.revealButton.disabled, true);
    assert.equal(elements.revealButton.textContent, 'Generating...');

    const requestBody = JSON.parse(fetchMock.calls[0].options.body);
    assert.deepEqual(requestBody, {
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

    assert.equal(elements.modifyModal.classList.contains('admin-modal--open'), false);
    assert.equal(elements.modifyModal.getAttribute('aria-hidden'), 'true');
    assert.equal(elements.revealButton.disabled, false);
    assert.equal(elements.revealButton.textContent, 'Reveal Punchline');

    const updatedSetupImage = elements.setupMedia.querySelector('img');
    const updatedPunchlineImage = elements.punchlineMedia.querySelector('img');
    assert.equal(updatedSetupImage.src, 'https://example.com/setup-new.png');
    assert.equal(updatedPunchlineImage.src, 'https://example.com/punchline-new.png');

    const updatedPayload = JSON.parse(elements.editButton.getAttribute('data-joke-data'));
    assert.equal(updatedPayload.setup_image_url, 'https://example.com/setup-new.png');
    assert.equal(updatedPayload.punchline_image_url, 'https://example.com/punchline-new.png');
  } finally {
    cleanup();
  }
});
