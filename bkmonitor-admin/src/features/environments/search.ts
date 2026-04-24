export function getSearchEnvironmentId(search: object): string | undefined {
  if (!('env' in search)) {
    return undefined;
  }

  return typeof search.env === 'string' ? search.env : undefined;
}

export function getSearchTenantId(search: object): string | undefined {
  if (!('tenant' in search)) {
    return undefined;
  }

  return typeof search.tenant === 'string' ? search.tenant : undefined;
}

export function createEnvironmentSearch(environmentId: string, tenantId: string) {
  return {
    env: environmentId,
    tenant: tenantId
  };
}

export function updateBrowserEnvironmentSearch(
  environmentId: string,
  tenantId: string,
  options: { replace?: boolean } = {}
) {
  if (typeof window === 'undefined') {
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.set('env', environmentId);
  url.searchParams.set('tenant', tenantId);

  const nextUrl = `${url.pathname}${url.search}${url.hash}`;

  if (options.replace) {
    window.history.replaceState(window.history.state, '', nextUrl);
    return;
  }

  window.history.pushState(window.history.state, '', nextUrl);
}
