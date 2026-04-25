import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';

export const clusterInfoSummarySchema = z.object({
  cluster_id: z.number(),
  cluster_name: z.string(),
  display_name: z.string().nullable().optional(),
  cluster_type: z.string(),
  domain_name: z.string().nullable().optional(),
  port: z.number().nullable().optional(),
  version: z.string().nullable().optional(),
  is_default_cluster: z.boolean().optional(),
  registered_system: z.string().nullable().optional(),
  label: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  associated_datasources: z.number().int().min(0).default(0),
  associated_storages: z.number().int().min(0).default(0),
  create_time: z.string().nullable().optional(),
  last_modify_time: z.string().nullable().optional()
});

export const clusterInfoListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  clusterName: z.string().optional(),
  clusterType: z.string().optional(),
  isDefaultCluster: z.boolean().optional(),
  registeredSystem: z.string().optional(),
  include: z.array(z.string()).optional()
});

export const clusterConfigSchema = z.object({
  namespace: z.string(),
  kind: z.string(),
  name: z.string(),
  origin_config: z.record(z.unknown()),
  component_config: z
    .object({
      sources: z.array(z.record(z.unknown())).optional(),
      sinks: z.array(z.record(z.unknown())).optional(),
      transforms: z.array(z.record(z.unknown())).optional(),
      status: z
        .object({
          phase: z.string().optional(),
          message: z.string().optional()
        })
        .nullable()
        .optional()
    })
    .nullable()
    .optional(),
  created_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional()
});

export const clusterInfoDetailResponseSchema = z.object({
  cluster_info: clusterInfoSummarySchema,
  cluster_configs: z.array(clusterConfigSchema),
  related_result_tables: z.number().int().min(0).default(0),
  related_datasources: z.number().int().min(0).default(0)
});

export const clusterInfoListResponseSchema = paginationResponseSchema.extend({
  items: z.array(clusterInfoSummarySchema)
});

export type ClusterInfoSummary = z.infer<typeof clusterInfoSummarySchema>;
export type ClusterInfoListQuery = z.infer<typeof clusterInfoListQuerySchema>;
export type ClusterConfig = z.infer<typeof clusterConfigSchema>;
export type ClusterInfoDetailResponse = z.infer<typeof clusterInfoDetailResponseSchema>;
export type ClusterInfoListResponse = z.infer<typeof clusterInfoListResponseSchema>;
