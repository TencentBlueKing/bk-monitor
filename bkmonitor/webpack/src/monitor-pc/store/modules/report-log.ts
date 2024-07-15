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
import { frontendReportEvent } from 'monitor-api/modules/commons';
import debounceDecorator from 'monitor-common/utils/debounce-decorator';
import { Action, Module, VuexModule, getModule } from 'vuex-module-decorators';

import { getRouteConfigById } from '../../router/router-config';
import store from '../store';

let oldRouteId = '';
@Module({ name: 'report-log', dynamic: true, namespaced: true, store })
class ReportLogStore extends VuexModule {
  @Action
  @debounceDecorator(1000)
  reportRouteLog(params: Record<string, any>) {
    if (oldRouteId === params.route_id) return;
    oldRouteId = params.route_id;
    const space = window.space_list?.find(item => +item.bk_biz_id === +window.cc_biz_id);
    const routeConfig = getRouteConfigById(params.nav_id);
    frontendReportEvent(
      {
        event_name: '用户运营数据',
        event_content: '基于前端路由的运营数据上报',
        target: 'bk_monitor',
        timestamp: Date.now(),
        dimensions: {
          ...params,
          space_id: space?.space_uid || window.cc_biz_id,
          space_name: space?.space_name || window.cc_biz_id,
          user_name: window.user_name || window.username,
          nav_name: (!space ? '临时 ' : '') + (params.nav_name || routeConfig?.name),
        },
      },
      {
        needMessage: false,
        needTraceId: false,
      }
    ).catch(() => false);
  }
}
export default getModule(ReportLogStore);
