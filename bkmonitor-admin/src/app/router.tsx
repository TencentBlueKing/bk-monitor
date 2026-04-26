import {
  Link,
  Navigate,
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useSearch
} from '@tanstack/react-router';
import { Database, Globe, HardDrive, Network, Settings2, Table2, Wrench } from 'lucide-react';
import { useEffect } from 'react';

import { ElasticsearchIcon, KubernetesIcon } from '../shared/components/BrandIcons';
import { EnvironmentGuard } from '../features/environments/EnvironmentGuard';
import { EnvironmentSettingsPage } from '../features/environments/EnvironmentSettingsPage';
import { EnvironmentSwitcher } from '../features/environments/EnvironmentSwitcher';
import { TenantSwitcher } from '../features/environments/TenantSwitcher';
import { useEnvironmentConfig } from '../features/environments/hooks';
import {
  createEnvironmentSearch,
  getSearchEnvironmentId,
  getSearchTenantId,
  updateBrowserEnvironmentSearch
} from '../features/environments/search';
import { DataSourceDetailPage } from '../features/datasource/DataSourceDetailPage';
import { DataSourceListPage } from '../features/datasource/DataSourceListPage';
import { EsStorageDetailPage } from '../features/es-storage/EsStorageDetailPage';
import { EsStorageListPage } from '../features/es-storage/EsStorageListPage';
import { ResultTableDetailPage } from '../features/result-table/ResultTableDetailPage';
import { ResultTableListPage } from '../features/result-table/ResultTableListPage';
import { ClusterInfoListPage } from '../features/cluster-info/ClusterInfoListPage';
import { ClusterInfoDetailPage } from '../features/cluster-info/ClusterInfoDetailPage';
import { BCSClusterInfoListPage } from '../features/bcs-cluster/BCSClusterInfoListPage';
import { BCSClusterInfoDetailPage } from '../features/bcs-cluster/BCSClusterInfoDetailPage';
import { DataLinkDetailPage } from '../features/datalink/DataLinkDetailPage';
import { DataLinkListPage } from '../features/datalink/DataLinkListPage';
import { QueryRouteDetailPage } from '../features/query-route/QueryRouteDetailPage';
import { QueryRoutePage } from '../features/query-route/QueryRoutePage';
import { BrandLogo } from '../shared/components/BrandLogo';
import {
  hasReturnTargetInSearch,
  migrateReturnTargetFromSearch
} from '../shared/navigation/returnTarget';

function RootLayout() {
  const { defaultEnvironmentId } = useEnvironmentConfig();

  return (
    <>
      <Outlet />
      <div className="sr-only" data-testid="default-environment">
        {defaultEnvironmentId}
      </div>
    </>
  );
}

function HomeRedirect() {
  const { currentTenantId, defaultEnvironmentId, environments, loading } = useEnvironmentConfig();

  if (loading) {
    return <div className="setup-shell">正在加载环境配置...</div>;
  }

  if (environments.length === 0 || !defaultEnvironmentId) {
    return <Navigate to="/settings/environments" />;
  }

  return (
    <Navigate
      to="/datasources"
      search={createEnvironmentSearch(defaultEnvironmentId, currentTenantId)}
    />
  );
}

function AppLayout() {
  const search = useSearch({ strict: false });
  const {
    currentEnvironment,
    currentTenantId,
    defaultEnvironmentId,
    environments,
    findEnvironment,
    loading,
    setCurrentEnvironmentId,
    setCurrentTenantId
  } = useEnvironmentConfig();
  const searchEnvironmentId = getSearchEnvironmentId(search);
  const searchTenantId = getSearchTenantId(search);
  const searchEnvironment = searchEnvironmentId ? findEnvironment(searchEnvironmentId) : null;
  const environment = searchEnvironment ?? currentEnvironment;
  const activeEnvironmentId = searchEnvironmentId ?? environment?.id ?? defaultEnvironmentId;
  const activeTenantId = searchTenantId ?? currentTenantId;

  useEffect(() => {
    if (searchEnvironment) {
      setCurrentEnvironmentId(searchEnvironment.id);
    }
  }, [searchEnvironment, setCurrentEnvironmentId]);

  useEffect(() => {
    if (searchTenantId && searchTenantId !== currentTenantId) {
      setCurrentTenantId(searchTenantId);
    }
  }, [currentTenantId, searchTenantId, setCurrentTenantId]);

  useEffect(() => {
    if (!activeEnvironmentId || searchTenantId) {
      return;
    }

    updateBrowserEnvironmentSearch(activeEnvironmentId, currentTenantId, { replace: true });
  }, [activeEnvironmentId, currentTenantId, searchTenantId]);

  useEffect(() => {
    if (typeof window === 'undefined' || !hasReturnTargetInSearch(search)) {
      return;
    }

    migrateReturnTargetFromSearch(window.location.pathname, search);
  }, [search]);

  if (loading) {
    return <div className="setup-shell">正在加载环境配置...</div>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="资源导航">
        <BrandLogo />
        <div className="sidebar-selectors">
          {environments.length > 0 ? <EnvironmentSwitcher /> : null}
          {environment ? <TenantSwitcher /> : null}
        </div>
        <nav className="nav-list">
          <div className="nav-section">
            <div className="nav-section-title">资源管理</div>
            <div className="nav-section-items">
              <Link
                to="/data-links"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <Network aria-hidden="true" size={18} />
                DataLink
              </Link>
              <Link
                to="/datasources"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <Database aria-hidden="true" size={18} />
                DataSource
              </Link>
              <Link
                to="/result-tables"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <Table2 aria-hidden="true" size={18} />
                ResultTable
              </Link>
              <Link
                to="/clusters"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <HardDrive aria-hidden="true" size={18} />
                存储集群
              </Link>
              <Link
                to="/es-storages"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <ElasticsearchIcon size={18} aria-hidden="true" />
                ESStorage
              </Link>
              <Link
                to="/bcs-clusters"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <KubernetesIcon size={18} aria-hidden="true" />
                BCS集群
              </Link>
            </div>
          </div>
          <div className="nav-section">
            <div className="nav-section-title">诊断工具</div>
            <div className="nav-section-items">
              <Link
                to="/query-route"
                search={createEnvironmentSearch(activeEnvironmentId, activeTenantId)}
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <Wrench aria-hidden="true" size={18} />
                查询路由
              </Link>
            </div>
          </div>
          <div className="nav-section">
            <div className="nav-section-title">系统设置</div>
            <div className="nav-section-items">
              <Link
                to="/settings/environments"
                search={
                  activeEnvironmentId
                    ? createEnvironmentSearch(activeEnvironmentId, activeTenantId)
                    : {}
                }
                activeProps={{ className: 'nav-link active' }}
                inactiveProps={{ className: 'nav-link' }}
              >
                <Settings2 aria-hidden="true" size={18} />
                环境配置
              </Link>
            </div>
          </div>
        </nav>
      </aside>
      <main className="content-shell">
        <Outlet />
      </main>
    </div>
  );
}

