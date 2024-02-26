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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import echarts from 'echarts';
import { GridItem, GridLayout } from 'monitor-vue-grid-layout';

import bus from '../../../monitor-common/utils/event-bus';
import { random } from '../../../monitor-common/utils/utils';
import { ITableItem, SceneType } from '../../../monitor-pc/pages/monitor-k8s/typings';
import { DashboardColumnType, IGridPos, IPanelModel, PanelModel } from '../typings';

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
  /** 根据column */
  customHeightFn?: Function | null;
  // 是否在分屏展示
  isSplitPanel?: boolean;
  isSingleChart?: boolean;
  needOverviewBtn?: boolean;
  backToType?: SceneType;
  dashboardId?: string;
}
interface IDashbordPanelEvents {
  onBackToOverview: void;
  onLintToDetail: ITableItem<'link'>;
}
@Component
export default class DashboardPanel extends tsc<IDashbordPanelProps, IDashbordPanelEvents> {
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
  /** 自定义高度计算 */
  @Prop({ default: null }) customHeightFn: Function | null;
  // 视图布局位置信息
  layout: IGridPos[] = [];
  // 视图实例集合
  localPanels: PanelModel[] = [];
  // 拖拽视图的id
  movedId: string | number = '';
  /* 展示收藏弹窗 */
  showCollect = false;
  /* 点击了单个视图保存仪表盘 */
  isCollectSingle = false;
  @InjectReactive('readonly') readonly: boolean;
  get singleChartPanel() {
    // return new PanelModel(this.panels[0]);
    const panels = this.panels.filter(item => (item.type === 'row' ? !!item.panels?.length : true));
    return new PanelModel(panels[0]?.type === 'row' ? panels[0]?.panels?.[0] : panels[0]);
  }

  /* k8s页面的cluster场景图表不可选中 */
  get isClusterOfK8s() {
    return this.$route?.name === 'k8s' && this.dashboardId === 'cluster';
  }

