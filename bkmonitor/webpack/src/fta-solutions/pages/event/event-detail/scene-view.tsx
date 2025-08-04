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
import { Component, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getSceneView, getSceneViewList } from 'monitor-api/modules/scene_view';
import { random } from 'monitor-common/utils/utils';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import DashboardPanel from 'monitor-ui/chart-plugins/components/dashboard-panel';
import { type IBookMark, type IPanelModel, type IViewOptions, BookMarkModel } from 'monitor-ui/chart-plugins/typings';

import { createAutoTimeRange } from './aiops-chart';
import { type IDetail, setBizIdToPanel } from './type';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './scene-view.scss';

interface IProps {
  detail?: IDetail;
  sceneId?: string;
  sceneName?: string;
  show?: boolean;
}

@Component
export default class SceneView extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: String, default: '' }) sceneId: string;
  /* 场景名称用于跳转到场景详情页 */
  @Prop({ type: String, default: '' }) sceneName: string;

  loading = false;
  // 配置panels
  localPanels: IPanelModel[] = [];
  dashboardPanelId = random(8);
  isSingleChart = false;

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 当前业务id
  @ProvideReactive('bkBizId') bkBizId: number | string = null;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  @Watch('show')
  handleShow(v: boolean) {
    if (!this.localPanels.length && v) {
      this.getSceneData();
    }
  }

  async getSceneData() {
    this.loading = true;
    const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimeRange(this.detail.begin_time, this.detail.end_time, interval);
    this.timeRange = [startTime, endTime];
    this.bkBizId = this.detail.bk_biz_id;
    this.viewOptions = {
      method: this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_method || 'AVG',
      variables: {},
      interval,
      group_by: [],
    };
    const viewList = await getSceneViewList({
      bk_biz_id: this.detail.bk_biz_id,
      scene_id: this.sceneId,
      type: 'detail',
    }).catch(() => []);
    if (!viewList.length) {
      this.loading = false;
      return;
    }
    const dashboardId = viewList[0].id;
    const data: IBookMark = await getSceneView({
      scene_id: this.sceneId,
      type: 'detail',
      id: dashboardId,
      bk_biz_id: this.detail.bk_biz_id,
    }).catch(() => ({ id: '', panels: [], name: '' }));
    const sceneData = new BookMarkModel(data || { id: '', panels: [], name: '' });
    this.isSingleChart =
      sceneData?.panelCount < 2 &&
      sceneData?.panels?.some(item => item.type !== 'graph') &&
      sceneData.panels.length < 2 &&
      (sceneData.panels?.[0].type === 'row' ? sceneData.panels[0]?.panels?.some(item => item.type !== 'graph') : true);
    this.localPanels = setBizIdToPanel(this.handleGetLocalPanels(sceneData.panels), this.detail.bk_biz_id);
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

  handleToCustomScene() {
    window.open(
      `${location.origin}${location.pathname}?bizId=${this.detail.bk_biz_id}#/custom-scenes/view/${this.sceneId}?name=${this.sceneName}`
    );
  }

  render() {
    return (
      <div
        class={['event-detail-scene-view', { show: this.show }]}
        v-bkloading={{ isLoading: this.loading }}
      >
        {!!this.localPanels.length && (
          <DashboardPanel
            id={this.dashboardPanelId}
            column={3}
            isSingleChart={this.isSingleChart}
            isSplitPanel={false}
            needOverviewBtn={false}
            panels={this.localPanels}
          />
        )}
        {!this.readonly && !!this.localPanels.length && (
          <div class='view-bottom'>
            <div class='view-bottom-label'>
              <i18n path='可{0}完整查看'>
                <span
                  class='link'
                  onClick={() => this.handleToCustomScene()}
                >
                  {window.i18n.t('跳转至自定义场景')}
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
