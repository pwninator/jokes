const assert = require('node:assert/strict');
const test = require('node:test');

global.window = {};

const { applySelectionState } = require('./joke_picker.js');

function createClassList() {
  const classes = new Set();
  return {
    add: (name) => classes.add(name),
    remove: (name) => classes.delete(name),
    toggle: (name, force) => {
      if (force) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
    },
    contains: (name) => classes.has(name),
  };
}

function createCard(jokeId) {
  return {
    dataset: {
      jokeId: jokeId,
      selectable: 'true',
    },
    classList: createClassList(),
    attributes: {},
    setAttribute: function (name, value) {
      this.attributes[name] = value;
    },
    getAttribute: function (name) {
      return this.attributes[name];
    },
  };
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
  assert.equal(card.getAttribute('aria-selected'), undefined);
});
