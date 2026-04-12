(function () {
  if (!('serviceWorker' in navigator)) {
    return;
  }

  let hasRefreshed = false;

  window.addEventListener('load', async function () {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js');

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
