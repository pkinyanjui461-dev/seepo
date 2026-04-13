(function () {
  /**
   * Global offline state manager
   * Handles online/offline transitions and automatic sync orchestration
   */

  const STATE = {
    isOnline: navigator.onLine,
    isInitialized: false,
    lastSyncTime: null,
    pendingCount: 0,
    isSyncing: false,
  };

  const BANNER_ID = 'seepo-global-offline-banner';
  const STATUS_INDICATOR_ID = 'seepo-online-status-indicator';
  const AUTO_SYNC_INTERVAL_MS = 5000; // Check every 5 seconds
  let autoSyncTimer = null;
  let deferredSyncTimer = null;

  function ensureOnlineBanner() {
    if (document.getElementById(BANNER_ID)) {
      return;
    }

    const banner = document.createElement('div');
    banner.id = BANNER_ID;
    banner.className = 'seepo-offline-banner';
    banner.innerHTML = `
      <div class="seepo-offline-banner-content">
        <span>📡 You're working offline. Data is saved locally and will sync when you're back online.</span>
        <button type="button" class="seepo-banner-close" aria-label="Close">&times;</button>
      </div>
    `;
    banner.style.display = 'none';

    document.body.insertBefore(banner, document.body.firstChild);

    banner.querySelector('.seepo-banner-close').addEventListener('click', () => {
      banner.style.display = 'none';
    });
  }

  function showOfflineBanner(visible) {
    ensureOnlineBanner();
    const banner = document.getElementById(BANNER_ID);
    if (banner) {
      banner.style.display = visible ? 'block' : 'none';
    }
  }

  function ensureStatusIndicator() {
    if (document.getElementById(STATUS_INDICATOR_ID)) {
      return;
    }

    const indicator = document.createElement('div');
    indicator.id = STATUS_INDICATOR_ID;
    indicator.className = 'seepo-online-status';
    indicator.title = 'Online status';
    indicator.setAttribute('aria-label', 'Online status indicator');
    indicator.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #10b981;
      z-index: 9999;
      box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
    `;

    document.body.appendChild(indicator);
  }

  function updateStatusIndicator() {
    ensureStatusIndicator();
    const indicator = document.getElementById(STATUS_INDICATOR_ID);
    if (!indicator) return;

    if (STATE.isOnline) {
      indicator.style.background = '#10b981';
      indicator.style.boxShadow = '0 0 0 2px rgba(16, 185, 129, 0.2)';
      indicator.title = 'Online';
    } else {
      indicator.style.background = '#ef4444';
      indicator.style.boxShadow = '0 0 0 2px rgba(239, 68, 68, 0.2)';
      indicator.title = 'Offline — data will sync when online';
    }
  }

  async function triggerAutoSync() {
    if (STATE.isSyncing || !STATE.isOnline || !window.seepoOfflineSync) {
      return;
    }

    STATE.isSyncing = true;

    try {
      await window.seepoOfflineSync.syncNow({ throwOnError: false });
    } catch (error) {
      console.warn('[AutoSync] Sync error:', error);
    } finally {
      STATE.isSyncing = false;
      STATE.lastSyncTime = Date.now();
    }
  }

  function scheduleAutoSync() {
    if (autoSyncTimer) {
      clearInterval(autoSyncTimer);
    }

    if (!STATE.isOnline) {
      return;
    }

    autoSyncTimer = setInterval(() => {
      triggerAutoSync();
    }, AUTO_SYNC_INTERVAL_MS);
  }

  function deferredSync(delayMs = 2000) {
    if (deferredSyncTimer) {
      clearTimeout(deferredSyncTimer);
    }

    deferredSyncTimer = setTimeout(() => {
      triggerAutoSync();
    }, delayMs);
  }

  function handleOnline() {
    STATE.isOnline = true;
    updateStatusIndicator();
    showOfflineBanner(false);
    scheduleAutoSync();
    triggerAutoSync();
    window.dispatchEvent(new CustomEvent('seepo:online'));
  }

  function handleOffline() {
    STATE.isOnline = false;
    updateStatusIndicator();
    showOfflineBanner(true);
    if (autoSyncTimer) {
      clearInterval(autoSyncTimer);
      autoSyncTimer = null;
    }
    window.dispatchEvent(new CustomEvent('seepo:offline'));
  }

  async function init() {
    if (STATE.isInitialized) {
      return;
    }

    ensureOnlineBanner();
    ensureStatusIndicator();
    updateStatusIndicator();

    if (STATE.isOnline) {
      showOfflineBanner(false);
      scheduleAutoSync();

      // Initial sync on load if online
      if (window.seepoOfflineSync && typeof window.seepoOfflineSync.syncNow === 'function') {
        deferredSync(3000);
      }
    } else {
      showOfflineBanner(true);
    }

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    STATE.isInitialized = true;
  }

  document.addEventListener('DOMContentLoaded', init);

  window.seepoOfflineState = {
    isOnline: () => STATE.isOnline,
    isSyncing: () => STATE.isSyncing,
    lastSyncTime: () => STATE.lastSyncTime,
    triggerSync: triggerAutoSync,
    deferredSync: deferredSync,
  };
})();
