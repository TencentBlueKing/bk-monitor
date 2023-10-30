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
import { Component } from 'vue-property-decorator';
import { Route } from 'vue-router';
import { Component as tsc } from 'vue-tsx-support';
import { TabPanel } from 'bk-magic-vue';

import MonitorTab from '../../../components/monitor-tab/monitor-tab';

import LinkStatus from './components/link-status';
import StorageState from './components/storage-state';
import { TabEnum } from './typings/detail';

import './collector-detail.scss';

Component.registerHooks(['beforeRouteEnter']);
@Component
export default class CollectorDetail extends tsc<{}> {
  active = TabEnum.StorageState;
  collectId = 0;

  beforeRouteEnter(to: Route, from: Route, next: Function) {
    const { params } = to;
    next((vm: CollectorDetail) => {
      vm.collectId = Number(params.id);
    });
  }

  render() {
    return (
      <div class='collector-detail-page'>
        <MonitorTab
          active={this.active}
          {...{ on: { 'update:active': v => (this.active = v) } }}
        >
          <TabPanel
            label={this.$t('链路状态')}
            name={TabEnum.DataLink}
          >
            <LinkStatus
              show={this.active === TabEnum.DataLink}
              collectId={this.collectId}
            />
          </TabPanel>
          <TabPanel
            label={this.$t('存储状态')}
            name={TabEnum.StorageState}
          >
            <StorageState collectId={this.collectId} />
          </TabPanel>
        </MonitorTab>
      </div>
    );
  }
}
