/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Mixins, Watch } from 'vue-property-decorator';

import {
  collectConfigList,
  // collectInstanceStatus,
  frontendCollectConfigDetail,
  frontendCollectConfigTargetInfo,
} from 'monitor-api/modules/collecting';
import { collectingTargetStatus, storageStatus } from 'monitor-api/modules/datalink';
import { listUserGroup } from 'monitor-api/modules/model';
import { random } from 'monitor-common/utils';

import MonitorTab from '../../../components/monitor-tab/monitor-tab';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as collectAuth from '../authority-map';
import { STATUS_LIST } from '../collector-host-detail/utils';
import CollectorConfiguration from './collector-configuration';
import CollectorStatusDetails from './collector-status-details';
import AlertTopic from './components/alert-topic';
import DetailLoadError from './components/detail-load-error';
import DetailSkeleton from './components/detail-skeleton';
import FieldDetails from './components/field-details';
import LinkStatus from './components/link-status';
import StorageState from './components/storage-state';
import DetailRequest from './detail-request';
import { type DetailData, TabEnum, TCollectorAlertStage } from './typings/detail';

import type { IAlarmGroupList } from './components/alarm-group';
import type { NavigationGuardNext, Route } from 'vue-router';

import './collector-detail.scss';

Component.registerHooks(['beforeRouteEnter']);
@Component
export default class CollectorDetail extends Mixins(authorityMixinCreate(collectAuth)) {
  active = TabEnum.Configuration;
  collectId = 0;

  detailData: DetailData = {
    basic_info: {},
    extend_info: {},
    metric_list: [],
    runtime_params: [],
    subscription_id: undefined,
  };

  allData = {
    [TabEnum.TargetDetail]: {
      data: null,
      updateKey: random(8),
      needPolling: true,
      timer: null,
      topicKey: '',
    },
    [TabEnum.StorageState]: {
      data: null,
      topicKey: '',
    },
    [TabEnum.Configuration]: {},
    [TabEnum.DataLink]: {
      topicKey: '',
    },
    [TabEnum.FieldDetails]: {},
  };

  // 采集目标
  targetInfo: Record<string, any> = {};
  // 告警组
  alarmGroupList: IAlarmGroupList[] = [];
  /* 从采集列表获取当前采集数据 */
  collectConfigData = null;

  requests = {
    config: new DetailRequest(),
    detail: new DetailRequest(),
    targets: new DetailRequest(),
    hosts: new DetailRequest(),
    storage: new DetailRequest(),
    groups: new DetailRequest(),
  };
  disposed = false;
  pollingPaused = false;

  beforeDestroy() {
    this.disposed = true;
    this.cancelRequests();
  }

  cancelRequests() {
    window.clearTimeout(this.allData[TabEnum.TargetDetail].timer);
    Object.values(this.requests).forEach(request => {
      request.cancel();
    });
  }

  @Watch('$route.params.id')
  handleCollectIdChange(value: string) {
    if (this.$route.name !== 'collect-config-detail' || Number(value) === this.collectId) return;
    this.cancelRequests();
    this.collectId = Number(value);
    Object.values(this.requests).forEach(request => {
      request.loaded = false;
      request.error = false;
    });
    this.collectConfigData = null;
    this.detailData = {
      basic_info: {},
      extend_info: {},
      metric_list: [],
      runtime_params: [],
      subscription_id: undefined,
    };
    this.targetInfo = {};
    this.allData[TabEnum.TargetDetail].data = null;
    this.allData[TabEnum.StorageState].data = null;
    this.getCollectConfigListItem();
    const tab = this.$route.query.tab as TabEnum;
    this.handleTabChange(Object.values(TabEnum).includes(tab) ? tab : TabEnum.Configuration, true);
  }

  public beforeRouteEnter(to: Route, _from: Route, next: NavigationGuardNext) {
    const { params } = to;
    next((vm: CollectorDetail) => {
      vm.collectId = Number(params.id);
    });
  }

  created() {
    this.collectId = Number(this.$route.params.id);
    this.$store.commit('app/SET_NAV_ROUTE_LIST', [
      { name: this.$t('route-数据采集'), id: 'collect-config' },
      { name: this.$t('route-采集详情'), id: 'collect-config-detail' },
    ]);
    this.getCollectConfigListItem();
    const tab = String(this.$route.query?.tab || this.active) as TabEnum;
    this.handleTabChange(Object.values(TabEnum).includes(tab) ? tab : TabEnum.Configuration, true);
  }
  async handleTabChange(v: TabEnum, init = false) {
    if (this.disposed || (!init && v === this.active)) return;
    this.requests.hosts.cancel();
    this.requests.storage.cancel();
    this.active = v;
    this.pollingPaused = false;
    window.clearTimeout(this.allData[TabEnum.TargetDetail].timer);
    switch (v) {
      case TabEnum.Configuration:
        {
          if (!this.requests.config.loaded) this.getCollectConfigListItem();
          this.getDetails();
          this.getTargetInfoData();
        }
        break;
      case TabEnum.TargetDetail:
        {
          this.getAlarmGroupList();
          this.getHosts();
        }
        break;
      case TabEnum.StorageState:
        {
          this.getAlarmGroupList();
          this.getStorageStateData();
        }
        break;
      case TabEnum.DataLink:
        {
          this.getAlarmGroupList();
        }
        break;
      case TabEnum.FieldDetails:
        {
          this.getDetails();
        }
        break;
    }
    if (this.allData[v] && 'topicKey' in this.allData[v]) {
      this.allData[v].topicKey = random(8);
    }
    if (!init) {
      this.$router.replace({
        name: this.$route.name,
        query: {
          ...this.$route.query,
          tab: v,
        },
      });
    }
  }

