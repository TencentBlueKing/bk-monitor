import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';

const optionalIntegerSchema = z.preprocess((val) => {
  if (val === undefined || val === null || val === '') return undefined;
  const num = typeof val === 'number' ? val : Number(val);
  return Number.isNaN(num) ? undefined : num;
}, z.number().int().optional());

export const esStorageTableKindSchema = z.enum(['physical', 'virtual']);

export const esStorageListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  tableId: z.string().optional(),
  dataLabel: z.string().optional(),
  tableKind: esStorageTableKindSchema.optional(),
  storageClusterId: optionalIntegerSchema,
  sourceType: z.string().optional(),
  needCreateIndex: z.boolean().optional(),
  ordering: z.string().optional()
});

export const esStorageClusterSummarySchema = z.object({
  cluster_id: z.number().int(),
  cluster_name: z.string(),
  display_name: z.string().nullable().optional(),
  cluster_type: z.string().optional()
});

export const esStorageResultTableSummarySchema = z.object({
  table_id: z.string(),
  table_name_zh: z.string().nullable().optional(),
  bk_biz_id: z.number().int().nullable().optional(),
  data_label: z.string().nullable().optional(),
  default_storage: z.string().nullable().optional(),
  is_enable: z.boolean().optional(),
  is_deleted: z.boolean().optional()
});

export const esStoragePhysicalTableSchema = z.object({
  table_id: z.string().nullable().optional(),
  exists: z.boolean().optional(),
  es_storage: z.record(z.unknown()).nullable().optional(),
  result_table: z.record(z.unknown()).nullable().optional()
});

export const esStorageSummarySchema = z.object({
  id: z.number().int().optional(),
  table_id: z.string(),
  origin_table_id: z.string().nullable().optional(),
  table_kind: esStorageTableKindSchema,
  bk_tenant_id: z.string().optional(),
  storage_cluster_id: z.number().int().nullable().optional(),
  storage_cluster: esStorageClusterSummarySchema.nullable().optional(),
  result_table: esStorageResultTableSummarySchema.nullable().optional(),
  physical_table: esStoragePhysicalTableSchema.nullable().optional(),
  virtual_table_count: z.number().int().min(0).default(0),
  retention: z.number().int().nullable().optional(),
  slice_size: z.number().int().nullable().optional(),
  slice_gap: z.number().int().nullable().optional(),
  date_format: z.string().nullable().optional(),
  time_zone: z.union([z.string(), z.number()]).nullable().optional(),
  source_type: z.string().nullable().optional(),
  index_set: z.string().nullable().optional(),
  need_create_index: z.boolean().nullable().optional(),
  archive_index_days: z.number().int().nullable().optional(),
  warm_phase_days: z.number().int().nullable().optional(),
  create_time: z.string().nullable().optional(),
  last_modify_time: z.string().nullable().optional()
});

export const esStorageListResponseSchema = paginationResponseSchema.extend({
  items: z.array(esStorageSummarySchema)
});

export const esStorageConfigSchema = esStorageSummarySchema.extend({
  warm_phase_settings: z.unknown().optional(),
  index_settings: z.unknown().optional(),
  mapping_settings: z.unknown().optional(),
  long_term_storage_settings: z.unknown().optional()
});

export const storageClusterRecordSchema = z.object({
  table_id: z.string(),
  cluster_id: z.number().int().nullable().optional(),
  cluster: esStorageClusterSummarySchema.nullable().optional(),
  is_current: z.boolean().optional(),
  is_deleted: z.boolean().optional(),
  enable_time: z.string().nullable().optional(),
  disable_time: z.string().nullable().optional(),
  delete_time: z.string().nullable().optional(),
  creator: z.string().nullable().optional(),
  create_time: z.string().nullable().optional()
});

export const resultTableOptionSchema = z.object({
  name: z.string(),
  value: z.unknown(),
  value_type: z.string().nullable().optional(),
  creator: z.string().nullable().optional(),
  create_time: z.string().nullable().optional()
});

export const esFieldQueryAliasSchema = z.object({
  query_alias: z.string(),
  field_path: z.string(),
  path_type: z.string().nullable().optional(),
  mapping_alias: z.unknown().optional()
});

export const esStorageVirtualTableSchema = z.object({
  table_id: z.string(),
  result_table: esStorageResultTableSummarySchema.nullable().optional()
});

export const esStorageDetailResponseSchema = z.object({
  es_storage: esStorageConfigSchema,
  result_table: esStorageResultTableSummarySchema.nullable().optional(),
  storage_cluster: esStorageClusterSummarySchema.nullable().optional(),
  storage_cluster_records: z.array(storageClusterRecordSchema).default([]),
  result_table_options: z.array(resultTableOptionSchema).default([]),
  field_aliases: z.array(esFieldQueryAliasSchema).default([]),
  physical_table: esStoragePhysicalTableSchema.nullable().optional(),
  virtual_tables: z.array(esStorageVirtualTableSchema).default([]),
  warnings: z.array(z.string()).optional()
});

export const esRuntimeIndexSchema = z.object({
  index: z.string(),
  health: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  docs_count: z.number().nullable().optional(),
  store_size: z.string().nullable().optional(),
  creation_date: z.string().nullable().optional()
});

export const esRuntimeAliasSchema = z.object({
  alias: z.string(),
  indices: z.array(z.string()).default([]),
  is_write_index: z.boolean().nullable().optional()
});

export const esRuntimeOverviewResponseSchema = z.object({
  table_id: z.string(),
  index_set: z.string().nullable().optional(),
  index_pattern: z.string().nullable().optional(),
  indices: z.array(esRuntimeIndexSchema).default([]),
  aliases: z.unknown().optional(),
  mapping: z.unknown().optional(),
  field_aliases: z.array(esFieldQueryAliasSchema).default([]),
  warnings: z.array(z.string()).default([])
});

export const esSampleResponseSchema = z.object({
  table_id: z.string(),
  index: z.string(),
  time_field: z.string().optional(),
  took: z.number().nullable().optional(),
  hit: z.unknown().nullable().optional(),
  warnings: z.array(z.string()).default([])
});

export type EsStorageTableKind = z.infer<typeof esStorageTableKindSchema>;
export type EsStorageListQuery = z.infer<typeof esStorageListQuerySchema>;
export type EsStorageSummary = z.infer<typeof esStorageSummarySchema>;
export type EsStorageListResponse = z.infer<typeof esStorageListResponseSchema>;
export type EsStorageDetailResponse = z.infer<typeof esStorageDetailResponseSchema>;
export type EsRuntimeOverviewResponse = z.infer<typeof esRuntimeOverviewResponseSchema>;
export type EsRuntimeIndex = z.infer<typeof esRuntimeIndexSchema>;
export type EsSampleResponse = z.infer<typeof esSampleResponseSchema>;
