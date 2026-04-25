import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';

export const bcsClusterSummarySchema = z.object({
  cluster_id: z.string(),
  bcs_api_cluster_id: z.string().nullable().optional(),
  bk_biz_id: z.number().nullable().optional(),
  project_id: z.string().nullable().optional(),
  status: z.string(),
  bk_env: z.string().nullable().optional(),
  K8sMetricDataID: z.number().optional(),
  CustomMetricDataID: z.number().optional(),
  K8sEventDataID: z.number().optional(),
  CustomEventDataID: z.number().optional(),
  SystemLogDataID: z.number().optional(),
  CustomLogDataID: z.number().optional(),
  operator_ns: z.string().nullable().optional(),
  trace_data_id: z.number().optional(),
  create_time: z.string().nullable().optional(),
  last_modify_time: z.string().nullable().optional()
});

export const bcsClusterListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  clusterId: z.string().optional(),
  bkBizId: z.preprocess((val) => {
    if (val === undefined || val === null || val === '') return undefined;
    const num = typeof val === 'number' ? val : Number(val);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().optional()),
  status: z.string().optional()
});

export const bcsClusterDetailResponseSchema = z.object({
  cluster: bcsClusterSummarySchema.extend({
    domain_name: z.string().nullable().optional(),
    port: z.number().nullable().optional(),
    server_address_path: z.string().nullable().optional(),
    api_key_type: z.string().nullable().optional(),
    has_api_key: z.boolean().optional(),
    is_skip_ssl_verify: z.boolean().optional()
  }),
  datasource_summaries: z
    .array(
      z.object({
        bk_data_id: z.number(),
        data_name: z.string(),
        data_description: z.string().nullable().optional(),
        source_label: z.string(),
        type_label: z.string(),
        is_enable: z.boolean()
      })
    )
    .optional()
});

export const bcsClusterListResponseSchema = paginationResponseSchema.extend({
  items: z.array(bcsClusterSummarySchema)
});

export type BcsClusterSummary = z.infer<typeof bcsClusterSummarySchema>;
export type BcsClusterListQuery = z.infer<typeof bcsClusterListQuerySchema>;
export type BcsClusterDetailResponse = z.infer<typeof bcsClusterDetailResponseSchema>;
export type BcsClusterListResponse = z.infer<typeof bcsClusterListResponseSchema>;