  getCollectConfigListItem() {
    if (this.disposed || this.requests.config.loading || this.requests.config.loaded) return;
    return this.requests.config.run(
      signal =>
        collectConfigList(
          { refresh_status: false, search: { id: this.collectId }, page: 1, limit: 1 },
          { signal, needMessage: false }
        ),
      data => {
        this.collectConfigData = data.config_list?.find(item => Number(item.id) === this.collectId) || null;
      }
    );
  }

  getDetails() {
    if (this.disposed || !this.collectId || this.requests.detail.loaded || this.requests.detail.loading) return;
    return this.requests.detail.run(
      signal =>
        frontendCollectConfigDetail({ id: this.collectId, with_target_info: false }, { signal, needMessage: false }),
      data => {
        this.detailData = data;
      }
    );
  }

  getTargetInfoData() {
    if (this.disposed || !this.collectId || this.requests.targets.loaded || this.requests.targets.loading) return;
    return this.requests.targets.run(
      signal => frontendCollectConfigTargetInfo({ id: this.collectId }, { signal, needMessage: false }),
      data => {
        this.targetInfo = data;
      }
    );
  }

  getStorageStateData() {
    if (this.disposed) return;
    return this.requests.storage.run(
      signal => storageStatus({ collect_config_id: this.collectId }, { signal, needMessage: false }),
      data => {
        this.allData[TabEnum.StorageState].data = data;
      }
    );
  }

  getAlarmGroupList(force = false) {
    if (this.disposed || this.requests.groups.loading || (!force && this.requests.groups.loaded)) return;
    return this.requests.groups.run(
      signal => listUserGroup({ exclude_detail_info: 1 }, { signal, needMessage: false }),
      data => {
        this.alarmGroupList = data.map(item => ({
          id: item.id,
          name: item.name,
          needDuty: item.need_duty,
          receiver:
            item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || [],
        }));
      }
    );
  }

  async getHosts() {
    if (this.disposed || this.active !== TabEnum.TargetDetail) return;
    const target = this.allData[TabEnum.TargetDetail];
    window.clearTimeout(target.timer);
    const success = await this.requests.hosts.run(
      signal => collectingTargetStatus({ collect_config_id: this.collectId }, { signal, needMessage: false }),
      data => {
        target.data = data;
        target.needPolling = data.contents.some(item => item.child.some(set => STATUS_LIST.includes(set.status)));
        target.updateKey = random(8);
      }
    );
    if (this.disposed || this.active !== TabEnum.TargetDetail || this.pollingPaused || this.requests.hosts.loading)
      return;
    if ((success || this.requests.hosts.error) && this.requests.hosts.loaded && target.needPolling)
      this.schedulePolling();
  }

  schedulePolling() {
    const target = this.allData[TabEnum.TargetDetail];
    window.clearTimeout(target.timer);
    if (this.disposed || this.active !== TabEnum.TargetDetail || this.pollingPaused) return;
    target.timer = window.setTimeout(() => this.getHosts(), 10000);
  }

  handlePolling(enabled = true) {
    this.pollingPaused = !enabled;
    window.clearTimeout(this.allData[TabEnum.TargetDetail].timer);
    if (enabled) this.schedulePolling();
    else this.requests.hosts.cancel();
  }

  handleRefreshData() {
    return this.getHosts();
  }

  /**
   * @description 跳转到采集视图
   */
  handleToRetrieval() {
    if (!this.collectConfigData) {
      this.getCollectConfigListItem();
      return;
    }
    const url = this.$router.resolve({
      name: 'collect-config-view',
      params: {
        id: this.collectConfigData.id,
        title: this.collectConfigData.name,
      },
      query: {
        name: this.collectConfigData.name,
        customQuery: JSON.stringify({
          pluginId: this.collectConfigData.plugin_id,
          bizId: this.collectConfigData.bk_biz_id,
        }),
      },
    });
    window.open(url.href);
  }

  async handleAlarmGroupListRefresh() {
    await this.getAlarmGroupList(true);
  }

