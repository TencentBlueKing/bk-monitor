export interface IHeaderInfo {
  basic_auth?: IUserInfo;
  bearer_token?: IToken;
  desc: string;
  enable?: boolean;
  form_data?: IParamsValueItem[];
  hide?: boolean;
  insecure_skip_verify?: boolean;
  key: THeaderType;
  name: string;
  raw?: IRaw;
  type?: string;
  value?: IParamsValueItem[] | ISetingValue | string;
  x_www_form_urlencoded?: IParamsValueItem[];
}
export interface IHttpData {
  method: TMethod;
  url: string;
}
export interface IParamsValueItem {
  desc: string;
  index?: number;
  isBuiltin?: boolean;
  isEnabled?: boolean;
  key: string;
  value: string;
}

export interface IRaw {
  content: string;
  type: string;
}
export interface ISelectListItem {
  data?: any;
  id: string;
  name: string;
  unit?: string;
}
export interface ISetingValue {
  maxRetryTimes: number;
  needPoll?: boolean;
  notifyInterval?: number;
  retryInterval: number;
  // interval: number,
  timeout: number;
}

export interface IToken {
  token: string;
}

export interface IUserInfo {
  password: string;
  username: string;
}

export type THeaderType = 'Authorization' | 'Body' | 'Headers' | 'Params' | 'Seting';

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
