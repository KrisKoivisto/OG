const CACHE = "wantneed-v3";
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(["./", "manifest.webmanifest", "icon-180.png", "icon-192.png"])).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
// The page itself: always try for the newest version first, fall back to the saved copy when offline.
// Everything else: saved copy first, refreshed in the background.
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const page = e.request.mode === "navigate";
  e.respondWith(caches.open(CACHE).then(async c => {
    const hit = await c.match(e.request, { ignoreSearch: true });
    const net = fetch(e.request, page ? { cache: "no-store" } : undefined).then(r => { if (r.ok && (r.type === "basic" || r.type === "cors")) c.put(e.request, r.clone()); return r; });
    if (page) return net.catch(() => hit || c.match("./"));
    return hit || net.catch(() => hit);
  }));
});
