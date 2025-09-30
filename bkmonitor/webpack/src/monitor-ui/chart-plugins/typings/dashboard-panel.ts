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
import { isObject, random, typeTools } from 'monitor-common/utils/utils';

import { filterDictConvertedToWhere, getMetricId } from '../utils/utils';

import type { MonitorEchartOptions } from './index';
import type { TimeSeriesType } from './time-series';

export type DashboardColumnType = 'custom' | number;
export interface DataQueryOptions {
  table_chart?: {
    async_columns: string[];
    // 异步获取表格部分数据相关配置
    async_dict_key: string;
  };
  time_series_forecast?: {
    forecast_time_range: [number, number] /** 时间范围 [开始时间， 结束时间] 单位：秒*/;
    no_result: boolean /** 过滤掉_result_的数据 */;
  };
}
export type FieldsSortType = Array<[string, string]>;

export interface IApdexChartOption {
  apdex_chart?: {
    enableContextmenu?: boolean; // 是否开启全局的右键菜单
    sceneType?: string;
  };
}

export interface IApmRelationGraphOption {
  apm_relation_graph?: {
    app_name?: string;
    service_name?: string;
  };
}

export interface IApmTimeSeriesOption {
  apm_time_series?: {
    app_name?: string;
    disableZoom?: boolean;
    enableContextmenu?: boolean; // 是否开启全局的右键菜单
    enableSeriesContextmenu?: boolean; // 是否开启series的右键菜单
    metric?: string;
    sceneType?: string;
    service_name?: string;
    unit?: string; // 详情单位
    xAxisSplitNumber?: number;
  };
}

/** 面板图表的通用配置 */
export interface IDashboardCommon {
  dashboard_common?: {
    static_width?: boolean; // true: dashboard的图表宽度不受布局影响一直为24
  };
}

export interface IDashbordConfig {
  id: number | string;
  panels: IPanelModel[];
}
export interface IDataQuery {
  // 别名 用于图例 设置有变量
  alias?: string;
  // 数据api
  api?: string;
  // 查询图表配置
  data: any;
  datasource?: null | string;
  // 数据类型 table time_series ...
  dataType?: string;
  // 映射的字段 变量的映射关系
  fields?: Record<string, string>;
  /** 排序后的fields, 用于前端id拼接 */
  fieldsSort?: FieldsSortType;
  /** 查询的单独配置 */
  options?: DataQueryOptions;
  handleCreateFilterDictValue?: (
    item: object,
    isFilterDict?: boolean,
    fieldsSort?: FieldsSortType
  ) => Record<string, any>;
  /** 根据接口数据提取对应的filter_dict值  */

  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId?: (item: object, isFilterDict?: boolean, fieldsSort?: FieldsSortType) => string;
}

export interface IFields {
  [key: string]: any;
}

export interface IFilterListItem {
  id: string;
  name: string;
}

// 视图位置信息 宽度 100% 分为 24
export interface IGridPos {
  h: number; // 高度 默认1 = 30px
  i?: number | string; // id
  isDraggable?: boolean; // 是否可以拖动
  isResizable?: boolean; // 是否可以改变大小
  maxH?: number; // max height
  maxW?: number; // max width
  minH?: number; // min height
  minW?: number; // min width
  static?: boolean; // 是否不可拖动 视图碰撞时不计算
  w: number; // 宽度 100% 分为24分  24即为100%
  x: number; // 左边距 类似left 默认1 = 30px
  y: number; // 上边距 类似top 默认1 = 30px
}
// 图例配置
export interface ILegendOption {
  // 图例额外计算配置
  calcs?: LegendCalcs[];
  // 模式
  displayMode?: LegendDisplayMode;
  // 布局位置
  placement?: LegendPlacement;
}
export interface IPanelModel {
  // 图表分类
  anomaly_dimension_class?: string;
  // 是否勾选图表
  checked?: boolean;
  // 是否折叠
  collapsed?: boolean;
  // 数据步长
  collect_interval?: number;
  // 图表dashboard id
  dashboardId?: number | string;
  // 图标带icon说明
  description?: string;
  // 维度列表
  dimensions?: string[];
  // 图表位置
  gridPos?: IGridPos;
  // 组id
  groupId?: number | string;
  id: number | string;
  // 是否实时
  instant?: boolean;
  // 匹配显示字段
  matchDisplay?: Record<string, any>;
  // 图表配置
  options?: PanelOption;
  // 组内视图列表
  panels?: IPanelModel[];
  // 是否显示
  show?: boolean;
  // 图表subTitle
  subTitle?: string;
  // 图表数据源
  targets: IDataQuery[];
  // 图表title
  title: string;
  // 图表类型 如 line-chart bar-chart status-chart group
  type: string;
}

