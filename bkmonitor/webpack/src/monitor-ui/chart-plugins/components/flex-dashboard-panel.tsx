/* eslint-disable no-param-reassign */
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
import { Component, Emit, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import echarts from 'echarts';

import bus from '../../../monitor-common/utils/event-bus';
import { random } from '../../../monitor-common/utils/utils';
import { ITableItem, SceneType } from '../../../monitor-pc/pages/monitor-k8s/typings';
import { DashboardColumnType, IPanelModel, PanelModel } from '../typings';

import ChartCollect from './chart-collect/chart-collect';
import ChartWrapper from './chart-wrapper';

import './dashboard-panel.scss';
/** 接收图表当前页面跳转事件 */
export const UPDATE_SCENES_TAB_DATA = 'UPDATE_SCENES_TAB_DATA';
interface IDashbordPanelProps {
  // 视图集合
  panels: IPanelModel[];
  // dashboard id
  id: string;
  // 自动展示初始化列数
  column?: DashboardColumnType;
  // 是否在分屏展示
  isSplitPanel?: boolean;
  isSingleChart?: boolean;
  needOverviewBtn?: boolean;
  backToType?: SceneType;
  /** 根据column */
  customHeightFn?: Function | null;
  dashboardId?: string;
  matchFields?: Record<string, any>;
}
interface IDashbordPanelEvents {
  onBackToOverview: void;
  onLintToDetail: ITableItem<'link'>;
}
@Component
export default class FlexDashboardPanel extends tsc<IDashbordPanelProps, IDashbordPanelEvents> {
  // 视图集合
  @Prop({ required: true, type: Array }) panels: IPanelModel[];
  // dashboard id
  @Prop({ required: true, type: String }) id: string;
  // 自动展示初始化列数
  @Prop({ default: 'custom', type: [String, Number] }) column: DashboardColumnType;
  // 是否在分屏展示
  @ProvideReactive('isSplitPanel')
  @Prop({ default: false, type: Boolean })
  isSplitPanel: boolean;
  // 是否为单图模式
  @Prop({ default: false, type: Boolean }) isSingleChart: boolean;
  // 是否需要返回概览按钮 isSingleChart: true生效
  @Prop({ type: Boolean, default: false }) needOverviewBtn: boolean;
  // 返回概览 或者 详情页面
  @Prop({ type: String }) backToType: SceneType;
  @Prop({ default: '' }) dashboardId: string;
  @Prop({ type: Object }) matchFields: Record<string, any>;
  /** 自定义高度 */
  @Prop({ default: null }) customHeightFn: Function | null;
  // 视图实例集合
  // localPanels: PanelModel[] = [];
  // 拖拽视图的id
  movedId: string | number = '';
  /* 展示收藏弹窗 */
  showCollect = false;
  /* 点击了单个视图保存仪表盘 */
  isCollectSingle = false;

  get singleChartPanel() {
    const panels = this.panels.filter(item => (item.type === 'row' ? !!item.panels?.length : true));
    return new PanelModel(panels[0]?.type === 'row' ? panels[0]?.panels?.[0] : panels[0]);
  }
  @Watch('panels', { immediate: true })
  handlePanelsChange() {
    if (!this.panels) return;
    this.handleInitPanelsGridpos(this.panels);
    (this as any).localPanels = this.handleInitLocalPanels(this.panels.slice());
  }
  @Watch('column')
  handleColumnChange() {
    echarts.disConnect(this.id.toString());
    this.handleInitPanelsGridpos((this as any).localPanels);
    this.handleConentEcharts();
  }
  mounted() {
    // 等待所以子视图实例创建完进行视图示例的关联 暂定5000ms 后期进行精细化配置
    this.handleConentEcharts();
    bus.$on(UPDATE_SCENES_TAB_DATA, this.handleLinkTo);
    bus.$on('switch_scenes_type', this.handleToSceneDetil);
    bus.$on('switch_to_overview', this.handleToSceneOverview);
  }
  beforeDestroy() {
    echarts.disConnect(this.id.toString());
  }
  destroyed() {
    bus.$off(UPDATE_SCENES_TAB_DATA);
    bus.$off('switch_scenes_type');
    bus.$off('switch_to_overview');
  }
  handleConentEcharts() {
    setTimeout(() => {
      if ((this as any).localPanels?.length < 300) {
        echarts.connect(this.id.toString());
      }
    }, 3000);
  }
  @Emit('linkTo')
  handleLinkTo(data) {
    return data;
  }
  /** 切换概览页面 */
  handleToSceneOverview() {
    this.handleBackToOverview();
  }

  /** 处理跳转视图详情 */
  @Emit('lintToDetail')
  handleToSceneDetil(data: ITableItem<'link'>) {
    return data;
  }
  /**
   * @description: 设置各个图表的位置大小信息
   * @param {*}
   * @return {*}
   */
  handleInitPanelsGridpos(panels: IPanelModel[]) {
    if (!panels) return;
    const updatePanelsGridpos = (list: IPanelModel[]) => {
      list.forEach(item => {
        if (item.type === 'row') {
          if (item.panels?.length) {
            updatePanelsGridpos(item.panels);
          }
        } else {
          item.options = {
            ...item.options,
            legend: {
              displayMode: this.column === 1 ? 'table' : 'list',
              placement: this.column === 1 ? 'right' : 'bottom'
            }
          } as any;
        }
      });
    };
    updatePanelsGridpos(panels);
  }
  getUnGroupPanel(y: number): IPanelModel {
    return {
      gridPos: {
        x: 0,
        y,
        w: 24,
        h: 1
      },
      id: random(10),
      options: {},
      panels: [],
      targets: [],
      title: '',
      type: 'row',
      collapsed: true,
      subTitle: ''
    };
  }
  getTransformPanel(panel: IPanelModel) {
    const item = new PanelModel({
      ...panel,
      dashboardId: this.id,
      panelIds: panel?.panels?.map(item => item.id) || []
    });
    return item;
  }
  /**
   * @description:初始化 dashboard 转换为 panelModel 并重新计算各个视图位置大小
   * @param {IPanelModel} panels
   * @return {*}
   */
  handleInitLocalPanels(panels: IPanelModel[]) {
    const list: PanelModel[] = [];
    let unGroupList: PanelModel[] = [];
    let i = 0;
    const len = panels.length;
    let isInUnGroup = false;
    let hasRowGroup = false;
    while (i < len) {
      const panel = panels[i];
      const isRowPanel = panel.type === 'row';
      if (isRowPanel) {
        // 是否组
        if (isInUnGroup && unGroupList.length) {
          unGroupList.forEach(item => {
            item.updateShow(true);
            item.groupId = list[list.length - 1].id;
          });
        }
        list.push(...unGroupList);
        isInUnGroup = false;
        unGroupList = [];
        const rowPanel = this.getTransformPanel(panel);
        list.push(rowPanel);
        if (panel?.panels?.length) {
          const childList = panel.panels.map(item =>
            this.getTransformPanel({
              ...item,
              show: !!panel.collapsed,
              groupId: rowPanel.id
            })
          );
          list.push(...childList);
        }
        hasRowGroup = true;
      } else {
        if (hasRowGroup && !isInUnGroup) {
          const rowPanel = this.getUnGroupPanel(list[list.length - 1].gridPos.y + 1);
          list.push(new PanelModel({ ...rowPanel }));
          isInUnGroup = true;
        }
        unGroupList.push(this.getTransformPanel(panel));
      }
      i += 1;
    }
    if (unGroupList.length) {
      if (list[list.length - 1]?.type === 'row') {
        unGroupList.forEach(item => {
          item.updateShow(true);
          item.groupId = list[list.length - 1].id;
        });
      }
      list.push(...unGroupList);
    }
    return list;
  }
  /**
   * @description: 选中图表触发事件
   * @param {boolean} check 是否选中
   * @param {PanelModel} panel 图表panel model
   * @return {*}
   */
  handleChartCheck(check: boolean, panel: PanelModel) {
    panel.updateChecked(check);
  }
  /**
   * @description: 全选或全不选
   * @param {*} isCheck 是否勾选
   * @return {*}
   */
  handleCheckAll(isCheck = true) {
    (this as any).localPanels.forEach(item => {
      if (item.type !== 'row' && item.canSetGrafana) {
        item.updateChecked(isCheck);
      }
      item.panels?.forEach(panels => {
        panels?.updateChecked?.(isCheck);
      });
    });
  }
  /**
   * @description: 分组时开闭设置
   * @param {boolean} collapse
   * @param {PanelModel} panel
   * @return {*}
   */
  handleCollapse(collapse: boolean, panel: PanelModel) {
    panel.updateCollapsed(collapse);
    panel.panels?.forEach(item => {
      const panel = (this as any).localPanels.find(set => set.id === item.id);
      panel?.updateShow(collapse);
    });
  }

  /**
   * @description: 保存仪表盘弹窗显示切换
   * @param {boolean} v
   * @return {*}
   */
  handleShowCollect(v: boolean) {
    this.showCollect = v;
    if (!v && this.isCollectSingle) {
      this.isCollectSingle = false;
      this.handleCheckAll(false);
    }
  }
  /**
   * @description: 点击保存仪表盘
   * @param {PanelModel} panel 视图配置
   * @return {*}
   */
  handleCollectChart(panel: PanelModel) {
    this.isCollectSingle = true;
    this.handleCheckAll(false);
    this.handleChartCheck(true, panel);
  }

  getPanelDisplay(panel: PanelModel) {
    if (!panel.show) return 'none';
    if (panel.matchDisplay && this.matchFields) {
      return Object.keys(panel.matchDisplay).every(key => this.matchFields[key] === panel.matchDisplay[key])
        ? 'flex'
        : 'none';
    }
    return 'flex';
  }

  @Emit('backToOverview')
  handleBackToOverview() {}

  /* 根据内容高度计算panelLayout的h属性， 表格切换每页条数时会用到 */
  handleChangeLayoutItemH(height: number, index: number) {
    const panel = (this as any).localPanels[index];
    panel?.updateRealHeight(height);
  }
  render() {
    if (!this.panels?.length) return <div class='dashboard-panel empty-data'>{this.$t('查无数据')}</div>;
    return (
      <div
        id='dashboard-panel'
        class='dashboard-panel'
      >
        {this.isSingleChart ? (
          <div class='single-chart-content'>
            <div class={['single-chart-main', { 'has-btn': !!this.backToType }]}>
              <div class='single-chart-wrap'>
                <ChartWrapper panel={this.singleChartPanel}></ChartWrapper>
              </div>
            </div>
          </div>
        ) : (
          [
            <div class='flex-dashboard'>
              {(this as any).localPanels.slice(0, 1000).map((panel, index) => (
                <div
                  class={{ 'flex-dashboard-item': true, 'row-panel': panel.type === 'row' }}
                  style={{
                    width: `calc(${(1 / +this.column) * 100}% - 16px)`,
                    maxWidth: `calc(${(1 / +this.column) * 100}% - 16px)`,
                    flex: `${(1 / +this.column) * 100}%`,
                    display: this.getPanelDisplay(panel),
                    height: this.customHeightFn
                      ? this.customHeightFn(this.column)
                      : panel.realHeight || (this.column === 1 ? '182px' : '256px')
                  }}
                  key={`${panel.id}__key__`}
                  id={`${panel.id}__key__`}
                >
                  <ChartWrapper
                    key={`${panel.id}__key__`}
                    panel={panel}
                    onChartCheck={v => this.handleChartCheck(v, panel)}
                    onCollapse={v => panel.type === 'row' && this.handleCollapse(v, panel)}
                    onCollectChart={() => this.handleCollectChart(panel)}
                    onChangeHeight={(height: number) => this.handleChangeLayoutItemH(height, index)}
                  />
                </div>
              ))}
            </div>,
            (this as any).localPanels.length ? (
              <ChartCollect
                localPanels={(this as any).localPanels}
                showCollect={this.showCollect}
                isCollectSingle={this.isCollectSingle}
                onCheckAll={() => this.handleCheckAll()}
                onCheckClose={() => this.handleCheckAll(false)}
                onShowCollect={(v: boolean) => this.handleShowCollect(v)}
              ></ChartCollect>
            ) : undefined
          ]
        )}
      </div>
    );
  }
}
