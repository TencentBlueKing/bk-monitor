/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { base64Decode, base64Encode } from "@/common/util";

/** 上下文日志路由只携带页面直开所需的最小检索参数 */
export interface IContextRetrieveParams {
  start_time?: string | number;
  end_time?: string | number;
  format?: string;
}

export interface IContextRoutePayload {
  indexSetId: number;
  logParams: Record<string, any>;
  retrieveParams: IContextRetrieveParams;
  backRoute: {
    name?: string;
    params?: Record<string, any>;
    query?: Record<string, any>;
  };
}

const toUriSafePayload = (payload: string) =>
  payload.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");

const fromUriSafePayload = (payload: string) => {
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padding = base64.length % 4;
  return padding ? base64.padEnd(base64.length + 4 - padding, "=") : base64;
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

export const decodeContextRoutePayload = (
  payload = "",
): IContextRoutePayload | null => {
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

  console.warn("decode context route payload error", errors);
  return null;
};