  render() {
    return (
      <div class='collector-detail-page'>
        {this.requests.groups.error &&
          [TabEnum.TargetDetail, TabEnum.DataLink, TabEnum.StorageState].includes(this.active) && (
            <DetailLoadError
              compact
              onRetry={this.handleAlarmGroupListRefresh}
            />
          )}
        <MonitorTab
          key={this.collectId}
          active={this.active}
          on-tab-change={v => this.handleTabChange(v)}
        >
          <bk-tab-panel
            label={this.$t('配置信息')}
            name={TabEnum.Configuration}
            renderDirective='if'
          >
            {!!this.collectId && (
              <CollectorConfiguration
                id={this.collectId as any}
                collectConfigData={this.collectConfigData}
                configLoading={this.requests.config.loading}
                detailData={this.detailData}
                detailLoaded={this.requests.detail.loaded}
                loadError={this.requests.detail.error}
                loading={this.requests.detail.loading}
                show={this.active === TabEnum.Configuration}
                tableLoading={this.requests.targets.loading}
                targetError={this.requests.targets.error}
                targetInfo={this.targetInfo}
                targetLoaded={this.requests.targets.loaded}
                onRetryDetail={this.getDetails}
                onRetryTargets={this.getTargetInfoData}
                {...{
                  on: {
                    'update-name': (_id, name) => {
                      this.detailData.basic_info.name = name;
                      if (this.collectConfigData) this.collectConfigData.name = name;
                    },
                  },
                }}
              />
            )}
          </bk-tab-panel>
          <bk-tab-panel
            label={this.$t('采集状态')}
            name={TabEnum.TargetDetail}
            renderDirective='if'
          >
            {
              <AlertTopic
                id={this.collectId as any}
                class='mb-24'
                alarmGroupList={this.alarmGroupList}
                alarmGroupListLoading={this.requests.groups.loading}
                stage={TCollectorAlertStage.collecting}
                updateKey={this.allData[TabEnum.TargetDetail].topicKey}
                onAlarmGroupListRefresh={this.handleAlarmGroupListRefresh}
              />
            }
            {this.requests.hosts.error && (
              <DetailLoadError
                compact={this.requests.hosts.loaded}
                onRetry={this.handleRefreshData}
              />
            )}
            {this.requests.hosts.loading && !this.requests.hosts.loaded ? (
              <DetailSkeleton section='status' />
            ) : (
              this.requests.hosts.loaded && (
                <CollectorStatusDetails
                  data={
                    this.allData[TabEnum.TargetDetail]?.data || {
                      contents: [],
                    }
                  }
                  tableLoading={false}
                  updateKey={this.allData[TabEnum.TargetDetail].updateKey}
                  onCanPolling={this.handlePolling}
                  onRefresh={this.handleRefreshData}
                />
              )
            )}
          </bk-tab-panel>
          <bk-tab-panel
            label={this.$t('链路状态')}
            name={TabEnum.DataLink}
            renderDirective='if'
          >
            <AlertTopic
              id={this.collectId as any}
              class='mb-24'
              alarmGroupList={this.alarmGroupList}
              alarmGroupListLoading={this.requests.groups.loading}
              stage={TCollectorAlertStage.transfer}
              updateKey={this.allData[TabEnum.DataLink].topicKey}
              onAlarmGroupListRefresh={this.handleAlarmGroupListRefresh}
            />
            <LinkStatus
              collectId={this.collectId}
              show={this.active === TabEnum.DataLink}
            />
          </bk-tab-panel>
          <bk-tab-panel
            label={this.$t('存储状态')}
            name={TabEnum.StorageState}
            renderDirective='if'
          >
            <AlertTopic
              id={this.collectId as any}
              class='mb-24'
              alarmGroupList={this.alarmGroupList}
              alarmGroupListLoading={this.requests.groups.loading}
              stage={TCollectorAlertStage.storage}
              updateKey={this.allData[TabEnum.StorageState].topicKey}
              onAlarmGroupListRefresh={this.handleAlarmGroupListRefresh}
            />
            {this.requests.storage.error && (
              <DetailLoadError
                compact={this.requests.storage.loaded}
                onRetry={this.getStorageStateData}
              />
            )}
            {this.requests.storage.loading && !this.requests.storage.loaded ? (
              <DetailSkeleton section='storage' />
            ) : (
              this.requests.storage.loaded && (
                <StorageState
                  collectId={this.collectId}
                  data={this.allData[TabEnum.StorageState].data}
                  loading={this.requests.storage.loading}
                />
              )
            )}
          </bk-tab-panel>
          <bk-tab-panel
            label={this.$t('指标/维度')}
            name={TabEnum.FieldDetails}
            renderDirective='if'
          >
            {this.requests.detail.error ? (
              <DetailLoadError onRetry={this.getDetails} />
            ) : (
              <FieldDetails
                detailData={this.detailData}
                loading={this.requests.detail.loading}
              />
            )}
          </bk-tab-panel>
          <span
            class='tab-right-tip'
            slot='setting'
          >
            <span class='icon-monitor icon-tishi' />
            <i18n path='数据采集好了，去 {0}'>
              <bk-button
                class='link-btn'
                disabled={!this.collectConfigData}
                loading={this.requests.config.loading}
                text
                onClick={() => this.handleToRetrieval()}
              >
                {this.$t('查看数据')}
              </bk-button>
            </i18n>
          </span>
        </MonitorTab>
        {this.requests.config.error && (
          <DetailLoadError
            compact
            onRetry={this.getCollectConfigListItem}
          />
        )}
      </div>
    );
  }
}
