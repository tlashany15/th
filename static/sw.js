/* sw.js — نسخة إلغاء (kill-switch)
 * الإصدارات القديمة كانت بتخزّن صفحات HTML (ومنها صفحة خطأ مؤقتة) وتفضل تعرضها
 * حتى بعد ما السيرفر يرجع طبيعي. الملف ده بيمسح كل الكاش ويشيل نفسه من المتصفح.
 */
self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach((c) => c.navigate(c.url));
  })());
});

// من غير أي اعتراض للطلبات — كل حاجة من الشبكة مباشرة
