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

import { ServicesInstance } from '@/platform/services';
import { defineStore } from 'pinia';
import { applicationPinia } from '../pinia';

import { getRouteConfigById } from '../../router/index';
import { useApplicationStore } from '../domains/application-store';

interface ReportLogState {
  oldRouteId: unknown;
  oldNavId: unknown;
  oldspaceUid: string;
}
export const useReportLogStore = defineStore('bklog.report-log', {
  state: (): ReportLogState => ({ oldRouteId: '', oldNavId: '', oldspaceUid: '' }),
  actions: {
    async reportRouteLog(params: Record<string, unknown>) {
      const store = useApplicationStore();
      const { isAppFirstLoad, bkBizId, spaceUid, mySpaceList: spaceList } = store;

      if (!(bkBizId || spaceUid)) {
        return;
      }

      if (
        !isAppFirstLoad &&
        this.oldspaceUid === spaceUid &&
        params.nav_name !== '日志聚类' &&
        (this.oldRouteId === params.route_id || this.oldNavId === params.nav_id)
      ) {
        return;
      }

      this.oldRouteId = params.route_id;
      this.oldNavId = params.nav_id;
      this.oldspaceUid = spaceUid;

      const username = store.userMeta?.username;
      const space = spaceList?.find((item) => item.space_uid === spaceUid);
      const routeConfig = getRouteConfigById(params.nav_id, spaceUid, bkBizId, params.externalMenu);

      ServicesInstance.report
        .frontendEventReport(
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
                version: localStorage.getItem('retrieve_version') || 'v3',
                ...params,
              },
            },
          },
          {
            catchIsShowMessage: false,
          },
        )
        .catch(() => false);

      // 首条路由事件进入上报流程后，启用后续路由去重。
      if (isAppFirstLoad) {
        store.updateState({ isAppFirstLoad: false });
      }
    },
  },
});
export default useReportLogStore(applicationPinia);
