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

import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse, type AxiosError } from 'axios';
import { getCookie } from 'monitor-common/utils/utils';
import * as qs from 'qs';

import { authorityStore, bkMessage, makeMessage } from '../utils/index';

// 类型定义
interface ErrorResponse {
  status: number;
  data: {
    code?: number;
    message?: string;
    error_details?: string;
    login_url?: string;
    has_plain?: boolean;
  };
}

interface CustomAxiosRequestConfig extends AxiosRequestConfig {
  needMessage?: boolean;
  needTraceId?: boolean;
  reject403?: boolean;
  headers?: any;
}

interface FileResponseData {
  filename: string;
  isfile: boolean;
  data: any;
}

interface ApiResponseData {
  result: boolean;
  data?: any;
  message?: string;
  code?: number;
  error_details?: string;
}

// 错误请求处理 3314001(名称重复)
const noMessageCode: number[] = [3314001, 3310003];

const errorHandle = (response: ErrorResponse, config: CustomAxiosRequestConfig): void => {
  const traceparent = config?.headers?.traceparent;
  const resMessage = makeMessage(
    response.data.error_details || response.data.message || '请求出错了！',
    traceparent,
    config.needTraceId
  );

  switch (response.status) {
    case 502:
      if (config.needMessage) bkMessage(resMessage);
      break;
    case 400:
      if (response.data.code && !noMessageCode.includes(response.data.code)) {
        if (config.needMessage) bkMessage(resMessage);
      }
      break;
    case 401:
      {
        const { data } = response;
        if (process.env.NODE_ENV === 'development') {
          if (data.login_url) {
            const url = new URL(data.login_url);
            url.searchParams.set('c_url', location.href);
            window.open(url.href, '_self');
          }
        } else {
          const handleLoginExpire = (): void => {
            window.location.href = `${window.bk_paas_host.replace(/\/$/g, '')}/login/`;
          };
          if (data?.has_plain) {
            try {
              if (data.login_url) {
                // 初始化api 用于转换登入
                if (config.url?.includes('/commons/context/enhanced') && config.params?.context_type === 'basic') {
                  const url = `${data.login_url.split('c_url=')[0]}c_url=${encodeURIComponent(location.href)}`;
                  window.open(url, '_self');
                  return;
                }
                const url = new URL(data.login_url);
                const curl = url.searchParams.get('c_url');
                url.protocol = location.protocol;
                if (curl) {
                  url.searchParams.set('c_url', curl.replace(/^http:/, location.protocol));
                  window.showLoginModal?.({ loginUrl: url.href });
                } else {
                  window.showLoginModal?.({ loginUrl: data.login_url.replace(/^http:/, location.protocol) });
                }
              } else {
                handleLoginExpire();
              }
            } catch {
              handleLoginExpire();
            }
          } else {
            handleLoginExpire();
          }
        }
      }
      break;
    case 404:
      if (config.needMessage) bkMessage(resMessage);
      break;
    case 403:
    case 499:
      /* 避免进入仪表盘内重复显示无权限提示 */
      if (
        !config.reject403 &&
        window.space_list?.length &&
        !(
          (['#/', '#/event-center'].includes(location.hash.replace(/\?.*/, '')) ||
            location.hash.includes('#/event-center/detail')) &&
          !config.url?.includes('/incident/')
        ) &&
        config.url !== 'rest/v2/grafana/dashboards/'
      ) {
        authorityStore?.()?.showAuthorityDetail?.(response.data);
      }
      break;
    default:
      break;
  }
};

const instance: AxiosInstance = axios.create({
  timeout: 1000 * 120,
  withCredentials: true,
  paramsSerializer(params: any): string {
    return qs.stringify(params, { arrayFormat: 'brackets' });
  },
  baseURL:
    (window.__BK_WEWEB_DATA__?.host || '').replace(/\/$/, '') +
    (process.env.NODE_ENV === 'production' ? window.site_url : process.env.APP === 'mobile' ? '/weixin' : '/'),
  xsrfCookieName: 'X-CSRFToken',
});

instance.defaults.headers.post['Content-Type'] = 'application/x-www-form-urlencoded';

instance.interceptors.request.use(
  (config: CustomAxiosRequestConfig): CustomAxiosRequestConfig => {
    if (!['HEAD', 'OPTIONS', 'TRACE'].includes(config.method?.toUpperCase() || '')) {
      config.headers = config.headers || {};
      config.headers['X-CSRFToken'] = window.csrf_token || getCookie(window.csrf_cookie_name);
    }
    config.headers = config.headers || {};
    config.headers['X-Requested-With'] = 'XMLHttpRequest';
    config.headers['Source-App'] = window.source_app;

    const isWhiteList = ['/get_context', 'get_token/get_share_params'].some(url => config.url?.includes(url));
    if (!isWhiteList && (window.__BK_WEWEB_DATA__?.token || window.token)) {
      config.headers.Authorization = `Bearer ${window.__BK_WEWEB_DATA__?.token || window.token}`;
    }
    return config;
  },
  (error: AxiosError): Promise<AxiosError> => Promise.reject(error)
);

instance.interceptors.response.use(
  // 请求成功
  (res: AxiosResponse<ApiResponseData>): Promise<AxiosResponse<ApiResponseData | FileResponseData>> => {
    if (res.status === 200) {
      if (res.headers['content-disposition'] && res.config.method?.toLowerCase() === 'post') {
        const filename = res.headers['content-disposition'].split('filename=')[1]?.split(';')[0]?.replace(/"/g, '');
        const fileData: FileResponseData = {
          filename,
          isfile: true,
          data: res.data,
        };
        return Promise.resolve({
          data: fileData,
        } as unknown as AxiosResponse<FileResponseData>);
      }
      if (!res.data.result) {
        return Promise.reject(res.data);
      }
      return Promise.resolve(res.data) as unknown as Promise<AxiosResponse<ApiResponseData>>;
    }
    return Promise.reject(res);
  },
  // 请求失败
  (error: AxiosError): Promise<AxiosError | AxiosResponse> => {
    const { response, config } = error;
    if (response) {
      // 请求已发出，但是不在2xx的范围
      errorHandle(response as ErrorResponse, config as CustomAxiosRequestConfig);
      return Promise.reject(response);
    }
    // 处理断网的情况
    // eg:请求超时或断网时，更新state的network状态
    // network状态在app.vue中控制着一个全局的断网提示组件的显示隐藏
    // 关于断网组件中的刷新重新获取数据，会在断网组件中说明
    // if (!window.navigator.onLine) {
    //     store.commit('changeNetwork', false)
    // } else {
    // }
    return Promise.reject(error);
  }
);

export default instance;
