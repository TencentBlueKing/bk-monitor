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

// import { listEventLog } from 'monitor-api/modules/alert_events'
import { listAlertLog } from 'monitor-api/modules/alert';
import { transformDataKey } from 'monitor-common/utils/utils';
import { Action, Module, VuexModule, getModule } from 'vuex-module-decorators';

import store from '@store/store';

@Module({ name: 'event-detail', dynamic: true, namespaced: true, store })
class EventDetail extends VuexModule {
  @Action
  async getListEventLog(params) {
    const data = await listAlertLog(params);
    for (const item of data) {
      item.logIcon = `icon-mc-alarm-${item.operate.toLocaleLowerCase()}`;
      if (item.operate === 'RECOVER' || item.operate === 'RECOVERING') {
        item.logIcon = 'icon-mc-alarm-recovered';
      }
      if (item.operate === 'ABORT_RECOVER') {
        item.logIcon = 'icon-mc-alarm-notice';
      }
      if (item.operate === 'ANOMALY_NOTICE') {
        item.logIcon = 'icon-mc-alarm-notice';
      }
      if (item.operate === 'ACTION' || item.operate === 'ALERT_QOS') {
        item.logIcon = 'icon-mc-alarm-converge';
      }

      if (item.operate === 'CLOSE' || item.operate === 'SYSTEM_CLOSE' || item.operate === 'EVENT_DROP') {
        item.logIcon = 'icon-mc-alarm-closed';
      }

      if (item.is_multiple) {
        item.collapse = true;
        item.expandTime = `${item.begin_time} 至 ${item.time}`;
        item.expand = false;
      } else {
        item.collapse = false;
        item.expand = true;
      }
      item.border = false;
      item.show = true;
      item.expandDate = '';
    }
    return transformDataKey(data);
  }
}

export default getModule(EventDetail);
