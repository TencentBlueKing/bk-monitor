/* eslint-disable @typescript-eslint/naming-convention */
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

import { random } from 'monitor-common/utils/utils';
import {
  type IPanelModel,
  type IVariableModel,
  PanelModel,
  VariableModel,
} from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import type { IMenuItem } from '.';
import type { SceneType } from '../components/common-page-new';
import type { IGroupByVariables } from '../components/group-compare-select/utils';
import type { TranslateResult } from 'vue-i18n';

// 视图模式 auto：平铺模式 custom：自定义模式
export type BookMarkMode = 'auto' | 'custom';
// dashboard 仪表盘模式  list: 列表模式 chart: 视图模式
export type DashboardMode = 'chart' | 'list';

// 页签配置
export interface IBookMark {
  // 页签id
  id: string;
  // 已请求数据
  isReady?: boolean;
  // 链接
  link?: string;
  // 列表模式视图配置
  list?: IPanelModel[];
  // 视图模式 auto：平铺模式 custom：自定义模式
  mode?: BookMarkMode;
  // 页签名称
  name: string;
  // 是否展示数字
  needCount?: boolean;
  // 页签配置
  options?: IBookMarkOptions;
  // 平铺模式 特有的图表配置顺序
  order?: IPanelModel[];
  overview_panels?: IPanelModel[];
  // 页签图表统计数据
  panel_count?: number;
  // 视图配置
  panels: IPanelModel[];
  // 是否展示页签图表统计数据
  show_panel_count?: boolean;
  // 变量设置
  variables?: IVariableModel[];
}

export interface IBookMarkOptions {
  // 主机详情
  ai_panel?: PanelModel;
  alert_filterable?: boolean; // 图表的告警状态接口是否需要加入$current_target作为请求参数
  // 详情配置
  detail_panel?: IPanelModel;
  enable_auto_grouping?: boolean; // 视图设置是否开启自动分组
  // 是否可设置group
  enable_group?: boolean;
  // 是否开启图表索引列表功能
  enable_index_list?: boolean;
  // 动态获取panels 类似service_monitor
  fetch_panels?: PanelModel;
  // group面板
  group_panel?: PanelModel;
  only_index_list?: boolean; // 仅展示索引列表
  // 概览详情配置
  overview_detail_panel?: IPanelModel;
  // 告警、策略统计数据
  overview_panel?: PanelModel;
  // 左侧选择配置
  selector_panel?: IPanelModel;
  // 是否可设置变量 filter
  variable_editable?: boolean;
  // 是否可设置页签
  view_editable?: boolean;
  // 视图面板的工具栏配置
  panel_tool?: {
    columns_toggle?: boolean; // 是否需要图表分列布局切换
    compare_select?: boolean; // 是否需要对比选择器
    full_table?: boolean; // 是否需要全屏表格
    interval_select?: boolean; // 是否需要汇聚周期选择器
    method_select?: boolean; // 是否需要汇聚周期选择器
    need_compare_target?: boolean; // 是否需要目标对比
    split_switcher?: boolean; // 是否需要合并、分割视图开关
  };
}

/** 变量数据 */
export interface ICurVarItem {
  alias: string;
  checked?: boolean;
  groupBy: string;
  key: string;
  loading: boolean;
  optionalValue: IOption[];
  value?: string[];
  where: IWhere[];
}

/** 可选值 */
export interface IOption {
  id: number | string;
  name: string | TranslateResult;
}

export interface IViewOptions {
  app_name?: string;
  bk_target_cloud_id?: string;
  bk_target_ip?: string;
  // 对比目标 主机监控特殊使用
  compare_targets?: Record<string, any>[];
  // 对比数据 如 目标对比 集成等
  compares?: Record<'targets', any>;
  // 当前选中的目标 主机和容器监控特殊使用
  current_target?: Record<string, any>;
  // filter 数据 视图最侧栏定位数据使用
  filters?: Record<string, any>;
  // 特殊数据组  主机监控使用 主机ip 云区域id
  group_by?: string[];
  groupByVariables?: IGroupByVariables;
  // 数据组 维度 指标组
  groups?: string[];
  // 汇聚周期
  interval?: 'auto' | number | string;
  // 用于动态判断panel是否显示
  matchFields?: Record<string, any>;
  // 汇聚方法
  method?: string;
  service_name?: string;
  // 策略id 用于hostIntelligentAnomalyRange接口
  strategy_id?: number | string;
  // 变量数据 视图变量
  variables?: Record<string, any>;
}

/** 条件 */
export interface IWhere {
  condition?: 'and' | 'or';
  key: string;
  method: string;
  value: string[];
}

