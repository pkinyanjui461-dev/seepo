(function () {
  if (!window.seepoOfflineDb) {
    return;
  }

  const MODEL_ORDER = ['group', 'member', 'monthly_form', 'expense'];

  class SeepoOfflineSync {
    constructor() {
      this.isSyncing = false;
      this.lastSyncError = null;
      this.statusTimer = null;
    }

    async init() {
      window.addEventListener('online', async () => {
        await this.refreshStatus();
        await this.syncNow();
      });

      window.addEventListener('offline', async () => {
        await this.refreshStatus();
      });

      this.statusTimer = setInterval(async () => {
        await this.refreshStatus();
      }, 5000);

      await this.refreshStatus();
      if (navigator.onLine) {
        await this.syncNow();
      }
    }

    getCsrfToken() {
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

    setBadge(state, text) {
      const badge = document.getElementById('sync-badge');
      if (!badge) {
        return;
      }

      badge.className = 'sync-badge';
      badge.classList.add('sync-state-' + state);
      badge.textContent = text;
    }

    showOfflineBanner(show) {
      const banner = document.getElementById('offline-banner');
      if (!banner) {
        return;
      }
      banner.style.display = show ? 'block' : 'none';
    }

    showToast(message) {
      const toast = document.getElementById('sync-toast');
      if (!toast) {
        return;
      }

      toast.textContent = message;
      toast.classList.add('show');
      clearTimeout(toast._hideTimer);
      toast._hideTimer = setTimeout(() => {
        toast.classList.remove('show');
      }, 3000);
    }

    async refreshStatus() {
      const pending = await window.seepoOfflineDb.getPendingCount();

      if (!navigator.onLine) {
        this.showOfflineBanner(true);
        this.setBadge('offline', pending > 0 ? pending + ' pending (offline)' : 'Offline');
        return;
      }

      this.showOfflineBanner(false);

      if (this.isSyncing) {
        this.setBadge('syncing', 'Syncing...');
        return;
      }

      if (this.lastSyncError) {
        this.setBadge('error', 'Sync error');
        return;
      }

      if (pending > 0) {
        this.setBadge('pending', pending + ' pending');
      } else {
        this.setBadge('synced', 'Synced');
      }
    }

    async saveOffline(modelName, record) {
      const table = window.seepoOfflineDb.tableForModel(modelName);
      const nowIso = new Date().toISOString();
      const payload = {
        ...record,
        client_uuid: record.client_uuid || crypto.randomUUID(),
        client_updated_at: nowIso,
        synced: 0
      };

      const existing = await table.where('client_uuid').equals(payload.client_uuid).first();
      if (existing) {
        await table.update(existing._localId, payload);
      } else {
        await table.add(payload);
      }

      await this.refreshStatus();
      return payload;
    }

    async syncNow() {
      if (this.isSyncing) {
        return;
      }

      if (!navigator.onLine) {
        await this.refreshStatus();
        return;
      }

      this.isSyncing = true;
      this.lastSyncError = null;
      await this.refreshStatus();

      try {
        for (const modelName of MODEL_ORDER) {
          await this.pushModel(modelName);
          await this.pullModel(modelName);
        }
      } catch (error) {
        this.lastSyncError = error;
        console.error('Sync failed:', error);
      } finally {
        this.isSyncing = false;
        await this.refreshStatus();
      }
    }

    async pushModel(modelName) {
      const table = window.seepoOfflineDb.tableForModel(modelName);
      const pending = await table.where('synced').equals(0).toArray();

      if (!pending.length) {
        return;
      }

      const records = pending.map((item) => {
        const data = { ...item };
        delete data._localId;
        delete data.synced;
        return data;
      });

      const response = await fetch('/api/sync/push/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCsrfToken()
        },
        body: JSON.stringify({ model: modelName, records })
      });

      if (!response.ok) {
        throw new Error('Push failed for model ' + modelName);
      }

      const result = await response.json();
      if (Array.isArray(result.records_saved)) {
        for (const saved of result.records_saved) {
          const local = await table.where('client_uuid').equals(saved.client_uuid).first();
          if (local) {
            await table.update(local._localId, {
              synced: 1,
              server_id: saved.server_id
            });
          }
        }
      }

      if (result.synced > 0) {
        this.showToast('Synced ' + result.synced + ' ' + modelName + ' records.');
      }
    }

    async pullModel(modelName) {
      const metaTable = window.seepoOfflineDb.db.table('sync_meta');
      const table = window.seepoOfflineDb.tableForModel(modelName);
      const meta = (await metaTable.get(modelName)) || { model: modelName, last_pull_ts: 0 };

      const response = await fetch(
        '/api/sync/pull/?model=' + encodeURIComponent(modelName) + '&since=' + encodeURIComponent(meta.last_pull_ts || 0),
        {
          method: 'GET',
          credentials: 'same-origin'
        }
      );

      if (!response.ok) {
        throw new Error('Pull failed for model ' + modelName);
      }

      const result = await response.json();
      const records = Array.isArray(result.records) ? result.records : [];

      for (const serverRecord of records) {
        const local = await table.where('client_uuid').equals(serverRecord.client_uuid).first();
        if (!local) {
          await table.add({ ...serverRecord, synced: 1 });
          continue;
        }

        const localTs = new Date(local.client_updated_at || 0).getTime();
        const serverTs = new Date(serverRecord.client_updated_at || 0).getTime();
        if (serverTs >= localTs || local.synced === 1) {
          await table.update(local._localId, {
            ...serverRecord,
            synced: 1
          });
        }
      }

      await metaTable.put({
        model: modelName,
        last_pull_ts: result.ts || Math.floor(Date.now() / 1000)
      });
    }
  }

  const syncEngine = new SeepoOfflineSync();
  window.seepoOfflineSync = syncEngine;

  document.addEventListener('DOMContentLoaded', async () => {
    await syncEngine.init();
  });
})();
