/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
export function rewriteLegacyEntry(requestUrl, base = '/') {
  const url = new URL(requestUrl || '/', 'http://localhost');
  const prefix = base.startsWith('/') ? base.replace(/\/?$/, '/') : '/';
  if (![`${prefix}legacy-v1`, `${prefix}legacy-v1/`].includes(url.pathname)) return requestUrl;
  return `${prefix}legacy-v1/index.html${url.search}`;
}
export function legacyStaticEntry() {
  return {
    name: 'legacy-v1-static-entry',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        request.url = rewriteLegacyEntry(request.url, server.config.base);
        next();
      });
    },
  };
}
