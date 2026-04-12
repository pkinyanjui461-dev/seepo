{% load static %}
const CACHE_NAME = 'seepo-offline-v1';
const APP_SHELL_URLS = [
  '/',
  '/manifest.webmanifest',
  '{% static "js/offline-db.js" %}',
  '{% static "js/offline-sync.js" %}',
  '{% static "js/offline-form-handler.js" %}',
  '{% static "js/sw-register.js" %}',
  '{% static "favicon.ico" %}',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  const response = await fetch(request);
  const cache = await caches.open(CACHE_NAME);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_NAME);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (_error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    throw _error;
  }
}

self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);

  if (event.request.method !== 'GET') {
    return;
  }

  if (requestUrl.pathname.startsWith('/api/sync/')) {
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (['script', 'style', 'image', 'font'].includes(event.request.destination)) {
    event.respondWith(cacheFirst(event.request));
  }
});
