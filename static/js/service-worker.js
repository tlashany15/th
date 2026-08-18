// Service Worker — تطبيق فريق تحصين الكتاكيت
// النسخة والإعدادات بتتحقن تلقائيًا من السيرفر (app.py) — متلمسش القيم دي هنا يدويًا.
const SW_VERSION = "__SW_VERSION__";
const CACHE_NAME = "th-app-cache-" + SW_VERSION;

// ==== Firebase Cloud Messaging — استقبال إشعارات والتطبيق مقفول تمامًا ====
importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js");

const FIREBASE_CONFIG = __FIREBASE_CONFIG_JSON__;

try {
  if (FIREBASE_CONFIG && FIREBASE_CONFIG.apiKey) {
    firebase.initializeApp(FIREBASE_CONFIG);
    const messaging = firebase.messaging();
    messaging.onBackgroundMessage(function (payload) {
      const n = (payload && payload.notification) || {};
      const data = (payload && payload.data) || {};
      self.registration.showNotification(n.title || "إشعار جديد", {
        body: n.body || "",
        icon: "/static/icons/icon-192.png",
        badge: "/static/icons/icon-192.png",
        data: { url: data.url || n.click_action || "/notifications" },
      });
    });
  }
} catch (e) {
  // تجاهل صامت لو Firebase مش متظبط لسه
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/notifications";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes(url) && "focus" in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

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
