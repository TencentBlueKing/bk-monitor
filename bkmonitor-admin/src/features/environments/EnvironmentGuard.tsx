import { Navigate, useSearch } from '@tanstack/react-router';
import type { ReactNode } from 'react';
import { useEffect } from 'react';

import { useEnvironmentConfig } from './hooks';
import type { AdminEnvironment } from './schemas';
import { createEnvironmentSearch, getSearchEnvironmentId, getSearchTenantId } from './search';

interface EnvironmentGuardProps {
  children: (context: { environment: AdminEnvironment }) => ReactNode;
}

export function EnvironmentGuard({ children }: EnvironmentGuardProps) {
  const search = useSearch({ strict: false });
  const {
    defaultEnvironmentId,
    environments,
    findEnvironment,
    loading,
    setCurrentEnvironmentId,
    setCurrentTenantId,
    currentTenantId,
    currentEnvironment
  } = useEnvironmentConfig();
  const routeEnvironmentId = getSearchEnvironmentId(search) ?? defaultEnvironmentId;
  const routeTenantId = getSearchTenantId(search) ?? currentTenantId;
  const environment = findEnvironment(routeEnvironmentId);

  useEffect(() => {
    if (environment) {
      setCurrentEnvironmentId(environment.id);
    }
  }, [environment, setCurrentEnvironmentId]);

  useEffect(() => {
    if (routeTenantId !== currentTenantId) {
      setCurrentTenantId(routeTenantId);
    }
  }, [currentTenantId, routeTenantId, setCurrentTenantId]);

  if (loading) {
    return <div className="page-state">正在加载环境配置...</div>;
  }

  if (environments.length === 0 || !defaultEnvironmentId) {
    return <Navigate to="/settings/environments" />;
  }

  if (!environment) {
    return (
      <Navigate
        to="/datasources"
        search={createEnvironmentSearch(defaultEnvironmentId, routeTenantId)}
      />
    );
  }

  return children({ environment: currentEnvironment ?? environment });
}
