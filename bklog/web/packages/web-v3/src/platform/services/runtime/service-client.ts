/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type { HttpClient, HttpClientResponse, RequestConfig, RequestOptions } from '@/platform/http/types';

/** Descriptors remain owned by each business module. The transport still owns
 * authentication, cancellation, caching and the original response envelope. */
export interface EndpointDefinition {
  readonly url: string | readonly string[];
  readonly method?: string;
}
export const defineEndpoint = <const Definition extends EndpointDefinition>(definition: Definition): Definition =>
  definition;

type TransportResponse = HttpClientResponse;
export type ServiceOperation = {
  <Response = TransportResponse>(options?: RequestOptions, config?: RequestConfig): Promise<Response>;
  /** Stable cache/diagnostic identity; never used by business code to dispatch. */
  readonly id: string;
};
export type ServiceModule<Definitions> = {
  readonly [Name in keyof Definitions as Definitions[Name] extends EndpointDefinition ? Name : never]: ServiceOperation;
};
export type ServiceModules<Definitions> = {
  readonly [Module in keyof Definitions]: ServiceModule<Definitions[Module]>;
};
let transport: Pick<HttpClient, 'request'> | undefined;
/** Called when the HTTP client is initialized, before application requests.
 * Keeping injection separate prevents the store → services → HTTP → store cycle. */
export function installServiceTransport(client: Pick<HttpClient, 'request'>): void {
  transport = client;
}
function getTransport(): Pick<HttpClient, 'request'> {
  if (!transport) throw new Error('Service transport has not been initialized');
  return transport;
}
export function createServiceModule<Definitions extends object>(
  namespace: string,
  definitions: Definitions,
  client: () => Pick<HttpClient, 'request'> = getTransport,
): ServiceModule<Definitions> {
  const operations: Record<string, ServiceOperation> = {};
  for (const [operation, descriptor] of Object.entries(definitions)) {
    if (!descriptor || typeof descriptor !== 'object' || !('url' in descriptor)) continue;
    const invoke = (...args: [options?: RequestOptions, config?: RequestConfig]) =>
      client().request(`${namespace}/${operation}`, ...args);
    operations[operation] = Object.freeze(Object.assign(invoke, { id: `${namespace}/${operation}` }));
  }
  return Object.freeze(operations) as ServiceModule<Definitions>;
}
export function createServices<Definitions extends Record<string, object>>(
  definitions: Definitions,
  client: () => Pick<HttpClient, 'request'> = getTransport,
): ServiceModules<Definitions> {
  return Object.freeze(
    Object.fromEntries(
      Object.entries(definitions).map(([namespace, module]) => [
        namespace,
        createServiceModule(namespace, module, client),
      ]),
    ),
  ) as ServiceModules<Definitions>;
}
