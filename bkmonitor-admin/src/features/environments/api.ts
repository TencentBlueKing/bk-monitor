import { defaultAdminConfig } from './defaults';
import { adminConfigSchema, type AdminConfig, type AdminEnvironment } from './schemas';

export type AdminConfigSource = 'database' | 'file' | 'default';

export interface LoadedAdminConfig {
  config: AdminConfig;
  source: AdminConfigSource;
}

export async function loadAdminConfig(signal?: AbortSignal): Promise<LoadedAdminConfig> {
  const databaseConfig = await fetchAdminApiConfig(signal);

  if (databaseConfig) {
    return { config: databaseConfig, source: 'database' };
  }

  const fileConfig = await fetchFileConfig(signal);

  if (fileConfig) {
    return { config: fileConfig, source: 'file' };
  }

  return { config: defaultAdminConfig, source: 'default' };
}

export async function saveEnvironment(environment: AdminEnvironment): Promise<AdminConfig> {
  return requestAdminConfig(`/admin-api/environments/${encodeURIComponent(environment.id)}`, {
    method: 'PUT',
    body: JSON.stringify(environment)
  });
}

export async function createEnvironment(environment: AdminEnvironment): Promise<AdminConfig> {
  return requestAdminConfig('/admin-api/environments', {
    method: 'POST',
    body: JSON.stringify(environment)
  });
}

export async function removeEnvironment(environmentId: string): Promise<AdminConfig> {
  return requestAdminConfig(`/admin-api/environments/${encodeURIComponent(environmentId)}`, {
    method: 'DELETE'
  });
}

export async function updateDefaultEnvironment(environmentId: string): Promise<AdminConfig> {
  return requestAdminConfig('/admin-api/config/default-environment', {
    method: 'PATCH',
    body: JSON.stringify({ environmentId })
  });
}

async function fetchAdminApiConfig(signal?: AbortSignal): Promise<AdminConfig | null> {
  try {
    return await requestAdminConfig('/admin-api/config', signal ? { signal } : {});
  } catch {
    return null;
  }
}

async function fetchFileConfig(signal?: AbortSignal): Promise<AdminConfig | null> {
  try {
    const response = await fetch('/admin-config.json', {
      ...(signal ? { signal } : {}),
      headers: { Accept: 'application/json' }
    });

    if (!response.ok) {
      return null;
    }

    return parseAdminConfig(await response.json());
  } catch {
    return null;
  }
}

async function requestAdminConfig(path: string, init: RequestInit = {}): Promise<AdminConfig> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...init.headers
    }
  });
  const payload: unknown = await response.json();

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.statusText));
  }

  return parseAdminConfig(payload);
}

function parseAdminConfig(payload: unknown): AdminConfig {
  const parsed = adminConfigSchema.safeParse(payload);

  if (!parsed.success) {
    throw new Error('环境配置响应不符合协议');
  }

  return parsed.data;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'message' in payload) {
    return String(payload.message);
  }

  return fallback || '环境配置接口请求失败';
}
