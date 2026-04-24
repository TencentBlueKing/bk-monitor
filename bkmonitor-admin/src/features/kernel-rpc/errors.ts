import type { RpcErrorPayload } from './schemas';

export class KernelRpcError extends Error {
  readonly code: string;

  readonly details: Record<string, unknown> | undefined;

  readonly traceId: string | undefined;

  constructor(payload: RpcErrorPayload) {
    super(payload.message);
    this.name = 'KernelRpcError';
    this.code = payload.code;
    this.details = payload.details;
    this.traceId = payload.trace_id;
  }
}
