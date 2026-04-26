import { z } from 'zod';

import { paginationQuerySchema, paginationResponseSchema } from '../../shared/schemas/pagination';
import { datasourceSummarySchema } from '../datasource/schemas';
import { resultTableSummarySchema } from '../result-table/schemas';

export const customReportTypeSchema = z.enum(['custom_metric', 'custom_event', 'custom_log']);
export type CustomReportType = z.infer<typeof customReportTypeSchema>;

export const customReportListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  reportType: customReportTypeSchema.optional(),
  bkBizId: z.preprocess((value) => {
    if (value === undefined || value === null || value === '') return undefined;
    const num = typeof value === 'number' ? value : Number(value);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().optional()),
  bkDataId: z.preprocess((value) => {
    if (value === undefined || value === null || value === '') return undefined;
    const num = typeof value === 'number' ? value : Number(value);
    return Number.isNaN(num) ? undefined : num;
  }, z.number().int().positive().optional()),
  tableId: z.string().optional(),
  groupName: z.string().optional(),
  createdFrom: z.string().optional(),
  hasApm: z.boolean().optional()
});
export type CustomReportListQuery = z.infer<typeof customReportListQuerySchema>;

export const customReportSummarySchema = z.object({
  report_type: customReportTypeSchema,
  group_id: z.number().int(),
  group_name: z.string(),
  bk_tenant_id: z.string(),
  bk_biz_id: z.number().int().nullable(),
  bk_data_id: z.number().int().nullable(),
  table_id: z.string().nullable(),
  data_label: z.string().nullable().optional(),
  created_from: z.string().nullable().optional(),
  is_enable: z.boolean().nullable().optional(),
  metric_count: z.number().int().min(0).default(0),
  field_count: z.number().int().min(0).default(0),
  monitor_web_source: z.string().nullable().optional(),
  apm_application_count: z.number().int().min(0).default(0),
  last_modify_time: z.string().nullable().optional()
});
export type CustomReportSummary = z.infer<typeof customReportSummarySchema>;

export const customReportListResponseSchema = paginationResponseSchema.extend({
  items: z.array(customReportSummarySchema)
});
export type CustomReportListResponse = z.infer<typeof customReportListResponseSchema>;

export const customReportMetricListQuerySchema = paginationQuerySchema.extend({
  bkTenantId: z.string().default('system'),
  groupId: z.number().int(),
  fieldName: z.string().optional(),
  isActive: z.boolean().optional()
});
export type CustomReportMetricListQuery = z.infer<typeof customReportMetricListQuerySchema>;

export const customReportMetricSchema = z.object({
  field_name: z.string(),
  table_id: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  unit: z.string().nullable().optional(),
  type: z.string().nullable().optional(),
  is_active: z.boolean().nullable().optional(),
  last_modify_time: z.string().nullable().optional()
});
export type CustomReportMetric = z.infer<typeof customReportMetricSchema>;

export const customReportMetricListResponseSchema = paginationResponseSchema.extend({
  items: z.array(customReportMetricSchema)
});
export type CustomReportMetricListResponse = z.infer<typeof customReportMetricListResponseSchema>;

export const customReportDetailResponseSchema = z.object({
  report: customReportSummarySchema.extend({
    description: z.string().nullable().optional(),
    token: z.string().nullable().optional(),
    status: z.string().nullable().optional()
  }),
  datasource: datasourceSummarySchema.nullable().optional(),
  result_table: resultTableSummarySchema.nullable().optional(),
  monitor_web_relation: z.unknown().nullable().optional(),
  apm_relations: z.array(z.unknown()).default([]),
  event_fields: z.array(z.unknown()).default([]),
  warnings: z.array(z.string()).default([])
});
export type CustomReportDetailResponse = z.infer<typeof customReportDetailResponseSchema>;
