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
import type { IHeaderInfo, IParamsValueItem } from './types';

export const localDataConvertToRequest = (data: IHeaderInfo[]) => {
  const headers = data.find(item => item.key === 'Headers');
  const authorize = data.find(item => item.key === 'Authorization');
  const body = data.find(item => item.key === 'Body');
  const failedRetry = data.find(item => item.key === 'Seting');
  const queryParams = data.find(item => item.key === 'Params');
  const res = {
    headers: [],
    queryParams: [],
    authorize: {
      authConfig: {},
      authType: '',
      insecure_skip_verify: false,
    },
    body: {
      dataType: '',
      contentType: '',
      content: '',
      params: [],
    },
    failedRetry: {},
  };
  // headers
  res.headers = ((headers.value as IParamsValueItem[]) || []).filter(item => {
    const { key, value, desc } = item;
    return key || value || desc;
  });
  // params
  res.queryParams = ((queryParams.value as IParamsValueItem[]) || []).filter(item => {
    const { key, value, desc } = item;
    return key || value || desc;
  });
  // authorize
  res.authorize.authType = authorize.type;
  const authValue = authorize[authorize.type];
  authValue && (res.authorize.authConfig = authValue);
  res.authorize.insecure_skip_verify = authorize.insecure_skip_verify ?? false;
  // body
  res.body.dataType = body.type;
  const { type } = body;
  const bodyValue = body[body.type];
  if (bodyValue) {
    if (type === 'raw') {
      res.body.contentType = bodyValue.type;
      res.body.content = bodyValue.content;
    }
    // type === 'raw' && (
    //   res.body[type] = {
    //     contentType: bodyValue.type,
    //     content: bodyValue.content
    //   }
    // )
    if (['form_data', 'x_www_form_urlencoded'].includes(type)) {
      res.body.params = bodyValue.filter(item => {
        const { key, value, desc } = item;
        return key || value || desc;
      });
      // res.body[type] = {
      //   params: bodyValue.filter((item) => {
      //     const { key, value, desc } = item
      //     return key || value || desc
      //   })
      // }
    }
  }
  // failedRetry
  res.failedRetry = failedRetry.value;
  return res;
};
