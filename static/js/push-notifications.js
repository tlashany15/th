// تفعيل إشعارات المتصفح (Web Push عن طريق Firebase Cloud Messaging)
(function () {
  "use strict";

  var STORAGE_KEY = "th_push_dismissed"; // لو المستخدم قفل البانر يدويًا
  var cfg = window.FIREBASE_CONFIG;
  var vapidKey = window.FIREBASE_VAPID_KEY;

  function configReady() {
    return !!(cfg && cfg.apiKey && vapidKey);
  }

  function supported() {
    return "serviceWorker" in navigator && "Notification" in window && configReady();
  }

  function dismissed() {
    try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch (e) { return false; }
  }

  function dismiss() {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch (e) {}
    var el = document.getElementById("th-push-banner");
    if (el) el.remove();
  }

  function showBanner() {
    if (document.getElementById("th-push-banner")) return;
    var bar = document.createElement("div");
    bar.id = "th-push-banner";
    bar.innerHTML =
      '<div class="th-push-inner">' +
      '  <span class="th-push-icon">' +
      '    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="20" height="20">' +
      '      <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>' +
      '    </svg>' +
      '  </span>' +
      '  <span class="th-push-text">فعّل الإشعارات عشان توصلك الرسايل حتى لو التطبيق قافل</span>' +
      '  <button type="button" class="th-push-btn" id="th-push-enable">تفعيل</button>' +
      '  <button type="button" class="th-push-close" id="th-push-close" aria-label="إغلاق">×</button>' +
      '</div>';
    document.body.appendChild(bar);
    document.getElementById("th-push-enable").addEventListener("click", enable);
    document.getElementById("th-push-close").addEventListener("click", dismiss);
  }

  function registerToken(token) {
    var body = new URLSearchParams();
    body.set("token", token);
    body.set("platform", "web");
    return fetch("/api/fcm/register", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
  }

  function enable() {
    if (!("Notification" in window)) return;
    Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") { dismiss(); return; }
      navigator.serviceWorker.ready.then(function (reg) {
        firebase.messaging().getToken({ vapidKey: vapidKey, serviceWorkerRegistration: reg })
          .then(function (token) {
            if (token) { registerToken(token).then(dismiss).catch(dismiss); }
            else { dismiss(); }
          })
          .catch(function () { dismiss(); });
      });
    });
  }

  function init() {
    if (!supported()) return;
    if (dismissed()) return;
    if (Notification.permission === "denied") return;
    if (window.firebase && !firebase.apps.length) {
      firebase.initializeApp(cfg);
    }
    if (Notification.permission === "granted") {
      // مفعّل بالفعل — نتأكد إن التوكن مسجّل من غير ما نضايق المستخدم ببانر
      navigator.serviceWorker.ready.then(function (reg) {
        try {
          firebase.messaging().getToken({ vapidKey: vapidKey, serviceWorkerRegistration: reg })
            .then(function (token) { if (token) registerToken(token); })
            .catch(function () {});
        } catch (e) {}
      });
      // استقبال إشعار والتطبيق مفتوح قدامك (foreground)
      try {
        firebase.messaging().onMessage(function (payload) {
          var n = (payload && payload.notification) || {};
          if (Notification.permission === "granted" && n.title) {
            new Notification(n.title, {
              body: n.body || "",
              icon: "/static/icons/icon-192.png",
            });
          }
        });
      } catch (e) {}
      return;
    }
    // لسه ماسألناش
    showBanner();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
