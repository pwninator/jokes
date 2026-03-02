const assert = require('node:assert/strict');
const test = require('node:test');

const { FakeElement } = require('./test_utils.js');
const { applySelectionState } = require('./joke_picker.js');

function createCard(jokeId) {
  const card = new FakeElement();
  card.dataset = {
    jokeId,
    selectable: 'true',
  };
  return card;
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
