// Keeps the page, its scripts and the maps on the phone, so a game can still
// be scored when Home Assistant can't be reached (photo reading needs it).
// Network first, so updates show up straight away when online.
const CACHE = "ttr-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
        }
        return resp;
      })
      .catch(() => caches.match(req).then((hit) => hit || Promise.reject(new Error("offline"))))
  );
});
