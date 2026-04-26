import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';
import { datasourceSummarySchema } from '../datasource/schemas';
import { resultTableSummarySchema } from '../result-table/schemas';
import { customReportSummarySchema } from '../custom-report/schemas';

export const apmApplicationListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  bkBizId: z.preprocess((value) => {
    if (value === undefined || value === null || value === '') return undefined;
    const num = typeof value === 'number' ? value : Number(value);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().optional()),
  appName: z.string().optional(),
  status: z.string().optional(),
  bkDataId: z.preprocess((value) => {
    if (value === undefined || value === null || value === '') return undefined;
    const num = typeof value === 'number' ? value : Number(value);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().positive().optional()),
  tableId: z.string().optional()
});
export type ApmApplicationListQuery = z.infer<typeof apmApplicationListQuerySchema>;

export const apmApplicationSummarySchema = z.object({
  application_id: z.number().int(),
  app_name: z.string(),
  app_alias: z.string().nullable().optional(),
  bk_tenant_id: z.string(),
  bk_biz_id: z.number().int(),
  status: z.string().nullable().optional(),
  metric_data_id: z.number().int().nullable().optional(),
  trace_data_id: z.number().int().nullable().optional(),
  log_data_id: z.number().int().nullable().optional(),
  profile_data_id: z.number().int().nullable().optional(),
  service_count: z.number().int().min(0).default(0),
  topo_node_count: z.number().int().min(0).default(0),
  last_modify_time: z.string().nullable().optional()
});
export type ApmApplicationSummary = z.infer<typeof apmApplicationSummarySchema>;

export const apmApplicationListResponseSchema = paginationResponseSchema.extend({
  items: z.array(apmApplicationSummarySchema)
});
export type ApmApplicationListResponse = z.infer<typeof apmApplicationListResponseSchema>;

export const apmServiceListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  applicationId: z.number().int(),
  serviceName: z.string().optional(),
  kind: z.string().optional()
});
export type ApmServiceListQuery = z.infer<typeof apmServiceListQuerySchema>;

export const apmServiceSchema = z.object({
  service_name: z.string(),
  topo_key: z.string(),
  kind: z.string().nullable().optional(),
  category: z.string().nullable().optional(),
  instance_count: z.number().int().min(0).default(0),
  endpoint_count: z.number().int().min(0).default(0),
  last_seen_time: z.string().nullable().optional()
});
export type ApmService = z.infer<typeof apmServiceSchema>;

export const apmServiceListResponseSchema = paginationResponseSchema.extend({
  items: z.array(apmServiceSchema)
});
export type ApmServiceListResponse = z.infer<typeof apmServiceListResponseSchema>;

export const apmTopoNodeSchema = z.object({
  topo_key: z.string(),
  kind: z.string().nullable().optional(),
  category: z.string().nullable().optional(),
  system: z.string().nullable().optional(),
  platform: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional()
});

export const apmTopoRelationSchema = z.object({
  from_topo_key: z.string(),
  to_topo_key: z.string(),
  kind: z.string().nullable().optional(),
  category: z.string().nullable().optional()
});

export const apmApplicationDetailResponseSchema = z.object({
  application: apmApplicationSummarySchema.extend({
    description: z.string().nullable().optional(),
    app_token: z.string().nullable().optional()
  }),
  datasources: z.array(datasourceSummarySchema),
  result_tables: z.array(resultTableSummarySchema),
  custom_reports: z.array(customReportSummarySchema),
  services_preview: z.array(apmServiceSchema).default([]),
  topo_nodes_preview: z.array(apmTopoNodeSchema).default([]),
  topo_relations_preview: z.array(apmTopoRelationSchema).default([]),
  service_summary: z.record(z.unknown()).default({}),
  topo_summary: z.record(z.unknown()).default({})
});
export type ApmApplicationDetailResponse = z.infer<typeof apmApplicationDetailResponseSchema>;
