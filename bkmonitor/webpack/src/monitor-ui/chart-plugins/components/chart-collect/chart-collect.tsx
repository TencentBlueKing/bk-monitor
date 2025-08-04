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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CollectionDialog from 'monitor-pc/pages/data-retrieval/components/collection-view-dialog';
import ViewDetail from 'monitor-pc/pages/view-detail/index';
import { isEnFn } from 'monitor-pc/utils';

import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';

import type { CallOptions } from '../../plugins/apm-service-caller-callee/type';
import type { IPanelModel, IViewOptions, ObservablePanelField, PanelModel } from '../../typings';
import type { PanelToolsType } from 'monitor-pc/pages/monitor-k8s/typings';

import './chart-collect.scss';

const isEn = isEnFn();

export interface ICheckPanel {
  id: number | string;
  panels?: ICheckPanel[];
}

interface IChartCollectEvent {
  onCheckAll?: () => void;
  onCheckClose?: () => void;
  onShowCollect?: (v: boolean) => void;
}

interface IChartCollectProps {
  isCollectSingle?: boolean; // 是否为收藏指定视图
  localPanels?: ICheckPanel[]; // 已选中的视图
  observablePanelsField?: ObservablePanelField; // 视图响应式数据
  showCollect?: boolean; // 展示收藏弹窗
}

@Component({
  name: 'ChartCollect',
})
export default class ChartCollect extends tsc<IChartCollectProps, IChartCollectEvent> {
  @Prop({ type: Array, default: () => [] }) localPanels: PanelModel[];
  @Prop({ type: Boolean, default: false }) showCollect: boolean;
  @Prop({ type: Boolean, default: false }) isCollectSingle: boolean;
  @Prop({ type: Object, default: undefined }) observablePanelsField: boolean;

  @InjectReactive('timeRange') readonly timeRange!: number;
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  @InjectReactive('compareType') readonly compareType!: PanelToolsType.CompareId;
  // 图表特殊参数
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('callOptions') readonly callOptions: CallOptions;

  showCollectionDialog = false; // 展示收藏弹窗
  showDetail = false;
  viewDetailConfig = {};

