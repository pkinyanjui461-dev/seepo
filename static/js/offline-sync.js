(function () {
  if (!window.seepoOfflineDb) {
    return;
  }

  const DEFAULT_MODEL_ORDER = ['group', 'member', 'monthly_form', 'expense'];

  function resolveModelOrder() {
    const body = document.body;
    const raw = body ? body.getAttribute('data-offline-models') : '';
    if (!raw) {
      return DEFAULT_MODEL_ORDER;
    }

    const allowed = raw
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item && window.seepoOfflineDb.modelTableMap[item]);

    return allowed.length ? allowed : DEFAULT_MODEL_ORDER;
  }

  class SeepoOfflineSync {
    constructor() {
      this.isSyncing = false;
      this.lastSyncError = null;
      this.lastSyncErrors = [];
      this.statusTimer = null;
      this.preloadTimer = null;
      this.preloadIntervalMs = 120000;
      this.modelOrder = resolveModelOrder();
      this.fabFlashTimer = null;
      this.fabFlashUntil = 0;
      this.networkBackoffMs = 15000;
      this.networkBackoffUntil = 0;
      this.networkBackoffMaxMs = 300000;
    }

    normalizeError(error, context) {
      const message = error && error.message ? error.message : String(error || 'Unknown error');
      return {
        context,
        message,
      };
    }

    isTransientNetworkError(error) {
      const message = error && error.message ? String(error.message) : String(error || '');
      return /Failed to fetch|NetworkError|ERR_INTERNET_DISCONNECTED|network request failed|The network connection was lost/i.test(message);
    }

    registerNetworkFailure() {
      this.networkBackoffUntil = Date.now() + this.networkBackoffMs;
      this.networkBackoffMs = Math.min(this.networkBackoffMs * 2, this.networkBackoffMaxMs);
    }

    resetNetworkBackoff() {
      this.networkBackoffUntil = 0;
      this.networkBackoffMs = 15000;
    }

    updateQueueChip(total, breakdown) {
      const chip = document.getElementById('sync-queue-chip');
      if (!chip) {
        return;
      }

      const labelMap = {
        group: 'Groups',
        member: 'Members',
        monthly_form: 'Monthly Forms',
        member_record: 'Monthly Rows',
        monthly_sheet: 'Sheet Drafts',
        expense: 'Expenses',
        user: 'Users',
        diary: 'Diary',
        draft: 'Drafts'
      };

      if (!total) {
        chip.classList.add('sync-queue-chip-empty');
        chip.textContent = 'No queued records';
        return;
      }

      const keys = Object.keys(breakdown).sort((a, b) => a.localeCompare(b));
      const items = keys.map((key) => {
        const label = labelMap[key] || key;
        return '<span class="sync-queue-pill">' + label + ': ' + breakdown[key] + '</span>';
      });

      chip.classList.remove('sync-queue-chip-empty');
      chip.innerHTML = items.join('');
    }

    async getQueueStatus() {
      const breakdown = await window.seepoOfflineDb.getPendingBreakdown();

      if (window.seepoOfflineDiary && typeof window.seepoOfflineDiary.pendingCount === 'function') {
        const diaryPending = Number(window.seepoOfflineDiary.pendingCount()) || 0;
        if (diaryPending > 0) {
          breakdown.diary = diaryPending;
        }
      }

      if (window.seepoOfflineDraftQueue && typeof window.seepoOfflineDraftQueue.pendingCount === 'function') {
        const draftPending = Number(window.seepoOfflineDraftQueue.pendingCount()) || 0;
        if (draftPending > 0) {
          breakdown.draft = draftPending;
        }
      }

      if (window.seepoOfflineMemberRecordQueue && typeof window.seepoOfflineMemberRecordQueue.pendingCount === 'function') {
        const rowPending = Number(window.seepoOfflineMemberRecordQueue.pendingCount()) || 0;
        if (rowPending > 0) {
          breakdown.member_record = rowPending;
        }
      }

      if (window.seepoOfflineMonthlyFormSheet && typeof window.seepoOfflineMonthlyFormSheet.pendingCount === 'function') {
        const monthlySheetPending = Number(window.seepoOfflineMonthlyFormSheet.pendingCount()) || 0;
        if (monthlySheetPending > 0) {
          breakdown.monthly_sheet = monthlySheetPending;
        }
      }

      const total = Object.values(breakdown).reduce((sum, count) => sum + (Number(count) || 0), 0);
      this.updateQueueChip(total, breakdown);

      window.dispatchEvent(
        new CustomEvent('seepo:queue-status', {
          detail: {
            total,
            breakdown,
          },
        })
      );

      return { total, breakdown };
    }

    async runAuxiliarySyncs() {
      const syncTasks = [];

      if (window.seepoOfflineDiary && typeof window.seepoOfflineDiary.syncNow === 'function') {
        syncTasks.push(window.seepoOfflineDiary.syncNow());
      }

      if (window.seepoOfflineDraftQueue && typeof window.seepoOfflineDraftQueue.syncNow === 'function') {
        syncTasks.push(window.seepoOfflineDraftQueue.syncNow());
      }

      if (window.seepoOfflineMemberRecordQueue && typeof window.seepoOfflineMemberRecordQueue.syncNow === 'function') {
        syncTasks.push(window.seepoOfflineMemberRecordQueue.syncNow());
      }

      if (window.seepoOfflineMonthlyFormSheet && typeof window.seepoOfflineMonthlyFormSheet.syncNow === 'function') {
        syncTasks.push(window.seepoOfflineMonthlyFormSheet.syncNow());
      }

      if (!syncTasks.length) {
        return;
      }

      const results = await Promise.allSettled(syncTasks);
      const failed = results.find((result) => result.status === 'rejected');
      if (failed) {
        throw failed.reason;
      }
    }

    async init() {
      window.addEventListener('online', async () => {
        await this.refreshStatus();
        await this.syncNow();
        await this.preloadReadData();
      });

      window.addEventListener('offline', async () => {
        await this.refreshStatus();
      });

      window.addEventListener('seepo:draft-queue-updated', async () => {
        await this.refreshStatus();
      });

      window.addEventListener('seepo:member-record-queue-updated', async () => {
        await this.refreshStatus();
      });

      window.addEventListener('seepo:monthly-sheet-queue-updated', async () => {
        await this.refreshStatus();
      });

      this.statusTimer = setInterval(async () => {
        await this.refreshStatus();
      }, 5000);

      this.preloadTimer = setInterval(async () => {
        await this.preloadReadData();
      }, this.preloadIntervalMs);

      await this.refreshStatus();
      if (navigator.onLine) {
        await this.syncNow();
        await this.preloadReadData();
      }
    }

    async preloadReadData() {
      if (!navigator.onLine || this.isSyncing || Date.now() < this.networkBackoffUntil) {
        return;
      }

      try {
        for (const modelName of this.modelOrder) {
          try {
            await this.pullModel(modelName);
          } catch (error) {
            if (this.isTransientNetworkError(error)) {
              this.registerNetworkFailure();
              return;
            }

            console.error('Read-data preload failed:', error);
            return;
          }
        }

        const metaTable = window.seepoOfflineDb.db.table('sync_meta');
        await metaTable.put({
          model: '_last_read_preload',
          last_pull_ts: Math.floor(Date.now() / 1000)
        });
      } catch (error) {
        console.error('Read-data preload failed:', error);
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
      this.setFabBaseState(state);
    }

    setFabClass(stateClass) {
      const fab = document.getElementById('sw-tools-fab');
      if (!fab) {
        return;
      }

      fab.classList.remove('fab-state-online', 'fab-state-offline', 'fab-state-success', 'fab-state-error');
      fab.classList.add(stateClass);
    }

    setFabBaseState(state) {
      if (Date.now() < this.fabFlashUntil) {
        return;
      }

      if (state === 'offline') {
        this.setFabClass('fab-state-offline');
        return;
      }

      if (state === 'error') {
        this.setFabClass('fab-state-error');
        return;
      }

      this.setFabClass('fab-state-online');
    }

    flashFabState(type, durationMs) {
      const duration = Number(durationMs) || 10000;
      const flashClass = type === 'success' ? 'fab-state-success' : 'fab-state-error';

      this.fabFlashUntil = Date.now() + duration;
      this.setFabClass(flashClass);

      clearTimeout(this.fabFlashTimer);
      this.fabFlashTimer = setTimeout(async () => {
        this.fabFlashUntil = 0;
        await this.refreshStatus();
      }, duration);
    }

    showOfflineBanner(show) {
      const banner = document.getElementById('offline-banner');
      if (!banner) {
        return;
      }

      const root = document.documentElement;
      if (show) {
        banner.style.display = 'block';
        const offset = Math.ceil(banner.getBoundingClientRect().height || banner.offsetHeight || 0);
        root.style.setProperty('--offline-banner-offset', offset + 'px');
        document.body.classList.add('offline-banner-visible');
        return;
      }

      banner.style.display = 'none';
      root.style.setProperty('--offline-banner-offset', '0px');
      document.body.classList.remove('offline-banner-visible');
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
      const queueStatus = await this.getQueueStatus();
      const pending = queueStatus.total;

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

    async syncNow(options) {
      const syncOptions = {
        throwOnError: false,
        ...(options || {}),
      };

      if (syncOptions.respectBackoff && Date.now() < this.networkBackoffUntil) {
        return {
          success: false,
          skipped: true,
          errors: [
            {
              context: 'network',
              message: 'Sync deferred after a recent network failure.',
            },
          ],
        };
      }

      if (this.isSyncing) {
        return {
          success: false,
          errors: [
            {
              context: 'sync',
              message: 'Sync is already running.',
            },
          ],
        };
      }

      if (!navigator.onLine) {
        await this.refreshStatus();
        return {
          success: false,
          errors: [
            {
              context: 'network',
              message: 'Cannot sync while offline.',
            },
          ],
        };
      }

      this.isSyncing = true;
      this.lastSyncError = null;
      this.lastSyncErrors = [];
      await this.refreshStatus();

      let sawTransientNetworkFailure = false;

      for (const modelName of this.modelOrder) {
        try {
          await this.pushModel(modelName);
        } catch (error) {
          const normalized = this.normalizeError(error, modelName);
          this.lastSyncError = normalized;
          this.lastSyncErrors.push(normalized);
          if (this.isTransientNetworkError(error)) {
            sawTransientNetworkFailure = true;
          }

          if (syncOptions.quietNetworkErrors && this.isTransientNetworkError(error)) {
            console.warn('Push failed for model', modelName, error);
          } else {
            console.error('Push failed for model', modelName, error);
          }
        }

        try {
          await this.pullModel(modelName);
        } catch (error) {
          const normalized = this.normalizeError(error, modelName);
          this.lastSyncError = normalized;
          this.lastSyncErrors.push(normalized);
          if (this.isTransientNetworkError(error)) {
            sawTransientNetworkFailure = true;
          }

          if (syncOptions.quietNetworkErrors && this.isTransientNetworkError(error)) {
            console.warn('Pull failed for model', modelName, error);
          } else {
            console.error('Pull failed for model', modelName, error);
          }
        }
      }

      try {
        await this.runAuxiliarySyncs();
      } catch (error) {
        const normalized = this.normalizeError(error, 'auxiliary');
        this.lastSyncError = normalized;
        this.lastSyncErrors.push(normalized);
        if (this.isTransientNetworkError(error)) {
          sawTransientNetworkFailure = true;
        }

        if (syncOptions.quietNetworkErrors && this.isTransientNetworkError(error)) {
          console.warn('Auxiliary queue sync failed', error);
        } else {
          console.error('Auxiliary queue sync failed', error);
        }
      }

      this.isSyncing = false;
      await this.refreshStatus();

      const result = {
        success: this.lastSyncErrors.length === 0,
        errors: this.lastSyncErrors.slice(),
      };

      window.dispatchEvent(new CustomEvent('seepo:sync-complete', {
        detail: {
          success: result.success,
          errors: result.errors.slice(),
          modelOrder: this.modelOrder.slice(),
          ts: Date.now(),
        },
      }));

      if (result.success) {
        this.resetNetworkBackoff();
        this.flashFabState('success', 10000);
      } else if (sawTransientNetworkFailure) {
        this.registerNetworkFailure();
        if (!syncOptions.quietNetworkErrors) {
          this.flashFabState('error', 10000);
        }
      } else {
        this.flashFabState('error', 10000);
      }

      if (!result.success && syncOptions.throwOnError) {
        const first = result.errors[0] && result.errors[0].message ? result.errors[0].message : 'Unknown sync error.';
        const moreCount = result.errors.length - 1;
        const suffix = moreCount > 0 ? ' (+' + moreCount + ' more)' : '';
        throw new Error(first + suffix);
      }

      return result;
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

      let result = null;
      try {
        result = await response.json();
      } catch (error) {
        result = null;
      }

      if (!response.ok) {
        const serverError = result && result.error ? String(result.error) : 'HTTP ' + response.status;
        throw new Error(modelName + ': ' + serverError);
      }

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

      if (Array.isArray(result.errors) && result.errors.length > 0) {
        const firstError = result.errors[0] && result.errors[0].error
          ? String(result.errors[0].error)
          : 'Unknown server validation error.';
        throw new Error(modelName + ': ' + firstError);
      }

      if (result.synced > 0) {
        this.showToast('Synced ' + result.synced + ' ' + modelName + ' records.');
      }
    }

    async pullModel(modelName, options) {
      const pullOptions = {
        forceFull: false,
        ...(options || {}),
      };

      const metaTable = window.seepoOfflineDb.db.table('sync_meta');
      const table = window.seepoOfflineDb.tableForModel(modelName);
      const meta = (await metaTable.get(modelName)) || { model: modelName, last_pull_ts: 0 };
      const syncedCount = await table.where('synced').equals(1).count();

      const sinceTs = pullOptions.forceFull
        ? 0
        : (syncedCount > 0 ? Number(meta.last_pull_ts || 0) : 0);

      const response = await fetch(
        '/api/sync/pull/?model=' + encodeURIComponent(modelName) + '&since=' + encodeURIComponent(sinceTs),
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
        let local = await table.where('client_uuid').equals(serverRecord.client_uuid).first();
        if (!local && serverRecord.server_id !== undefined && serverRecord.server_id !== null) {
          local = await table
            .filter((item) => Number(item.server_id || 0) === Number(serverRecord.server_id))
            .first();
        }
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
