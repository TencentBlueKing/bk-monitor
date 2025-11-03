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
import { Action, getModule, Module, VuexModule } from 'vuex-module-decorators';

import $http from '../../api';
import { getRouteConfigById } from '../../router';
import store from '@/store';

let oldRouteId = '';
let oldNavId = '';
let oldspaceUid = '';
@Module({ name: 'report-log', dynamic: true, namespaced: true, store })
class ReportLogStore extends VuexModule {
  @Action
  reportRouteLog(params: Record<string, any>) {
    const { isAppFirstLoad, bkBizId, spaceUid, mySpaceList: spaceList } = store.state;

    if (!(bkBizId || spaceUid)) {
      return;
    }

    if (
      !isAppFirstLoad &&
      oldspaceUid === spaceUid &&
      params.nav_name !== '日志聚类' &&
      (oldRouteId === params.route_id || oldNavId === params.nav_id)
    ) {
      return;
    }

    oldRouteId = params.route_id;
    oldNavId = params.nav_id;
    oldspaceUid = spaceUid;

    const username = store.state.userMeta?.username;
    const space = spaceList?.find(item => item.space_uid === spaceUid);
    const routeConfig = getRouteConfigById(params.nav_id, spaceUid, bkBizId, params.externalMenu);

    $http
      .request(
        'report/frontendEventReport',
        {
          data: {
            event_name: '用户运营数据',
            event_content: '基于前端路由的运营数据上报',
            target: 'bk_log',
            timestamp: Date.now(),
            dimensions: {
              space_id: space?.space_uid || bkBizId,
              space_name: space?.space_name || bkBizId,
              user_name: username,
              nav_name: params.nav_name || routeConfig?.meta?.title,
              version: localStorage.getItem('retrieve_version') || 'v2',
              ...params,
            },
          },
        },
        {
          catchIsShowMessage: false,
        },
      )
      .catch(() => false);
  }
}
export default getModule(ReportLogStore);
