import type { AdminEnvironment } from '../environments/schemas';
import { getMockResponse } from './mock';
import type { AdminOperation } from './operations';
import { KernelRpcError } from './errors';
import {
  legacyRpcResponseSchema,
  rpcEnvelopeSchema,
  rpcErrorSchema,
  type RpcEnvelope
} from './schemas';

export interface KernelRpcCallOptions {
  environment: AdminEnvironment;
  operation: AdminOperation;
  params: Record<string, unknown>;
}

export interface KernelRpcTransportOptions {
  fetchImpl?: typeof fetch;
}

export class KernelRpcClient {
  private readonly fetchImpl: typeof fetch;

  constructor(options: KernelRpcTransportOptions = {}) {
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  async call<TData>(options: KernelRpcCallOptions): Promise<RpcEnvelope<TData>> {
    try {
      const response = await this.fetchImpl('/admin-api/kernel-rpc/call', {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          environment_id: options.environment.id,
          operation: options.operation,
          params: options.params
        })
      });

      const payload: unknown = await response.json();

      if (!response.ok) {
        const parsedError = rpcErrorSchema.safeParse(payload);
        throw new KernelRpcError(
          parsedError.success
            ? parsedError.data
            : {
                code: `HTTP_${response.status}`,
                message: response.statusText || 'Kernel RPC request failed.'
              }
        );
      }

      return normalizeRpcPayload<TData>(payload, options.environment.id, options.operation);
    } catch (error) {
      if (shouldUseMockFallback(error, options.environment)) {
        return getMockResponse<TData>(options);
      }

      if (error instanceof KernelRpcError || options.environment.mockFallback === false) {
        throw error;
      }

      return getMockResponse<TData>(options);
    }
  }
}

export const kernelRpcClient = new KernelRpcClient();

function normalizeRpcPayload<TData>(
  payload: unknown,
  environmentId: string,
  operation: AdminOperation
): RpcEnvelope<TData> {
  const appGatewayPayload = unwrapAppGatewayPayload(payload);

  if (isObjectRecord(payload) && payload.result === false) {
    const rawCode = payload.code;
    const rawMessage = payload.message;
    throw new KernelRpcError({
      code:
        typeof rawCode === 'string' || typeof rawCode === 'number' ? String(rawCode) : 'UNKNOWN',
      message: typeof rawMessage === 'string' ? rawMessage : 'RPC request failed.'
    });
  }

  const envelope = rpcEnvelopeSchema.safeParse(appGatewayPayload);

  if (envelope.success) {
    return withClientMeta(envelope.data as RpcEnvelope<TData>, environmentId, operation);
  }

  const legacy = legacyRpcResponseSchema.safeParse(appGatewayPayload);

  if (legacy.success) {
    const nestedEnvelope = rpcEnvelopeSchema.safeParse(legacy.data.result);

    if (nestedEnvelope.success) {
      return withClientMeta(nestedEnvelope.data as RpcEnvelope<TData>, environmentId, operation);
    }

    if (isObjectRecord(legacy.data.result) && 'data' in legacy.data.result) {
      const resultEnvelope = legacy.data.result as {
        data: TData;
        meta?: RpcEnvelope<TData>['meta'];
        trace_id?: string;
        warnings?: RpcEnvelope<TData>['warnings'];
      };

      return withClientMeta(
        {
          data: resultEnvelope.data,
          trace_id: resultEnvelope.trace_id,
          warnings: resultEnvelope.warnings ?? [],
          meta: resultEnvelope.meta ?? {
            operation,
            safety_level: 'read'
          }
        },
        environmentId,
        operation
      );
    }

    return withClientMeta(
      {
        data: legacy.data.result as TData,
        trace_id: undefined,
        warnings: [],
        meta: {
          operation,
          safety_level: 'read'
        }
      },
      environmentId,
      operation
    );
  }

  return withClientMeta(
    {
      data: payload as TData,
      trace_id: undefined,
      warnings: ['响应没有使用标准 envelope，已按原始 payload 展示。'],
      meta: {
        operation,
        safety_level: 'read'
      }
    },
    environmentId,
    operation
  );
}

function unwrapAppGatewayPayload(payload: unknown): unknown {
  if (
    isObjectRecord(payload) &&
    payload.result === true &&
    isObjectRecord(payload.data) &&
    Object.prototype.hasOwnProperty.call(payload.data, 'func_name')
  ) {
    return payload.data;
  }

  return payload;
}

function shouldUseMockFallback(error: unknown, environment: AdminEnvironment) {
  return (
    environment.mockFallback === true &&
    error instanceof KernelRpcError &&
    error.code === 'ADMIN_KERNEL_RPC_PROXY_ERROR'
  );
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function withClientMeta<TData>(
  envelope: RpcEnvelope<TData>,
  environmentId: string,
  operation: AdminOperation
): RpcEnvelope<TData> {
  return {
    ...envelope,
    warnings: envelope.warnings ?? [],
    meta: {
      environment_id: environmentId,
      operation,
      safety_level: 'read',
      ...envelope.meta
    }
  };
}
