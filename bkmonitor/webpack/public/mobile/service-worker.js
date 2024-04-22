const cacheVersion = '__cache_version___';
const cacheJsName = 'monitor-cache-js-' + cacheVersion;
const cacheCssName = 'monitor-cache-css-' + cacheVersion;
const cacheFontName = 'monitor-cache-font-' + cacheVersion;
const cacheImgName = 'monitor-cache-img-' + cacheVersion;
const cacheApiName = 'monitor-cache-api-' + cacheVersion;
const cacheList = [cacheJsName, cacheCssName, cacheFontName, cacheImgName];
const staticUrl = '${STATIC_URL}';
// const cacheApiFiles = [
//     '/rest/',
//     '/api/'
// ]
const setCache = (cacheName, request) =>
  caches.open(cacheName).then(cache =>
    cache
      .match(request)
      .then(
        res =>
          res ||
          fetch(request).then(res => {
            cache.put(request.url, res.clone());
            return res;
          }),
      )
      .catch(err => {
        console.error(err);
        return fetch(request)
          .then(res => {
            cache.put(request.url, res.clone());
            return res;
          })
          .catch(err => {
            throw err;
          });
      }),
  );
if (self.importScripts) {
  self.importScripts(staticUrl + 'asset-manifest.js');
  if (self.assetData) {
    self.assetData = self.assetData.map(url => url.replace('__STATIC_URL__', staticUrl));
  }
}
self.addEventListener('error', e => {
  console.log(e);
});

self.addEventListener('install', e => {
  const promiseList = [];
  const cacheJsUtil = caches
    .open(cacheJsName)
    .then(cache => cache.addAll(self.assetData.filter(url => url.match(/\.js$/))));
  promiseList.push(cacheJsUtil);
  const cacheCssUtil = caches
    .open(cacheCssName)
    .then(cache => cache.addAll(self.assetData.filter(url => url.match(/\.css$/))));
  promiseList.push(cacheCssUtil);
  const cacheFontUtil = caches
    .open(cacheFontName)
    .then(cache => cache.addAll(self.assetData.filter(url => url.match(/\.(ttf|woff|eot)$/))));
  promiseList.push(cacheFontUtil);
  const cacheImgUtil = caches
    .open(cacheImgName)
    .then(cache => cache.addAll(self.assetData.filter(url => url.match(/\.(png|jpe?g|gif|svg)$/))));
  promiseList.push(cacheImgUtil);
  caches.keys().then(keys => {
    keys.forEach(key => {
      if (!cacheList.includes(key) && key !== cacheApiName) {
        promiseList.push(caches.delete(key));
      }
    });
  });
  e.waitUntil(
    Promise.all(promiseList).then(() => {
      self.skipWaiting();
    }),
  );
});

self.addEventListener('fetch', e => {
  const requestUrl = e.request.url;
  const needCache =
    requestUrl.match(/\.(css|js|ttf|woff|eot|png|jpe?g|gif|svg)$/) &&
    self.assetData.some(url => requestUrl.includes(url));
  if (needCache) {
    if (requestUrl.match(/\.css$/)) {
      e.respondWith(setCache(cacheCssName, e.request));
    } else if (requestUrl.match(/\.js$/)) {
      e.respondWith(setCache(cacheJsName, e.request));
    } else if (requestUrl.match(/\.(ttf|woff|eot)$/)) {
      e.respondWith(setCache(cacheFontName, e.request));
    } else if (requestUrl.match(/\.(png|jpe?g|gif|svg)$/)) {
      e.respondWith(setCache(cacheImgName, e.request));
    }
  }
  // else if (cacheApiFiles.some(url => requestUrl.includes(url))) {
  //     e.respondWith(
  //         caches.open(cacheApiName).then(cache => {
  //             return fetch(e.request).then(res => {
  //                 cache.put(e.request.url, res.clone())
  //                 return res
  //             })
  //         })
  //     )
  // }
});

self.addEventListener('activate', e => {
  const cacheUtil = caches.keys().then(keys => {
    const promiseList = [];
    keys.forEach(key => {
      if (!cacheList.includes(key) && key !== cacheApiName) {
        promiseList.push(caches.delete(key));
      }
    });
    return Promise.all(promiseList);
  });
  e.waitUntil(
    cacheUtil.then(() => {
      self.clients.claim();
    }),
  );
});

self.addEventListener('redundant', () => {
  console.log('Service Worker 状态： redundant');
});
