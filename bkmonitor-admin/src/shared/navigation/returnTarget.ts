export interface ReturnTarget {
  href: string;
  label: string;
}

const ephemeralReturnTargets = new Map<string, ReturnTarget>();

export function buildHref(pathname: string, search: Record<string, unknown>) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(search)) {
    if (key === 'returnTo' || key === 'returnLabel') {
      continue;
    }
    if (value === undefined || value === null || value === '') {
      continue;
    }
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      params.set(key, String(value));
    }
  }

  const searchText = params.toString();
  return searchText ? `${pathname}?${searchText}` : pathname;
}

export function rememberReturnTarget(targetHref: string, returnTarget: ReturnTarget) {
  ephemeralReturnTargets.set(targetHref, returnTarget);
}

export function getStoredReturnTarget(
  currentHref: string,
  fallbackHref: string,
  fallbackLabel: string
): ReturnTarget {
  return (
    ephemeralReturnTargets.get(currentHref) ?? {
      href: fallbackHref,
      label: fallbackLabel
    }
  );
}

export function getOptionalStoredReturnTarget(currentHref: string): ReturnTarget | null {
  return ephemeralReturnTargets.get(currentHref) ?? null;
}

export function migrateReturnTargetFromSearch(
  currentPathname: string,
  search: object
): ReturnTarget | null {
  const returnTo = normalizeSearchString(getSearchValue(search, 'returnTo'));
  const returnLabel = normalizeSearchString(getSearchValue(search, 'returnLabel'));
  if (!returnTo || !returnTo.startsWith('/')) {
    return null;
  }

  const target = { href: returnTo, label: returnLabel || '上一页' };
  const cleanHref = buildHref(currentPathname, omitReturnTarget(search));
  rememberReturnTarget(cleanHref, target);

  if (typeof window !== 'undefined') {
    window.history.replaceState(window.history.state, '', cleanHref);
  }

  return target;
}

export function omitReturnTarget(search: object): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(search)) {
    if (key === 'returnTo' || key === 'returnLabel') {
      continue;
    }
    result[key] = value;
  }
  return result;
}

export function hasReturnTargetInSearch(search: object) {
  return Boolean(getSearchValue(search, 'returnTo') || getSearchValue(search, 'returnLabel'));
}

function getSearchValue(search: object, key: string): unknown {
  if (!(key in search)) {
    return undefined;
  }
  return search[key as keyof typeof search];
}

function normalizeSearchString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      return typeof parsed === 'string' ? parsed : trimmed;
    } catch {
      return trimmed;
    }
  }

  return trimmed;
}
