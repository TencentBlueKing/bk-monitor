import { z } from 'zod';

export const safetyLevelSchema = z.enum(['read', 'inspect', 'dry_run', 'write', 'destructive']);

export const rpcWarningSchema = z.union([
  z.string(),
  z.object({
    code: z.string().optional(),
    message: z.string()
  })
]);

export const rpcEnvelopeSchema = z
  .object({
    data: z.unknown(),
    trace_id: z.string().optional(),
    warnings: z.array(rpcWarningSchema).default([]),
    meta: z
      .object({
        environment_id: z.string().optional(),
        operation: z.string(),
        func_name: z.string().optional(),
        effective_bk_tenant_id: z.string().optional(),
        safety_level: safetyLevelSchema
      })
      .optional()
  })
  .refine((value) => Object.prototype.hasOwnProperty.call(value, 'data'), {
    message: 'RPC envelope must contain data'
  });

export const legacyRpcResponseSchema = z.object({
  func_name: z.string(),
  protocol: z.string().optional(),
  result: z.unknown()
});

export const rpcErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()).optional(),
  trace_id: z.string().optional()
});

export type RpcEnvelope<TData> = Omit<z.infer<typeof rpcEnvelopeSchema>, 'data'> & {
  data: TData;
};

export type RpcErrorPayload = z.infer<typeof rpcErrorSchema>;