export class BookMarkModel implements IBookMark {
  // 主机 详情
  aiPanel: PanelModel;
  // 策略、告警数据
  alarmPanel?: PanelModel;
  allVariables: Set<string> = undefined;
  // 详情栏配置
  detailPanel?: PanelModel;
  // 动态获取panels 类似service_monitor的动态视图能力
  fetchPanel?: PanelModel;
  // group panel 配置
  groupPanel: PanelModel;
  // 页签id
  id: string;
  // 是否需要精准过滤
  isShowPreciseFilter = false;
  // 链接
  link?: string;
  // 列表视图配置
  list: IPanelModel[] = [];
  // 视图模式 auto：平铺模式 custom：自定义模式
  mode: BookMarkMode = 'auto';
  // 页签名称
  name: string;
  // 是否展示数字
  needCount?: boolean;
  // 页签配置
  options?: IBookMarkOptions;
  // 平铺模式 特有的图表配置顺序
  order?: IPanelModel[];
  // 宽窄表overview模式视图
  overview_panels: IPanelModel[];
  // 概览详情栏配置
  overviewDetailPanel?: PanelModel;
  overviewPanelCount = 0;
  // 页签图表统计数据
  panelCount = 0;
  // 视图配置
  panels: IPanelModel[];
  // 左侧选择栏配置
  selectorPanel?: PanelModel;
  // 是否展示页签图表统计数据
  show_panel_count = false;
  // 变量设置
  variables?: IVariableModel[] = [];
  constructor(public bookmark: IBookMark) {
    Object.assign(this, { ...this.bookmark });
    if (this.options?.detail_panel) {
      this.detailPanel = new PanelModel(this.options.detail_panel);
    }
    // if (this.options?.ai_panel) {
    //   this.aiPanel = new PanelModel(this.options.ai_panel);
    // }
    if (this.options?.overview_detail_panel) {
      this.overviewDetailPanel = new PanelModel(this.options.overview_detail_panel);
    }
    if (this.options?.selector_panel) {
      this.selectorPanel = new PanelModel(this.options.selector_panel);
    }
    if (this.options?.overview_panel) {
      this.alarmPanel = new PanelModel(this.options.overview_panel);
    }
    if (this.options?.fetch_panels) {
      this.fetchPanel = new PanelModel(this.options.fetch_panels);
    }
    // group panel
    if (this.options?.group_panel) {
      this.groupPanel = new PanelModel(this.options.group_panel);
    }
    this.updatePanels('detail');
    if (this.overview_panels?.length) {
      this.updatePanels('overview');
    }
    if (bookmark?.variables?.length) {
      this.variables = bookmark.variables.map(item => new VariableModel(item));
    }
    this.allVariables = this.getAllVariables();
  }
  // dashboard tool menu list
  get dashboardToolMenuList(): IMenuItem[] {
    return [
      { id: 'edit-tab', name: window.i18n.tc('编辑页签'), show: this.viewEditable },
      { id: 'edit-variate', name: window.i18n.tc('编辑变量'), show: this.variableEditable },
      { id: 'edit-dashboard', name: window.i18n.tc('编辑视图'), show: this.orderEditable },
      {
        id: 'view-demo',
        name: window.i18n.tc('DEMO'),
        show: window.space_list.some(item => item.is_demo),
      },
    ].filter(item => item.show);
  }
  // 所有视图ID
  // get allPanelId() {
  //   const tempSet = new Set();
  //   this.panels.forEach(panel => {
  //     if (panel.type === 'row') {
  //       panel?.panels?.forEach(p => {
  //         tempSet.add(p.id);
  //       });
  //     } else {
  //       tempSet.add(panel.id);
  //     }
  //   });
  //   return Array.from(tempSet) as string[];
  // }
  // 左侧选择栏默认宽度
  get defaultSelectorPanelWidth() {
    return (this.selectorPanel?.options?.selector_list?.status_filter ?? false) ? 400 : 240;
  }
  // 是否可配置group
  get enableGroup() {
    return !!this.options?.enable_group;
  }
  // 是否需要分组
  get hasGroup() {
    // return !!this.panels?.some(item => item.type === 'row' && item.id !== '__UNGROUP__');
    return !!this.panels?.some(item => item.type === 'row');
  }
  // 是否有列表模式
  get hasListPanels() {
    return this.list?.length > 0;
  }
  // 是否存在必选得变量
  get hasRequiredVariable() {
    return !!this.variables?.some(item => !!item.options?.variables?.required);
  }
  /* 将group选择替换为group by与compare混合的选择器   */
  get isGroupCompareType() {
    return this.options?.group_panel?.type === 'compare_or_group';
  }
  // 是否显示状态统计组件
  get isStatusFilter() {
    return this.selectorPanel?.options?.[this.selectorPanel.type]?.show_status_bar || false;
  }
  /* group by limit_sort_methods */
  get limitSortMethods() {
    return this.options?.group_panel?.options?.limit_sort_methods || [];
  }
  /* group by metric_cal_types */
  get metricCalTypes() {
    return this.options?.group_panel?.options?.metric_cal_types || [];
  }
  // 是否可配置视图
  get orderEditable() {
    return this.mode === 'auto' && !!this.order?.length;
  }
  // 搜索列表
  get searchData() {
    // const panels = sceneType === 'overview' ? this.overview_panels : this.panels;
    if (!this.panels?.length) return [];
    // 自定义模式下特殊处理
    if (!this.hasGroup) {
      const list = [];
      for (const item of this.panels) {
        if (item.type === 'row') {
          list.push(
            ...item.panels
              // .filter(set => set.type === 'tag-chart')
              .map(set => ({
                id: set.id.toString(),
                name: set.title.toString(),
              }))
          );
        } else {
          list.push({
            id: item.id.toString(),
            name: item.title.toString(),
          });
        }
      }
      return [
        {
          id: '__UN_GROUP__',
          name: window.i18n.tc('未分组视图'),
          multiple: true,
          children: list,
        },
      ];
    }
    if (this.hasGroup) {
      return this.panels.map(item => ({
        id: item.id.toString(),
        name: item.title.toString(),
        multiple: true,
        children:
          item.panels?.map(set => ({
            id: set.id.toString(),
            name: set.title.toString(),
          })) || [],
      }));
    }
    const list = [];
    for (const item of this.panels) {
      if (item.type === 'row') {
        list.push(
          ...item.panels.map(set => ({
            id: set.id.toString(),
            name: set.title.toString(),
          }))
        );
      } else
        list.push({
          id: item.id.toString(),
          name: item.title.toString(),
        });
    }
    return list;
  }
  // 设置视图的menu列表
  get settingMenuList(): IMenuItem[] {
    return [
      { id: 'edit-tab', name: '页签设置', show: this.viewEditable },
      { id: 'edit-variate', name: '变量设置', show: this.variableEditable },
      { id: 'edit-dashboard', name: '视图设置', show: this.orderEditable },
    ].filter(item => item.show);
  }
  // 是否显示info
  get showInfoPanel() {
    return !!this.detailPanel;
  }
  // 是否显示数据总览
  get showOverview() {
    return this.selectorPanel?.options?.[this.selectorPanel.type]?.show_overview || false;
  }
  // 是否先做出selector panel
  get showSelectPanel() {
    return !!this.selectorPanel;
  }
  // 状态映射
  get statusMapping() {
    return this.selectorPanel?.options?.[this.selectorPanel.type]?.status_mapping || [];
  }

