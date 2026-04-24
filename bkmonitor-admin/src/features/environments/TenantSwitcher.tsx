import { Building2 } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { useNavigate } from '@tanstack/react-router';

import { Select } from '../../shared/components/ui/select';
import { useEnvironmentConfig } from './hooks';
import { useTenantList } from './tenantQueries';

const MANUAL_TENANT_VALUE = '__manual__';

export function TenantSwitcher() {
  const navigate = useNavigate();
  const { currentEnvironment, currentTenantId, setCurrentTenantId } = useEnvironmentConfig();
  const tenantQuery = useTenantList(currentEnvironment);
  const tenants = useMemo(() => tenantQuery.data?.items ?? [], [tenantQuery.data]);
  const hasCurrentTenantOption = tenants.some((tenant) => tenant.id === currentTenantId);
  const selectValue = hasCurrentTenantOption ? currentTenantId : MANUAL_TENANT_VALUE;

  useEffect(() => {
    const firstTenant = tenants[0];

    if (firstTenant && !hasCurrentTenantOption) {
      const envId = currentEnvironment?.id;

      if (envId) {
        setCurrentTenantId(firstTenant.id);
        void navigate({
          to: window.location.pathname,
          search: { env: envId, tenant: firstTenant.id },
          replace: true
        });
      }
    }
  }, [tenants, hasCurrentTenantOption, currentEnvironment?.id, setCurrentTenantId, navigate]);

  return (
    <div className="tenant-switcher">
      <Building2 aria-hidden="true" size={16} />
      <span>当前租户 ID</span>
      <Select
        value={selectValue}
        className="tenant-switcher-select"
        disabled={tenantQuery.isLoading || tenants.length === 0}
        title={tenantQuery.isError ? '租户列表加载失败，可继续手动输入租户 ID' : undefined}
        onChange={(event) => {
          const nextTenantId = event.target.value;

          if (nextTenantId === MANUAL_TENANT_VALUE) {
            return;
          }

          setCurrentTenantId(nextTenantId);
          void navigate({
            to: window.location.pathname,
            search: { env: currentEnvironment?.id, tenant: nextTenantId },
            replace: true
          });
        }}
      >
        {!hasCurrentTenantOption ? (
          <option value={MANUAL_TENANT_VALUE}>{currentTenantId}</option>
        ) : null}
        {tenants.map((tenant) => (
          <option value={tenant.id} key={tenant.id}>
            {getTenantOptionLabel(tenant)}
          </option>
        ))}
      </Select>
    </div>
  );
}

function getTenantOptionLabel(tenant: {
  id?: string | undefined;
  name?: string | undefined;
  display_name?: string | null | undefined;
}) {
  const name = tenant.display_name || tenant.name;

  return name ? `${name} (${tenant.id})` : (tenant.id ?? '');
}
