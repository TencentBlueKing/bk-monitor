interface UserRecord { username: string; display_name?: string }
interface LookupResponse { code?: number; data?: { results?: UserRecord[] }; results?: UserRecord[] }
type LookupParams = { app_code: string; exact_lookups: string; page_size: number; page: number };
type LookupRequest = (api: string, params: LookupParams, signal?: AbortSignal) => Promise<LookupResponse>;
let sequence = 0;

/** Existing legacy directory protocol, retained for validated Enter selection. */
const jsonp: LookupRequest = (api, params, signal) => new Promise((resolve, reject) => {
  const url = new URL(api, document.baseURI);
  const callback = `__bklog_user_lookup_${++sequence}`;
  const callbacks = window as unknown as Record<string, unknown>;
  const script = document.createElement('script');
  let timer: ReturnType<typeof setTimeout> | undefined;
  const cleanup = () => { clearTimeout(timer); script.remove(); delete callbacks[callback]; signal?.removeEventListener('abort', abort); };
  const abort = () => { cleanup(); reject(new DOMException('Aborted', 'AbortError')); };
  if (signal?.aborted) { abort(); return; }
  callbacks[callback] = (response: LookupResponse) => { cleanup(); resolve(response); };
  script.onerror = () => { cleanup(); reject(new Error('User lookup failed')); };
  Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, String(value)));
  url.searchParams.set('callback', callback);
  script.src = url.href;
  signal?.addEventListener('abort', abort, { once: true });
  timer = setTimeout(() => { cleanup(); reject(new Error('User lookup timed out')); }, 120000);
  document.head.appendChild(script);
});

export async function lookupLegacyUsernames(api: string, usernames: string[], signal?: AbortSignal, request: LookupRequest = jsonp) {
  if (!api) return [];
  const unique = [...new Set(usernames.map(name => name.trim()).filter(Boolean))];
  const batches: Promise<LookupResponse>[] = [];
  for (let start = 0; start < unique.length; start += 100) {
    batches.push(request(api, { app_code: 'bk-magicbox', exact_lookups: unique.slice(start, start + 100).join(','), page_size: 100, page: 1 }, signal));
  }
  const records = (await Promise.all(batches)).flatMap(response =>
    response.code !== undefined && response.code !== 0 ? [] : response.data?.results ?? response.results ?? []);
  const found = new Set(records.map(user => user.username));
  return unique.filter(username => found.has(username));
}
