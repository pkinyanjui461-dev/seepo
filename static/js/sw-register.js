(function () {
  const SW_ASSET_VERSION = '38';
  const SW_SCRIPT_URL = '/sw.js?v=' + SW_ASSET_VERSION;
  const SW_FORCE_UPDATE_INTERVAL_MS = 90 * 1000;
  const SW_UPDATE_WARN_THROTTLE_MS = 120 * 1000;
  const SW_REFRESH_TOAST_FLAG_KEY = 'seepoSwRefreshedToastV1';
  const SW_REFRESH_TOAST_MAX_AGE_MS = 2 * 60 * 1000;
  const hasServiceWorkerSupport = 'serviceWorker' in navigator;
  const localHostPattern = /^(localhost|127\.0\.0\.1)(:\d+)?$/i;

  let hasRefreshed = false;
  let deferredInstallPrompt = null;
  let installButton = null;
  let hostReadyBadge = null;
  let hostReadyTimer = null;
  let swForceUpdateTimer = null;
  let lastSwUpdateWarnAt = 0;

  function showInstallMessage(message) {
    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
      window.seepoOfflineSync.showToast(message);
      return;
    }

    window.alert(message);
  }

  function showInAppToast(message) {
    if (window.seepoOfflineSync && typeof window.seepoOfflineSync.showToast === 'function') {
      window.seepoOfflineSync.showToast(message);
      return;
    }

    if (!document.body) {
      return;
    }

    const existing = document.getElementById('sw-refresh-toast');
    if (existing) {
      existing.remove();
    }

    const toast = document.createElement('div');
    toast.id = 'sw-refresh-toast';
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.left = '50%';
    toast.style.bottom = '80px';
    toast.style.transform = 'translateX(-50%)';
    toast.style.background = 'rgba(17, 24, 39, 0.95)';
    toast.style.color = '#ffffff';
    toast.style.padding = '10px 14px';
    toast.style.borderRadius = '10px';
    toast.style.boxShadow = '0 10px 24px rgba(0, 0, 0, 0.28)';
    toast.style.fontSize = '13px';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '1200';
    toast.style.maxWidth = '80vw';
    toast.style.textAlign = 'center';
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.18s ease';
    document.body.appendChild(toast);

    window.requestAnimationFrame(function () {
      toast.style.opacity = '1';
    });

    window.setTimeout(function () {
      toast.style.opacity = '0';
      window.setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 220);
    }, 3200);
  }

  function markSwRefreshToastPending() {
    try {
      window.sessionStorage.setItem(SW_REFRESH_TOAST_FLAG_KEY, String(Date.now()));
    } catch (error) {
      // Ignore storage failures silently.
    }
  }

  function consumeSwRefreshToastPending() {
    try {
      const raw = window.sessionStorage.getItem(SW_REFRESH_TOAST_FLAG_KEY);
      if (!raw) {
        return false;
      }

      window.sessionStorage.removeItem(SW_REFRESH_TOAST_FLAG_KEY);
      const timestamp = Number(raw);
      if (!Number.isFinite(timestamp)) {
        return true;
      }

      return Date.now() - timestamp <= SW_REFRESH_TOAST_MAX_AGE_MS;
    } catch (error) {
      return false;
    }
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

    const shouldShow = Boolean(isVisible) && Boolean(deferredInstallPrompt) && !inStandaloneMode();
    button.hidden = !shouldShow;
  }

  function resolveRegistrationScriptUrl(registration) {
    if (!registration) {
      return '';
    }

    const worker = registration.installing || registration.waiting || registration.active;
    return worker && worker.scriptURL ? String(worker.scriptURL) : '';
  }

  function normalizeScriptUrl(scriptUrl) {
    if (!scriptUrl) {
      return '(unknown script)';
    }

    try {
      const parsed = new URL(scriptUrl, window.location.origin);
      return parsed.pathname + parsed.search;
    } catch (error) {
      return String(scriptUrl);
    }
  }

  function hasExpectedScriptVersion(scriptUrl) {
    if (!scriptUrl) {
      return false;
    }

    try {
      const parsed = new URL(scriptUrl, window.location.origin);
      return parsed.pathname === '/sw.js' && parsed.searchParams.get('v') === SW_ASSET_VERSION;
    } catch (error) {
      return scriptUrl.indexOf('/sw.js?v=' + SW_ASSET_VERSION) !== -1;
    }
  }

  function warnUpdateFailure(message, error) {
    const now = Date.now();
    if (now - lastSwUpdateWarnAt < SW_UPDATE_WARN_THROTTLE_MS) {
      return;
    }

    lastSwUpdateWarnAt = now;
    console.warn(message, error);
  }

  async function recoverRegistration(registration) {
    try {
      if (registration) {
        await registration.unregister();
      }

      const freshRegistration = await navigator.serviceWorker.register(SW_SCRIPT_URL, {
        scope: '/',
        updateViaCache: 'none',
      });

      if (freshRegistration.waiting) {
        freshRegistration.waiting.postMessage('SKIP_WAITING');
      }

      return freshRegistration;
    } catch (error) {
      warnUpdateFailure('Service worker recovery failed.', error);
      return registration;
    }
  }

  async function forceServiceWorkerUpdate(registration) {
    if (!registration) {
      return null;
    }

    if (!navigator.onLine) {
      return registration;
    }

    let activeRegistration = registration;
    const currentScriptUrl = resolveRegistrationScriptUrl(activeRegistration);

    if (currentScriptUrl && !hasExpectedScriptVersion(currentScriptUrl)) {
      activeRegistration = await recoverRegistration(activeRegistration);
    }

    try {
      await activeRegistration.update();
      if (activeRegistration.waiting) {
        activeRegistration.waiting.postMessage('SKIP_WAITING');
      }
      return activeRegistration;
    } catch (error) {
      const failedScriptUrl = resolveRegistrationScriptUrl(activeRegistration) || currentScriptUrl;
      warnUpdateFailure(
        'Service worker update check failed for ' + normalizeScriptUrl(failedScriptUrl) + '.',
        error
      );

      if (failedScriptUrl && !hasExpectedScriptVersion(failedScriptUrl)) {
        return recoverRegistration(activeRegistration);
      }

      return activeRegistration;
    }
  }

  function startForceUpdateCycle(initialRegistration) {
    if (swForceUpdateTimer) {
      clearInterval(swForceUpdateTimer);
    }

    let registration = initialRegistration;

    swForceUpdateTimer = setInterval(function () {
      forceServiceWorkerUpdate(registration)
        .then(function (updatedRegistration) {
          if (updatedRegistration) {
            registration = updatedRegistration;
          }
        })
        .catch(function () {});
    }, SW_FORCE_UPDATE_INTERVAL_MS);
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

    if (consumeSwRefreshToastPending()) {
      showInAppToast('Offline engine refreshed successfully.');
    }

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
      navigator.serviceWorker.getRegistration('/').then(forceServiceWorkerUpdate).catch(function () {});
    }
  });

  window.addEventListener('focus', function () {
    navigator.serviceWorker.getRegistration('/').then(forceServiceWorkerUpdate).catch(function () {});
  });

  window.addEventListener('online', function () {
    navigator.serviceWorker.getRegistration('/').then(forceServiceWorkerUpdate).catch(function () {});
  });

  if (!hasServiceWorkerSupport) {
    return;
  }

  window.addEventListener('load', async function () {
    try {
      let registration = await navigator.serviceWorker.register(SW_SCRIPT_URL, {
        scope: '/',
        updateViaCache: 'none',
      });

      registration = (await forceServiceWorkerUpdate(registration)) || registration;
      startForceUpdateCycle(registration);

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
        markSwRefreshToastPending();
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
