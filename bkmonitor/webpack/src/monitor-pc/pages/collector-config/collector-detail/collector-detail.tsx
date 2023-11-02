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
import { Component, Mixins, Provide } from 'vue-property-decorator';
import { Route } from 'vue-router';
import { random } from '@common/utils';
import { TabPanel } from 'bk-magic-vue';

import { collectInstanceStatus, frontendCollectConfigDetail } from '../../../../monitor-api/modules/collecting';
import { listUserGroup } from '../../../../monitor-api/modules/model';
import MonitorTab from '../../../components/monitor-tab/monitor-tab';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as collectAuth from '../authority-map';

import { IAlarmGroupList } from './components/alarm-group';
import AlertTopic from './components/alert-topic';
import FieldDetails from './components/field-details';
import LinkStatus from './components/link-status';
import StorageState from './components/storage-state';
import { DetailData, TabEnum } from './typings/detail';
import CollectorConfiguration from './collector-configuration';
import CollectorStatusDetails from './collector-status-details';

import './collector-detail.scss';

Component.registerHooks(['beforeRouteEnter']);
@Component
export default class CollectorDetail extends Mixins(authorityMixinCreate(collectAuth)) {
  @Provide('authority') authority: Record<string, boolean> = {};
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Provide('authorityMap') authorityMap;

  active = TabEnum.StorageState;
  collectId = 0;

  detailData: DetailData = {
    basic_info: {},
    extend_info: {},
    metric_list: [],
    runtime_params: [],
    subscription_id: undefined,
    target_info: {}
  };

  allData = {
    [TabEnum.TargetDetail]: {
      data: null,
      updateKey: random(8)
    },
    [TabEnum.FieldDetails]: {
      fieldData: []
    }
  };

  // 告警组
  alarmGroupList: IAlarmGroupList[] = [];

  public beforeRouteEnter(to: Route, from: Route, next: Function) {
    const { params } = to;
    next((vm: CollectorDetail) => {
      vm.collectId = Number(params.id);
    });
  }

  created() {
    this.getAlarmGroupList();
  }

  handleTabChange(v: TabEnum) {
    this.active = v;
    if (this.active === TabEnum.TargetDetail) {
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
        this.allData[TabEnum.TargetDetail].data = data;
        this.allData[TabEnum.TargetDetail].updateKey = random(8);
      })
      .catch(() => {
        // this.data = mockData;
        // this.updateKey = random(8);
      });
  }

  getDetails() {
    frontendCollectConfigDetail({ id: this.collectId }).then(res => {
      this.detailData = res;
    });
  }

  mounted() {
    this.getDetails();
  }

  getAlarmGroupList() {
    return listUserGroup({ exclude_detail_info: 1 }).then(data => {
      this.alarmGroupList = data.map(item => ({
        id: item.id,
        name: item.name,
        needDuty: item.need_duty,
        receiver:
          item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || []
      }));
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
            label={this.$t('配置信息')}
            name={TabEnum.Configuration}
          >
            <CollectorConfiguration
              id={this.collectId}
              show={this.active === TabEnum.Configuration}
            ></CollectorConfiguration>
          </TabPanel>
          <TabPanel
            label={this.$t('采集详情')}
            name={TabEnum.TargetDetail}
          >
            <AlertTopic alarmGroupList={this.alarmGroupList}></AlertTopic>
            <CollectorStatusDetails
              class='mt-24'
              data={this.allData[TabEnum.TargetDetail].data}
              updateKey={this.allData[TabEnum.TargetDetail].updateKey}
            ></CollectorStatusDetails>
          </TabPanel>
          <TabPanel
            label={this.$t('链路状态')}
            name={TabEnum.DataLink}
          >
            <AlertTopic alarmGroupList={this.alarmGroupList}></AlertTopic>
            <LinkStatus
              class='mt-24'
              show={this.active === TabEnum.DataLink}
              collectId={this.collectId}
            />
          </TabPanel>
          <TabPanel
            label={this.$t('存储状态')}
            name={TabEnum.StorageState}
          >
            <AlertTopic alarmGroupList={this.alarmGroupList}></AlertTopic>
            <StorageState
              class='mt-24'
              collectId={this.collectId}
            />
          </TabPanel>
          <TabPanel
            label={this.$t('字段详情')}
            name={TabEnum.FieldDetails}
          >
            <FieldDetails detailData={this.detailData} />
          </TabPanel>
        </MonitorTab>
      </div>
    );
  }
}
