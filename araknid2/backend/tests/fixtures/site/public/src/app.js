(() => {
  'use strict';

  // Ask the server for every item.
  async function loadItems() {
    const r = await fetch('/api/items', { cache: 'no-store' });
    return r.json();
  }

  async function api(path, options = {}) {
    return fetch(path, options);
  }

  async function save(id) {
    await api(`/api/items/${id}`, { method: 'PATCH' });
  }

  loadItems();
})();
