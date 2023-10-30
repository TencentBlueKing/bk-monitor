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
import { random } from '@common/utils';
import { TabPanel } from 'bk-magic-vue';

import { collectInstanceStatus } from '../../../../monitor-api/modules/collecting';
import MonitorTab from '../../../components/monitor-tab/monitor-tab';

import LinkStatus from './components/link-status';
import StorageState from './components/storage-state';
import { TabEnum } from './typings/detail';
import CollectorStatusDetails from './collector-status-details';

import './collector-detail.scss';

Component.registerHooks(['beforeRouteEnter']);
@Component
export default class CollectorDetail extends tsc<{}> {
  active = TabEnum.StorageState;
  collectId = 0;

  allData = {
    [TabEnum.targetDetail]: {
      data: null,
      updateKey: random(8)
    }
  };

  public beforeRouteEnter(to: Route, from: Route, next: Function) {
    const { params } = to;
    next((vm: CollectorDetail) => {
      vm.collectId = Number(params.id);
    });
  }

  handleTabChange(v: TabEnum) {
    this.active = v;
    if (this.active === TabEnum.targetDetail) {
      this.getStatusDetails();
    }
  }

  /**
   * @description 获取采集详情tab数据
   */
  getStatusDetails() {
    collectInstanceStatus({
      // collect_config_id: this.id
      id: this.collectId
    })
      .then(data => {
        this.allData[TabEnum.targetDetail].data = data;
        this.allData[TabEnum.targetDetail].updateKey = random(8);
      })
      .catch(() => {
        // this.data = mockData;
        // this.updateKey = random(8);
      });
  }

  render() {
    return (
      <div class='collector-detail-page'>
        <MonitorTab
          active={this.active}
          on-tab-change={this.handleTabChange}
        >
          <TabPanel
            label={this.$t('采集详情')}
            name={TabEnum.targetDetail}
          >
            <CollectorStatusDetails
              data={this.allData[TabEnum.targetDetail].data}
              updateKey={this.allData[TabEnum.targetDetail].updateKey}
            ></CollectorStatusDetails>
          </TabPanel>
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
