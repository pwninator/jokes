const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

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

  toggle(token, force) {
    if (force === undefined) {
      if (this._tokens.has(token)) {
        this._tokens.delete(token);
        return false;
      }
      this._tokens.add(token);
      return true;
    }
    if (force) {
      this._tokens.add(token);
      return true;
    }
    this._tokens.delete(token);
    return false;
  }

  contains(token) {
    return this._tokens.has(token);
  }

  toString() {
    return Array.from(this._tokens).join(' ');
  }
}

class FakeElement {
  constructor({ id = '', className = '', tagName = 'div', parent = null } = {}) {
    this.id = id;
    this.tagName = String(tagName).toUpperCase();
    this.parentNode = parent;
    this.children = [];
    this.dataset = {};
    this.classList = new FakeClassList(className.split(/\s+/));
    this.attributes = new Map();
    this.listeners = new Map();
    this.hidden = false;
    this.textContent = '';
    this.value = '';
    this.min = '';
    this.max = '';
    this.clientWidth = 0;
    this.scrollWidth = 0;
    this.scrollLeft = 0;
    this.innerHTML = '';
    this._rect = {
      left: 0,
      width: 0,
    };
    this._scrollIntoViewCalls = [];
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  setAttribute(name, value) {
    const stringValue = String(value);
    this.attributes.set(name, stringValue);
    if (name === 'id') {
      this.id = stringValue;
      return;
    }
    if (name === 'class') {
      this.classList = new FakeClassList(stringValue.split(/\s+/));
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
    return this.attributes.get(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name.startsWith('data-')) {
      const dataKey = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      delete this.dataset[dataKey];
    }
  }

  addEventListener(type, listener) {
    const list = this.listeners.get(type) || [];
    list.push(listener);
    this.listeners.set(type, list);
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

  contains(node) {
    let current = node;
    while (current) {
      if (current === this) {
        return true;
      }
      current = current.parentNode || null;
    }
    return false;
  }

  closest(selector) {
    let current = this;
    while (current) {
      if (current.matches(selector)) {
        return current;
      }
      current = current.parentNode || null;
    }
    return null;
  }

  matches(selector) {
    if (selector === '.admin-jokes-calendar-day') {
      return this.classList.contains('admin-jokes-calendar-day');
    }
    if (selector === '.admin-jokes-calendar-day-button[draggable="true"]') {
      return this.classList.contains('admin-jokes-calendar-day-button')
        && this.getAttribute('draggable') === 'true';
    }
    return false;
  }

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  getBoundingClientRect() {
    return {
      left: this._rect.left,
      width: this._rect.width,
    };
  }

  setBoundingRect(rect) {
    this._rect = {
      ...this._rect,
      ...rect,
    };
  }

  scrollIntoView(options) {
    this._scrollIntoViewCalls.push(options);
  }
}

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
    return null;
  }

  querySelectorAll(selector) {
    if (selector === '.admin-jokes-calendar-month') {
      return this._monthCards.slice();
    }
    if (selector === '.admin-jokes-calendar-day--droppable') {
      return Array.from(this._registeredCells).filter((cell) =>
        cell.classList.contains('admin-jokes-calendar-day--droppable'));
    }
    return [];
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

function createDataTransfer() {
  const data = new Map();
  return {
    effectAllowed: '',
    dropEffect: '',
    setData(type, value) {
      data.set(type, value);
    },
    getData(type) {
      return data.get(type);
    },
  };
}

function createFetchMock(responses) {
  const queue = responses.slice();
  const calls = [];

  async function fetchMock(url, options = {}) {
    calls.push({
      url: String(url),
      options,
    });
    if (!queue.length) {
      throw new Error(`No mocked response remaining for ${url}`);
    }
    const next = queue.shift();
    const response = typeof next === 'function' ? next(url, options, calls) : next;
    return {
      ok: response.ok !== false,
      status: response.status || (response.ok === false ? 400 : 200),
      async json() {
        return response.json;
      },
    };
  }

  fetchMock.calls = calls;
  return fetchMock;
}

function createFixedDateClass(isoString) {
  const RealDate = Date;
  const fixedTime = new RealDate(isoString).getTime();
  return class FixedDate extends RealDate {
    constructor(...args) {
      if (args.length === 0) {
        super(fixedTime);
        return;
      }
      super(...args);
    }

    static now() {
      return fixedTime;
    }
  };
}

function buildEnvironment(fetchResponses, options = {}) {
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

  const elements = {
    'admin-jokes-calendar-toggle-button': toggleButton,
    'admin-jokes-calendar-panel': panel,
    'admin-jokes-calendar-month-picker': picker,
    'admin-jokes-calendar-error': errorBox,
    'admin-jokes-calendar-loading': loadingBox,
    'admin-jokes-calendar-scroll': scrollContainer,
    'admin-jokes-calendar-months': monthsContainer,
  };

  const fetchMock = createFetchMock(fetchResponses);
  const RealDate = global.Date;
  const FixedDate = createFixedDateClass(options.today || '2026-03-15T12:00:00Z');

  global.window = {
    __adminJokesCalendarInitialized: false,
    location: {
      origin: 'https://example.com',
    },
    requestAnimationFrame(callback) {
      callback();
      return 1;
    },
  };
  global.document = new FakeDocument(elements);
  global.fetch = fetchMock;
  global.Date = FixedDate;

  const modulePath = path.resolve(__dirname, 'admin_jokes_calendar.js');
  delete require.cache[require.resolve(modulePath)];
  const moduleExports = require(modulePath);

  function cleanup() {
    global.Date = RealDate;
    delete global.window;
    delete global.document;
    delete global.fetch;
    delete require.cache[require.resolve(modulePath)];
  }

  return {
    cleanup,
    elements,
    fetchMock,
    initAdminJokesCalendar: moduleExports.initAdminJokesCalendar,
    monthsContainer,
    scrollContainer,
  };
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

test('calendar opens lazily and fetches previous/current/next month only once', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2025-12'),
          buildMonth('2026-01'),
          buildMonth('2026-02'),
          buildMonth('2026-03', {
            '05': {
              joke_id: 'joke-1',
              setup_text: 'March joke',
              thumbnail_url: 'thumb.png',
            },
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
    },
  ]);

  try {
    env.initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');

    assert.equal(env.fetchMock.calls.length, 1);
    assert.match(env.fetchMock.calls[0].url, /start_month=2025-12/);
    assert.match(env.fetchMock.calls[0].url, /end_month=2026-06/);
    assert.equal(env.elements['admin-jokes-calendar-panel'].hidden, false);
    assert.equal(
      env.elements['admin-jokes-calendar-toggle-button'].getAttribute('aria-expanded'),
      'true',
    );
    assert.equal(env.elements['admin-jokes-calendar-month-picker'].min, '2026-01');
    assert.equal(env.elements['admin-jokes-calendar-month-picker'].max, '2027-03');
    assert.equal(env.elements['admin-jokes-calendar-month-picker'].value, '2026-03');
    assert.match(env.monthsContainer.innerHTML, /data-joke-id="joke-1"/);
    assert.doesNotMatch(env.monthsContainer.innerHTML, /March joke/);
    assert.match(
      env.monthsContainer.innerHTML,
      /admin-jokes-calendar-day admin-jokes-calendar-day--today" data-month-id="2026-03" data-day-key="15" data-date="2026-03-15"/,
    );

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');
    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');

    assert.equal(env.fetchMock.calls.length, 1);
  } finally {
    env.cleanup();
  }
});

test('month picker fetches surrounding months for unloaded targets', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-02'),
          buildMonth('2026-03'),
          buildMonth('2026-04'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
    {
      json: {
        months: [
          buildMonth('2026-05'),
          buildMonth('2026-06'),
          buildMonth('2026-07'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
  ]);

  try {
    env.initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');
    env.elements['admin-jokes-calendar-month-picker'].value = '2026-06';
    await env.elements['admin-jokes-calendar-month-picker'].dispatch('change');

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
        months: [
          buildMonth('2026-02'),
          buildMonth('2026-03'),
          buildMonth('2026-04'),
        ],
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
    env.initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');

    env.scrollContainer.scrollLeft = 50;
    await env.scrollContainer.dispatch('scroll');

    env.scrollContainer.scrollLeft = 850;
    env.scrollContainer.scrollWidth = 1600;
    env.scrollContainer.clientWidth = 600;
    await env.scrollContainer.dispatch('scroll');

    assert.equal(env.fetchMock.calls.length, 3);
    assert.match(env.fetchMock.calls[1].url, /start_month=2026-01/);
    assert.match(env.fetchMock.calls[2].url, /start_month=2026-05/);
  } finally {
    env.cleanup();
  }
});

test('successful drop posts move and keeps joke on target date optimistically', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-02'),
          buildMonth('2026-03', {
            '05': {
              joke_id: 'joke-1',
              setup_text: 'March joke',
              thumbnail_url: 'thumb.png',
            },
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
    env.initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');

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
      draggable: false,
    });
    const dataTransfer = createDataTransfer();

    await env.monthsContainer.dispatch('dragstart', {
      target: source.button,
      dataTransfer,
    });
    await env.monthsContainer.dispatch('drop', {
      target: target.cell,
      dataTransfer,
    });

    assert.equal(env.fetchMock.calls.length, 2);
    assert.equal(env.fetchMock.calls[1].options.method, 'POST');
    assert.deepEqual(JSON.parse(env.fetchMock.calls[1].options.body), {
      joke_id: 'joke-1',
      source_date: '2026-03-05',
      target_date: '2026-03-07',
    });

    const targetHtml = daySegment(env.monthsContainer.innerHTML, '2026-03-07');
    const sourceHtml = daySegment(env.monthsContainer.innerHTML, '2026-03-05');
    assert.match(targetHtml, /data-joke-id="joke-1"/);
    assert.doesNotMatch(sourceHtml, /data-joke-id="joke-1"/);
    assert.equal(env.elements['admin-jokes-calendar-error'].hidden, true);
  } finally {
    env.cleanup();
  }
});

test('drop on occupied date is rejected without posting', async () => {
  const env = buildEnvironment([
    {
      json: {
        months: [
          buildMonth('2026-02'),
          buildMonth('2026-03', {
            '05': {
              joke_id: 'joke-1',
              setup_text: 'March joke',
              thumbnail_url: 'thumb.png',
            },
            '07': {
              joke_id: 'joke-2',
              setup_text: 'Taken slot',
              thumbnail_url: 'taken.png',
            },
          }, ['05', '06', '07']),
          buildMonth('2026-04'),
        ],
        earliest_month_id: '2026-01',
        latest_month_id: '2027-03',
        initial_month_id: '2026-03',
      },
    },
  ]);

  try {
    env.initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');

    const source = createCell(env.monthsContainer, {
      monthId: '2026-03',
      dayKey: '05',
      date: '2026-03-05',
      draggable: true,
      jokeId: 'joke-1',
    });
    const occupied = createCell(env.monthsContainer, {
      monthId: '2026-03',
      dayKey: '07',
      date: '2026-03-07',
      draggable: false,
      jokeId: 'joke-2',
    });
    const dataTransfer = createDataTransfer();

    await env.monthsContainer.dispatch('dragstart', {
      target: source.button,
      dataTransfer,
    });
    await env.monthsContainer.dispatch('drop', {
      target: occupied.cell,
      dataTransfer,
    });

    assert.equal(env.fetchMock.calls.length, 1);
    const sourceHtml = daySegment(env.monthsContainer.innerHTML, '2026-03-05');
    assert.match(sourceHtml, /data-joke-id="joke-1"/);
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
            '05': {
              joke_id: 'joke-1',
              setup_text: 'March joke',
              thumbnail_url: 'thumb.png',
            },
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
      json: {
        error: 'Target date already has a scheduled joke',
      },
    },
  ]);

  try {
    env.initAdminJokesCalendar({
      calendarDataUrl: '/admin/jokes/calendar-data',
      calendarMoveUrl: '/admin/jokes/calendar-move',
    });

    await env.elements['admin-jokes-calendar-toggle-button'].dispatch('click');

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
      draggable: false,
    });
    const dataTransfer = createDataTransfer();

    await env.monthsContainer.dispatch('dragstart', {
      target: source.button,
      dataTransfer,
    });
    await env.monthsContainer.dispatch('drop', {
      target: target.cell,
      dataTransfer,
    });

    const targetHtml = daySegment(env.monthsContainer.innerHTML, '2026-03-07');
    const sourceHtml = daySegment(env.monthsContainer.innerHTML, '2026-03-05');
    assert.doesNotMatch(targetHtml, /data-joke-id="joke-1"/);
    assert.match(sourceHtml, /data-joke-id="joke-1"/);
    assert.equal(env.elements['admin-jokes-calendar-error'].hidden, false);
    assert.equal(
      env.elements['admin-jokes-calendar-error'].textContent,
      'Target date already has a scheduled joke',
    );
  } finally {
    env.cleanup();
  }
});
