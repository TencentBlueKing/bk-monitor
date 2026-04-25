import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';
import { datasourceSummarySchema } from '../datasource/schemas';

export const resultTableListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  tableId: z.string().optional(),
  tableNameZh: z.string().optional(),
  bkBizId: z.preprocess((val) => {
    if (val === undefined || val === null || val === '') return undefined;
    const num = typeof val === 'number' ? val : Number(val);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().optional()),
  bkDataId: z.preprocess((val) => {
    if (val === undefined || val === null || val === '') return undefined;
    const num = typeof val === 'number' ? val : Number(val);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().optional()),
  dataLabel: z.string().optional(),
  label: z.string().optional(),
  schemaType: z.string().optional(),
  defaultStorage: z.string().optional(),
  isEnable: z.boolean().optional(),
  isDeleted: z.boolean().optional(),
  isBuiltin: z.boolean().optional()
});

export const resultTableSummarySchema = z.object({
  table_id: z.string(),
  table_name_zh: z.string(),
  bk_tenant_id: z.string(),
  bk_biz_id: z.number(),
  label: z.string(),
  data_label: z.string().nullable().optional(),
  schema_type: z.string(),
  default_storage: z.string().nullable().optional(),
  is_custom_table: z.boolean(),
  is_builtin: z.boolean(),
  is_enable: z.boolean(),
  is_deleted: z.boolean(),
  create_time: z.string().nullable().optional(),
  last_modify_time: z.string().nullable().optional(),
  field_count: z.number().int().min(0).default(0),
  datasource_count: z.number().int().min(0).default(0),
  has_es_storage: z.boolean().default(false),
  has_vm_record: z.boolean().default(false),
  custom_group_type: z.string().nullable().optional()
});

export const resultTableListResponseSchema = paginationResponseSchema.extend({
  items: z.array(resultTableSummarySchema)
});

export const resultTableOptionSchema = z.object({
  name: z.string(),
  value: z.unknown(),
  value_type: z.string().optional(),
  creator: z.string().optional(),
  create_time: z.string().nullable().optional()
});

export const resultTableEsStorageSchema = z.object({
  table_id: z.string(),
  table_kind: z.enum(['physical', 'virtual']).optional(),
  origin_table_id: z.string().nullable().optional(),
  storage_cluster_id: z.number().int().nullable().optional(),
  index_set: z.string().nullable().optional(),
  need_create_index: z.boolean().nullable().optional(),
  retention: z.number().int().nullable().optional(),
  slice_size: z.number().int().nullable().optional(),
  slice_gap: z.number().int().nullable().optional()
});

export const resultTableDetailResponseSchema = z.object({
  result_table: resultTableSummarySchema.extend({
    bk_biz_id_alias: z.string().nullable().optional(),
    labels: z.record(z.unknown()).nullable().optional(),
    creator: z.string().nullable().optional(),
    last_modify_user: z.string().nullable().optional()
  }),
  options: z.array(resultTableOptionSchema),
  datasources: z.array(datasourceSummarySchema),
  custom_groups: z.array(z.record(z.unknown())),
  es_storages: z.array(resultTableEsStorageSchema),
  es_storage: z.record(z.unknown()).nullable(),
  vm_record: z.record(z.unknown()).nullable()
});

export const resultTableFieldListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  tableId: z.string().min(1),
  fieldName: z.string().optional(),
  fieldType: z.string().optional(),
  tag: z.string().optional(),
  isConfigByUser: z.boolean().optional(),
  isDisabled: z.boolean().optional(),
  hasOption: z.boolean().optional()
});

export const resultTableFieldSchema = z.object({
  field_name: z.string(),
  field_type: z.string(),
  tag: z.string(),
  description: z.string().nullable().optional(),
  unit: z.string().nullable().optional(),
  is_config_by_user: z.boolean(),
  alias_name: z.string().nullable().optional(),
  is_disabled: z.boolean(),
  last_modify_time: z.string().nullable().optional(),
  option_count: z.number().int().min(0),
  options: z.array(z.record(z.unknown())).optional()
});

export const resultTableFieldListResponseSchema = paginationResponseSchema.extend({
  items: z.array(resultTableFieldSchema)
});

export type ResultTableListQuery = z.infer<typeof resultTableListQuerySchema>;
export type ResultTableSummary = z.infer<typeof resultTableSummarySchema>;
export type ResultTableListResponse = z.infer<typeof resultTableListResponseSchema>;
export type ResultTableDetailResponse = z.infer<typeof resultTableDetailResponseSchema>;
export type ResultTableField = z.infer<typeof resultTableFieldSchema>;
export type ResultTableFieldListQuery = z.infer<typeof resultTableFieldListQuerySchema>;
export type ResultTableFieldListResponse = z.infer<typeof resultTableFieldListResponseSchema>;