export interface IPercentageBarOption {
  percentage_bar?: {
    filter_key?: string; // 切换数据源的参数名
    filter_list?: IFilterListItem[];
    filter_value?: string; // 切换数据源的默认参数值
  };
}

export interface IRatioRingChartOption {
  hideLabel?: boolean; // 是否隐藏圆环中间label
}

export interface IRelatedLogChartoption {
  related_log_chart?: {
    defaultKeyword: string;
    isSimpleChart?: boolean; // 是否为精简模式
  };
}

export interface IResourceChartOption {
  alert_filterable?: {
    data?: {
      bcs_cluster_id?: string; // 集群id
      data_source_label?: string; // 事件类型 custom表示自定义上报事件
      data_type_label?: string; // 数据类型 event表示查询的是事件数据
      where?: {
        // 过滤条件
        key: string;
        method: string;
        value: string[];
      }[];
    };
    event_center?: {
      query_string?: {
        // 查询字符串
        metric?: string; // 指标ID的值
      }[];
    };
    filter_type?: string; // 点击检索跳转到的页面类型 event 事件检索
    save_to_dashboard?: boolean; // 是否显示保存到仪表盘
  };
}
export interface ISelectorList {
  selector_list?: {
    default_sort_field?: string; // 宽窄如果支持排序，需默认排序字段
    field_sort?: boolean; // 是否启用字段排序
    query_update_url?: boolean; // 是否更新搜索条件到url
    status_filter?: boolean; // 是否启用状态筛选组件
  };
}

export interface ITableChartAsyncOption {
  async_field: string;
  async_field_key: string;
  async_field_request_name: string;
}

export interface ITableChartOption {
  table_chart?: {
    async_config?: Record<string, ITableChartAsyncOption>;
    json_viewer_data_empty_text?: string; // json格式数据为空的情况下提示内容 show_expand=true生效
    json_viewer_data_key?: string; // 显示json格式数据的key show_expand=true生效
    need_filters?: boolean; // 是否需要表格筛选tab
    need_title?: boolean; // 表格图是否需要标题栏
    query_update_url?: boolean; // 是否更新表格搜索条件到url
    search_type?: 'input' | 'none' | 'search_select'; // 普通搜索 | search select组件
    show_expand?: boolean; // 是否需要点击展开内容
  };
}

export interface ITargetListOption {
  target_list?: {
    placeholder?: string;
    show_overview?: boolean;
    show_status_bar?: boolean;
    status_tab_list?: {
      id: string;
      name: string;
      status: string;
      tips: string;
    }[];
    time_range_change_refresh?: boolean; // 时间范围变化是否刷新列表数据
  };
}

export interface ITimeSeriesForecastOption {
  time_series_forecast?: {
    duration: number /** 预测时长 单位：秒 */;
    markArea?: Record<string, any>;
    markLine?: Record<string, any>;
    need_hover_style?: boolean;
  };
}

export interface ITimeSeriesListOption {
  disable_wrap_check?: boolean;
  time_series_list?: {
    need_hover_style?: boolean;
  };
}

export interface ITimeSeriesOption {
  time_series?: {
    custom_timerange?: boolean;
    echart_option?: MonitorEchartOptions;
    hoverAllTooltips?: boolean;
    markArea?: Record<string, any>;
    markLine?: Record<string, any>;
    nearSeriesNum?: number;
    needAllAlertMarkArea?: boolean;
    noTransformVariables?: boolean;
    only_one_result?: boolean;
    type?: TimeSeriesType;
    YAxisLabelWidth?: number;
  };
}

