const assert = require('node:assert/strict');
const test = require('node:test');

const {
  FakeElement,
  append,
  createDataTransfer,
  createFetchMock,
  createFixedDateClass,
} = require('./test_utils.js');
const {
  addMonths,
  applyOptimisticMoveToMonths,
  buildMonthFetchPlan,
  findCenteredMonthId,
  initAdminJokesCalendar,
  revertOptimisticMoveInMonths,
} = require('./admin_jokes_calendar.js');

class FakeMonthCard extends FakeElement {
  constructor(monthId, offsetLeft) {
    super({ className: 'admin-jokes-calendar-month' });
    this.setAttribute('data-month-id', monthId);
    this.offsetLeft = offsetLeft;
    this.clientWidth = 320;
  }
}

class FakeMonthsContainer extends FakeElement {
  constructor() {
    super({ id: 'admin-jokes-calendar-months' });
    this._monthCards = [];
    this._registeredCells = new Set();
    this._innerHTML = '';
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this._monthCards = [];
    const seen = new Set();
    const regex = /<section class="admin-jokes-calendar-month" data-month-id="([^"]+)">/g;
    let match = regex.exec(this._innerHTML);
    let index = 0;
    while (match) {
      const monthId = match[1];
      if (!seen.has(monthId)) {
        seen.add(monthId);
        this._monthCards.push(new FakeMonthCard(monthId, index * 334));
        index += 1;
      }
      match = regex.exec(this._innerHTML);
    }
  }

  get innerHTML() {
    return this._innerHTML;
  }

  registerCell(cell) {
    this._registeredCells.add(cell);
  }

  querySelector(selector) {
    const monthMatch = selector.match(/^\[data-month-id="([^"]+)"\]$/);
    if (monthMatch) {
      return this._monthCards.find((card) => card.getAttribute('data-month-id') === monthMatch[1]) || null;
    }
    return super.querySelector(selector);
  }

  querySelectorAll(selector) {
    if (selector === '.admin-jokes-calendar-month') {
      return this._monthCards.slice();
    }
    if (selector === '.admin-jokes-calendar-day--droppable') {
      return Array.from(this._registeredCells).filter((cell) =>
        cell.classList.contains('admin-jokes-calendar-day--droppable'));
    }
    return super.querySelectorAll(selector);
  }
}

class FakeDocument {
  constructor(elements) {
    this._elements = elements;
  }

  getElementById(id) {
    return this._elements[id] || null;
  }
}

function buildMonth(monthId, entries = {}, movableDayKeys = []) {
  const [year, month] = monthId.split('-').map((value) => parseInt(value, 10));
  return {
    month_id: monthId,
    year,
    month,
    days_in_month: 31,
    first_weekday: 0,
    entries,
    movable_day_keys: movableDayKeys,
  };
}

function createCell(monthsContainer, { monthId, dayKey, date, draggable = false, jokeId = null }) {
  const cell = new FakeElement({ className: 'admin-jokes-calendar-day' });
  cell.setAttribute('data-month-id', monthId);
  cell.setAttribute('data-day-key', dayKey);
  cell.setAttribute('data-date', date);

  const button = new FakeElement({ className: 'admin-jokes-calendar-day-button', parent: cell });
  button.setAttribute('draggable', draggable ? 'true' : 'false');
  if (jokeId) {
    button.setAttribute('data-joke-id', jokeId);
  }
  cell.appendChild(button);
  monthsContainer.registerCell(cell);
  return { cell, button };
}

function daySegment(html, isoDate) {
  const token = `data-date="${isoDate}"`;
  const start = html.indexOf(token);
  if (start < 0) {
    return '';
  }
  const next = html.indexOf('data-date="', start + token.length);
  return html.slice(start, next >= 0 ? next : html.length);
}

