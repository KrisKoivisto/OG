"""Builds the standalone Want / Need web app in app/ from wantneed.html.

The artifact page and the standalone app share one source. Run this after
changing wantneed.html:  python3 build-app.py
"""
from pathlib import Path

here = Path(__file__).parent
src = (here / "wantneed.html").read_text()
split = src.index('<div class="wrap">')
head, body = src[:split], src[split:]
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Want / Need">
<meta name="theme-color" content="#09090B">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" type="image/png" href="icon-192.png">
<style>:root{{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
{head.strip()}
</head>
<body>
{body.strip()}
</body>
</html>
"""
out = here / "app"
out.mkdir(exist_ok=True)
(out / "index.html").write_text(page)

(out / "manifest.webmanifest").write_text("""{
  "name": "Want / Need",
  "short_name": "Want / Need",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "background_color": "#09090B",
  "theme_color": "#09090B",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
""")

# Offline: serve the app from the phone's cache, refresh it in the background.
(out / "sw.js").write_text("""const CACHE = "wantneed-v1";
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(["./", "manifest.webmanifest", "icon-180.png", "icon-192.png"])).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(caches.open(CACHE).then(async c => {
    const hit = await c.match(e.request, { ignoreSearch: true });
    const net = fetch(e.request).then(r => { if (r.ok && (r.type === "basic" || r.type === "cors")) c.put(e.request, r.clone()); return r; }).catch(() => hit);
    return hit || net;
  }));
});
""")
print("built", out)
