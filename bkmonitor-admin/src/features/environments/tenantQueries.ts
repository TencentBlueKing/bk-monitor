import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from './schemas';
import { listTenants } from './tenantApi';

export function useTenantList(environment: AdminEnvironment | null) {
  return useQuery({
    queryKey: ['tenant', environment?.id, environment, 'list'],
    queryFn: () => listTenants(environment!),
    enabled: Boolean(environment)
  });
}
