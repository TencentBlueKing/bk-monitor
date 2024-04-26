const staticUrl = '${STATIC_URL}monitor/';
const cacheNames = {
  js: `monitor-cache-js-__cache_version___`,
  css: `monitor-cache-css-__cache_version___`,
  font: `monitor-cache-font-__cache_version___`,
  img: `monitor-cache-img-__cache_version___`,
  api: `monitor-cache-api-__cache_version___`,
};
const cacheList = Object.keys(cacheNames).map(key => cacheNames[key]);

const setCache = (cacheName, request) =>
  caches.open(cacheName).then(cache =>
    cache.match(request).then(
      response =>
        response ||
        fetch(request).then(res => {
          cache.put(request.url, res.clone());
          return res;
        }),
    ),
  );

if (self.importScripts) {
  self.importScripts(staticUrl + 'asset-manifest.js');
  if (self.assetData) {
    self.assetData = self.assetData.map(url => url.replace('__STATIC_URL__', staticUrl));
  }
}

self.addEventListener('install', e => {
  const cacheResources = (type, pattern) =>
    caches.open(cacheNames[type]).then(cache => {
      const assets = self.assetData.filter(url => url.match(pattern));
      return cache.addAll(assets);
    });

  const promiseList = [
    cacheResources('js', /\.js$/),
    cacheResources('css', /\.css$/),
    cacheResources('font', /\.(ttf|woff|eot)$/),
    cacheResources('img', /\.(png|jpe?g|gif|svg)$/),
  ];

  e.waitUntil(Promise.all(promiseList).then(() => self.skipWaiting()));
});

self.addEventListener('fetch', e => {
  const requestUrl = e.request.url;
  const needCache =
    /\.(css|js|ttf|woff|eot|png|jpe?g|gif|svg)$/.test(requestUrl) &&
    self.assetData.some(url => requestUrl.includes(url));

  if (needCache) {
    const type = Object.keys(cacheNames).find(key => requestUrl.match(new RegExp('\\.' + key)));
    e.respondWith(setCache(cacheNames[type], e.request));
  }
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.map(key => {
          if (!cacheList.includes(key) && key !== cacheNames.api) {
            return caches.delete(key);
          }
        }),
      ).then(() => self.clients.claim()),
    ),
  );
});
