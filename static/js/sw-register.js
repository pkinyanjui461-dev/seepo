(function () {
  const SW_ASSET_VERSION = '23';
  const SW_SCRIPT_URL = '/sw.js?v=' + SW_ASSET_VERSION;
  const hasServiceWorkerSupport = 'serviceWorker' in navigator;
  const localHostPattern = /^(localhost|127\.0\.0\.1)(:\d+)?$/i;

  let hasRefreshed = false;
  let deferredInstallPrompt = null;
  let installButton = null;
  let hostReadyBadge = null;
  let hostReadyTimer = null;

  function showInstallMessage(message) {
    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
      window.seepoOfflineSync.showToast(message);
      return;
    }

    window.alert(message);
  }

  function getManualInstallHint() {
    const ua = (window.navigator.userAgent || '').toLowerCase();
    const isIOS = /iphone|ipad|ipod/.test(ua);

    if (isIOS) {
      return 'To install on iPhone/iPad, tap Share and choose Add to Home Screen.';
    }

    return 'If the install prompt does not appear, use your browser menu and choose Install App.';
  }

  function canUseServiceWorkersOnThisHost() {
    return window.isSecureContext || localHostPattern.test(window.location.host);
  }

  function getHostReadyBadge() {
    if (hostReadyBadge) {
      return hostReadyBadge;
    }

    hostReadyBadge = document.getElementById('offline-host-ready-badge');
    return hostReadyBadge;
  }

  function setHostReadyBadge(status, text, title) {
    const badge = getHostReadyBadge();
    if (!badge) {
      return;
    }

    badge.className = 'offline-host-ready-badge';
    badge.classList.add('host-ready-' + status);
    badge.textContent = text;
    badge.title = title || text;
  }

  function getSwBadgeLabel(swVersion) {
    const normalized = String(swVersion || SW_ASSET_VERSION || '').replace(/^v/i, '');
    return normalized ? 'SW' + normalized : 'SW';
  }

  async function updateOfflineHostReadyStatus() {
    const hostLabel = window.location.host;

    if (!hasServiceWorkerSupport) {
      setHostReadyBadge(
        'error',
        'OH-Unsupported',
        'This browser does not support Service Workers.'
      );
      return;
    }

    if (!canUseServiceWorkersOnThisHost()) {
      setHostReadyBadge(
        'error',
        'OH-HTTPS',
        'Service Workers require HTTPS on non-local hosts.'
      );
      return;
    }

    setHostReadyBadge('checking', 'OH-Checking');

    try {
      const registration = await navigator.serviceWorker.getRegistration('/');
      if (!registration || !registration.active) {
        setHostReadyBadge(
          'warn',
          'OH-NotReady',
          'Service Worker is not active on this host yet.'
        );
        return;
      }

      if (!navigator.serviceWorker.controller) {
        setHostReadyBadge(
          'warn',
          'OH-Reload',
          'Service Worker is installed. Reload once so this tab is controlled.'
        );
        return;
      }

      const cacheKeys = await caches.keys();
      const shellCacheKey = cacheKeys.find(function (key) {
        return key.indexOf('seepo-offline-shell-') === 0;
      });
      const runtimeCacheKey = cacheKeys.find(function (key) {
        return key.indexOf('seepo-offline-runtime-') === 0;
      });

      const swVersion = shellCacheKey
        ? shellCacheKey.replace('seepo-offline-shell-', '')
        : (runtimeCacheKey ? runtimeCacheKey.replace('seepo-offline-runtime-', '') : '');
      const swVersionLabel = ' | ' + getSwBadgeLabel(swVersion);

      if (!shellCacheKey) {
        setHostReadyBadge(
          'warn',
          'OH-Priming' + swVersionLabel,
          'Shell cache has not been created yet for this host.'
        );
        return;
      }

      const shellCache = await caches.open(shellCacheKey);
      const checks = await Promise.all([
        shellCache.match('/', { ignoreSearch: true }),
        shellCache.match('/offline/', { ignoreSearch: true }),
        shellCache.match('/manifest.webmanifest', { ignoreSearch: true }),
      ]);

      if (checks.every(Boolean)) {
        setHostReadyBadge(
          'ok',
          'OH-Ready' + swVersionLabel,
          'This host has an active Service Worker and a primed offline shell cache. Version: ' + swVersion
        );
      } else {
        setHostReadyBadge(
          'warn',
          'OH-Partial' + swVersionLabel,
          'Service Worker is active, but required shell entries are still priming. Version: ' + swVersion
        );
      }
    } catch (error) {
      setHostReadyBadge(
        'error',
        'OH-Error',
        'Readiness check failed: ' + (error && error.message ? error.message : String(error))
      );
    }
  }

  function inStandaloneMode() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function getInstallButton() {
    if (installButton) {
      return installButton;
    }

    installButton = document.getElementById('pwa-install-btn');
    if (!installButton) {
      return null;
    }

    installButton.addEventListener('click', async function () {
      if (!deferredInstallPrompt) {
        showInstallMessage(getManualInstallHint());
        return;
      }

      deferredInstallPrompt.prompt();
      try {
        await deferredInstallPrompt.userChoice;
      } catch (error) {
        console.warn('PWA install prompt was dismissed.', error);
      }

      deferredInstallPrompt = null;
      installButton.hidden = true;
    });

    return installButton;
  }

  function setInstallButtonVisible(isVisible) {
    const button = getInstallButton();
    if (!button) {
      return;
    }

    button.hidden = !isVisible || inStandaloneMode();
  }

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredInstallPrompt = event;
    setInstallButtonVisible(true);
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    setInstallButtonVisible(false);
    updateOfflineHostReadyStatus();
  });

  window.addEventListener('DOMContentLoaded', function () {
    getHostReadyBadge();
    getInstallButton();
    setInstallButtonVisible(true);
    updateOfflineHostReadyStatus();

    if (!hostReadyTimer) {
      hostReadyTimer = setInterval(updateOfflineHostReadyStatus, 15000);
    }
  });

  window.addEventListener('online', updateOfflineHostReadyStatus);
  window.addEventListener('offline', updateOfflineHostReadyStatus);
  window.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
      updateOfflineHostReadyStatus();
    }
  });

  if (!hasServiceWorkerSupport) {
    return;
  }

  window.addEventListener('load', async function () {
    try {
      const registration = await navigator.serviceWorker.register(SW_SCRIPT_URL, { scope: '/' });

      if (registration.waiting) {
        registration.waiting.postMessage('SKIP_WAITING');
      }

      registration.addEventListener('updatefound', function () {
        const worker = registration.installing;
        if (!worker) {
          return;
        }

        worker.addEventListener('statechange', function () {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            worker.postMessage('SKIP_WAITING');
          }
        });
      });

      navigator.serviceWorker.addEventListener('controllerchange', function () {
        if (hasRefreshed) {
          return;
        }

        hasRefreshed = true;
        window.location.reload();
      });

      await updateOfflineHostReadyStatus();
    } catch (error) {
      console.error('Service worker registration failed:', error);
      setHostReadyBadge(
        'error',
        'OH-RegError',
        'Service Worker registration failed: ' + (error && error.message ? error.message : String(error))
      );
    }
  });
})();
