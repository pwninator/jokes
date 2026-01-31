/* global initJokeViewer */
(function () {
  'use strict';

  function isJokeSelected(selectedJokes, jokeId) {
    if (!jokeId) {
      return false;
    }
    return selectedJokes.some((joke) => joke && joke.id === jokeId);
  }

  function applySelectionState(card, selectedJokes) {
    if (!card || !card.dataset || card.dataset.selectable !== 'true') {
      return;
    }
    const jokeId = card.dataset.jokeId;
    const isSelected = isJokeSelected(selectedJokes, jokeId);
    card.classList.toggle('joke-card--selected', isSelected);
    card.setAttribute('aria-selected', isSelected ? 'true' : 'false');
  }

  function JokePicker(options) {
    const config = options || {};
    this.container = document.querySelector(config.container || '');
    this.states = Array.isArray(config.states) ? config.states : [];
    this.publicOnly = Boolean(config.publicOnly);
    this.maxSelection = Number.isFinite(config.maxSelection)
      ? config.maxSelection
      : 5;
    this.onSelectionChange = typeof config.onSelectionChange === 'function'
      ? config.onSelectionChange
      : function () {};

    this.selectedJokes = [];
    this.currentCategory = null;
    this.cursor = null;
    this.hasMore = true;
    this.isLoading = false;
    this.observer = null;
    this.sentinel = null;

    this.selectionRow = null;
    this.categoriesContainer = null;
    this.grid = null;
    this.loadingIndicator = null;
    this.endMessage = null;

    this._init();
  }

  JokePicker.prototype._init = function () {
    if (!this.container) {
      return;
    }

    this.selectionRow = this.container.querySelector('[data-role="selection-row"]');
    this.categoriesContainer = this.container.querySelector('[data-role="categories"]');
    this.grid = this.container.querySelector('[data-role="grid"]');
    this.loadingIndicator = this.container.querySelector('[data-role="loading"]');
    this.endMessage = this.container.querySelector('[data-role="end-message"]');

    this._setupEvents();
    this._fetchCategories();
    this._resetAndLoad();
  };

  JokePicker.prototype._setupEvents = function () {
    if (this.grid) {
      this.grid.addEventListener('click', this._onGridClick.bind(this));
    }
  };

  JokePicker.prototype._onGridClick = function (event) {
    const mediaTarget = event.target.closest(
      '.joke-slide-media, .joke-slide-placeholder',
    );
    if (!mediaTarget) {
      return;
    }
    const card = event.target.closest('.joke-card[data-selectable="true"]');
    if (!card || !card.dataset.jokeId) {
      return;
    }

    const jokeId = card.dataset.jokeId;
    const existingIndex = this.selectedJokes.findIndex(
      (item) => item.id === jokeId,
    );
    if (existingIndex >= 0) {
      this.selectedJokes.splice(existingIndex, 1);
      card.classList.remove('joke-card--selected');
      card.setAttribute('aria-selected', 'false');
    } else {
      if (this.selectedJokes.length >= this.maxSelection) {
        window.alert('You can select up to 5 jokes.');
        return;
      }
      this.selectedJokes.push({
        id: jokeId,
        setupUrl: card.dataset.setupUrl || '',
      });
      card.classList.add('joke-card--selected');
      card.setAttribute('aria-selected', 'true');
    }

    this._renderSelectionRow();
    this.onSelectionChange(this.getSelectedJokes());
  };

  JokePicker.prototype._fetchCategories = function () {
    if (!this.categoriesContainer) {
      return;
    }

    fetch('/admin/api/jokes/categories', {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
    })
      .then((response) => response.json())
      .then((data) => {
        const categories = Array.isArray(data.categories) ? data.categories : [];
        this._renderCategories(categories);
      })
      .catch((error) => {
        console.error('Failed to load joke categories:', error);
      });
  };

  JokePicker.prototype._renderCategories = function (categories) {
    if (!this.categoriesContainer) {
      return;
    }
    this.categoriesContainer.innerHTML = '';

    const allButton = this._createCategoryChip('', 'All', !this.currentCategory);
    this.categoriesContainer.appendChild(allButton);

    categories.forEach((category) => {
      const label = `${category.display_name} (${category.public_joke_count || 0})`;
      const isSelected = Boolean(category.id) && category.id === this.currentCategory;
      const button = this._createCategoryChip(category.id, label, isSelected);
      this.categoriesContainer.appendChild(button);
    });
  };

  JokePicker.prototype._createCategoryChip = function (categoryId, label, isSelected) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'filter-chip text-button';
    if (isSelected) {
      button.classList.add('filter-chip--selected');
    }
    button.setAttribute('data-category', categoryId);
    button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
    button.textContent = label;
    button.addEventListener('click', () => {
      if (this.currentCategory === categoryId) {
        return;
      }
      this.currentCategory = categoryId || null;
      this._updateCategoryChipStates(button);
      this._resetAndLoad();
    });
    return button;
  };

  JokePicker.prototype._updateCategoryChipStates = function (selectedChip) {
    if (!this.categoriesContainer) {
      return;
    }
    const chips = Array.from(this.categoriesContainer.querySelectorAll('.filter-chip'));
    chips.forEach((chip) => {
      const isSelected = chip === selectedChip;
      chip.classList.toggle('filter-chip--selected', isSelected);
      chip.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
    });
  };

  JokePicker.prototype._resetAndLoad = function () {
    if (this.grid) {
      this.grid.innerHTML = '';
    }
    this.cursor = null;
    this.hasMore = true;
    this._toggleEndMessage(false);
    this._setupObserver();
    this._loadMore();
  };

  JokePicker.prototype._setupObserver = function () {
    if (!this.grid) {
      return;
    }
    if (this.sentinel && this.sentinel.parentNode) {
      this.sentinel.parentNode.removeChild(this.sentinel);
    }
    this.sentinel = document.createElement('div');
    this.sentinel.className = 'joke-picker__sentinel';
    this.sentinel.setAttribute('aria-hidden', 'true');
    this.grid.parentNode.insertBefore(this.sentinel, this.grid.nextSibling);

    if (this.observer) {
      try {
        this.observer.disconnect();
      } catch (e) {
        // Ignore.
      }
    }

    this.observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && this.hasMore && !this.isLoading) {
          this._loadMore();
        }
      });
    }, {
      rootMargin: '200px',
      threshold: 0,
    });

    this.observer.observe(this.sentinel);
  };

  JokePicker.prototype._loadMore = function () {
    if (this.isLoading || !this.hasMore) {
      return;
    }

    this.isLoading = true;
    this._toggleLoading(true);

    const url = new URL('/admin/api/jokes/picker', window.location.origin);
    url.searchParams.set('states', this.states.join(','));
    if (this.publicOnly) {
      url.searchParams.set('public_only', 'true');
    }
    if (this.currentCategory) {
      url.searchParams.set('category', this.currentCategory);
    }
    if (this.cursor) {
      url.searchParams.set('cursor', this.cursor);
    }

    fetch(url.toString(), {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
    })
      .then((response) => response.json())
      .then((data) => {
        if (data && data.html && this.grid) {
          const temp = document.createElement('div');
          temp.innerHTML = data.html;
          const cards = temp.querySelectorAll('.joke-card');
          cards.forEach((card) => {
            this.grid.appendChild(card);
            const viewer = card.querySelector('[data-joke-viewer]');
            if (viewer && typeof window.initJokeViewer === 'function') {
              window.initJokeViewer(viewer);
            }
            this._applySelectionState(card);
          });
        }

        this.cursor = data.cursor || null;
        this.hasMore = Boolean(data.has_more);
        if (!this.hasMore) {
          this._toggleEndMessage(true);
          if (this.observer && this.sentinel) {
            this.observer.unobserve(this.sentinel);
          }
        }
      })
      .catch((error) => {
        console.error('Failed to load jokes:', error);
      })
      .finally(() => {
        this.isLoading = false;
        this._toggleLoading(false);
      });
  };

  JokePicker.prototype._toggleLoading = function (isActive) {
    if (!this.loadingIndicator) {
      return;
    }
    this.loadingIndicator.classList.toggle('active', Boolean(isActive));
  };

  JokePicker.prototype._toggleEndMessage = function (isActive) {
    if (!this.endMessage) {
      return;
    }
    this.endMessage.classList.toggle('active', Boolean(isActive));
  };

  JokePicker.prototype._renderSelectionRow = function () {
    if (!this.selectionRow) {
      return;
    }
    this.selectionRow.innerHTML = '';
    this.selectedJokes.forEach((joke) => {
      const thumb = document.createElement('div');
      thumb.className = 'pin-selection-item';
      if (joke.setupUrl) {
        const img = document.createElement('img');
        img.src = joke.setupUrl;
        img.alt = 'Selected setup image';
        img.loading = 'lazy';
        thumb.appendChild(img);
      } else {
        thumb.textContent = 'No setup';
      }
      this.selectionRow.appendChild(thumb);
    });
  };

  JokePicker.prototype._applySelectionState = function (card) {
    applySelectionState(card, this.selectedJokes);
  };

  JokePicker.prototype._syncSelectionState = function () {
    if (!this.grid) {
      return;
    }
    const cards = this.grid.querySelectorAll('.joke-card[data-selectable="true"]');
    cards.forEach((card) => {
      this._applySelectionState(card);
    });
  };

  JokePicker.prototype._resetSelection = function () {
    this.selectedJokes = [];
    this._syncSelectionState();
    this._renderSelectionRow();
    this.onSelectionChange(this.getSelectedJokes());
  };

  JokePicker.prototype.getSelectedJokes = function () {
    return this.selectedJokes.slice();
  };

  JokePicker.prototype.clearSelection = function () {
    this._resetSelection();
  };

  if (typeof window !== 'undefined') {
    window.JokePicker = JokePicker;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      JokePicker: JokePicker,
      applySelectionState: applySelectionState,
    };
  }
})();
