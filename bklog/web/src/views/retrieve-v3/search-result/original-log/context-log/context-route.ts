/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { base64Decode, base64Encode } from '@/common/util';

import type { ConsitionItem } from '@/store/store.type';

/** 上下文日志路由携带的检索参数（与 store.getters.retrieveParams 子集对齐） */
export interface IContextRetrieveParams {
  addition: ConsitionItem[];
  keyword: string;
  search_mode: string;
  start_time?: string;
  end_time?: string;
  format?: string;
  begin?: number;
  size?: number;
  ip_chooser?: Record<string, unknown>;
  host_scopes?: Record<string, unknown>;
  interval?: string;
  sort_list?: Array<[string, string]>;
  bk_biz_id?: number;
  time_zone?: string;
  space_uid?: string;
  table_id_conditions?: unknown;
  scene_filter_values?: Record<string, unknown>;
}

export interface IContextRoutePayload {
  indexSetId: number;
  rowIndex: number;
  logParams: Record<string, any>;
  retrieveParams: IContextRetrieveParams;
  targetFields: string[];
  backRoute: {
    name?: string;
    params?: Record<string, any>;
    query?: Record<string, any>;
  };
}

const toUriSafePayload = (payload: string) => payload
  .replace(/\+/g, '-')
  .replace(/\//g, '_')
  .replace(/=+$/g, '');

const fromUriSafePayload = (payload: string) => {
  const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
  const padding = base64.length % 4;
  return padding ? base64.padEnd(base64.length + 4 - padding, '=') : base64;
};

export const encodeContextRoutePayload = (payload: IContextRoutePayload) => {
  return toUriSafePayload(base64Encode(JSON.stringify(payload)));
};

const decodePayloadCandidates = (payload: string) => {
  const candidates = [payload];
  let decoded = payload;

  for (let index = 0; index < 2; index++) {
    try {
      decoded = decodeURIComponent(decoded);
      candidates.push(decoded);
    } catch {
      break;
    }
  }

  return [...new Set(candidates)];
};

export const decodeContextRoutePayload = (payload = ''): IContextRoutePayload | null => {
  if (!payload) {
    return null;
  }

  const candidates = decodePayloadCandidates(payload);
  const errors: any[] = [];

  for (const candidate of candidates) {
    try {
      return JSON.parse(base64Decode(fromUriSafePayload(candidate)));
    } catch (error) {
      errors.push(error);
    }
  }

  console.warn('decode context route payload error', errors);
  return null;
};
