/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type HttpRequest from '../_httpRequest';
import type CachedPromise from '../cached-promise';
import type RequestQueue from '../request-queue';
import type { AxiosRequestConfig } from 'axios';

export interface RequestOptions {
  params?: Record<string, unknown>;
  query?: Record<string, unknown>;
  data?: unknown;
  [option: string]: unknown;
}
export interface RequestConfig extends AxiosRequestConfig {
  requestId?: string;
  globalError?: boolean;
  fromCache?: boolean;
  clearCache?: boolean;
  originalResponse?: boolean;
  cancelWhenRouteChange?: boolean;
  cancelPrevious?: boolean;
  catchIsShowMessage?: boolean;
}
/** The getter is installed with Object.defineProperty in the source client.
 * Response inference stays identical to the existing JS request implementation;
 * callers can supply T where an endpoint response contract is available. */
export type HttpClientResponse = Awaited<ReturnType<HttpRequest['request']>>;

export interface HttpClient {
  request<T = HttpClientResponse>(
    service: string,
    options?: RequestOptions,
    config?: RequestConfig,
  ): Promise<T>;
  $request: HttpRequest;
  queue: RequestQueue;
  cache: CachedPromise;
  cancelRequest(requestId: string): Promise<unknown>;
  cancelCache(requestId: string): void;
  cancel(requestId: string): Promise<unknown[]>;
}
