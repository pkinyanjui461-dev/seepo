(function () {
  const hasServiceWorkerSupport = 'serviceWorker' in navigator;
  const localHostPattern = /^(localhost|127\.0\.0\.1)(:\d+)?$/i;

  let hasRefreshed = false;
  let deferredInstallPrompt = null;
  let installButton = null;
  let hostReadyBadge = null;
  let hostReadyTimer = null;

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

  async function updateOfflineHostReadyStatus() {
    const hostLabel = window.location.host;

    if (!hasServiceWorkerSupport) {
      setHostReadyBadge(
        'error',
        'Offline Host: Unsupported (' + hostLabel + ')',
        'This browser does not support Service Workers.'
      );
      return;
    }

    if (!canUseServiceWorkersOnThisHost()) {
      setHostReadyBadge(
        'error',
        'Offline Host: HTTPS Required (' + hostLabel + ')',
        'Service Workers require HTTPS on non-local hosts.'
      );
      return;
    }

    setHostReadyBadge('checking', 'Offline Host: Checking (' + hostLabel + ')');

    try {
      const registration = await navigator.serviceWorker.getRegistration('/');
      if (!registration || !registration.active) {
        setHostReadyBadge(
          'warn',
          'Offline Host: Not Ready (' + hostLabel + ')',
          'Service Worker is not active on this host yet.'
        );
        return;
      }

      if (!navigator.serviceWorker.controller) {
        setHostReadyBadge(
          'warn',
          'Offline Host: Reload Needed (' + hostLabel + ')',
          'Service Worker is installed. Reload once so this tab is controlled.'
        );
        return;
      }

      const cacheKeys = await caches.keys();
      const shellCacheKey = cacheKeys.find(function (key) {
        return key.indexOf('seepo-offline-shell-') === 0;
      });

      if (!shellCacheKey) {
        setHostReadyBadge(
          'warn',
          'Offline Host: Priming (' + hostLabel + ')',
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
          'Offline Host: Ready (' + hostLabel + ')',
          'This host has an active Service Worker and a primed offline shell cache.'
        );
      } else {
        setHostReadyBadge(
          'warn',
          'Offline Host: Partial (' + hostLabel + ')',
          'Service Worker is active, but required shell entries are still priming.'
        );
      }
    } catch (error) {
      setHostReadyBadge(
        'error',
        'Offline Host: Check Failed (' + hostLabel + ')',
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
    setInstallButtonVisible(false);
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
      const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });

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
        'Offline Host: Registration Failed (' + window.location.host + ')',
        'Service Worker registration failed: ' + (error && error.message ? error.message : String(error))
      );
    }
  });
})();
