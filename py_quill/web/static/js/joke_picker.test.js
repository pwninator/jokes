const assert = require('node:assert/strict');
const test = require('node:test');

const { FakeDocument, FakeElement, createFetchMock, createFetchResponse } = require('./test_utils.js');
const { JokePicker, applySelectionState } = require('./joke_picker.js');

function createCard(jokeId) {
  const card = new FakeElement();
  card.dataset = {
    jokeId,
    selectable: 'true',
  };
  return card;
}

function createPickerContainer() {
  const container = new FakeElement();
  const selectionRow = new FakeElement();
  selectionRow.dataset = { role: 'selection-row' };
  const categories = new FakeElement();
  categories.dataset = { role: 'categories' };
  const grid = new FakeElement();
  grid.dataset = { role: 'grid' };
  const loading = new FakeElement();
  loading.dataset = { role: 'loading' };
  const endMessage = new FakeElement();
  endMessage.dataset = { role: 'end-message' };
  container.appendChild(selectionRow);
  container.appendChild(categories);
  container.appendChild(grid);
  container.appendChild(loading);
  container.appendChild(endMessage);
  container.querySelector = (sel) => {
    if (sel === '[data-role="selection-row"]') return selectionRow;
    if (sel === '[data-role="categories"]') return categories;
    if (sel === '[data-role="grid"]') return grid;
    if (sel === '[data-role="loading"]') return loading;
    if (sel === '[data-role="end-message"]') return endMessage;
    return null;
  };
  return container;
}

test('applySelectionState marks selected cards', () => {
  const card = createCard('joke-1');
  applySelectionState(card, [{ id: 'joke-1' }]);

  assert.equal(card.classList.contains('joke-card--selected'), true);
  assert.equal(card.getAttribute('aria-selected'), 'true');
});

test('applySelectionState clears unselected cards', () => {
  const card = createCard('joke-2');
  card.classList.add('joke-card--selected');
  card.setAttribute('aria-selected', 'true');

  applySelectionState(card, [{ id: 'joke-1' }]);

  assert.equal(card.classList.contains('joke-card--selected'), false);
  assert.equal(card.getAttribute('aria-selected'), 'false');
});

test('applySelectionState ignores non-selectable cards', () => {
  const card = createCard('joke-3');
  card.dataset.selectable = 'false';

  applySelectionState(card, [{ id: 'joke-3' }]);

  assert.equal(card.classList.contains('joke-card--selected'), false);
  assert.equal(card.getAttribute('aria-selected'), null);
});

test('JokePicker sends without_social_post=true when excludeWithSocialPost is set', async () => {
  const doc = new FakeDocument();
  const container = createPickerContainer();
  container.id = 'test-picker';
  doc.body.appendChild(container);

  const fetchResponse = createFetchResponse({ html: '', cursor: null, has_more: false, categories: [] });
  const fetchMock = createFetchMock([fetchResponse, fetchResponse]);

  const savedDocument = global.document;
  const savedFetch = global.fetch;
  const savedWindow = global.window;
  const savedIntersectionObserver = global.IntersectionObserver;
  global.document = doc;
  global.fetch = fetchMock;
  global.window = { location: { origin: 'http://localhost' } };
  global.IntersectionObserver = class { observe() {} disconnect() {} };

  try {
    new JokePicker({
      container: '#test-picker',
      states: ['DAILY'],
      excludeWithSocialPost: true,
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
  } finally {
    global.document = savedDocument;
    global.fetch = savedFetch;
    global.window = savedWindow;
    global.IntersectionObserver = savedIntersectionObserver;
  }

  const pickerCall = fetchMock.calls.find((c) => c.url.includes('/admin/api/jokes/picker'));
  assert.ok(pickerCall, 'expected a picker fetch call');
  assert.ok(pickerCall.url.includes('without_social_post=true'), `expected without_social_post=true in URL, got: ${pickerCall.url}`);
});

test('JokePicker omits without_social_post when excludeWithSocialPost is false', async () => {
  const doc = new FakeDocument();
  const container = createPickerContainer();
  container.id = 'test-picker2';
  doc.body.appendChild(container);

  const fetchResponse = createFetchResponse({ html: '', cursor: null, has_more: false, categories: [] });
  const fetchMock = createFetchMock([fetchResponse, fetchResponse]);

  const savedDocument = global.document;
  const savedFetch = global.fetch;
  const savedWindow = global.window;
  const savedIntersectionObserver = global.IntersectionObserver;
  global.document = doc;
  global.fetch = fetchMock;
  global.window = { location: { origin: 'http://localhost' } };
  global.IntersectionObserver = class { observe() {} disconnect() {} };

  try {
    new JokePicker({
      container: '#test-picker2',
      states: ['DAILY'],
      excludeWithSocialPost: false,
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
  } finally {
    global.document = savedDocument;
    global.fetch = savedFetch;
    global.window = savedWindow;
    global.IntersectionObserver = savedIntersectionObserver;
  }

  const pickerCall = fetchMock.calls.find((c) => c.url.includes('/admin/api/jokes/picker'));
  assert.ok(pickerCall, 'expected a picker fetch call');
  assert.ok(!pickerCall.url.includes('without_social_post'), `expected no without_social_post in URL, got: ${pickerCall.url}`);
});

