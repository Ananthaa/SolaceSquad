const CACHE_NAME = 'soulsquad-v18';
const STATIC_ASSETS = [
    '/manifest.json',
    '/static/css/styles.css?v=18',
    '/static/js/main.js',
    '/static/images/logo.png'
];

// Authenticated routes — NEVER cache these
const AUTH_PREFIXES = ['/app/', '/consultant/', '/admin/', '/api/'];
function isAuthRoute(url) {
    const path = new URL(url).pathname;
    return AUTH_PREFIXES.some(p => path.startsWith(p));
}

// Install: cache static assets only
self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS).catch(err => console.error(err)))
    );
});

// Fetch strategy:
// - Auth/API routes → always network, never cache
// - HTML navigation → network-first (cache only public pages as offline fallback)
// - Static assets → cache-first
self.addEventListener('fetch', event => {
    const req = event.request;
    const url = req.url;

    // Auth & API routes: always go to network, never serve from cache
    if (isAuthRoute(url)) {
        event.respondWith(fetch(req));
        return;
    }

    // HTML navigation (public pages only): network-first, cache as offline fallback
    if (req.mode === 'navigate' || req.headers.get('Accept')?.includes('text/html')) {
        event.respondWith(
            fetch(req)
                .then(response => {
                    // Only cache public pages (non-auth)
                    if (response.ok && !isAuthRoute(url)) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(req, clone));
                    }
                    return response;
                })
                .catch(() => caches.match(req)) // offline fallback for public pages
        );
        return;
    }

    // Static assets: cache-first
    event.respondWith(
        caches.match(req).then(cached => cached || fetch(req))
    );
});

// Activate: delete old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});