// topo_tree特有配置
export interface ITopoTreeOption {
  topo_tree?: {
    // 是否可以选节点 default false
    can_check_node?: boolean;
    show_overview?: boolean;
    show_status_bar?: boolean;
  };
}

export interface IVariableModel {
  checked: boolean; // 是否选中的变量
  fields: IFields; // 变量接口数据映射关系
  fieldsKey: string; // 变量的唯一key
  fieldsSort: FieldsSortType; // 有序的变量字段映射关系
  isMultiple: boolean; // 是否多选
  options?: IVariablesOption; // 变量的配置
  targets: DataQuery[]; // 变量的接口数据
  title: string; // 变量的标题
  type: string; // 接口数据类型
  value: Record<string, any>; // 值
  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId: (item: object, isFilterDict?: boolean) => string;
}

// 变量特有配置
export interface IVariablesOption {
  variables?: {
    // 是否可以清空  default true
    clearable?: boolean;
    // 是否内置
    internal?: boolean;
    // 是否可以多选 default true
    multiple?: boolean;
    // 是否必选 default false
    required?: boolean;
  };
}

// 图例计算配置
export type LegendCalcs = 'avg' | 'max' | 'min' | 'sum';

// 图例呈现模式
export type LegendDisplayMode = 'hidden' | 'list' | 'table';

// 图例展示位置
export type LegendPlacement = 'bottom' | 'right';

export interface ObservablePanelField {
  [key: number | string]: Pick<IPanelModel, 'checked' | 'collapsed' | 'show'>;
}
// 视图特殊配置
export type PanelOption = {
  child_panels_selector_variables?: {
    id?: string;
    title?: string;
  }[];
  is_code_redefine?: boolean; // 是否有返回码重定义功能
  collect_interval_display?: string; // 数据步长（步长过大情况时需要，正常情况无此字段）
  enable_panels_selector?: boolean;
  header?: {
    tips: string; // 提示
  };
  is_support_compare?: boolean;
  is_support_group_by?: boolean;
  legend?: ILegendOption;
  need_zr_click_event?: boolean; // 是否需要zrender click 事件
  precision?: number; // 单位精度
  unit?: string; // 单位
} & IApdexChartOption &
  IApmRelationGraphOption &
  IApmTimeSeriesOption &
  IDashboardCommon &
  IPercentageBarOption &
  IRatioRingChartOption &
  IRelatedLogChartoption &
  IResourceChartOption &
  ISelectorList &
  ITableChartOption &
  ITargetListOption &
  ITimeSeriesForecastOption &
  ITimeSeriesListOption &
  ITimeSeriesOption &
  ITopoTreeOption &
  IVariablesOption;