function buildEnvironment(fetchResponses, options = {}) {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalFetch = global.fetch;
  const originalDate = global.Date;

  const toggleButton = new FakeElement({ id: 'admin-jokes-calendar-toggle-button' });
  const panel = new FakeElement({ id: 'admin-jokes-calendar-panel' });
  panel.hidden = true;
  const picker = new FakeElement({ id: 'admin-jokes-calendar-month-picker', tagName: 'input' });
  const errorBox = new FakeElement({ id: 'admin-jokes-calendar-error' });
  errorBox.hidden = true;
  const loadingBox = new FakeElement({ id: 'admin-jokes-calendar-loading' });
  loadingBox.hidden = true;
  const scrollContainer = new FakeElement({ id: 'admin-jokes-calendar-scroll' });
  scrollContainer.hidden = true;
  scrollContainer.clientWidth = options.clientWidth || 600;
  scrollContainer.scrollWidth = options.scrollWidth || 1200;
  scrollContainer.scrollLeft = options.scrollLeft || 0;
  scrollContainer.setBoundingRect({ left: 0, width: scrollContainer.clientWidth });
  const monthsContainer = new FakeMonthsContainer();

  global.window = {
    __adminJokesCalendarInitialized: false,
    location: { origin: 'https://example.com' },
    requestAnimationFrame(callback) {
      callback();
      return 1;
    },
  };
  global.document = new FakeDocument({
    'admin-jokes-calendar-toggle-button': toggleButton,
    'admin-jokes-calendar-panel': panel,
    'admin-jokes-calendar-month-picker': picker,
    'admin-jokes-calendar-error': errorBox,
    'admin-jokes-calendar-loading': loadingBox,
    'admin-jokes-calendar-scroll': scrollContainer,
    'admin-jokes-calendar-months': monthsContainer,
  });
  global.fetch = createFetchMock(fetchResponses);
  global.Date = createFixedDateClass(options.today || '2026-03-15T12:00:00Z');

  return {
    cleanup() {
      global.window = originalWindow;
      global.document = originalDocument;
      global.fetch = originalFetch;
      global.Date = originalDate;
    },
    elements: {
      toggleButton,
      panel,
      picker,
      errorBox,
      loadingBox,
    },
    fetchMock: global.fetch,
    monthsContainer,
    scrollContainer,
  };
}

test('addMonths crosses year boundaries', () => {
  assert.equal(addMonths('2026-01', -1), '2025-12');
  assert.equal(addMonths('2026-12', 1), '2027-01');
});

test('buildMonthFetchPlan skips loaded, loading, and out-of-bounds months', () => {
  const plan = buildMonthFetchPlan({
    bounds: {
      earliestMonthId: '2026-01',
      latestMonthId: '2026-05',
    },
    monthsById: new Map([['2026-02', buildMonth('2026-02')]]),
    loadingMonthIds: new Set(['2026-03']),
  }, '2025-12', '2026-05');

  assert.deepEqual(plan, ['2026-01', '2026-04', '2026-05']);
});

test('applyOptimisticMoveToMonths and revertOptimisticMoveInMonths update month maps', () => {
  const monthsById = new Map([
    ['2026-03', buildMonth('2026-03', {
      '05': { joke_id: 'joke-1' },
    }, ['05', '07'])],
  ]);

  const moveResult = applyOptimisticMoveToMonths(monthsById, '2026-03', '05', '2026-03', '07');
  assert.equal(moveResult.monthsById.get('2026-03').entries['05'], undefined);
  assert.deepEqual(moveResult.monthsById.get('2026-03').entries['07'], { joke_id: 'joke-1' });

  const reverted = revertOptimisticMoveInMonths(moveResult.monthsById, moveResult.snapshot);
  assert.deepEqual(reverted.get('2026-03').entries['05'], { joke_id: 'joke-1' });
  assert.equal(reverted.get('2026-03').entries['07'], undefined);
});

test('findCenteredMonthId picks the card closest to viewport center', () => {
  const cards = [
    new FakeMonthCard('2026-02', 0),
    new FakeMonthCard('2026-03', 334),
    new FakeMonthCard('2026-04', 668),
  ];
  assert.equal(findCenteredMonthId(cards, 300, 600), '2026-03');
});

