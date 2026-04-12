(function () {
  const STORAGE_KEY = 'seepoDiaryPendingUpdatesV1';

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

    console.info('[Diary Offline]', message);
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

  function normalizeUpdate(update) {
    const diaryId = parseInt(update && update.diaryId, 10);
    const field = String((update && update.field) || '').trim().toLowerCase();

    if (!diaryId || !field) {
      return null;
    }

    return {
      diaryId: diaryId,
      field: field,
      value: String((update && update.value) || ''),
      updatedAt: new Date().toISOString(),
    };
  }

  function queueUpdate(update) {
    const normalized = normalizeUpdate(update);
    if (!normalized) {
      return false;
    }

    const queue = getQueue();
    const existingIndex = queue.findIndex(function (item) {
      return item.diaryId === normalized.diaryId && item.field === normalized.field;
    });

    if (existingIndex >= 0) {
      queue[existingIndex] = normalized;
    } else {
      queue.push(normalized);
    }

    setQueue(queue);
    return true;
  }

  async function pushUpdate(item) {
    const response = await fetch('/groups/api/diary/' + item.diaryId + '/update/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        field: item.field,
        value: item.value,
      }),
      credentials: 'same-origin',
    });

    if (!response.ok) {
      throw new Error('HTTP ' + response.status);
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(data.error || 'Diary update failed.');
    }
  }

  async function syncNow() {
    if (!navigator.onLine) {
      return {
        synced: 0,
        remaining: getQueue().length,
      };
    }

    const queue = getQueue();
    if (!queue.length) {
      return {
        synced: 0,
        remaining: 0,
      };
    }

    const remaining = [];
    let synced = 0;

    for (const item of queue) {
      try {
        await pushUpdate(item);
        synced += 1;
      } catch (error) {
        console.error('Diary queued update failed:', error);
        remaining.push(item);
      }
    }

    setQueue(remaining);

    if (synced > 0) {
      showToast('Synced ' + synced + ' offline diary change' + (synced === 1 ? '' : 's') + '.');
    }

    return {
      synced: synced,
      remaining: remaining.length,
    };
  }

  window.seepoOfflineDiary = {
    getQueue: getQueue,
    queueUpdate: queueUpdate,
    syncNow: syncNow,
    pendingCount: function () {
      return getQueue().length;
    },
    clear: function () {
      setQueue([]);
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    if (navigator.onLine) {
      syncNow();
    }
  });

  window.addEventListener('online', function () {
    syncNow();
  });
})();