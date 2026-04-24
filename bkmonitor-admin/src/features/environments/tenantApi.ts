import { paginationResponseSchema } from '../../shared/schemas/pagination';
import type { AdminEnvironment } from './schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import { z } from 'zod';

export const tenantSummarySchema = z.object({
  id: z.string(),
  name: z.string().optional(),
  display_name: z.string().nullable().optional(),
  source: z.string().optional(),
  datasource_count: z.number().int().min(0).default(0),
  result_table_count: z.number().int().min(0).default(0)
});

export const tenantListResponseSchema = paginationResponseSchema.extend({
  items: z.array(tenantSummarySchema)
});

export type TenantSummary = z.infer<typeof tenantSummarySchema>;
export type TenantListResponse = z.infer<typeof tenantListResponseSchema>;

export async function listTenants(environment: AdminEnvironment): Promise<TenantListResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'tenant.list',
    params: {
      page: 1,
      page_size: 200
    }
  });

  return tenantListResponseSchema.parse(envelope.data);
}
