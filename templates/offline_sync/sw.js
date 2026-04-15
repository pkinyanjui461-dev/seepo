{% load static %}
const CACHE_VERSION = 'v37';
const CSS_ASSET_VERSION = '12';
const OFFLINE_SYNC_ASSET_VERSION = '7';
const OFFLINE_DB_ASSET_VERSION = '4';
const SW_REGISTER_ASSET_VERSION = '37';
const DEXIE_ASSET_VERSION = '1';
const OFFLINE_FORM_AUTO_PERSIST_VERSION = '1';
const OFFLINE_GLOBAL_STATE_VERSION = '4';
const SHELL_CACHE = `seepo-offline-shell-${CACHE_VERSION}`;
const RUNTIME_CACHE = `seepo-offline-runtime-${CACHE_VERSION}`;
const OFFLINE_FALLBACK_URL = '/offline/';
const NAVIGATION_ROUTE_FALLBACKS = [
  { prefix: '/accounts/notifications/', fallback: '/accounts/notifications/' },
  { prefix: '/accounts/', fallback: '{% url "dashboard" %}' },
  { prefix: '/groups/offline/workspace/', fallback: '/groups/offline/workspace/' },
  { prefix: '/finance/forms/offline/', fallback: '{% url "monthly_form_detail_offline" %}' },
  { prefix: '/groups/', fallback: '/groups/' },
  { prefix: '/members/', fallback: '/groups/' },
  { prefix: '/finance/', fallback: '/finance/expenses/' },
  { prefix: '/reports/', fallback: '/reports/' },
  { prefix: '/offline/', fallback: OFFLINE_FALLBACK_URL },
  { prefix: '/', fallback: '{% url "dashboard" %}' },
];

const APP_SHELL_URLS = [
  OFFLINE_FALLBACK_URL,
  '{% url "dashboard" %}',
  '/admin/',
  '/accounts/login/',
  '/accounts/profile/',
  '/accounts/settings/',
  '/accounts/data-admin/',
  '/accounts/users/',
  '/accounts/users/create/',
  '/accounts/notifications/',
  '/groups/',
  '/groups/offline/workspace/',
  '/groups/create/',
  '/groups/diary/',
  '/finance/expenses/',
  '{% url "monthly_form_detail_offline" %}',
  '/reports/',
  '/reports/entities/',
  '/manifest.webmanifest',
  '{% static "css/main.css" %}?v=' + CSS_ASSET_VERSION,
  '{% static "css/main.css" %}',
  '{% static "js/sidebar.js" %}',
  '{% static "js/calculations.js" %}',
  '{% static "js/dev-log-tools.js" %}',
  '{% static "js/vendor/dexie.min.js" %}?v=' + DEXIE_ASSET_VERSION,
  '{% static "js/vendor/dexie.min.js" %}',
  '{% static "js/offline-db.js" %}?v=' + OFFLINE_DB_ASSET_VERSION,
  '{% static "js/offline-db.js" %}',
  '{% static "js/offline-sync.js" %}?v=' + OFFLINE_SYNC_ASSET_VERSION,
  '{% static "js/offline-sync.js" %}',
  '{% static "js/offline-diary-sync.js" %}',
  '{% static "js/offline-draft-queue.js" %}',
  '{% static "js/offline-form-handler.js" %}',
  '{% static "js/offline-form-auto-persist.js" %}?v=' + OFFLINE_FORM_AUTO_PERSIST_VERSION,
  '{% static "js/offline-form-auto-persist.js" %}',
  '{% static "js/offline-global-state.js" %}?v=' + OFFLINE_GLOBAL_STATE_VERSION,
  '{% static "js/offline-global-state.js" %}',
  '{% static "js/offline-monthly-form-detail.js" %}?v=4',
  '{% static "js/offline-monthly-form-detail.js" %}',
  '{% static "js/sw-register.js" %}?v=' + SW_REGISTER_ASSET_VERSION,
  '{% static "js/sw-register.js" %}',
  '{% static "img/logo.png" %}',
  '{% static "img/pwa-icon-192.png" %}',
  '{% static "img/pwa-icon-512.png" %}',
  '{% static "favicon.ico" %}',
  '{% static "robots.txt" %}'
];

async function precacheAppShell() {
  const cache = await caches.open(SHELL_CACHE);

  await Promise.all(
    APP_SHELL_URLS.map(async (url) => {
      try {
        await cache.add(new Request(url, { cache: 'reload' }));
      } catch (error) {
        console.warn('[SW] Precache failed for:', url, error);
      }
    })
  );
}

self.addEventListener('install', (event) => {
  event.waitUntil(precacheAppShell().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then(
        (keys) =>
          Promise.all(
            keys
              .filter((key) => key !== SHELL_CACHE && key !== RUNTIME_CACHE)
              .map((key) => caches.delete(key))
          )
      )
      .then(() => self.clients.claim())
  );
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    if (response && (response.ok || response.type === 'opaque')) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const fallback = await caches.match(request, { ignoreSearch: true });
    if (fallback) {
      return fallback;
    }

    return new Response('Offline resource unavailable. Please reconnect and retry.', {
      status: 503,
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    if (response && (response.ok || response.type === 'opaque')) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }

    return new Response('Offline resource unavailable. Please reconnect and retry.', {
      status: 503,
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  }
}

function getNavigationFallback(pathname) {
  const matched = NAVIGATION_ROUTE_FALLBACKS.find((entry) => pathname.startsWith(entry.prefix));
  return matched ? matched.fallback : OFFLINE_FALLBACK_URL;
}

async function navigationNetworkFirst(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    if (response && (response.ok || response.type === 'opaque')) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request, { ignoreSearch: true });
    if (cached) {
      return cached;
    }

    const requestUrl = new URL(request.url);
    const routeFallbackUrl = getNavigationFallback(requestUrl.pathname);
    const routeFallback = await caches.match(routeFallbackUrl, { ignoreSearch: true });
    if (routeFallback) {
      return routeFallback;
    }

    const offlineFallback = await caches.match(OFFLINE_FALLBACK_URL, { ignoreSearch: true });
    if (offlineFallback) {
      return offlineFallback;
    }

    return new Response('Offline. Please reconnect and retry.', {
      status: 503,
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  }
}

self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);
  const acceptHeader = event.request.headers.get('accept') || '';
  const isApiRequest =
    requestUrl.origin === self.location.origin &&
    (requestUrl.pathname.includes('/api/') || acceptHeader.includes('application/json'));

  if (event.request.method !== 'GET') {
    return;
  }

  // Let API/data requests fail normally when offline so client code can handle fetch errors.
  if (isApiRequest) {
    return;
  }

  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(navigationNetworkFirst(event.request));
    return;
  }

  if (['script', 'style', 'image', 'font'].includes(event.request.destination)) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  if (requestUrl.origin === self.location.origin) {
    event.respondWith(networkFirst(event.request));
  }
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
