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
const NO_NEED_ERROR_MESSAGE = 'bk_monitor_api_no_message';
const defaultConfig = {
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

const noMessageCode = [3308005, 3314003, 3314004, ...axiosError]; // 无数据状态下 不弹窗
const pendingRequest = new Map(); // 请求取消映射表
// 添加请求取消
const addPendingRequest = (method, url, config) => {
  const requestKey = `${method}_${url}`;
  config.cancelToken =
    config.cancelToken ??
    new CancelToken(cancel => {
      if (!pendingRequest.has(requestKey)) {
        pendingRequest.set(requestKey, cancel);
      }
    });
};
// 移除请求取消
const removePendingRequest = (method, url) => {
  const requestKey = `${method}_${url}`;
  if (pendingRequest.has(requestKey)) {
    pendingRequest.get(requestKey)();
    pendingRequest.delete(requestKey);
  }
};
export const request = (method, url) => {
  return (id, params, config = {}) => {
    let newUrl = url;
    let data = {};
    const hasBizId = !(window.cc_biz_id === -1 || !window.cc_biz_id);
    if (typeof id === 'number' || typeof id === 'string') {
      newUrl = url.replace('{pk}', id);
      data = params || {};
      // biome-ignore lint/style/noParameterAssign:0
      config = Object.assign({}, defaultConfig, config || {});
    } else {
      data = id || {};
      // biome-ignore lint/style/noParameterAssign:0
      config = Object.assign({}, defaultConfig, params || {});
    }
    const methodType = method.toLocaleLowerCase() || 'get';
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
        data.bk_biz_id = window.cc_biz_id;
      } else if (window.space_uid) {
        data.space_uid = window.space_uid;
      }
      return axios({
        method: 'get',
        url: newUrl,
        params: data,
        needMessage: false,
        ...config,
      })
        .then(res => {
          if (config.needRes) {
            return Promise.resolve(res);
          }
          return Promise.resolve(res.data);
        })
        .catch(err => {
          const message = makeMessage(err.error_details || err.message, traceparent, config.needTraceId);
          if (message && config.needMessage && !noMessageCode.includes(err.code)) {
            bkMessage(message);
          }
          // !err.error_details && err.message && (err.message = message);
          return Promise.reject(axiosError.includes(err?.code) ? '' : err);
        });
    }
    for (const value of Object.values(data)) {
      const type = String(value);
      if (type === '[object FileList]' || type === '[object File]') {
        const formData = new FormData();
        for (const [key, val] of Object.entries(data)) {
          formData.append(key, val);
        }
        data = formData;
        config.headers = {
          ...config.headers,
          'content-type': 'multipart/form-data',
          productionTip: true,
        };
      }
    }
    if (config.needBiz && !Object.prototype.hasOwnProperty.call(data, 'bk_biz_id')) {
      if (data instanceof FormData) {
        if (hasBizId) {
          !data.has('bk_biz_id') && data.append('bk_biz_id', window.cc_biz_id);
        } else if (window.space_uid) {
          !data.has('space_uid') && data.append('space_uid', window.space_uid);
        }
      } else {
        if (hasBizId) {
          data.bk_biz_id = window.cc_biz_id;
        } else if (window.space_uid) {
          data.space_uid = window.space_uid;
        }
      }
    }
    return axios({
      method,
      url: newUrl,
      data,
      ...config,
    })
      .then(res => {
        if (config.needRes) {
          return Promise.resolve(res);
        }
        return Promise.resolve(res.data);
      })
      .catch(err => {
        const message = makeMessage(err.error_details || err.message || '', traceparent, config.needTraceId);
        if (message && config.needMessage && !noMessageCode.includes(err.code)) {
          bkMessage(message);
        }
        // !err.error_details && err.message && (err.message = message);
        return Promise.reject(axiosError.includes(err?.code) ? '' : err);
      });
  };
};
