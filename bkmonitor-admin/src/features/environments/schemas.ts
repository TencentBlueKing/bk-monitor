import { z } from 'zod';

export const authModeSchema = z.preprocess((value) => {
  if (value === undefined || value === 'same-origin' || value === 'proxy' || value === 'custom') {
    return 'apigw';
  }

  return value;
}, z.literal('apigw'));

export const adminEnvironmentSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string().optional(),
  apiBaseUrl: z.string().min(1),
  kernelRpcPath: z.string().min(1),
  gatewayBaseUrl: z.string().optional(),
  appCode: z.string().optional(),
  secretKey: z.string().optional(),
  authMode: authModeSchema,
  readonly: z.boolean().default(true),
  tags: z.array(z.string()).default([]),
  mockFallback: z.boolean().default(false)
});

export const adminConfigSchema = z.object({
  environments: z.array(adminEnvironmentSchema).default([]),
  defaultEnvironmentId: z.string().optional()
});

export type AdminEnvironment = z.infer<typeof adminEnvironmentSchema>;
export type AdminConfig = z.infer<typeof adminConfigSchema>;
