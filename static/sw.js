/* sw.js — كاش ذكي عشان التنقل يبقى فوري والتطبيق ما يرجعش من الأول لما النت يفصل */
const VERSION = 'th-v4';
const SHELL = 'shell-' + VERSION;
const PAGES = 'pages-' + VERSION;

const STATIC_RE = /\/static\/.+\.(css|js|png|jpg|jpeg|svg|webp|woff2?|ico)$/i;
// صفحات آمنة بس اللي بتتخزن — أي صفحة تانية بتتجاب من الشبكة على طول
const CACHEABLE_PAGES = ['/dashboard', '/history', '/chats', '/group', '/notifications', '/me/profile'];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(['/offline']).catch(() => {})));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !k.endsWith(VERSION)).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // ملفات ثابتة: من الكاش فورًا (stale-while-revalidate)
  if (STATIC_RE.test(url.pathname)) {
    event.respondWith(
      caches.open(SHELL).then(async (cache) => {
        const hit = await cache.match(req);
        const net = fetch(req).then((res) => {
          if (res && res.ok) cache.put(req, res.clone());
          return res;
        }).catch(() => hit);
        return hit || net;
      })
    );
    return;
  }

  // صفحات: الشبكة الأول، ولو فشلت نرجّع آخر نسخة متخزنة (مش من الأول)
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    if (!CACHEABLE_PAGES.includes(url.pathname) || url.search) return;
    event.respondWith(
      fetch(req).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(PAGES).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(async () => {
        const cached = await caches.match(req, { ignoreSearch: false });
        return cached || (await caches.match('/offline')) ||
          new Response('<h1 dir="rtl">مفيش نت</h1>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      })
    );
  }
});
