/* ============================================
   星衍AI · Service Worker
   离线缓存：页面资源 + 预加载数据
   ============================================ */

const CACHE_NAME = 'xingyan-offline-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.js',
  '/offline-asr.js',
  '/audio-processor.js',
  '/api/departments',
];

// 安装：预缓存静态资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// 请求拦截：网络优先，离线时回退缓存
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // 只处理同源 GET 请求
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }
  
  // API 请求：网络优先，失败时尝试缓存（预加载的离线包）
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // 缓存 GET API 响应（供离线使用）
          if (response.ok && url.pathname.startsWith('/api/offline/package')) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  
  // 静态资源：缓存优先
  event.respondWith(
    caches.match(event.request)
      .then((cached) => {
        if (cached) return cached;
        return fetch(event.request)
          .then((response) => {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            return response;
          })
          .catch(() => caches.match('/index.html'));
      })
  );
});