export class DataQuery implements IDataQuery {
  // 别名 用于图例 设置有变量
  alias?: string;
  // 数据api
  api?: string;
  chart_type: 'bar' | 'line' = undefined;
  /** 目标对比的字段映射 */
  compareFieldsSort?: FieldsSortType = [];
  // 查询图表配置
  data: any;
  datasource?: null | string;
  // 数据类型 table time_series ...
  dataType?: string;
  expression?: string;
  field?: Record<string, string> = {};
  // 变量的映射关系
  fields?: Record<string, string> = {};
  fieldsKey?: string = '';
  /** fields的拼接顺序 */
  fieldsSort?: FieldsSortType = [];
  // 用于主机ipv6 去除不需要的group_by字段
  ignore_group_by?: string[];
  isMultiple?: boolean;
  options?: DataQueryOptions;
  // 主键参数
  primary_key?: string;
  yAxisIndex?: number;
  constructor(model: IDataQuery, isMultiple = false) {
    this.isMultiple = isMultiple;
    Object.keys(model || {}).forEach(key => {
      this[key] = model[key];
      if (key === 'fields') {
        const fields = model[key];
        // Object.entries(fields)
        //   ?.map(item => item[0])
        //   ?.sort()
        //   ?.forEach(key => this.fieldsSort.push([key, fields[key]]));
        this.fieldsSort = this.handleCreateFieldsSort(fields);
        this.fieldsKey = this.handleCreateFieldsKey(this.fieldsSort);
        // this.fieldsKey = this.fieldsSort.reduce((total, cur, index) => {
        //   const joiner = !index ? '' : '-';
        //   return total = `${total}${joiner}${cur[1]}`;
        // }, '');
      } else if (key === 'compare_fields') {
        const fields = model[key];
        this.compareFieldsSort = this.handleCreateFieldsSort(fields);
      }
    });
  }
  get apiFunc() {
    return this.api?.split('.')[1] || '';
  }
  get apiModule() {
    return this.api?.split('.')[0] || '';
  }
  handleCreateCompares(data: object) {
    const localFieldsSort = this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data?.[itemKey];
      if (value === undefined && isExist) {
        isExist = false;
      }
      value =
        this.isMultiple || ['pod_name_list'].includes(itemKey)
          ? Array.isArray(value)
            ? value
            : [value]
          : isObject(value)
            ? value.value
            : value; // 兼容对象结构的value
      total[filterDictKey] = value;
      return total;
    }, {});
    return isExist ? result : null;
  }
  handleCreateComparesSingle(data: object) {
    const localFieldsSort = this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data?.[itemKey];
      if (value === undefined && isExist) {
        isExist = false;
      }
      value = isObject(value) ? value.value : value; // 兼容对象结构的value
      total[filterDictKey] = value;
      return total;
    }, {});
    return isExist ? result : null;
  }
  /** 生成一个唯一的key */
  handleCreateFieldsKey(fieldsSort) {
    return fieldsSort.reduce((total, cur, index) => {
      const joiner = !index ? '' : '-';
      return `${total}${joiner}${cur[1]}`;
    }, '');
  }
  /** 对象生成有序的二维数组 */
  handleCreateFieldsSort(fields: Record<string, string>): FieldsSortType {
    const fieldsSort: FieldsSortType = [];
    const list =
      Object.entries(fields)
        ?.map(item => item[0])
        ?.sort() || [];
    for (const key of list) {
      fieldsSort.push([key, fields[key]]);
    }
    return fieldsSort;
  }
  /** 根据接口数据提取对应的filter_dict值 */
  handleCreateFilterDictValue(data: object, isFilterDict = false, fieldsSort?: FieldsSortType) {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data?.[isFilterDict ? filterDictKey : itemKey];
      if (value === undefined && isExist) {
        isExist = false;
      }
      value =
        this.isMultiple || ['pod_name_list'].includes(itemKey)
          ? Array.isArray(value)
            ? value
            : [value]
          : isObject(value)
            ? value.value
            : value; // 兼容对象结构的value
      total[itemKey] = value;
      return total;
    }, {});
    return isExist ? result : null;
  }
  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId(item: object, isFilterDict = false, fieldsSort?: FieldsSortType, splitChar = '-') {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const itemIds = [];
    for (const set of localFieldsSort) {
      const [itemKey, filterDictKey] = set;
      const key = isFilterDict ? filterDictKey : itemKey;
      let value = item[key];
      if (value === undefined && isExist) {
        isExist = false;
      }
      value =
        this.isMultiple || ['pod_name_list'].includes(key)
          ? Array.isArray(value)
            ? value
            : [value]
          : isObject(value)
            ? value.value
            : value; // 兼容对象结构的value
      itemIds.push(value);
    }
    return isExist ? itemIds.filter(item => item !== undefined).join(splitChar) : null;
  }
}

class VariableDataQuery extends DataQuery {
  /** 根据接口数据提取对应的filter_dict值 */
  handleCreateFilterDictValue(data: object, isFilterDict = false, fieldsSort?: FieldsSortType) {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data?.[isFilterDict ? filterDictKey : itemKey];
      if (value === undefined && isExist) {
        isExist = false;
      }
      value =
        this.isMultiple || ['pod_name_list'].includes(itemKey)
          ? Array.isArray(value)
            ? value
            : [value]
          : isObject(value)
            ? value.value
            : value; // 兼容对象结构的value
      total[filterDictKey] = value;
      return total;
    }, {});
    return isExist ? result : null;
  }
}

