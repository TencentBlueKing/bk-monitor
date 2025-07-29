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
import { Component, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getSceneView } from 'monitor-api/modules/scene_view';
import { random } from 'monitor-common/utils';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import DashboardPanel from 'monitor-ui/chart-plugins/components/dashboard-panel';

import { createAutoTimeRange } from './aiops-chart';

import type { IDetail } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IQueryData } from 'monitor-pc/pages/monitor-k8s/typings';
import type { BookMarkModel, IPanelModel, IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './log-info.scss';

interface IProps {
  detail?: IDetail;
  show?: boolean;
}

@Component
export default class LogInfo extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;

  // 当前场景数据模型
  sceneData: BookMarkModel = null;
  // 配置panels
  localPanels: IPanelModel[] = [];
  dashboardPanelId = random(8);
  loading = false;

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 当前业务id
  @ProvideReactive('bkBizId') bkBizId: number | string = null;
  @ProvideReactive('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;

  @Watch('show')
  handleShow(v: boolean) {
    if (v && !this.localPanels.length) {
      this.getSceneData();
    }
  }

  /* 获取场景数据 */
  async getSceneData() {
    this.loading = true;
    this.bkBizId = this.detail.bk_biz_id;
    const variables: Record<string, any> = {
      bk_host_innerip: '0.0.0.0',
      bk_cloud_id: '0',
    };
    const hostMap = ['bk_host_id'];
    const ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];
    const cloudMap = ['bk_target_cloud_id', 'bk_cloud_id', 'bk_host_id'];
    this.detail.dimensions.forEach(item => {
      if (hostMap.includes(item.key) && item.value) {
        variables.bk_host_id = item.value;
      }
      if (cloudMap.includes(item.key) && item.value) {
        variables.bk_cloud_id = item.value;
      }
      if (ipMap.includes(item.key) && item.value) {
        variables.bk_host_innerip = item.value;
      }
    });
    const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimeRange(this.detail.begin_time, this.detail.end_time, interval);
    this.timeRange = [startTime, endTime];
    this.viewOptions = Object.assign(this.viewOptions, {
      method: 'AVG',
      ...variables,
      interval,
      group_by: [],
      current_target: {},
      // service_name: 'http:test_zj_1'
    });
    const data = await getSceneView({
      bk_biz_id: this.detail.bk_biz_id,
      scene_id: 'alert',
      type: '',
      id: 'log',
      ...variables,
    }).catch(() => ({ id: '', panels: [], name: '' }));
    this.localPanels = data.overview_panels || [];
    // this.localPanels[0].gridPos.h
    this.loading = false;
  }

  render() {
    return (
      <div
        class={['event-detail-log-info-component', { show: this.show }]}
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.localPanels.length ? (
          <DashboardPanel
            id={this.dashboardPanelId}
            isSingleChart={false}
            isSplitPanel={false}
            needOverviewBtn={false}
            panels={this.localPanels}
          />
        ) : (
          ''
        )}
      </div>
    );
  }
}