test('calendar opens lazily and fetches the surrounding month window once', async () => {
  const env = buildEnvironment([{
    json: {
      months: [
        buildMonth('2025-12'),
        buildMonth('2026-01'),
        buildMonth('2026-02'),
        buildMonth('2026-03', {
          '05': { joke_id: 'joke-1', setup_text: 'March joke', thumbnail_url: 'thumb.png' },
        }, ['05', '06', '07']),
        buildMonth('2026-04'),
        buildMonth('2026-05'),
        buildMonth('2026-06'),
      ],
      earliest_month_id: '2026-01',
      latest_month_id: '2027-03',
      initial_month_id: '2026-03',
      today_iso_date: '2026-03-15',
    },
  }]);

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements.toggleButton.dispatch('click');
    assert.equal(env.fetchMock.calls.length, 1);
    assert.match(env.fetchMock.calls[0].url, /start_month=2025-12/);
    assert.match(env.fetchMock.calls[0].url, /end_month=2026-06/);
    assert.equal(env.elements.panel.hidden, false);
    assert.equal(env.elements.picker.value, '2026-03');

    await env.elements.toggleButton.dispatch('click');
    await env.elements.toggleButton.dispatch('click');
    assert.equal(env.fetchMock.calls.length, 1);
  } finally {
    env.cleanup();
  }
});

test('month picker fetches surrounding months for unloaded targets', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [buildMonth('2026-02'), buildMonth('2026-03'), buildMonth('2026-04')],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
    {
      json: {
        months: [buildMonth('2026-05'), buildMonth('2026-06'), buildMonth('2026-07')],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
  ]);

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });
    await env.elements.toggleButton.dispatch('click');
    env.elements.picker.value = '2026-06';
    await env.elements.picker.dispatch('change');

    assert.equal(env.fetchMock.calls.length, 2);
    assert.match(env.fetchMock.calls[1].url, /start_month=2026-05/);
    assert.match(env.fetchMock.calls[1].url, /end_month=2026-07/);
  } finally {
    env.cleanup();
  }
});

test('scrolling near left and right edges loads more months within bounds', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [buildMonth('2026-02'), buildMonth('2026-03'), buildMonth('2026-04')],
        earliest_month_id: '2026-01',
        latest_month_id: '2026-05',
        initial_month_id: '2026-03',
      },
    },
    {
      json: {
        months: [buildMonth('2026-01')],
        earliest_month_id: '2026-01',
        latest_month_id: '2026-05',
        initial_month_id: '2026-03',
      },
    },
    {
      json: {
        months: [buildMonth('2026-05')],
        earliest_month_id: '2026-01',
        latest_month_id: '2026-05',
        initial_month_id: '2026-03',
      },
    },
  ], {
    clientWidth: 600,
    scrollWidth: 1600,
  });

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });
    await env.elements.toggleButton.dispatch('click');

    env.scrollContainer.scrollLeft = 50;
    await env.scrollContainer.dispatch('scroll');
    env.scrollContainer.scrollLeft = 850;
    await env.scrollContainer.dispatch('scroll');

    assert.equal(env.fetchMock.calls.length, 3);
    assert.match(env.fetchMock.calls[1].url, /start_month=2026-01/);
    assert.match(env.fetchMock.calls[2].url, /start_month=2026-05/);
  } finally {
    env.cleanup();
  }
});