export class PanelModel implements IPanelModel {
  // 当前业务id
  bk_biz_id?: number | string;
  // 是否被勾选
  checked?: boolean = false;
  // 是否折叠
  collapsed?: boolean = false;
  collect_interval: number;
  // dashbordId
  dashboardId?: string;
  // 图标带icon说明
  description!: string;
  dimension_panels?: PanelModel[];
  // 维度列表
  dimensions: string[];
  // 是否正在drag中
  dragging = false;
  externalData: Record<string, any>; // 一些额外自定义数据 用于图表
  extra_panels?: PanelModel[];
  // 图表位置
  gridPos!: IGridPos;
  // 组id
  groupId?: number | string;
  // 图表id
  id!: number | string;
  // 是否为实时
  instant = false;
  // 匹配显示字段
  matchDisplay?: Record<string, any>;
  // 图表配置
  options?: PanelOption;

  panels?: PanelModel[];
  // 是否显示百分比
  percent?: boolean;
  rawTargetQueryMap = new WeakMap<Record<string, any>>();
  realHeight = 0;
  // 是否显示
  show?: boolean = true;
  // eslint-disable-next-line @typescript-eslint/naming-convention
  sub_title?: string;
  subTitle!: string;
  // 图表数据源
  targets: DataQuery[];
  // 图表title
  title!: string;
  // 图表类型 如 line-chart bar-chart status-chart group
  type!: string;
  constructor(model: Partial<IPanelModel> & { panelIds?: (number | string)[] }) {
    this.id = model.id || random(10);
    // biome-ignore lint/complexity/noForEach: <explanation>
    Object.keys(model).forEach(key => {
      if (key === 'targets') {
        this.targets = model[key].map(item => new DataQuery(item));
      } else if (key === 'extra_panels') {
        this.extra_panels =
          model[key]?.map(
            item =>
              new PanelModel({
                ...item,
                options: {
                  ...item.options,
                  need_zr_click_event: true,
                },
              })
          ) || [];
      } else {
        this[key] = model[key];
      }
    });
    if (this.type === 'graph') {
      this.options = {
        legend: {
          displayMode: 'list',
          placement: 'bottom',
        },
        ...this.options,
      };
    }
    this.updateGridPos(model.gridPos);
  }
  get canDrag() {
    // return !(['row'].includes(this.type) && this.collapsed);
    // 当期需求默认配置视图不可拖拽
    return false;
  }
  get canResize() {
    // return !['row'].includes(this.type);
    // 当期需求默认配置视图不可resize
    return false;
  }
  get canSetGrafana() {
    return [
      'graph',
      'performance-chart',
      'caller-line-chart',
      'apm-timeseries-chart',
      'apm-custom-graph',
      'k8s_custom_graph',
    ].includes(this.type);
  }
  setRawQueryConfigs(target: Record<string, any>, data: Record<string, any>) {
    this.rawTargetQueryMap.set(target, data);
  }
  public toDashboardPanels() {
    const queries = this.targets
      .map(set => {
        if (this.rawTargetQueryMap.has(set)) {
          const config = structuredClone(this.rawTargetQueryMap.get(set) || {});
          return {
            alias: set.alias || '',
            expression: set.expression || 'A',
            ...config,
            query_configs: [
              filterDictConvertedToWhere(
                Array.isArray(config.query_configs) ? config.query_configs[0] : config.query_configs
              ),
            ],
          };
        }
        return undefined;
      })
      .filter(Boolean);
    if (!queries.length) return undefined;
    return {
      name: this.title,
      fill: this.fill,
      min_y_zero: this.min_y_zero,
      queries,
    };
  }
  public toDataRetrieval() {
    const targets = this.targets
      .map(set => {
        if (this.rawTargetQueryMap.has(set)) {
          const config = structuredClone(this.rawTargetQueryMap.get(set) || {});
          return {
            data: {
              ...config,
              query_configs: [
                filterDictConvertedToWhere(
                  Array.isArray(config.query_configs) ? config.query_configs[0] : config.query_configs
                ),
              ],
            },
          };
        }
        return undefined;
      })
      .filter(Boolean);
    if (!targets.length) return undefined;
    return targets;
  }
  public toRelateEvent() {
    const queries = this.targets
      .map(set => {
        if (this.rawTargetQueryMap.has(set)) {
          const config = structuredClone(this.rawTargetQueryMap.get(set) || {});
          return {
            query_configs: [
              filterDictConvertedToWhere(
                Array.isArray(config.query_configs) ? config.query_configs[0] : config.query_configs
              ),
            ],
          };
        }
        return undefined;
      })
      .filter(Boolean);
    if (!queries.length) return undefined;
    const metricIdMap = {};
    const promqlSet = new Set<string>();
    for (const target of queries) {
      if (target?.query_configs?.length) {
        for (const item of target.query_configs) {
          if (item.promql) {
            promqlSet.add(JSON.stringify(item.promql));
          } else {
            const metricId = getMetricId(
              item.data_source_label,
              item.data_type_label,
              item.metrics?.[0]?.field,
              item.table,
              item.index_set_id
            );
            if (metricId) {
              metricIdMap[metricId] = 'true';
            }
          }
        }
      }
    }
    let queryString = '';
    for (const metricId of Object.keys(metricIdMap)) {
      queryString += `${queryString.length ? ' OR ' : ''}指标ID : ${metricId}`;
    }
    let promqlString = '';
    for (const promql of promqlSet) {
      promqlString = `promql=${promql}`;
    }
    return promqlString || `queryString=${queryString}`;
  }
  public toStrategy() {
    const queries = this.targets
      .map(set => {
        if (this.rawTargetQueryMap.has(set)) {
          const config = structuredClone(this.rawTargetQueryMap.get(set) || {});
          return {
            expression: set.expression || 'A',
            query_configs: (Array.isArray(config.query_configs) ? config.query_configs : [config.query_configs]).map(
              item => filterDictConvertedToWhere(item)
            ),
          };
        }
        return undefined;
      })
      .filter(Boolean);
    if (!queries.length) return undefined;
    return queries[0];
  }
  public updateChecked(v: boolean) {
    this.checked = v;
  }
  public updateCollapsed(v: boolean) {
    this.collapsed = v;
    this.panels?.length && this.panels.forEach(item => item?.updateShow?.(v));
  }
  public updateDragging(v: boolean) {
    this.dragging = v;
  }
  public updateGridPos(v: IGridPos) {
    this.gridPos = {
      ...v,
      minH: 1,
      minW: 1,
      maxH: 30,
      maxW: 24,
      i: this.id,
      static: !(this.canDrag && this.canResize),
      isDraggable: this.canDrag,
      isResizable: this.canResize,
    };
  }
  public updateRealHeight(v: number) {
    this.realHeight = v;
  }
  public updateShow(v: boolean) {
    this.show = v;
  }
}

