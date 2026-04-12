(function () {
  const STORAGE_KEY = 'seepoDraftFormQueueV1';

  function getCsrfToken() {
    const cookieName = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];

    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(cookieName)) {
        return decodeURIComponent(cookie.slice(cookieName.length));
      }
    }

    return '';
  }

  function showToast(message) {
    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
      window.seepoOfflineSync.showToast(message);
      return;
    }

    alert(message);
  }

  function getQueue() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return [];
      }

      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  function setQueue(queue) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  }

  function serializeFormEntries(form) {
    const formData = new FormData(form);
    const entries = [];

    formData.forEach(function (value, key) {
      if (key === 'csrfmiddlewaretoken') {
        return;
      }

      entries.push({
        key: key,
        value: String(value),
      });
    });

    return entries;
  }

  function queueSubmission(form) {
    const method = (form.getAttribute('method') || 'POST').toUpperCase();
    const action = form.getAttribute('action') || window.location.pathname;
    const label = (form.getAttribute('data-offline-draft-label') || 'draft').trim().toLowerCase();
    const customKey = (form.getAttribute('data-offline-draft-key') || '').trim();
    const dedupeKey = customKey || method + ':' + action;
    const entries = serializeFormEntries(form);

    const queue = getQueue();
    const payload = {
      id: Date.now() + '-' + Math.random().toString(36).slice(2, 8),
      method: method,
      action: action,
      label: label,
      dedupeKey: dedupeKey,
      entries: entries,
      createdAt: new Date().toISOString(),
    };

    const existingIndex = queue.findIndex(function (item) {
      return item.dedupeKey === dedupeKey;
    });

    if (existingIndex >= 0) {
      queue[existingIndex] = payload;
    } else {
      queue.push(payload);
    }

    setQueue(queue);
    window.dispatchEvent(new CustomEvent('seepo:draft-queue-updated', { detail: { pending: queue.length } }));
    return payload;
  }

  async function syncNow() {
    if (!navigator.onLine) {
      return { synced: 0, remaining: getQueue().length };
    }

    const queue = getQueue();
    if (!queue.length) {
      return { synced: 0, remaining: 0 };
    }

    const remaining = [];
    let synced = 0;

    for (const item of queue) {
      try {
        const params = new URLSearchParams();
        item.entries.forEach(function (entry) {
          params.append(entry.key, entry.value);
        });

        const csrfToken = getCsrfToken();
        if (csrfToken) {
          params.set('csrfmiddlewaretoken', csrfToken);
        }

        const response = await fetch(item.action, {
          method: item.method || 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'X-CSRFToken': csrfToken,
          },
          body: params.toString(),
        });

        if (!response.ok || !response.redirected) {
          remaining.push(item);
          continue;
        }

        synced += 1;
      } catch (error) {
        console.error('Draft queue sync failed:', error);
        remaining.push(item);
      }
    }

    setQueue(remaining);
    window.dispatchEvent(new CustomEvent('seepo:draft-queue-updated', { detail: { pending: remaining.length } }));

    if (synced > 0) {
      showToast('Synced ' + synced + ' queued form draft' + (synced === 1 ? '' : 's') + '.');
    }

    return { synced: synced, remaining: remaining.length };
  }

  function onDraftSubmit(event) {
    const form = event.currentTarget;

    if (navigator.onLine) {
      return;
    }

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    event.preventDefault();
    queueSubmission(form);

    const message =
      form.getAttribute('data-offline-draft-message') ||
      'Saved offline as a draft. It will sync when online.';
    showToast(message);

    const redirectUrl = form.getAttribute('data-offline-redirect-url');
    if (redirectUrl) {
      window.location.href = redirectUrl;
    }
  }

  function bindDraftForms() {
    const forms = document.querySelectorAll('form[data-offline-draft-form="true"]');
    forms.forEach(function (form) {
      form.addEventListener('submit', onDraftSubmit);
    });
  }

  window.seepoOfflineDraftQueue = {
    getQueue: getQueue,
    pendingCount: function () {
      return getQueue().length;
    },
    syncNow: syncNow,
    clear: function () {
      setQueue([]);
      window.dispatchEvent(new CustomEvent('seepo:draft-queue-updated', { detail: { pending: 0 } }));
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    bindDraftForms();
    if (navigator.onLine) {
      syncNow();
    }
  });

  window.addEventListener('online', function () {
    syncNow();
  });
})();