function GuardedDataSourceListPage() {
  return <EnvironmentGuard>{() => <DataSourceListPage />}</EnvironmentGuard>;
}

function GuardedDataSourceDetailPage() {
  return <EnvironmentGuard>{() => <DataSourceDetailPage />}</EnvironmentGuard>;
}

function GuardedResultTableListPage() {
  return <EnvironmentGuard>{() => <ResultTableListPage />}</EnvironmentGuard>;
}

function GuardedResultTableDetailPage() {
  return <EnvironmentGuard>{() => <ResultTableDetailPage />}</EnvironmentGuard>;
}

function GuardedEsStorageListPage() {
  return <EnvironmentGuard>{() => <EsStorageListPage />}</EnvironmentGuard>;
}

function GuardedEsStorageDetailPage() {
  return <EnvironmentGuard>{() => <EsStorageDetailPage />}</EnvironmentGuard>;
}

function GuardedClusterInfoListPage() {
  return <EnvironmentGuard>{() => <ClusterInfoListPage />}</EnvironmentGuard>;
}

function GuardedClusterInfoDetailPage() {
  return <EnvironmentGuard>{() => <ClusterInfoDetailPage />}</EnvironmentGuard>;
}

function GuardedBCSClusterInfoListPage() {
  return <EnvironmentGuard>{() => <BCSClusterInfoListPage />}</EnvironmentGuard>;
}

function GuardedBCSClusterInfoDetailPage() {
  return <EnvironmentGuard>{() => <BCSClusterInfoDetailPage />}</EnvironmentGuard>;
}

function GuardedDataLinkListPage() {
  return <EnvironmentGuard>{() => <DataLinkListPage />}</EnvironmentGuard>;
}

function GuardedDataLinkDetailPage() {
  return <EnvironmentGuard>{() => <DataLinkDetailPage />}</EnvironmentGuard>;
}

function GuardedQueryRoutePage() {
  return <EnvironmentGuard>{() => <QueryRoutePage />}</EnvironmentGuard>;
}

function GuardedQueryRouteDetailPage() {
  return <EnvironmentGuard>{() => <QueryRouteDetailPage />}</EnvironmentGuard>;
}

const rootRoute = createRootRoute({
  component: RootLayout
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HomeRedirect
});

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'app',
  component: AppLayout
});

const settingsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'settings'
});

const standaloneEnvironmentSettingsRoute = createRoute({
  getParentRoute: () => settingsRoute,
  path: 'environments',
  component: EnvironmentSettingsPage
});

const datasourceListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'datasources',
  component: GuardedDataSourceListPage
});

const datasourceDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'datasources/$bkDataId',
  component: GuardedDataSourceDetailPage
});

const resultTableListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'result-tables',
  component: GuardedResultTableListPage
});

const resultTableDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'result-tables/$tableId',
  component: GuardedResultTableDetailPage
});

const esStorageListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'es-storages',
  component: GuardedEsStorageListPage
});

const esStorageDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'es-storages/$tableId',
  component: GuardedEsStorageDetailPage
});

const clusterInfoListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'clusters',
  component: GuardedClusterInfoListPage
});

const clusterInfoDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'clusters/$clusterId',
  component: GuardedClusterInfoDetailPage
});

const bcsClusterListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'bcs-clusters',
  component: GuardedBCSClusterInfoListPage
});

const bcsClusterDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'bcs-clusters/$clusterId',
  component: GuardedBCSClusterInfoDetailPage
});

const queryRouteRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'query-route',
  component: GuardedQueryRoutePage
});

const queryRouteDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'query-route/$tableId',
  component: GuardedQueryRouteDetailPage
});

const dataLinkListRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'data-links',
  component: GuardedDataLinkListPage
});

const dataLinkDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: 'data-links/detail',
  component: GuardedDataLinkDetailPage
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  appRoute.addChildren([
    settingsRoute.addChildren([standaloneEnvironmentSettingsRoute]),
    datasourceListRoute,
    datasourceDetailRoute,
    resultTableListRoute,
    resultTableDetailRoute,
    esStorageListRoute,
    esStorageDetailRoute,
    clusterInfoListRoute,
    clusterInfoDetailRoute,
    bcsClusterListRoute,
    bcsClusterDetailRoute,
    queryRouteRoute,
    queryRouteDetailRoute,
    dataLinkListRoute,
    dataLinkDetailRoute
  ])
]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
