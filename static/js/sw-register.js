(function () {
  if (!('serviceWorker' in navigator)) {
    return;
  }

  let hasRefreshed = false;
  let deferredInstallPrompt = null;
  let installButton = null;

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
  });

  window.addEventListener('DOMContentLoaded', function () {
    getInstallButton();
    setInstallButtonVisible(false);
  });

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
    } catch (error) {
      console.error('Service worker registration failed:', error);
    }
  });
})();