  get checkList(): IPanelModel[] {
    const variablesService = new VariablesService(this.viewOptions);
    const transformVariables = (panel: PanelModel) => {
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange as any);
      const interval = reviewInterval(
        this.viewOptions.interval,
        dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
        panel.collect_interval
      );
      return {
        ...panel,
        targets: panel.targets.map(target => ({
          ...target,
          data: {
            ...target.data,
            ...variablesService.transformVariables(target.data, {
              ...this.viewOptions.filters,
              ...(this.viewOptions.filters?.current_target || {}),
              ...this.viewOptions,
              ...this.viewOptions.variables,
              ...this.callOptions,
              interval,
            }),
          },
        })),
      };
    };
    const checkList = [];
    // biome-ignore lint/complexity/noForEach: <explanation>
    this.localPanels?.forEach(item => {
      const { checked } = this.observablePanelsField?.[item.id] || item;
      if (item.type !== 'row' && item.canSetGrafana && checked) {
        checkList.push({
          ...transformVariables(JSON.parse(JSON.stringify({ ...item }))),
          rawQueryPanel: item,
        });
      }
      // biome-ignore lint/complexity/noForEach: <explanation>
      item.panels?.forEach(panel => {
        if (panel.checked) {
          checkList.push({
            ...transformVariables(JSON.parse(JSON.stringify({ ...panel }))),
            rawQueryPanel: panel,
          });
        }
      });
    });
    return checkList;
  }

  get total() {
    return this.localPanels.reduce((acc, cur) => {
      let total = acc;
      if (cur.type === 'graph') {
        total += 1;
      }
      if (cur.panels?.length) {
        total += cur.panels.length;
      }
      return total;
    }, 0);
  }

  @Watch('showCollect')
  handleShowCollect(v: boolean) {
    this.showCollectionDialog = v;
  }

  @Watch('isCollectSingle')
  handleIsCollectSingle(v: boolean) {
    this.showCollectionDialog = v;
  }

  // 点击全选
  @Emit('checkAll')
  handleCheckAll() {}
  // 点击全不选
  @Emit('checkClose')
  handleCheckClose() {}
  // 收藏弹窗
  @Emit('showCollect')
  handleShowCollectEmit(v: boolean) {
    return v;
  }
  // 收藏成功
  handleCollectSuccess() {
    this.handleCheckClose();
  }

  // 跳转至数据检索
  handleToDataRetrieval() {
    let targets = this.checkList.reduce((pre, item) => {
      pre.push(...(item?.rawQueryPanel?.toDataRetrieval?.() || item.targets));
      return pre;
    }, []);
    const variablesService = new VariablesService(this.viewOptions);
    targets = targets.map(item =>
      variablesService.transformVariables(item, {
        ...this.viewOptions.filters,
        ...(this.viewOptions.filters?.current_target || {}),
        ...this.viewOptions,
        ...this.viewOptions.variables,
      })
    );
    window.open(
      `${location.href.replace(location.hash, '#/data-retrieval')}?targets=${encodeURIComponent(
        JSON.stringify(targets)
      )}&from=${this.timeRange[0]}&to=${this.timeRange[1]}`
    );
  }

  // 查看大图
  handleViewDetail() {
    const config = this.checkList.reduce((acc, item) => {
      if (!acc) {
        return item;
      }
      acc.targets.push(...item.targets);
      acc.title = window.i18n.t('对比');
      acc.subTitle = '';
      return acc;
    }, null);
    this.viewDetailConfig = {
      config,
      compareValue: {
        compare: {
          type: this.compareType,
          value: this.compareType === 'time' ? this.timeOffset : '',
        },
        tools: {
          timeRange: this.timeRange,
        },
        type: ['time', 'metric'].includes(this.compareType) ? this.compareType : 'none',
      },
    };
    this.showDetail = true;
  }

  handleCloseDetail() {
    this.showDetail = false;
  }

  render() {
    return (
      <div class='chart-colllect-component'>
        <transition name='collection-fade'>
          {this.checkList.length && !this.isCollectSingle ? (
            <div class={['view-collection', { en: isEn }]}>
              <div style='flex-grow: 1'>
                <span>{window.i18n.t('已勾选{count}个', { count: this.checkList.length })}</span>
                <span
                  class='view-collection-btn'
                  onClick={this.handleCheckAll}
                >
                  {window.i18n.t('点击全选')}
                </span>
                <span
                  class='view-collection-btn'
                  onClick={() => this.handleShowCollectEmit(true)}
                >
                  {window.i18n.t('收藏至仪表盘')}
                </span>
                <span
                  class='view-collection-btn'
                  onClick={() => this.handleToDataRetrieval()}
                >
                  {window.i18n.t('route-数据探索')}
                </span>
                {this.checkList.length > 1 ? (
                  <span
                    class={['view-collection-btn', isEn ? 'mr24' : 'mr5']}
                    onClick={this.handleViewDetail}
                  >
                    {window.i18n.t('对比')}
                  </span>
                ) : undefined}
              </div>
              <i
                class='icon-monitor icon-mc-close-fill'
                onClick={this.handleCheckClose}
              />
            </div>
          ) : undefined}
        </transition>
        <CollectionDialog
          collectionList={this.checkList}
          isShow={this.showCollectionDialog}
          onOnCollectionSuccess={() => this.handleCollectSuccess}
          onShow={(v: boolean) => this.handleShowCollectEmit(v)}
        />
        {this.showDetail && (
          <ViewDetail
            showModal={this.showDetail}
            viewConfig={this.viewDetailConfig}
            on-close-modal={this.handleCloseDetail}
          />
        )}
      </div>
    );
  }
}
