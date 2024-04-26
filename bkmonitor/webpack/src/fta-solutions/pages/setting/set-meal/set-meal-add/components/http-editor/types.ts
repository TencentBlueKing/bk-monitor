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
export type TMethod = 'GET' | 'POST';
export interface IHttpData {
  method: TMethod;
  url: string;
}
export interface ISelectListItem {
  id: string;
  name: string;
  unit?: string;
  data?: any;
}

export interface IToken {
  token: string;
}
export interface IUserInfo {
  username: string;
  password: string;
}
export interface IRaw {
  type: string;
  content: string;
}

export type THeaderType = 'Authorization' | 'Body' | 'Headers' | 'Params' | 'Seting';

export interface IHeaderInfo {
  insecure_skip_verify?: boolean;
  key: THeaderType;
  name: string;
  enable?: boolean;
  desc: string;
  hide?: boolean;
  value?: IParamsValueItem[] | ISetingValue | string;
  type?: string;
  bearer_token?: IToken;
  basic_auth?: IUserInfo;
  form_data?: IParamsValueItem[];
  x_www_form_urlencoded?: IParamsValueItem[];
  raw?: IRaw;
}

export interface ISetingValue {
  // interval: number,
  timeout: number;
  retryInterval: number;
  maxRetryTimes: number;
  needPoll?: boolean;
  notifyInterval?: number;
}

export interface IParamsValueItem {
  index?: number;
  key: string;
  value: string;
  desc: string;
  isEnabled?: boolean;
  isBuiltin?: boolean;
}
