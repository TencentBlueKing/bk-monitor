import { describe, expect, it, vi } from 'vitest';

import type { AdminEnvironment } from '../environments/schemas';
import { KernelRpcClient } from './client';
import type { KernelRpcError } from './errors';

const environment: AdminEnvironment = {
  id: 'local',
  name: '本地开发',
  apiBaseUrl: 'http://localhost:8000/',
  kernelRpcPath: '/api/v4/kernel_rpc/call/',
  authMode: 'apigw',
  readonly: true,
  tags: ['dev'],
  mockFallback: false
};

describe('KernelRpcClient', () => {
  it('calls local admin rpc proxy without APIGW credentials in browser', async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        Response.json({
          data: { items: [], page: 1, page_size: 20, total: 0 },
          trace_id: 'trace-1',
          warnings: [],
          meta: {
            environment_id: 'local',
            operation: 'datasource.list',
            safety_level: 'read'
          }
        })
      )
    );
    const client = new KernelRpcClient({ fetchImpl });
    const response = await client.call({
      environment: {
        ...environment,
        appCode: 'bk_monitor',
        secretKey: 'secret'
      },
      operation: 'datasource.list',
      params: { bk_tenant_id: 'system', page: 1, page_size: 20 }
    });

    expect(response.trace_id).toBe('trace-1');
    expect(fetchImpl).toHaveBeenCalledWith(
      '/admin-api/kernel-rpc/call',
      expect.objectContaining({
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          environment_id: 'local',
          operation: 'datasource.list',
          params: { bk_tenant_id: 'system', page: 1, page_size: 20 }
        })
      })
    );
  });

  it('unwraps kernel RPC response when admin envelope is nested in result', async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        Response.json({
          func_name: 'admin.datasource.list',
          protocol: 'call',
          result: {
            data: { items: [], page: 1, page_size: 20, total: 0 },
            warnings: [{ code: 'EMPTY', message: 'no data' }],
            meta: {
              operation: 'datasource.list',
              func_name: 'admin.datasource.list',
              safety_level: 'read',
              effective_bk_tenant_id: 'system'
            }
          }
        })
      )
    );
    const client = new KernelRpcClient({ fetchImpl });
    const response = await client.call<{ items: unknown[] }>({
      environment,
      operation: 'datasource.list',
      params: { bk_tenant_id: 'system', page: 1, page_size: 20 }
    });

    expect(response.data.items).toEqual([]);
    expect(response.meta?.environment_id).toBe('local');
    expect(response.meta?.effective_bk_tenant_id).toBe('system');
    expect(response.warnings[0]).toEqual({ code: 'EMPTY', message: 'no data' });
  });

  it('unwraps APIGW kernel RPC payload when proxy returns the outer gateway envelope', async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        Response.json({
          result: true,
          code: 200,
          message: 'OK',
          data: {
            func_name: 'admin.datasource.list',
            protocol: 'call',
            result: {
              data: { items: [], page: 1, page_size: 20, total: 0 },
              warnings: [],
              meta: {
                operation: 'datasource.list',
                func_name: 'admin.datasource.list',
                safety_level: 'read',
                effective_bk_tenant_id: 'system'
              }
            }
          }
        })
      )
    );
    const client = new KernelRpcClient({ fetchImpl });
    const response = await client.call<{ page: number; items: unknown[] }>({
      environment,
      operation: 'datasource.list',
      params: { bk_tenant_id: 'system', page: 1, page_size: 20 }
    });

    expect(response.data.page).toBe(1);
    expect(response.data.items).toEqual([]);
    expect(response.meta?.func_name).toBe('admin.datasource.list');
  });

  it('parses backend error payload', async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        Response.json(
          {
            code: 'RESOURCE_NOT_FOUND',
            message: '未找到匹配资源',
            trace_id: 'trace-error'
          },
          { status: 404 }
        )
      )
    );
    const client = new KernelRpcClient({ fetchImpl });

    await expect(
      client.call({
        environment,
        operation: 'datasource.detail',
        params: { bk_tenant_id: 'system', bk_data_id: 1 }
      })
    ).rejects.toMatchObject({
      code: 'RESOURCE_NOT_FOUND',
      traceId: 'trace-error'
    } satisfies Partial<KernelRpcError>);
  });

  it('uses mock fallback when enabled and network fails', async () => {
    const fetchImpl = vi.fn(() => Promise.reject(new TypeError('network failed')));
    const client = new KernelRpcClient({ fetchImpl });
    const response = await client.call({
      environment: { ...environment, mockFallback: true },
      operation: 'datasource.list',
      params: { bk_tenant_id: 'system', page: 1, page_size: 20 }
    });

    expect(response.meta?.environment_id).toBe('local');
    expect(response.warnings[0]).toContain('mock fallback');
  });

  it('uses mock fallback when local proxy reports upstream transport failure', async () => {
    const fetchImpl = vi.fn(() =>
      Promise.resolve(
        Response.json(
          {
            code: 'ADMIN_KERNEL_RPC_PROXY_ERROR',
            message: 'Kernel RPC 代理请求失败'
          },
          { status: 502 }
        )
      )
    );
    const client = new KernelRpcClient({ fetchImpl });
    const response = await client.call({
      environment: { ...environment, mockFallback: true },
      operation: 'datasource.list',
      params: { bk_tenant_id: 'system', page: 1, page_size: 20 }
    });

    expect(response.meta?.environment_id).toBe('local');
    expect(response.warnings[0]).toContain('mock fallback');
  });
});
