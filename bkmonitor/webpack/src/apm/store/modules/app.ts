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
/* eslint-disable new-cap */
import { getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';
import store from '@store/store';
import { docCookies, LANGUAGE_COOKIE_KEY, LOCAL_BIZ_STORE_KEY } from 'monitor-common/utils';

import { IDocLinkData, ISpaceItem } from '../../typings';

export interface IAppState {
  navId: string;
  userName: string;
  bizId: number;
  bizList: ISpaceItem[];
  csrfCookieName: string;
  siteUrl: string;
  bkUrl: string;
  lang: string;
  navRouteList: INavRouteListItem[];
  extraDocLinkMap: Record<string, IDocLinkData>;
}

interface INavRouteListItem {
  id: string;
  name: string;
}

@Module({ name: 'app', namespaced: true, dynamic: true, store })
class AppStore extends VuexModule implements IAppState {
  public navId = 'home';
  public userName = '';
  public bizId;
  public bizList = [];
  public csrfCookieName = '';
  public siteUrl = '/';
  public navTitle = '';
  public navRouteList = [];
  public bkUrl = '';
  public lang = docCookies.getItem(LANGUAGE_COOKIE_KEY) || 'zh-cn';
  public extraDocLinkMap = {};
  @Mutation
  SET_APP_STATE(data: IAppState) {
    Object.keys(data).forEach(key => {
      this[key] = data[key];
    });
  }
  @Mutation
  SET_NAV_TITLE(title: string) {
    this.navTitle = title;
  }

  @Mutation
  SET_NAV_ID(navId: string) {
    this.navId = navId;
  }

  /**
   * 修改全局的面包屑数据
   * @param list 面包屑数据
   */
  @Mutation
  setNavRouterList(list: INavRouteListItem[]) {
    this.navRouteList = list;
  }

  /** 切换业务id逻辑 */
  @Mutation
  handleChangeBizId({ bizId, ctx }) {
    window.cc_biz_id = +bizId;
    window.bk_biz_id = +bizId;
    localStorage.setItem(LOCAL_BIZ_STORE_KEY, `${bizId}`);
    const { navId } = ctx.$route.meta;
    const handleReload = () => {
      const { needClearQuery } = ctx.$route.meta;
      // 清空query查询条件
      if (needClearQuery) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${ctx.$route.path}`;
      } else {
        location.search = `?bizId=${window.cc_biz_id}`;
      }
    };
    // 所有页面的子路由在切换业务的时候都统一返回到父级页面
    if (navId !== ctx.$route.name) {
      const parentRoute = ctx.$router.options.routes.find(item => item.name === navId);
      if (parentRoute) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${parentRoute.path}`;
      } else {
        handleReload();
      }
    } else {
      handleReload();
    }
  }

  /**
   * @description: 更新文档链接
   * @param {Object} data
   */
  @Mutation
  updateExtraDocLinkMap(data: Record<string, IDocLinkData>) {
    this.extraDocLinkMap = data;
  }
}

export default getModule(AppStore);
