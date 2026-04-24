import Fastify from 'fastify';
import { ZodError, z } from 'zod';

import { adminEnvironmentSchema } from '../src/features/environments/schemas';
import type { AdminEnvironment } from '../src/features/environments/schemas';
import { operationToFuncName, type AdminOperation } from '../src/features/kernel-rpc/operations';
import { serverConfig } from './config';
import type { EnvironmentStore } from './store';
import { MysqlEnvironmentStore } from './stores/mysql';
import { SqliteEnvironmentStore } from './stores/sqlite';

const APIGW_TENANT_ID = 'system';

const defaultEnvironmentRequestSchema = z.object({
  environmentId: z.string().min(1)
});
const kernelRpcRequestSchema = z.object({
  environment_id: z.string().min(1),
  operation: z.string().min(1),
  params: z.record(z.unknown()).default({})
});

async function main() {
  const store = createStore();
  await store.init();

  const app = Fastify({ logger: true });

  app.get('/admin-api/health', () => ({
    ok: true,
    dbClient: serverConfig.dbClient
  }));

  app.get('/admin-api/config', async () => store.getConfig());

  app.post('/admin-api/environments', async (request) => {
    const environment = adminEnvironmentSchema.parse(request.body);
    return store.upsertEnvironment(environment);
  });

  app.put('/admin-api/environments/:environmentId', async (request) => {
    const { environmentId } = z.object({ environmentId: z.string().min(1) }).parse(request.params);
    const environment = adminEnvironmentSchema.parse(request.body);

    if (environment.id !== environmentId) {
      throw new Error('路径环境 ID 与请求体环境 ID 不一致');
    }

    return store.upsertEnvironment(environment);
  });

  app.delete('/admin-api/environments/:environmentId', async (request) => {
    const { environmentId } = z.object({ environmentId: z.string().min(1) }).parse(request.params);
    return store.deleteEnvironment(environmentId);
  });

  app.patch('/admin-api/config/default-environment', async (request) => {
    const { environmentId } = defaultEnvironmentRequestSchema.parse(request.body);
    return store.setDefaultEnvironment(environmentId);
  });

  app.post('/admin-api/kernel-rpc/call', async (request, reply) => {
    const payload = kernelRpcRequestSchema.parse(request.body);
    const environment = await getEnvironment(store, payload.environment_id);
    const funcName = getKernelRpcFuncName(payload.operation);

    try {
      const upstreamResponse = await fetch(buildKernelRpcUrl(environment), {
        method: 'POST',
        headers: buildKernelRpcHeaders(environment),
        body: JSON.stringify({
          func_name: funcName,
          params: payload.params
        })
      });
      const upstreamPayload = await parseUpstreamPayload(upstreamResponse);

      if (!upstreamResponse.ok) {
        void reply.status(upstreamResponse.status).send(upstreamPayload);
        return;
      }

      return normalizeUpstreamKernelRpcPayload(upstreamPayload, payload.operation);
    } catch (error) {
      void reply.status(502).send({
        code: 'ADMIN_KERNEL_RPC_PROXY_ERROR',
        message: `Kernel RPC 代理请求失败：${error instanceof Error ? error.message : String(error)}`
      });
    }
  });

  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof ZodError) {
      void reply.status(400).send({
        code: 'VALIDATION_ERROR',
        message: '请求参数不符合环境配置协议',
        details: error.flatten()
      });
      return;
    }

    const message = error instanceof Error ? error.message : String(error);

    void reply.status(500).send({
      code: 'ADMIN_API_ERROR',
      message
    });
  });

  const close = async () => {
    await app.close();
    await store.close();
  };

  process.once('SIGINT', () => {
    void close().finally(() => process.exit(0));
  });
  process.once('SIGTERM', () => {
    void close().finally(() => process.exit(0));
  });

  await app.listen({ host: serverConfig.host, port: serverConfig.port });
}

function createStore(): EnvironmentStore {
  if (serverConfig.dbClient === 'mysql') {
    return new MysqlEnvironmentStore(serverConfig.mysql);
  }

  return new SqliteEnvironmentStore(serverConfig.sqlitePath);
}

void main();

async function getEnvironment(
  store: EnvironmentStore,
  environmentId: string
): Promise<AdminEnvironment> {
  const config = await store.getConfig();
  const environment = config.environments.find((item) => item.id === environmentId);

  if (!environment) {
    throw new Error(`环境不存在: ${environmentId}`);
  }

  return environment;
}

function getKernelRpcFuncName(operation: string): string {
  if (Object.prototype.hasOwnProperty.call(operationToFuncName, operation)) {
    return operationToFuncName[operation as AdminOperation];
  }

  throw new Error(`不支持的 Kernel RPC operation: ${operation}`);
}

function buildKernelRpcUrl(environment: AdminEnvironment): string {
  const baseUrl = environment.apiBaseUrl.replace(/\/$/, '');
  const rpcPath = environment.kernelRpcPath.startsWith('/')
    ? environment.kernelRpcPath
    : `/${environment.kernelRpcPath}`;

  return `${baseUrl}${rpcPath}`;
}

function buildKernelRpcHeaders(environment: AdminEnvironment): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-Bk-Tenant-Id': APIGW_TENANT_ID
  };

  if (environment.appCode || environment.secretKey) {
    headers['X-Bkapi-Authorization'] = JSON.stringify({
      bk_app_code: environment.appCode ?? '',
      bk_app_secret: environment.secretKey ?? ''
    });
  }

  return headers;
}

async function parseUpstreamPayload(response: Response): Promise<unknown> {
  const text = await response.text();

  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return {
      code: `HTTP_${response.status}`,
      message: text
    };
  }
}

function normalizeUpstreamKernelRpcPayload(payload: unknown, operation: string): unknown {
  const appGatewayPayload =
    isRecord(payload) && payload.result === true && isRecord(payload.data) ? payload.data : payload;

  if (
    !isRecord(appGatewayPayload) ||
    !('func_name' in appGatewayPayload) ||
    !('result' in appGatewayPayload)
  ) {
    return appGatewayPayload;
  }

  const result = appGatewayPayload.result;

  if (isRecord(result) && 'data' in result) {
    return result;
  }

  return {
    data: result,
    warnings: [],
    meta: {
      operation,
      func_name: String(appGatewayPayload.func_name),
      safety_level: 'read'
    }
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
