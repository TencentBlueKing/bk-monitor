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
/*
 * @Date: 2021-06-13 20:42:22
 * @LastEditTime: 2021-06-26 11:33:00
 * @Description:
 */

import Vue from 'vue';

import { docCookies, LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';
import { Module, Mutation, VuexModule } from 'vuex-module-decorators';

import type { ISpaceItem } from '../../typings';

// 设置 biz bg color
export const SET_BIZ_BGCOLOR = 'SET_BIZ_BGCOLOR';

export const SET_NAV_ROUTE_LIST = 'SET_NAV_ROUTE_LIST';
export interface IAppState {
  bizBgColor: string;
  bizId: string;
  bizIdMap: Map<string, ISpaceItem>;
  bizList: ISpaceItem[];
  bkUrl: string;
  csrfCookieName: string;
  lang: string;
  navId: string;
  navRouteList: any[];
  siteUrl: string;
  spaceUidMap: Map<string, ISpaceItem>;
  userName: string;
}

@Module({ name: 'app', namespaced: true })
export default class App extends VuexModule implements IAppState {
  public bizBgColor = ''; // 业务颜色
  public bizId = '';
  public bizIdMap;
  public bizList = [];
  public bkUrl = '';
  public csrfCookieName = '';
  public lang = docCookies.getItem(LANGUAGE_COOKIE_KEY) || 'zh-cn';
  public navId = 'home';
  public navRouteList = [];
  public navTitle = '';
  public siteUrl = '/';
  public spaceUidMap;
  public userName = ''; // 业务id是否切换

  @Mutation
  SET_APP_STATE(data: IAppState) {
    for (const [key, value] of Object.entries(data)) {
      if (key === 'bizList') {
        this[key] = value.map(item => {
          const pinyinStr = Vue.prototype.$bkToPinyin(item.space_name, true, ',') || '';
          const pyText = pinyinStr.replace(/,/g, '');
          const pyfText = pinyinStr
            .split(',')
            .map(str => str.charAt(0))
            .join('');
          return {
            ...item,
            py_text: pyText,
            pyf_text: pyfText,
          };
        });
        this.spaceUidMap = new Map(this.bizList.map(item => [item.space_uid, item]));
        this.bizIdMap = new Map(this.bizList.map(item => [item.bk_biz_id, item]));
        continue;
      }
      this[key] = value;
    }
  }
  @Mutation
  [SET_BIZ_BGCOLOR](val: string) {
    this.bizBgColor = val;
  }

  @Mutation
  SET_NAV_ID(navId: string) {
    this.navId = navId;
  }

  @Mutation
  [SET_NAV_ROUTE_LIST](list) {
    this.navRouteList = list;
  }

  @Mutation
  SET_NAV_TITLE(title: string) {
    this.navTitle = title;
  }
}
