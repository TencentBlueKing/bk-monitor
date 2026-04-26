import { Building2 } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from '@tanstack/react-router';

import { ChoiceInput } from '../../shared/components/ChoiceInput';
import { useEnvironmentConfig } from './hooks';
import { useTenantList } from './tenantQueries';

const MANUAL_TENANT_VALUE = '__manual__';

export function TenantSwitcher() {
  const navigate = useNavigate();
  const location = useLocation();
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
          to: location.pathname,
          search: (prev) => ({ ...prev, tenant: firstTenant.id }),
          replace: true
        });
      }
    }
  }, [
    tenants,
    hasCurrentTenantOption,
    currentEnvironment?.id,
    setCurrentTenantId,
    navigate,
    location.pathname
  ]);

  return (
    <div className="tenant-switcher">
      <Building2 aria-hidden="true" size={16} />
      <span>租户</span>
      <ChoiceInput
        value={selectValue}
        className="tenant-switcher-select"
        disabled={tenantQuery.isLoading || tenants.length === 0}
        ariaLabel="切换租户"
        options={[
          ...(!hasCurrentTenantOption
            ? [{ label: currentTenantId, value: MANUAL_TENANT_VALUE }]
            : []),
          ...tenants.map((tenant) => ({
            label: getTenantOptionLabel(tenant),
            value: tenant.id ?? ''
          }))
        ].filter((option) => option.value)}
        onChange={(value) => {
          const nextTenantId = Array.isArray(value) ? value[0] : value;

          if (!nextTenantId || nextTenantId === MANUAL_TENANT_VALUE) {
            return;
          }

          setCurrentTenantId(nextTenantId);
          void navigate({
            to: location.pathname,
            search: (prev) => ({ ...prev, tenant: nextTenantId }),
            replace: true
          });
        }}
      />
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