  // 是否可配置变量
  get variableEditable() {
    return !!this.options?.variable_editable;
  }

  // 是否可配置页签
  get viewEditable() {
    return !!this.options?.view_editable;
  }

  getAllVariables() {
    let str = JSON.stringify(this.bookmark);
    const variableList = new Set<string>();
    str = str.replace(/\${([^}]+)}/gm, (m, key) => {
      variableList.add(key);
      return key;
    });
    str.replace(/"\$([^"]+)"/gm, (m, key) => {
      variableList.add(key);
      return m;
    });
    return variableList;
  }
  // 设置 和 判断是否有对应字段
  hasPanelFields(name: string, fieldName: string, panels: IPanelModel[]) {
    if (!this[name]) {
      this[name] = panels.some(set => typeof set[fieldName] !== 'undefined');
    }
  }
  // 动态更新panels
  updatePanels(sceneType: SceneType): number {
    let panelCount = 0;
    const panels = sceneType === 'overview' ? this.overview_panels : this.panels;
    if (!panels) return;
    if (panels.length) {
      if (this.mode === 'auto') {
        const rowPanelList = panels.filter(item => {
          if (item.type === 'row') {
            panelCount += item.panels.length;
            // item.panels.forEach(set => !set.id && (set.id = random(10)));
            if (!this.isShowPreciseFilter) {
              this.isShowPreciseFilter = item.panels.some(set => typeof set.dimensions !== 'undefined');
            }
            return true;
          }
          if (!this.isShowPreciseFilter) {
            this.isShowPreciseFilter = typeof item.dimensions !== 'undefined';
          }

          panelCount += 1;
          return false;
        });
        if (rowPanelList.length) {
          for (const item of rowPanelList) {
            item.collapsed = true;
          }
        }
      } else {
        // 自定义模式下重新设置唯一id
        for (const item of panels) {
          item.id = random(10);
          if (item.type === 'row' && item.panels?.length) {
            panelCount += item.panels.length;
            for (const set of item.panels) {
              set.id = random(10);
            }
            if (!this.isShowPreciseFilter) {
              this.isShowPreciseFilter = item.panels.some(set => typeof set.dimensions !== 'undefined');
            }
          } else {
            panelCount += 1;
            if (!this.isShowPreciseFilter) {
              this.isShowPreciseFilter = typeof item.dimensions !== 'undefined';
            }
          }
        }
      }
    }
    if (sceneType === 'overview') {
      this.overviewPanelCount = panelCount;
    } else {
      this.panelCount = panelCount;
    }
    return panelCount;
  }
}
