import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';

export const datasourceListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  bkDataId: z.preprocess(
    (val) => {
      if (val === undefined || val === null || val === '') return undefined;
      const num = typeof val === 'number' ? val : Number(val);
      return Number.isNaN(num) ? undefined : num;
    },
    z.number().int().positive().optional()
  ),
  dataName: z.string().optional(),
  createdFrom: z.string().optional(),
  sourceLabel: z.string().optional(),
  typeLabel: z.string().optional(),
  isEnable: z.boolean().optional(),
  spaceUid: z.string().optional(),
  tableId: z.string().optional()
});

export const kafkaClusterSchema = z.object({
  cluster_id: z.number(),
  cluster_name: z.string(),
  display_name: z.string().nullable().optional(),
  cluster_type: z.string().optional(),
  is_default_cluster: z.boolean().optional(),
  registered_system: z.string().nullable().optional(),
  label: z.string().nullable().optional()
});

export const kafkaTopicConfigSchema = z.object({
  id: z.number().optional(),
  bk_data_id: z.number(),
  topic: z.string(),
  partition: z.number().int(),
  batch_size: z.number().nullable().optional(),
  flush_interval: z.string().nullable().optional(),
  consume_rate: z.number().nullable().optional()
});

export const datasourceSummarySchema = z.object({
  bk_data_id: z.number(),
  data_name: z.string(),
  data_description: z.string().nullable().optional(),
  bk_tenant_id: z.string(),
  type_label: z.string(),
  source_label: z.string(),
  created_from: z.string(),
  is_enable: z.boolean(),
  is_custom_source: z.boolean(),
  is_platform_data_id: z.boolean(),
  space_uid: z.string().nullable().optional(),
  mq_cluster_id: z.number().nullable().optional(),
  mq_config_id: z.number().nullable().optional(),
  kafka_cluster: kafkaClusterSchema.nullable().optional(),
  transfer_cluster_id: z.string().nullable().optional(),
  create_time: z.string().nullable().optional(),
  last_modify_time: z.string().nullable().optional(),
  result_table_count: z.number().int().min(0).default(0),
  space_count: z.number().int().min(0).default(0),
  option_count: z.number().int().min(0).default(0),
  has_data_id_config: z.boolean().default(false)
});

export const datasourceListResponseSchema = paginationResponseSchema.extend({
  items: z.array(datasourceSummarySchema)
});

export const datasourceOptionSchema = z.object({
  name: z.string(),
  value: z.unknown(),
  value_type: z.string().optional(),
  creator: z.string().optional(),
  create_time: z.string().nullable().optional()
});

export const datasourceResultTableSchema = z.object({
  bk_data_id: z.number().optional(),
  table_id: z.string(),
  table_name_zh: z.string().optional(),
  bk_biz_id: z.number().optional(),
  data_label: z.string().nullable().optional(),
  default_storage: z.string().nullable().optional(),
  is_enable: z.boolean().optional(),
  is_deleted: z.boolean().optional()
});

export const spaceDatasourceSchema = z.object({
  space_type_id: z.string(),
  space_id: z.string(),
  space_uid: z.string(),
  bk_tenant_id: z.string(),
  bk_data_id: z.number(),
  from_authorization: z.boolean().optional()
});

export const datasourceDetailResponseSchema = z.object({
  datasource: datasourceSummarySchema.extend({
    has_token: z.boolean(),
    source_system: z.string().nullable().optional(),
    custom_label: z.string().nullable().optional(),
    space_type_id: z.string().nullable().optional(),
    etl_config: z.string().nullable().optional(),
    creator: z.string().nullable().optional(),
    last_modify_user: z.string().nullable().optional()
  }),
  options: z.array(datasourceOptionSchema),
  space_datasources: z.array(spaceDatasourceSchema),
  data_source_result_tables: z.array(datasourceResultTableSchema),
  result_tables: z.array(datasourceResultTableSchema),
  data_id_config: z.record(z.unknown()).nullable(),
  kafka_cluster: kafkaClusterSchema.nullable(),
  kafka_topic_config: kafkaTopicConfigSchema.nullable()
});

export type DataSourceListQuery = z.infer<typeof datasourceListQuerySchema>;
export type DataSourceSummary = z.infer<typeof datasourceSummarySchema>;
export type DataSourceListResponse = z.infer<typeof datasourceListResponseSchema>;
export type DataSourceDetailResponse = z.infer<typeof datasourceDetailResponseSchema>;
