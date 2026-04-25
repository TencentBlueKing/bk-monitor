import { z } from 'zod';

const listInputSchema = z.array(z.string().min(1)).default([]);

export const queryRouteQuerySchema = z.object({
  bkTenantId: z.string().default('system'),
  spaceUid: z.string().optional(),
  tableIds: listInputSchema,
  dataLabels: listInputSchema,
  fieldNames: listInputSchema,
  refreshTargets: z.array(z.enum(['space', 'table', 'data_label'])).optional()
});

export const queryRouteFilterConditionSchema = z.object({
  field: z.string(),
  operator: z.string(),
  value: z.unknown()
});

export const queryRouteFilterGroupSchema = z.object({
  conditions: z.array(queryRouteFilterConditionSchema).default([]),
  raw: z.unknown().optional()
});

export const queryRouteTableRefSchema = z.object({
  table_id: z.string(),
  in_space: z.boolean().default(false),
  has_detail: z.boolean().default(false),
  in_input_table_ids: z.boolean().default(false)
});

export const queryRouteSpaceEntrySchema = z.object({
  table_id: z.string(),
  filters: z.array(queryRouteFilterGroupSchema).default([]),
  in_input_table_ids: z.boolean().default(false),
  in_any_data_label: z.boolean().default(false),
  has_detail: z.boolean().default(false),
  raw: z.unknown().optional()
});

export const queryRouteDataLabelEntrySchema = z.object({
  data_label: z.string(),
  exists: z.boolean().default(false),
  table_ids: z.array(queryRouteTableRefSchema).default([]),
  raw: z.unknown().optional()
});

export const queryRouteFieldSchema = z.object({
  field_name: z.string(),
  field_type: z.string().nullable().optional(),
  tag: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  alias_name: z.string().nullable().optional(),
  raw: z.unknown().optional()
});

export const queryRouteResultTableDetailSchema = z.object({
  table_id: z.string(),
  normalized_table_id: z.string().optional(),
  exists: z.boolean(),
  storage_type: z.string().nullable().optional(),
  storage_id: z.union([z.string(), z.number()]).nullable().optional(),
  db: z.string().nullable().optional(),
  measurement: z.string().nullable().optional(),
  field_count: z.number().int().min(0).default(0),
  matched_field_names: z.array(z.string()).default([]),
  missing_field_names: z.array(z.string()).default([]),
  fields: z.array(queryRouteFieldSchema).default([]),
  detail: z.unknown().nullable().optional()
});

export const queryRouteDiagnosticStatusSchema = z.enum(['ok', 'missing', 'warning', 'error']);

export const queryRouteDiagnosticSchema = z.object({
  id: z.string(),
  status: queryRouteDiagnosticStatusSchema,
  label: z.string(),
  target: z.string(),
  message: z.string()
});

export const queryRouteRefreshResultSchema = z.object({
  refreshed: z.boolean().default(false),
  targets: z.array(z.string()).default([]),
  message: z.string().optional(),
  warnings: z.array(z.string()).default([])
});

export const queryRouteResponseSchema = z.object({
  space_uid: z.string().nullable().optional(),
  inputs: queryRouteQuerySchema.omit({ bkTenantId: true }),
  space_routes: z.array(queryRouteSpaceEntrySchema).default([]),
  data_label_routes: z.array(queryRouteDataLabelEntrySchema).default([]),
  result_table_details: z.array(queryRouteResultTableDetailSchema).default([]),
  diagnostics: z.array(queryRouteDiagnosticSchema).default([]),
  refresh: queryRouteRefreshResultSchema.optional(),
  warnings: z.array(z.string()).default([])
});

export type QueryRouteQuery = z.infer<typeof queryRouteQuerySchema>;
export type QueryRouteFilterCondition = z.infer<typeof queryRouteFilterConditionSchema>;
export type QueryRouteFilterGroup = z.infer<typeof queryRouteFilterGroupSchema>;
export type QueryRouteSpaceEntry = z.infer<typeof queryRouteSpaceEntrySchema>;
export type QueryRouteDataLabelEntry = z.infer<typeof queryRouteDataLabelEntrySchema>;
export type QueryRouteField = z.infer<typeof queryRouteFieldSchema>;
export type QueryRouteResultTableDetail = z.infer<typeof queryRouteResultTableDetailSchema>;
export type QueryRouteDiagnosticStatus = z.infer<typeof queryRouteDiagnosticStatusSchema>;
export type QueryRouteDiagnostic = z.infer<typeof queryRouteDiagnosticSchema>;
export type QueryRouteRefreshResult = z.infer<typeof queryRouteRefreshResultSchema>;
export type QueryRouteResponse = z.infer<typeof queryRouteResponseSchema>;
