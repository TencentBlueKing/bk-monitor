/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import CancelToken from 'axios/lib/cancel/CancelToken';
import { random } from 'monitor-common/utils/utils';

import axios from './axios/axios';
import { axiosError, bkMessage, makeMessage } from './utils/index';

interface RequestConfig {
  /* 是否需要自动带上业务ID */
  needBiz?: boolean;
  /* 是否需要返回原始 response */
  needRes?: boolean;
  /* 是否需要header 加上 X-Async-Task */
  isAsync?: boolean;
  /* 是否报错时需要 message 弹窗 */
  needMessage?: boolean;
  /* 是否需要拒绝403 */
  reject403?: boolean;
  /* cancelToken */
  cancelToken?: any;
  /* 是否需要自动取消重复请求 */
  needCancel?: boolean;
  /* 是否需要配置header Traceparent */
  needTraceId?: boolean;
  /* 是否需要配置header */
  headers?: Record<string, any>;
  /* 取消请求 */
  cancelFn?: () => void;
  /* 上传进度 */
  onUploadProgress?: (progressEvent: any) => void;
}

interface ApiError {
  code?: number | string;
  message?: string;
  error_details?: string;
}

type RequestMethod = 'delete' | 'get' | 'head' | 'options' | 'patch' | 'post' | 'put';

// 常量定义
const NO_NEED_ERROR_MESSAGE = 'bk_monitor_api_no_message';

const defaultConfig: RequestConfig = {
  needBiz: true,
  needRes: false,
  isAsync: false,
  needMessage: localStorage.getItem(NO_NEED_ERROR_MESSAGE) !== 'true',
  reject403: false,
  cancelToken: null,
  needCancel: false,
  needTraceId: true,
  cancelFn() {},
  onUploadProgress() {},
};

const noMessageCode: (number | string)[] = [3308005, 3314003, 3314004, ...axiosError]; // 无数据状态下 不弹窗
const pendingRequest = new Map<string, () => void>(); // 请求取消映射表

// 添加请求取消
const addPendingRequest = (method: string, url: string, config: RequestConfig): void => {
  const requestKey = `${method}_${url}`;
  config.cancelToken =
    config.cancelToken ??
    new CancelToken((cancel: () => void) => {
      if (!pendingRequest.has(requestKey)) {
        pendingRequest.set(requestKey, cancel);
      }
    });
};

// 移除请求取消
const removePendingRequest = (method: string, url: string): void => {
  const requestKey = `${method}_${url}`;
  if (pendingRequest.has(requestKey)) {
    const cancel = pendingRequest.get(requestKey);
    if (cancel) {
      cancel();
    }
    pendingRequest.delete(requestKey);
  }
};

// 请求函数类型定义
type RequestFunction = {
  <T = any>(id: number | string, params?: Record<string, any>, config?: RequestConfig): Promise<T>;
  <T = any>(params?: Record<string, any>, config?: RequestConfig): Promise<T>;
};

export const request = (method: RequestMethod, url: string): RequestFunction => {
  return <T = any>(
    id?: number | Record<string, any> | string,
    params?: Record<string, any> | RequestConfig,
    config?: RequestConfig
  ): Promise<T> => {
    let newUrl = url;
    let data: FormData | Record<string, any> = {};
    const hasBizId = !(window.cc_biz_id === -1 || !window.cc_biz_id);

    if (typeof id === 'number' || typeof id === 'string') {
      newUrl = url.replace('{pk}', String(id));
      data = (params as Record<string, any>) || {};
      config = Object.assign({}, defaultConfig, config || {});
    } else {
      data = (id as Record<string, any>) || {};
      config = Object.assign({}, defaultConfig, (params as RequestConfig) || {});
    }

    const methodType = method.toLowerCase() || 'get';

    if (config.isAsync) {
      config.headers = {
        'X-Async-Task': true,
      };
    }

    const traceparent = `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`;
    config.headers = {
      ...config.headers,
      traceparent,
    };

    // needCancel用于配置是否需要设置取消请求
    if (config.needCancel) {
      // 取消上次请求
      removePendingRequest(method, url);
      // 添加本次请求
      addPendingRequest(method, url, config);
    }

    if (methodType === 'get') {
      if (hasBizId && !('bk_biz_id' in data)) {
        (data as Record<string, any>).bk_biz_id = window.cc_biz_id;
      } else if (window.space_uid) {
        (data as Record<string, any>).space_uid = window.space_uid;
      }

      return axios({
        method: 'get',
        url: newUrl,
        params: data,
        needMessage: false,
        ...config,
      })
        .then((res: any) => {
          if (config.needRes) {
            return Promise.resolve(res as T);
          }
          return Promise.resolve(res.data);
        })
        .catch((err: ApiError) => {
          const message = makeMessage(err.error_details || err.message, traceparent, config.needTraceId);
          if (message && config.needMessage && err.code && !noMessageCode.includes(err.code)) {
            bkMessage(message);
          }
          return Promise.reject(axiosError.includes(String(err?.code)) ? '' : err);
        });
    }

    // 处理文件上传
    for (const value of Object.values(data)) {
      const type = String(value);
      if (type === '[object FileList]' || type === '[object File]') {
        const formData = new FormData();
        for (const [key, val] of Object.entries(data)) {
          formData.append(key, val as Blob | string);
        }
        data = formData;
        config.headers = {
          ...config.headers,
          'content-type': 'multipart/form-data',
          productionTip: true,
        };
        break;
      }
    }

    if (config.needBiz && !('bk_biz_id' in data)) {
      if (data instanceof FormData) {
        if (hasBizId) {
          !data.has('bk_biz_id') && data.append('bk_biz_id', String(window.cc_biz_id));
        } else if (window.space_uid) {
          !data.has('space_uid') && data.append('space_uid', window.space_uid);
        }
      } else {
        if (hasBizId) {
          (data as Record<string, any>).bk_biz_id = window.cc_biz_id;
        } else if (window.space_uid) {
          (data as Record<string, any>).space_uid = window.space_uid;
        }
      }
    }

    return axios({
      method,
      url: newUrl,
      data,
      ...config,
    })
      .then((res: any) => {
        if (config.needRes) {
          return Promise.resolve(res as T);
        }
        return Promise.resolve(res.data);
      })
      .catch((err: ApiError) => {
        const message = makeMessage(err.error_details || err.message || '', traceparent, config.needTraceId);
        if (message && config.needMessage && err.code && !noMessageCode.includes(err.code)) {
          bkMessage(message);
        }
        return Promise.reject(axiosError.includes(String(err?.code)) ? '' : err);
      });
  };
};
