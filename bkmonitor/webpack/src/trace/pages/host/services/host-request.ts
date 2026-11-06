/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { parseBizId } from 'monitor-common/utils';

export interface HostRequestTimeContext {
  timeRange: readonly (number | string)[];
  timezone: string;
}

interface PendingRequest {
  afterPending?: Promise<unknown>;
  promise: Promise<unknown>;
}

type RequestWindow = Window & {
  __BK_WEWEB_DATA__?: Window['__BK_WEWEB_DATA__'] & { token?: string };
  __MONITOR_HOST_PENDING_REQUESTS__?: Map<string, PendingRequest>;
  space_uid?: string;
  token?: string;
};

const serialize = (value: unknown) =>
  JSON.stringify(value, (_, item) =>
    item && typeof item === 'object' && !Array.isArray(item)
      ? Object.fromEntries(
          Object.keys(item)
            .sort()
            .map(key => [key, item[key]])
        )
      : item
  );

/** 只共享在途请求；宿主保留 Promise，页面负责忽略卸载或过期的响应。 */
export const requestHost = <T>(
  api: string,
  params: object,
  request: (params: Record<string, unknown>) => Promise<T>,
  options: { afterPending?: boolean; timeContext?: HostRequestTimeContext } = {}
): Promise<T> => {
  const context = window as RequestWindow;
  const data = JSON.parse(serialize(params)) as Record<string, unknown>;
  // 与 monitor-api 的隐式业务参数保持一致，并在发请求前固定上下文。
  if (!('bk_biz_id' in data)) {
    const bizId = parseBizId(context.cc_biz_id);
    if (bizId && bizId !== -1) data.bk_biz_id = bizId;
    else if (context.space_uid) data.space_uid = context.space_uid;
  }
  const owner = (context.rawWindow || context) as RequestWindow;
  const pending = (owner.__MONITOR_HOST_PENDING_REQUESTS__ ??= new Map());
  const keyParams = { ...data };
  // 动态时间按原始表达式判等，实际请求仍发送本次换算的时间戳。
  for (const [index, field] of ['start_time', 'end_time'].entries()) {
    const value = options.timeContext?.timeRange[index];
    if (field in keyParams && typeof value === 'string' && value.startsWith('now')) keyParams[field] = value;
  }
  const key = serialize([
    context.user_name || context.username || context.uin || '',
    context.site_url,
    context.__BK_WEWEB_DATA__?.host || '',
    context.__BK_WEWEB_DATA__?.token || context.token || '',
    context.source_app,
    api,
    keyParams,
    options.timeContext?.timezone,
  ]);

  const acquire = (waitForPending = false): Promise<T> => {
    const current = pending.get(key);
    if (current) {
      if (!waitForPending) return current.promise as Promise<T>;
      // 保存配置后的读取必须发生在旧读取结束之后，同一批刷新只追加一次。
      current.afterPending ??= current.promise.then(
        () => acquire(),
        () => acquire()
      );
      return current.afterPending as Promise<T>;
    }
    const entry: PendingRequest = {
      promise: new Promise<T>(resolve => resolve(request(data))).finally(() => {
        if (pending.get(key) === entry) pending.delete(key);
      }),
    };
    pending.set(key, entry);
    return entry.promise as Promise<T>;
  };

  return acquire(options.afterPending);
};