  @Watch('panels', { immediate: true })
  handlePanelsChange() {
    if (this.column !== 'custom') {
      this.handleInitPanelsGridpos(this.panels);
    }
    const panels = this.panels.slice().sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x);
    this.localPanels = this.handleInitLocalPanels(panels);
    this.handleUpdateLayout();
  }
  @Watch('column')
  handleColumnChange() {
    echarts.disConnect(this.id.toString());
    this.handleInitPanelsGridpos(this.localPanels);
    this.handleUpdateLayout();
    this.handleConentEcharts();
  }
  mounted() {
    // 等待所以子视图实例创建完进行视图示例的关联 暂定5000ms 后期进行精细化配置
    this.handleConentEcharts();
    bus.$on(UPDATE_SCENES_TAB_DATA, this.handleLinkTo);
    bus.$on('switch_to_overview', this.handleToSceneOverview);
  }
  beforeDestroy() {
    echarts.disConnect(this.id.toString());
  }
  destroyed() {
    bus.$off(UPDATE_SCENES_TAB_DATA);
    bus.$off('switch_to_overview');
  }
  handleConentEcharts() {
    setTimeout(() => {
      if (this.layout?.length < 300) {
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
    let prePanel: IPanelModel = null;
    let index = 0;
    const w = 24 / +this.column;
    const updatePanelsGridpos = (list: IPanelModel[]) => {
      list.forEach(item => {
        if (item.type === 'row') {
          index = 0;
          item.gridPos = {
            ...item.gridPos,
            x: 0,
            y: prePanel ? prePanel.gridPos.h + prePanel.gridPos.y : 0,
            h: 1,
            w: 24
          };
          prePanel = item;
          if (item.panels?.length) {
            updatePanelsGridpos(item.panels);
          }
        } else {
          const panelIndex = index % +this.column;
          /** 固定宽度，不受布局影响 */
          const isStaticWidth = !!item.options?.dashboard_common?.static_width;
          item.gridPos = {
            ...item.gridPos,
            x: !panelIndex ? 0 : panelIndex * w,
            // eslint-disable-next-line no-nested-ternary
            y: !panelIndex ? (prePanel ? prePanel.gridPos.h + prePanel.gridPos.y : 0) : prePanel.gridPos.y,
            h: this.customHeightFn?.(this.column) || (this.column === 1 ? 5 : 7),
            w: isStaticWidth ? 24 : w
          };
          // event-log类型图表，最小高度占比为22
          if (item.type === 'event-log' && item.gridPos.h < 22) item.gridPos.h = 22;
          item.options = {
            ...item.options,
            legend: {
              displayMode: this.column === 1 ? 'table' : 'list',
              placement: this.column === 1 ? 'right' : 'bottom'
            }
          } as any;
          prePanel = item;
          index += 1;
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
   * @description: 更新layout x 、y
   * @param {*}
   * @return {*}
   */
  handleUpdateLayout() {
    const list: IGridPos[] = [];
    const updateLayout = (panelList: PanelModel[]) => {
      let i = 0;
      const panels = panelList
        .slice()
        .sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x)
        .filter(item => item.show);
      const len = panels.length;
      while (i < len) {
        const curPanel = panels[i];
        const preGrid = list[list.length - 1];
        if (!preGrid) {
          list.push(curPanel.gridPos);
          curPanel.panels?.length && updateLayout(curPanel.panels);
        } else {
          const curGrid = curPanel.gridPos;
          // eslint-disable-next-line prefer-const
          let { x, y, w } = curGrid;
          const { x: preX, y: preY, h: preH, w: preW } = preGrid;
          if (x !== preX) {
            if (y < preY + preH) {
              if (w > 24 - preW) {
                x = 0;
                y = preY + preH;
              }
            } else {
              y = preY + preH;
            }
          } else if (w > 24 - preW) {
            x = 0;
            y = preY + preH;
          } else {
            y = preY + preH;
          }
          curPanel.gridPos.x = x;
          curPanel.gridPos.y = y;
          list.push(curPanel.gridPos);
          curPanel.panels?.length && updateLayout(curPanel.panels);
        }
        i += 1;
      }
    };
    updateLayout(this.localPanels);
    this.layout = list;
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
          list[list.length - 1].panels = unGroupList;
        } else {
          list.push(...unGroupList);
        }
        isInUnGroup = false;
        unGroupList = [];
        const rowPanel = this.getTransformPanel(panel);
        list.push(rowPanel);
        if (panel?.panels?.length) {
          const childList = panel.panels
            .sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x)
            .map(item =>
              this.getTransformPanel({
                ...item,
                show: !!panel.collapsed,
                groupId: rowPanel.id
              })
            );
          list[list.length - 1].panels = childList;
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
        list[list.length - 1].panels = unGroupList;
      } else {
        list.push(...unGroupList);
      }
    }
    return list;
  }
  /**
   * @description: layout变化后触发 这里特别处理组的单元移动算法
   * @param {IGridPos} layout
   * @return {*}
   */
  handleLayoutUpdated(layout: IGridPos[]) {
    this.layout = layout;
    const panels = this.localPanels.slice();
    layout.forEach(item => {
      const panel = this.getPanelsItem(item.i);
      panel?.updateGridPos(item);
    });
    if (this.movedId) {
      const panel = this.getPanelsItem(this.movedId);
      const deletePanel = (panel: PanelModel) => {
        const curRowIndex = panels.findIndex(p => p.id === panel.id || !!p.panels?.some(i => i.id === panel.id));
        if (panels[curRowIndex].id === panel.id) {
          panels.splice(curRowIndex, 1);
        } else {
          const index = panels[curRowIndex].panels.findIndex(p => p.id === panel.id);
          panels[curRowIndex].panels.splice(index, 1);
        }
      };
      // 移动插件
      if (panel.type !== 'row') {
        const rowPanelIndex = panels.findIndex(item => item.type === 'row');
        if (rowPanelIndex > -1) {
          const newRowIndex = panels.findIndex(p => p.type === 'row' && p.gridPos.y > panel.gridPos.y);
          if (newRowIndex === -1) {
            const rowPanel = panels[panels.length - 1];
            if (rowPanel.panels?.some(item => item.id === panel.id)) return;
            deletePanel(panel);
            rowPanel.panels = [...(rowPanel.panels || []), panel];
            rowPanel.panels.sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x);
          } else if (newRowIndex <= rowPanelIndex) {
            if (panels.some(item => item.id === panel.id)) return;
            deletePanel(panel);
            panels.unshift(panel);
          } else if (newRowIndex > rowPanelIndex) {
            const row = panels[newRowIndex - 1];
            if (row.panels.some(item => item.id === panel.id)) return;
            deletePanel(panel);
            row.panels = [...(row.panels || []), panel];
            row.panels.sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x);
          }
        }
      } else {
        // 移动组
        panels.sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x);
        panels.forEach(item => {
          if (item.id === panel.id) return;
          const maxY = (panel.panels || []).reduce(
            (pre, cur) => Math.max(cur.gridPos.y + cur.gridPos.h, pre),
            panel.gridPos.y + panel.gridPos.h
          );
          if (item.type !== 'row') {
            const rowPanel = panels
              .slice()
              .reverse()
              .find(set => set.type === 'row' && set.gridPos.y < item.gridPos.y);
            if (rowPanel?.id === panel.id) {
              deletePanel(item);
              item.gridPos.y = maxY;
              panel.panels = [...panel.panels, item];
            }
          } else {
            item?.panels.forEach(child => {
              const rowPanel = panels
                .slice()
                .reverse()
                .find(set => set.type === 'row' && set.gridPos.y < child.gridPos.y);
              if (rowPanel?.id === panel.id) {
                deletePanel(child);
                child.gridPos.y = maxY;
                panel.panels = [...panel.panels, child];
              }
            });
          }
        });
      }
    }
    panels.sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x);
    this.movedId = undefined;
    this.localPanels = panels;
  }
  /**
   * @description: 获取panel item的数据
   * @param {*} id
   */
  getPanelsItem(id: string | number) {
    let item = this.localPanels.find(set => set.id === id);
    if (item) return item;
    for (let i = 0, len = this.localPanels.length; i < len; i++) {
      item = this.localPanels[i].panels?.find(set => id === set.id);
      if (item) break;
    }
    return item;
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
    this.localPanels.forEach(item => {
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
    let distance = 0;
    const len = +panel.panels?.length;
    len &&
      this.localPanels.forEach(item => {
        if (item.id === panel.id) {
          item.panels.sort((a, b) => a.gridPos.y - b.gridPos.y || a.gridPos.x - b.gridPos.x);
          const lastGrid = item.panels[len - 1].gridPos;
          const firstGrid = item.panels[0].gridPos;
          distance = lastGrid.y + lastGrid.h - firstGrid.y;
          distance = collapse ? distance : -distance;
        } else {
          item.gridPos.y += distance;
          item.panels?.forEach(set => (set.gridPos.y += distance));
        }
      });
    this.handleUpdateLayout();
  }
  handleItemMoved(newY: number, panel: PanelModel) {
    this.movedId = panel.id;
    // if (panel.type === 'row') {
    //   console.info();
    // }
  }
  /**
   * @description: 拖拽视图
   * @param {PanelModel} panel 拖拽的视图实例
   * @return {*}
   */
  handleItemMoving(panel: PanelModel) {
    panel.updateDraging(true);
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

  /* 根据内容高度计算panelLayout的h属性， 表格切换每页条数时会用到 */
  handleChangeLayoutItemH(height: number, index: number) {
    const maxIndexs = [];
    const yArray = this.layout.map(item => Number(item.y || 0));
    const maxY = Math.max(...yArray);
    this.layout.forEach((item, index) => {
      if (item.y === maxY) {
        maxIndexs.push(index);
      }
    });
    if (maxIndexs.includes(index)) {
      // Math.round(rowHeight * h + Math.max(0, h - 1) * margin[1]) = height 实际高度计算方式
      const h = Math.round((height + 8) / 38);
      this.layout[index].h = h;
    }
  }

  @Emit('backToOverview')
  handleBackToOverview() {}

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
            <GridLayout
              layout={this.layout}
              colNum={24}
              rowHeight={30}
              isResizable={true}
              isDraggable={true}
              responsive={false}
              verticalCompact={true}
              useCssTransforms={false}
              margin={[16, 8]}
              draggableOptions={{
                autoScroll: {
                  container: '#dashboard-panel'
                },
                allowFrom: '.draggable-handle---no'
              }}
              on-layout-updated={this.handleLayoutUpdated}
            >
              {this.layout?.slice(0, 1000).map((item, index) => {
                const panel = this.getPanelsItem(item.i);
                return (
                  <GridItem
                    {...{ props: item }}
                    class={{ 'row-panel': panel.type === 'row' }}
                    key={`${item.i}_${index}__key__`}
                    id={`${item.i}__key__`}
                    onMove={() => this.handleItemMoving(panel)}
                    onMoved={(i, newX, newY) => this.handleItemMoved(newY, panel)}
                  >
                    <ChartWrapper
                      key={`${item.i}_${index}__key__`}
                      panel={panel}
                      {...{
                        attrs: this.$attrs
                      }}
                      needCheck={!this.isClusterOfK8s}
                      onChartCheck={v => this.handleChartCheck(v, panel)}
                      onCollapse={v => panel.type === 'row' && this.handleCollapse(v, panel)}
                      onCollectChart={() => this.handleCollectChart(panel)}
                      onChangeHeight={(height: number) => this.handleChangeLayoutItemH(height, index)}
                    />
                  </GridItem>
                );
              })}
            </GridLayout>,
            !this.readonly && this.localPanels.length ? (
              <ChartCollect
                localPanels={this.localPanels}
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
