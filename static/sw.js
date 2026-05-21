const CACHE = 'study-v6';
const API_CACHE = 'study-api-v1';

const PRE_CACHE = [
  '/',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

// Install: pre-cache essentials
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRE_CACHE).catch(() => {}))
  );
});

// Activate: clean old caches, take control
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE && k !== API_CACHE).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

// Fetch: 3-tier strategy
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const isSameOrigin = url.origin === self.location.origin;

  // 1. API responses: cache-with-network-update
  if (isSameOrigin && url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          // Cache successful API responses for offline
          if (res.ok) {
            const clone = res.clone();
            caches.open(API_CACHE).then(c => c.put(e.request, clone));
          }
          return res;
        })
        .catch(() => {
          // Offline: serve from API cache if available
          return caches.match(e.request).then(cached => {
            if (cached) return cached;
            // Return offline indicator for API calls
            return new Response(JSON.stringify({
              offline: true,
              error: '当前离线模式，使用缓存数据'
            }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            });
          });
        })
    );
    return;
  }

  // 2. HTML navigate: network-first (fresh page always)
  if (e.request.mode === 'navigate' || (e.request.method === 'GET' && url.pathname === '/')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          // Cache the HTML for offline
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request).then(cached => cached || caches.match('/')))
    );
    return;
  }

  // 3. Static assets (CSS, JS, images): cache-first
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      if (res.ok) {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return res;
    }))
  );
});

// Listen for skipWaiting message
self.addEventListener('message', e => {
  if (e.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