/** 变量数据类 */
export class VariableModel implements IVariableModel {
  checked = true;
  fields: Record<string, any> = {};
  fieldsKey = '';
  fieldsSort: FieldsSortType = [];
  options: IVariablesOption = {};
  targets: DataQuery[] = [];
  title = '';
  type = '';
  value: Record<string, any> = {};
  constructor(model) {
    for (const key of Object.keys(model || {})) {
      if (key === 'targets') {
        this.targets = model[key].map(item => new VariableDataQuery(item, model.options?.variables?.multiple ?? true));
        const target = this.targets[0];
        this.fields = target.fields;
        this.fieldsSort = target.fieldsSort;
        this.fieldsKey = target.fieldsKey;
        // this.fieldsKey = target?.fieldsSort.reduce((total, cur, index) => {
        //   const joiner = !index ? '' : '-';
        //   return total = `${total}${joiner}${cur[1]}`;
        // }, '');
      } else {
        this[key] = model[key];
      }
    }
  }
  /** 变量是否支持多选 */
  get isMultiple() {
    return this.options?.variables?.multiple ?? false;
  }
  /** 生成id */
  handleCreateItemId(srcData: IFields, isFilterDict = false) {
    const JOINER = '-';
    let isExits = true;
    const resData = this.fieldsSort.reduce((total, item) => {
      const [itemKey, filterDictKey] = item;
      const value = srcData[isFilterDict ? filterDictKey : itemKey];
      if (value === undefined && isExits) {
        isExits = false;
      }
      typeTools.isObject(value)
        ? total.push(
            ...Object.keys(value)
              .sort()
              .map(key => value[key])
          )
        : total.push(`${value}`);
      return total;
    }, []);
    return isExits ? resData.join(JOINER) : null;
  }
}
