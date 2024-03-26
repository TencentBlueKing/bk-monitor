/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { defineStore } from 'pinia';

import { IDocLinkData, ISpaceItem } from '../../typings';

export interface IAppState {
  userName: string;
  bizId: string | number;
  bizList: ISpaceItem[];
  csrfCookieName: string;
  siteUrl: string;
  navId: string;
  bkUrl: string;
  extraDocLinkMap: Record<string, IDocLinkData>;
}

export const useAppStore = defineStore('app', {
  state: (): IAppState => ({
    navId: 'home',
    userName: window.user_name,
    bizId: window.cc_biz_id,
    bizList: window.space_list,
    csrfCookieName: window.csrf_cookie_name || '',
    siteUrl: window.site_url,
    bkUrl: window.bk_url,
    extraDocLinkMap: {}
  }),
  actions: {
    /**
     * @description: 更新文档链接
     * @param {Object} data
     */
    updateExtraDocLinkMap(data: Record<string, IDocLinkData>) {
      this.extraDocLinkMap = data;
    }
  }
});
