/** 读取当前 URL 中的全部 query（兼容 hash 路由与 location.search） */
export const getLocationQueryParams = (): Record<string, string> => {
  const query: Record<string, string> = {};
  const merge = (source: string) => {
    if (!source) {
      return;
    }
    const search = source.startsWith('?') ? source : `?${source}`;
    new URLSearchParams(search).forEach((value, key) => {
      query[key] = value;
    });
  };
  merge(window.location.search);
  const hashQuery = window.location.hash.includes('?') ? window.location.hash.split('?').slice(1).join('?') : '';
  merge(hashQuery);
  return query;
};