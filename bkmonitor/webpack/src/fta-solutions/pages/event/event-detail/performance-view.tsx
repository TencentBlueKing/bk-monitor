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
import { Component, InjectReactive, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getSceneView } from 'monitor-api/modules/scene_view';
import { random } from 'monitor-common/utils/utils';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import DashboardPanel from 'monitor-ui/chart-plugins/components/dashboard-panel';
import { type IBookMark, type IPanelModel, type IViewOptions, BookMarkModel } from 'monitor-ui/chart-plugins/typings';

import { createAutoTimeRange } from './aiops-chart';
import { type IDetail, setBizIdToPanel } from './type';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './performance-view.scss';

interface IProps {
  detail?: IDetail;
  isProcess?: boolean; // 是否为进程
  show?: boolean;
}

@Component
export default class PerformanceView extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: Boolean, default: false }) isProcess: boolean;

  // 当前场景数据模型
  sceneData: BookMarkModel = null;
  // 配置panels
  localPanels: IPanelModel[] = [];
  dashboardPanelId = random(8);

  /* 用于跳转到主机详情 */
  ip = '0.0.0.0';
  cloudId = '0';
  bkHostId = 0;

  loading = false;

  // 时间范围缓存用于复位功能
  cacheTimeRange = [];

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 当前业务id
  @ProvideReactive('bkBizId') bkBizId: number | string = null;
  // 是否是只读模式
  @InjectReactive('readonly') readonly: boolean;
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }
  @Watch('show')
  handleShow(v: boolean) {
    if (v && !this.localPanels.length) {
      this.getSceneData();
    }
  }

  /* 获取场景数据 */
  async getSceneData() {
    this.loading = true;
    const currentTarget: Record<string, any> = {
      bk_target_ip: '0.0.0.0',
      bk_target_cloud_id: '0',
    };
    const variables: Record<string, any> = {
      bk_target_ip: '0.0.0.0',
      bk_target_cloud_id: '0',
      ip: '0.0.0.0',
      bk_cloud_id: '0',
    };
    this.bkBizId = this.detail.bk_biz_id;
    this.detail.tags?.forEach(item => {
      variables[item.key] = item.value;
    });
    this.detail.dimensions.forEach(item => {
      if (item.key === 'bk_host_id') {
        this.bkHostId = item.value;
        variables.bk_host_id = item.value;
        currentTarget.bk_host_id = item.value;
      }
      if (['bk_target_ip', 'ip', 'bk_host_id'].includes(item.key)) {
        this.ip = item.value;
        variables.bk_target_ip = item.value;
        variables.ip = item.value;
        currentTarget.bk_target_ip = item.value;
      }
      if (['bk_cloud_id', 'bk_target_cloud_id', 'bk_host_id'].includes(item.key)) {
        this.cloudId = item.value;
        variables.bk_target_cloud_id = item.value;
        variables.bk_cloud_id = item.value;
        currentTarget.bk_target_cloud_id = item.value;
      }
    });
    const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimeRange(this.detail.begin_time, this.detail.end_time, interval);
    this.timeRange = [startTime, endTime];
    this.viewOptions = {
      method: 'AVG',
      variables,
      interval,
      group_by: [],
      current_target: currentTarget,
    };
    const data: IBookMark = await getSceneView(
      this.isProcess
        ? {
            bk_biz_id: this.detail.bk_biz_id,
            scene_id: 'host',
            type: 'detail',
            id: 'process',
          }
        : {
            bk_biz_id: this.detail.bk_biz_id,
            scene_id: 'host',
            type: 'detail',
            id: 'host',
          }
    ).catch(() => ({ id: '', panels: [], name: '' }));
    this.sceneData = new BookMarkModel(data || { id: '', panels: [], name: '' });
    this.localPanels = setBizIdToPanel(this.handleGetLocalPanels(this.sceneData.panels), this.detail.bk_biz_id);
    this.loading = false;
  }

  handleGetLocalPanels(panels) {
    const unGroupKey = '__UNGROUP__';
    /** 处理只有一个分组且为未分组时则不显示组名 */
    const rowPanels = panels.filter(item => item.type === 'row');
    if (rowPanels.length === 1 && rowPanels[0]?.id === unGroupKey) {
      const resultPanels = [];
      panels.forEach(item => {
        if (item.type === 'row') {
          resultPanels.push(...item.panels);
        } else {
          resultPanels.push(item);
        }
      });
      return resultPanels;
    }
    /* 当有多个分组且未分组为空的情况则不显示未分组 */
    if (panels.length > 1 && panels.some(item => item.id === unGroupKey)) {
      return panels.filter(item => (item.id === unGroupKey ? !!item.panels?.length : true));
    }
    return panels;
  }

  handleToPerformance() {
    const detailId = this.bkHostId ? this.bkHostId : `${this.ip}-${this.cloudId}`;
    window.open(
      `${location.origin}${location.pathname}?bizId=${this.detail.bk_biz_id}#/performance/detail/${detailId}`
    );
  }

  handleToPerformanceList() {
    window.open(`${location.origin}${location.pathname}?bizId=${this.detail.bk_biz_id}#/performance`);
  }

  handleToNodemanHost() {
    window.open(`${this.$store.getters.bkNodeManHost}#/plugin-manager/list`);
  }

  render() {
    return (
      <div
        class={['event-detail-performance-view', { show: this.show }]}
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.localPanels.length ? (
          <DashboardPanel
            id={this.dashboardPanelId}
            column={3}
            isSingleChart={false}
            isSplitPanel={false}
            needOverviewBtn={false}
            panels={this.localPanels}
          />
        ) : (
          <div class='no-data'>
            {/* 无数据情况暂且不做 */}
            {}
            {/* <img class="no-data-img" src={require('../../../static/img/empty.svg')}></img>
          <div class="no-data-msg">
            {(() => {
              if (this.noDataStatus === '3') {
                return <div class="no-data-01">
                  <div class="row">{window.i18n.t('当前主机无数据 ，跳转主机监控查看')}</div>
                  <div class="link row" onClick={() => this.handleToPerformance()}>{window.i18n.t('跳转到主机监控')}</div>
                </div>;
              } if (this.noDataStatus === '1') {
                return <div class="no-data-02">
                  <div class="row">
                    <span>1. {window.i18n.t('当前主机未安装Agent，跳转节点管理进行配置')}</span>
                    <span class="link" onClick={() => this.handleToNodemanHost()}>{window.i18n.t('跳转到节点管理')}</span>
                  </div>
                  <div class="row">
                    <span>2. {window.i18n.t('直接查看主机监控列表')}</span>
                    <span class="link" onClick={() => this.handleToPerformanceList()}>{window.i18n.t('跳转到主机列表')}</span>
                  </div>
                </div>;
              }
            })()}
          </div> */}
          </div>
        )}
        {!this.readonly && !!this.localPanels.length && (
          <div class='view-bottom'>
            <div class='view-bottom-label'>
              <i18n path='可{0}完整查看'>
                <span
                  class='link'
                  onClick={() => this.handleToPerformance()}
                >
                  {window.i18n.t('跳转至主机监控')}
                  <span class='icon-monitor icon-fenxiang' />
                </span>
              </i18n>
            </div>
          </div>
        )}
      </div>
    );
  }
}