test('successful drop posts move and keeps the joke on the target date', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-02'),
          buildMonth('2026-03', {
            '05': { joke_id: 'joke-1', setup_text: 'March joke', thumbnail_url: 'thumb.png' },
          }, ['05', '06', '07']),
          buildMonth('2026-04'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
    {
      json: {
        joke_id: 'joke-1',
        source_date: '2026-03-05',
        target_date: '2026-03-07',
      },
    },
  ]);

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });
    await env.elements.toggleButton.dispatch('click');

    const source = createCell(env.monthsContainer, {
      monthId: '2026-03',
      dayKey: '05',
      date: '2026-03-05',
      draggable: true,
      jokeId: 'joke-1',
    });
    const target = createCell(env.monthsContainer, {
      monthId: '2026-03',
      dayKey: '07',
      date: '2026-03-07',
    });

    const dataTransfer = createDataTransfer();
    await env.monthsContainer.dispatch('dragstart', { target: source.button, dataTransfer });
    await env.monthsContainer.dispatch('drop', { target: target.cell, dataTransfer });

    assert.equal(env.fetchMock.calls.length, 2);
    assert.deepEqual(JSON.parse(env.fetchMock.calls[1].options.body), {
      joke_id: 'joke-1',
      source_date: '2026-03-05',
      target_date: '2026-03-07',
    });
    assert.match(daySegment(env.monthsContainer.innerHTML, '2026-03-07'), /data-joke-id="joke-1"/);
  } finally {
    env.cleanup();
  }
});

test('open calendar sync loads an unloaded month and adds a scheduled daily joke', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-03'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2026-05',
        initial_month_id: '2026-03',
      },
    },
    {
      json: {
        months: [
          buildMonth('2026-05'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2026-05',
        initial_month_id: '2026-03',
      },
    },
  ]);

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });
    await env.elements.toggleButton.dispatch('click');

    await global.window.syncAdminJokesCalendarJokeState({
      removeDate: null,
      addDate: '2026-05-07',
      entry: {
        joke_id: 'joke-2',
        setup_text: 'May joke',
        thumbnail_url: 'may-thumb.png',
      },
    });

    assert.equal(env.fetchMock.calls.length, 2);
    assert.match(env.fetchMock.calls[1].url, /start_month=2026-05/);
    assert.match(daySegment(env.monthsContainer.innerHTML, '2026-05-07'), /data-joke-id="joke-2"/);
  } finally {
    env.cleanup();
  }
});

test('open calendar sync removes a joke when it leaves the daily state', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-03', {
            '05': { joke_id: 'joke-1', setup_text: 'March joke', thumbnail_url: 'thumb.png' },
          }, ['05', '06', '07']),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2026-05',
        initial_month_id: '2026-03',
      },
    },
  ]);

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });
    await env.elements.toggleButton.dispatch('click');

    await global.window.syncAdminJokesCalendarJokeState({
      removeDate: '2026-03-05',
      addDate: null,
      entry: null,
    });

    assert.doesNotMatch(daySegment(env.monthsContainer.innerHTML, '2026-03-05'), /data-joke-id="joke-1"/);
  } finally {
    env.cleanup();
  }
});

test('failed move reverts optimistic UI and shows error message', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-02'),
          buildMonth('2026-03', {
            '05': { joke_id: 'joke-1', setup_text: 'March joke', thumbnail_url: 'thumb.png' },
          }, ['05', '06', '07']),
          buildMonth('2026-04'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
    {
      ok: false,
      status: 400,
      json: { error: 'Target date already has a scheduled joke' },
    },
  ]);

  try {
    initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });
    await env.elements.toggleButton.dispatch('click');

    const source = createCell(env.monthsContainer, {
      monthId: '2026-03',
      dayKey: '05',
      date: '2026-03-05',
      draggable: true,
      jokeId: 'joke-1',
    });
    const target = createCell(env.monthsContainer, {
      monthId: '2026-03',
      dayKey: '07',
      date: '2026-03-07',
    });

    const dataTransfer = createDataTransfer();
    await env.monthsContainer.dispatch('dragstart', { target: source.button, dataTransfer });
    await env.monthsContainer.dispatch('drop', { target: target.cell, dataTransfer });

    assert.doesNotMatch(daySegment(env.monthsContainer.innerHTML, '2026-03-07'), /data-joke-id="joke-1"/);
    assert.match(daySegment(env.monthsContainer.innerHTML, '2026-03-05'), /data-joke-id="joke-1"/);
    assert.equal(env.elements.errorBox.hidden, false);
    assert.equal(env.elements.errorBox.textContent, 'Target date already has a scheduled joke');
  } finally {
    env.cleanup();
  }
});
