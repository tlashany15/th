// Service Worker — تطبيق فريق تحصين الكتاكيت
// النسخة بتتغيّر تلقائي مع أي تعديل في الملف ده (عن طريق SW_VERSION اللي بيحقنها السيرفر)
const SW_VERSION = "__SW_VERSION__";
const CACHE_NAME = "th-app-cache-" + SW_VERSION;

// الحد الأدنى من الملفات اللي لازم تتخزن أول ما التطبيق يتفتح
const PRECACHE_URLS = [
  "/offline",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // ما نتدخلش في POST (تسجيل حضور، شات، إلخ)

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // مش شغالين على روابط خارجية

  // تنقل بين الصفحات (HTML): نجرب الشبكة الأول، ولو النت مقطوع نرجّع صفحة أوفلاين
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("/offline"))
    );
    return;
  }

  // ملفات ثابتة (CSS/JS/صور): كاش الأول وبعدين تحديث في الخلفية
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req)
          .then((res) => {
            if (res && res.ok) {
              const clone = res.clone();
              caches.open(CACHE_NAME).then((c) => c.put(req, clone));
            }
            return res;
          })
          .catch(() => cached);
        return cached || fetchPromise;
      })
    );
  }
});
