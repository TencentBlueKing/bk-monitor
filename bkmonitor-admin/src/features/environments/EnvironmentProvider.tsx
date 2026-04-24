import type { PropsWithChildren } from 'react';
import { createContext, useCallback, useEffect, useMemo, useState } from 'react';

import {
  createEnvironment as createEnvironmentRequest,
  loadAdminConfig,
  removeEnvironment as removeEnvironmentRequest,
  saveEnvironment as saveEnvironmentRequest,
  updateDefaultEnvironment,
  type AdminConfigSource
} from './api';
import { resolveDefaultEnvironmentId } from './configLoader';
import { defaultAdminConfig } from './defaults';
import type { AdminConfig, AdminEnvironment } from './schemas';

interface EnvironmentContextValue {
  config: AdminConfig;
  environments: AdminEnvironment[];
  defaultEnvironmentId: string;
  currentEnvironment: AdminEnvironment | null;
  currentTenantId: string;
  setCurrentEnvironmentId: (environmentId: string) => void;
  setCurrentTenantId: (tenantId: string) => void;
  findEnvironment: (environmentId: string) => AdminEnvironment | null;
  source: AdminConfigSource;
  loading: boolean;
  error: string | null;
  reloadConfig: () => Promise<void>;
  createEnvironment: (environment: AdminEnvironment) => Promise<void>;
  saveEnvironment: (environment: AdminEnvironment) => Promise<void>;
  removeEnvironment: (environmentId: string) => Promise<void>;
  setDefaultEnvironmentId: (environmentId: string) => Promise<void>;
}

export const EnvironmentContext = createContext<EnvironmentContextValue | null>(null);

export function EnvironmentProvider({ children }: PropsWithChildren) {
  const [config, setConfig] = useState<AdminConfig>(defaultAdminConfig);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<AdminConfigSource>('default');
  const [error, setError] = useState<string | null>(null);
  const [currentEnvironmentId, setCurrentEnvironmentId] = useState(
    resolveDefaultEnvironmentId(defaultAdminConfig)
  );
  const [currentTenantId, setCurrentTenantIdState] = useState(() =>
    readTenantId(resolveDefaultEnvironmentId(defaultAdminConfig))
  );

  const applyConfig = useCallback((nextConfig: AdminConfig) => {
    const nextDefaultEnvironmentId = resolveDefaultEnvironmentId(nextConfig);
    setConfig(nextConfig);
    setCurrentEnvironmentId((previous) => {
      const urlEnvironmentId = getUrlEnvironmentId(nextConfig);

      if (urlEnvironmentId) {
        return urlEnvironmentId;
      }

      return nextConfig.environments.some((environment) => environment.id === previous)
        ? previous
        : nextDefaultEnvironmentId;
    });
  }, []);

  const reloadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const loaded = await loadAdminConfig();
      applyConfig(loaded.config);
      setSource(loaded.source);
    } catch (nextError) {
      setError(String(nextError));
      applyConfig(defaultAdminConfig);
      setSource('default');
    } finally {
      setLoading(false);
    }
  }, [applyConfig]);

  useEffect(() => {
    const abortController = new AbortController();
    let mounted = true;

    void loadAdminConfig(abortController.signal)
      .then((loaded) => {
        if (!mounted) {
          return;
        }

        applyConfig(loaded.config);
        setSource(loaded.source);
        setError(null);
      })
      .catch((nextError) => {
        if (!mounted) {
          return;
        }

        setError(String(nextError));
        applyConfig(defaultAdminConfig);
        setSource('default');
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      abortController.abort();
      mounted = false;
    };
  }, [applyConfig]);

  useEffect(() => {
    setCurrentTenantIdState(readTenantId(currentEnvironmentId));
  }, [currentEnvironmentId]);

  const setCurrentTenantId = useCallback(
    (tenantId: string) => {
      const normalizedTenantId = tenantId.trim() || FALLBACK_TENANT_ID;
      setCurrentTenantIdState(normalizedTenantId);
      writeTenantId(currentEnvironmentId, normalizedTenantId);
    },
    [currentEnvironmentId]
  );

  const value = useMemo<EnvironmentContextValue>(() => {
    const findEnvironment = (environmentId: string) =>
      config.environments.find((environment) => environment.id === environmentId) ?? null;

    return {
      config,
      environments: config.environments,
      defaultEnvironmentId: resolveDefaultEnvironmentId(config),
      currentEnvironment: findEnvironment(currentEnvironmentId),
      currentTenantId,
      setCurrentEnvironmentId,
      setCurrentTenantId,
      findEnvironment,
      source,
      loading,
      error,
      reloadConfig,
      createEnvironment: async (environment) => {
        applyConfig(await createEnvironmentRequest(environment));
        setSource('database');
      },
      saveEnvironment: async (environment) => {
        applyConfig(await saveEnvironmentRequest(environment));
        setSource('database');
      },
      removeEnvironment: async (environmentId) => {
        applyConfig(await removeEnvironmentRequest(environmentId));
        setSource('database');
      },
      setDefaultEnvironmentId: async (environmentId) => {
        applyConfig(await updateDefaultEnvironment(environmentId));
        setSource('database');
      }
    };
  }, [
    applyConfig,
    config,
    currentEnvironmentId,
    currentTenantId,
    error,
    loading,
    reloadConfig,
    setCurrentTenantId,
    source
  ]);

  return <EnvironmentContext.Provider value={value}>{children}</EnvironmentContext.Provider>;
}

const FALLBACK_TENANT_ID = 'system';

function getTenantStorageKey(environmentId: string) {
  return `bkmonitor-admin:tenant:${environmentId || 'default'}`;
}

function readTenantId(environmentId: string) {
  if (!environmentId || typeof window === 'undefined') {
    return FALLBACK_TENANT_ID;
  }

  return window.localStorage.getItem(getTenantStorageKey(environmentId)) || FALLBACK_TENANT_ID;
}

function getUrlEnvironmentId(config: AdminConfig): string | undefined {
  if (typeof window === 'undefined') {
    return undefined;
  }

  const env = new URL(window.location.href).searchParams.get('env');

  if (env && config.environments.some((e) => e.id === env)) {
    return env;
  }

  return undefined;
}

function writeTenantId(environmentId: string, tenantId: string) {
  if (!environmentId || typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(getTenantStorageKey(environmentId), tenantId);
}
