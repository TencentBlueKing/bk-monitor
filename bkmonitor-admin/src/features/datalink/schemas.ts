import { z } from 'zod';
import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';

export const dataLinkKindSchema = z.enum([
  'DataId',
  'ResultTable',
  'VmStorageBinding',
  'ElasticSearchBinding',
  'DorisBinding',
  'Databus',
  'ConditionalSink',
  'KafkaChannel',
  'VmStorage',
  'ElasticSearch',
  'Doris',
  'DataLink'
]);
export type DataLinkKind = z.infer<typeof dataLinkKindSchema>;

// --- Component (DRLRB) Schemas ---

export const componentListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  kind: dataLinkKindSchema.exclude([
    'DataLink',
    'KafkaChannel',
    'VmStorage',
    'ElasticSearch',
    'Doris'
  ] as const),
  namespace: z.string().optional(),
  search: z.string().optional(),
  status: z.string().optional(),
  bkDataId: z.preprocess((val) => {
    if (val === undefined || val === null || val === '') return undefined;
    const num = typeof val === 'number' ? val : Number(val);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().positive().optional()),
  dataType: z.string().optional(),
  vmClusterName: z.string().optional(),
  esClusterName: z.string().optional(),
  dorisClusterName: z.string().optional(),
  hasDataLink: z.boolean().optional()
});
export type ComponentListQuery = z.infer<typeof componentListQuerySchema>;

const drlrbCommonFields = z.object({
  kind: dataLinkKindSchema,
  name: z.string(),
  namespace: z.string(),
  status: z.string(),
  data_link_name: z.string().nullable().optional(),
  bk_biz_id: z.number(),
  bk_tenant_id: z.string(),
  created_at: z.string(),
  updated_at: z.string()
});

export const componentListItemSchema = drlrbCommonFields.extend({
  bk_data_id: z.number().optional(),
  table_id: z.string().optional(),
  data_type: z.string().optional(),
  bkbase_table_id: z.string().optional(),
  vm_cluster_name: z.string().optional(),
  es_cluster_name: z.string().optional(),
  doris_cluster_name: z.string().optional(),
  bkbase_result_table_name: z.string().optional(),
  timezone: z.number().optional(),
  data_id_name: z.string().optional(),
  sink_names: z.unknown().optional()
});
export type ComponentListItem = z.infer<typeof componentListItemSchema>;

export const componentListResponseSchema = paginationResponseSchema.extend({
  items: z.array(componentListItemSchema)
});
export type ComponentListResponse = z.infer<typeof componentListResponseSchema>;

export const componentDetailParamsSchema = z.object({
  bkTenantId: z.string().default('system'),
  kind: dataLinkKindSchema,
  namespace: z.string(),
  name: z.string(),
  include: z.array(z.string()).optional()
});
export type ComponentDetailParams = z.infer<typeof componentDetailParamsSchema>;

export const componentDetailResponseSchema = drlrbCommonFields.extend({
  bk_data_id: z.number().optional(),
  table_id: z.string().optional(),
  data_type: z.string().optional(),
  bkbase_table_id: z.string().optional(),
  vm_cluster_name: z.string().optional(),
  es_cluster_name: z.string().optional(),
  doris_cluster_name: z.string().optional(),
  bkbase_result_table_name: z.string().optional(),
  timezone: z.number().optional(),
  data_id_name: z.string().optional(),
  sink_names: z.unknown().optional(),
  component_config: z.unknown().optional()
});
export type ComponentDetailResponse = z.infer<typeof componentDetailResponseSchema>;

// --- ClusterConfig Schemas ---

export const clusterConfigListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  kind: z.enum(['KafkaChannel', 'VmStorage', 'ElasticSearch', 'Doris']).optional(),
  namespace: z.string().optional(),
  search: z.string().optional()
});
export type ClusterConfigListQuery = z.infer<typeof clusterConfigListQuerySchema>;

export const clusterConfigListItemSchema = z.object({
  name: z.string(),
  kind: z.string(),
  namespace: z.string(),
  bk_tenant_id: z.string(),
  origin_config: z.unknown(),
  created_at: z.string(),
  updated_at: z.string()
});
export type ClusterConfigListItem = z.infer<typeof clusterConfigListItemSchema>;

export const clusterConfigListResponseSchema = paginationResponseSchema.extend({
  items: z.array(clusterConfigListItemSchema)
});
export type ClusterConfigListResponse = z.infer<typeof clusterConfigListResponseSchema>;

export const clusterConfigDetailParamsSchema = z.object({
  bkTenantId: z.string().default('system'),
  kind: z.string(),
  namespace: z.string(),
  name: z.string(),
  include: z.array(z.string()).optional()
});

export const clusterConfigDetailResponseSchema = clusterConfigListItemSchema.extend({
  component_config: z.unknown().optional()
});
export type ClusterConfigDetailResponse = z.infer<typeof clusterConfigDetailResponseSchema>;

// --- DataLink Schemas ---

export const datalinkListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  namespace: z.string().optional(),
  search: z.string().optional(),
  dataLinkStrategy: z.string().optional(),
  bkDataId: z.preprocess((val) => {
    if (val === undefined || val === null || val === '') return undefined;
    const num = typeof val === 'number' ? val : Number(val);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().positive().optional())
});
export type DataLinkListQuery = z.infer<typeof datalinkListQuerySchema>;

export const datalinkListItemSchema = z.object({
  data_link_name: z.string(),
  namespace: z.string(),
  data_link_strategy: z.string(),
  bk_data_id: z.number(),
  table_ids_count: z.number(),
  bk_tenant_id: z.string(),
  created_at: z.string(),
  updated_at: z.string()
});
export type DataLinkListItem = z.infer<typeof datalinkListItemSchema>;

export const datalinkListResponseSchema = paginationResponseSchema.extend({
  items: z.array(datalinkListItemSchema)
});
export type DataLinkListResponse = z.infer<typeof datalinkListResponseSchema>;

export const datalinkDetailParamsSchema = z.object({
  bkTenantId: z.string().default('system'),
  dataLinkName: z.string(),
  include: z.array(z.string()).optional()
});

const dataLinkChildComponentSchema = z.object({
  kind: z.string(),
  name: z.string(),
  namespace: z.string(),
  component_config: z.unknown().optional()
});

export const datalinkDetailResponseSchema = z.object({
  kind: z.literal('DataLink'),
  data_link_name: z.string(),
  bk_tenant_id: z.string(),
  namespace: z.string(),
  data_link_strategy: z.string(),
  bk_data_id: z.number(),
  table_ids: z.array(z.string()),
  created_at: z.string(),
  updated_at: z.string(),
  components: z.record(z.string(), z.array(dataLinkChildComponentSchema))
});
export type DataLinkDetailResponse = z.infer<typeof datalinkDetailResponseSchema>;

// --- ComponentConfig (lazy fetch, shared) ---
export const componentConfigParamsSchema = z.object({
  bkTenantId: z.string().default('system'),
  kind: z.string(),
  namespace: z.string(),
  name: z.string()
});

export const componentConfigResponseSchema = z.object({
  kind: z.string(),
  namespace: z.string(),
  name: z.string(),
  component_config: z.unknown()
});
export type ComponentConfigResponse = z.infer<typeof componentConfigResponseSchema>;
