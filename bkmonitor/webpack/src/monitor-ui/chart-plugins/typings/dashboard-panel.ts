/* eslint-disable no-nested-ternary */
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
import type { EChartOption } from 'echarts';

import { isObject, random, typeTools } from '../../../monitor-common/utils/utils';

import { TimeSeriesType } from './time-series';

// 图例呈现模式
export type LegendDisplayMode = 'table' | 'list' | 'hidden';
// 图例展示位置
export type LegendPlacement = 'right' | 'bottom';
// 图例计算配置
export type LegendCalcs = 'max' | 'min' | 'avg' | 'sum';

export interface IFilterListItem {
  id: string;
  name: string;
}

// 图例配置
export interface ILegendOption {
  // 模式
  displayMode?: LegendDisplayMode;
  // 布局位置
  placement?: LegendPlacement;
  // 图例额外计算配置
  calcs?: LegendCalcs[];
}

export type FieldsSortType = Array<[string, string]>;

// 变量特有配置
export interface IVariablesOption {
  variables?: {
    // 是否可以多选 default true
    multiple?: boolean;
    // 是否必选 default false
    required?: boolean;
    // 是否内置
    internal?: boolean;
    // 是否可以清空  default true
    clearable?: boolean;
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
export interface ITimeSeriesOption {
  time_series?: {
    type?: TimeSeriesType;
    only_one_result?: boolean;
    echart_option?: EChartOption<EChartOption.Series>;
    markLine?: Record<string, any>;
    markArea?: Record<string, any>;
    custom_timerange?: boolean;
    nearSeriesNum?: number;
    noTransformVariables?: boolean;
  };
}

export interface ITimeSeriesListOption {
  disable_wrap_check?: boolean;
  time_series_list?: {
    need_hover_style?: boolean;
  };
}

export interface ITimeSeriesForecastOption {
  time_series_forecast?: {
    need_hover_style?: boolean;
    duration: number /** 预测时长 单位：秒 */;
    markLine?: Record<string, any>;
    markArea?: Record<string, any>;
  };
}

export interface ISelectorList {
  selector_list?: {
    status_filter?: boolean; // 是否启用状态筛选组件
    field_sort?: boolean; // 是否启用字段排序
    default_sort_field?: string; // 宽窄如果支持排序，需默认排序字段
    query_update_url?: boolean; // 是否更新搜索条件到url
  };
}
export interface ITargetListOption {
  target_list?: {
    show_overview?: boolean;
    show_status_bar?: boolean;
    placeholder?: string;
  };
}
export interface ITableChartOption {
  table_chart?: {
    need_filters?: boolean; // 是否需要表格筛选tab
    need_title?: boolean; // 表格图是否需要标题栏
    search_type?: 'input' | 'search_select' | 'none'; // 普通搜索 | search select组件
    json_viewer_data_key?: string; // 显示json格式数据的key show_expand=true生效
    json_viewer_data_empty_text?: string; // json格式数据为空的情况下提示内容 show_expand=true生效
    show_expand?: boolean; // 是否需要点击展开内容
    query_update_url?: boolean; // 是否更新表格搜索条件到url
    async_config?: Record<string, ITableChartAsyncOption>;
  };
}

export interface ITableChartAsyncOption {
  async_field_key: string;
  async_field_request_name: string;
  async_field: string;
}

/** 面板图表的通用配置 */
export interface IDashboardCommon {
  dashboard_common?: {
    static_width?: boolean; // true: dashboard的图表宽度不受布局影响一直为24
  };
}

// 视图位置信息 宽度 100% 分为 24
export interface IGridPos {
  x: number; // 左边距 类似left 默认1 = 30px
  y: number; // 上边距 类似top 默认1 = 30px
  w: number; // 宽度 100% 分为24分  24即为100%
  h: number; // 高度 默认1 = 30px
  static?: boolean; // 是否不可拖动 视图碰撞时不计算
  i?: number | string; // id
  maxW?: number; // max width
  maxH?: number; // max height
  minW?: number; // min width
  minH?: number; // min height
  isDraggable?: boolean; // 是否可以拖动
  isResizable?: boolean; // 是否可以改变大小
}

export interface DataQueryOptions {
  time_series_forecast?: {
    forecast_time_range: [number, number] /** 时间范围 [开始时间， 结束时间] 单位：秒*/;
    no_result: boolean /** 过滤掉_result_的数据 */;
  };
  table_chart?: {
    // 异步获取表格部分数据相关配置
    async_dict_key: string;
    async_columns: string[];
  };
}
export interface IDataQuery {
  datasource?: string | null;
  // 查询图表配置
  data: any;
  // 数据api
  api?: string;
  // 数据类型 table time_series ...
  dataType?: string;
  // 别名 用于图例 设置有变量
  alias?: string;
  // 映射的字段 变量的映射关系
  fields?: Record<string, string>;
  /** 排序后的fields, 用于前端id拼接 */
  fieldsSort?: FieldsSortType;
  /** 查询的单独配置 */
  options?: DataQueryOptions;
  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId?: (item: object, isFilterDict?: boolean, fieldsSort?: FieldsSortType) => string;
  /** 根据接口数据提取对应的filter_dict值  */
  // eslint-disable-next-line max-len
  handleCreateFilterDictValue?: (
    item: object,
    isFilterDict?: boolean,
    fieldsSort?: FieldsSortType
  ) => Record<string, any>;
}

export class DataQuery implements IDataQuery {
  datasource?: string | null;
  // 查询图表配置
  data: any;
  // 数据api
  api?: string;
  // 数据类型 table time_series ...
  dataType?: string;
  // 别名 用于图例 设置有变量
  alias?: string;
  // 变量的映射关系
  fields?: Record<string, string> = {};
  /** fields的拼接顺序 */
  fieldsSort?: FieldsSortType = [];
  fieldsKey?: string = '';
  field?: Record<string, string> = {};
  isMultiple?: boolean;
  options?: DataQueryOptions;
  /** 目标对比的字段映射 */
  compareFieldsSort?: FieldsSortType = [];
  // 用于主机ipv6 去除不需要的group_by字段
  ignore_group_by?: string[];
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
  get apiModule() {
    return this.api?.split('.')[0] || '';
  }
  get apiFunc() {
    return this.api?.split('.')[1] || '';
  }
  /** 对象生成有序的二维数组 */
  handleCreateFieldsSort(fields: Record<string, string>): FieldsSortType {
    const fieldsSort: FieldsSortType = [];
    Object.entries(fields)
      ?.map(item => item[0])
      ?.sort()
      ?.forEach(key => fieldsSort.push([key, fields[key]]));
    return fieldsSort;
  }
  /** 生成一个唯一的key */
  handleCreateFieldsKey(fieldsSort) {
    return fieldsSort.reduce((total, cur, index) => {
      const joiner = !index ? '' : '-';
      return (total = `${total}${joiner}${cur[1]}`);
    }, '');
  }
  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId(item: Object, isFilterDict = false, fieldsSort?: FieldsSortType, splitChar = '-') {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const itemIds = [];
    localFieldsSort.forEach(set => {
      const [itemKey, filterDictKey] = set;
      const key = isFilterDict ? filterDictKey : itemKey;
      let value = item[key];
      value === undefined && isExist && (isExist = false);
      value =
        this.isMultiple || ['pod_name_list'].includes(key)
          ? Array.isArray(value)
            ? value
            : [value]
          : isObject(value)
            ? value.value
            : value; // 兼容对象结构的value
      itemIds.push(value);
    });
    return isExist ? itemIds.filter(item => item !== undefined).join(splitChar) : null;
  }
  /** 根据接口数据提取对应的filter_dict值 */
  handleCreateFilterDictValue(data: Object, isFilterDict = false, fieldsSort?: FieldsSortType) {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data?.[isFilterDict ? filterDictKey : itemKey];
      value === undefined && isExist && (isExist = false);
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
  handleCreateCompares(data: Object) {
    const localFieldsSort = this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data?.[itemKey];
      value === undefined && isExist && (isExist = false);
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

export interface IRatioRingChartOption {
  hideLabel?: boolean; // 是否隐藏圆环中间label
}

export interface IPercentageBarOption {
  percentage_bar?: {
    filter_key?: string; // 切换数据源的参数名
    filter_value?: string; // 切换数据源的默认参数值
    filter_list?: IFilterListItem[];
  };
}

export interface IResourceChartOption {
  alert_filterable?: {
    filter_type?: string; // 点击检索跳转到的页面类型 event 事件检索
    save_to_dashboard?: boolean; // 是否显示保存到仪表盘
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
  };
}

export interface IRelatedLogChartoption {
  related_log_chart?: {
    defaultKeyword: string;
  };
}

// eslint-disable-next-line max-len
// 视图特殊配置
export type PanelOption = {
  legend?: ILegendOption;
  unit?: string; // 单位
  header?: {
    tips: string; // 提示
  };
} & ISelectorList &
  IDashboardCommon &
  IVariablesOption &
  ITopoTreeOption &
  ITimeSeriesOption &
  ITargetListOption &
  ITableChartOption &
  ITimeSeriesListOption &
  ITimeSeriesForecastOption &
  IRatioRingChartOption &
  IPercentageBarOption &
  IResourceChartOption &
  IRelatedLogChartoption;

export interface IPanelModel {
  id: string | number;
  // 图表位置
  gridPos?: IGridPos;
  // 图表类型 如 line-chart bar-chart status-chart group
  type: string;
  // 图表分类
  anomaly_dimension_class?: string;
  // 图表title
  title: string;
  // 图表subTitle
  subTitle?: string;
  // 图标带icon说明
  descrition?: string;
  // 是否折叠
  collapsed?: boolean;
  // 图表数据源
  targets: IDataQuery[];
  // 图表配置
  options?: PanelOption;
  // 图表dashboard id
  dashboardId?: string | number;
  // 组内视图列表
  panels?: IPanelModel[];
  // 是否显示
  show?: boolean;
  // 组id
  groupId?: string | number;
  // 是否实时
  instant?: boolean;
  // 数据步长
  collect_interval?: number;
  // 维度列表
  dimensions?: string[];
  // 匹配显示字段
  matchDisplay?: Record<string, any>;
}

export class PanelModel implements IPanelModel {
  // 图表id
  id!: string | number;
  // 图表位置
  gridPos!: IGridPos;
  // 图表类型 如 line-chart bar-chart status-chart group
  type!: string;
  // 图表title
  title!: string;
  subTitle!: string;
  // 图标带icon说明
  descrition!: string;
  // 是否折叠
  collapsed?: boolean = false;
  // 图表数据源
  targets: DataQuery[];
  // 图表配置
  options?: PanelOption;
  // dashbordId
  dashboardId?: string;
  // 是否被勾选
  checked?: boolean = false;
  // 组id
  groupId?: string | number;
  // 是否显示
  show?: boolean = true;
  panels?: PanelModel[];
  // 是否正在drag中
  draging = false;
  // 是否为实时
  instant = false;

  collect_interval: number;
  // 维度列表
  dimensions: string[];
  realHeight = 0;
  // 匹配显示字段
  matchDisplay?: Record<string, any>;
  // 是否显示百分比
  percent?: boolean;
  // 当前业务id
  bk_biz_id?: string | number;

  constructor(model: IPanelModel & { panelIds?: (string | number)[] }) {
    this.id = model.id || random(10);
    Object.keys(model).forEach(key => {
      if (key === 'targets') {
        this.targets = model[key].map(item => new DataQuery(item));
      } else {
        this[key] = model[key];
      }
    });
    if (this.type === 'graph') {
      this.options = {
        legend: {
          displayMode: 'list',
          placement: 'bottom'
        },
        ...this.options
      };
    }
    this.updateGridPos(model.gridPos);
  }
  get canSetGrafana() {
    return ['graph', 'performance-chart'].includes(this.type);
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
      isResizable: this.canResize
    };
  }
  public updateChecked(v: boolean) {
    this.checked = v;
  }
  public updateCollapsed(v: boolean) {
    this.collapsed = v;
    this.panels?.length && this.panels.forEach(item => item?.updateShow?.(v));
  }
  public updateShow(v: boolean) {
    this.show = v;
  }
  public updateDraging(v: boolean) {
    this.draging = v;
  }
  public updateRealHeight(v: number) {
    this.realHeight = v;
  }
}

export interface IFields {
  [key: string]: any;
}
export interface IVariableModel {
  options?: IVariablesOption; // 变量的配置
  targets: DataQuery[]; // 变量的接口数据
  title: string; // 变量的标题
  type: string; // 接口数据类型
  fields: IFields; // 变量接口数据映射关系
  fieldsKey: string; // 变量的唯一key
  fieldsSort: FieldsSortType; // 有序的变量字段映射关系
  value: Record<string, any>; // 值
  checked: boolean; // 是否选中的变量
  isMultiple: boolean; // 是否多选
  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId: (item: object, isFilterDict?: boolean) => string;
}
/** 变量数据类 */
export class VariableModel implements IVariableModel {
  type = '';
  title = '';
  targets: DataQuery[] = [];
  options: IVariablesOption = {};
  fieldsKey = '';
  fieldsSort: FieldsSortType = [];
  value: Record<string, any> = {};
  checked = true;
  fields: Record<string, any> = {};
  constructor(model) {
    Object.keys(model || {}).forEach(key => {
      if (key === 'targets') {
        this.targets = model[key].map(item => new DataQuery(item, model.options?.variables?.multiple ?? false));
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
    });
  }
  /** 生成id */
  handleCreateItemId(srcData: IFields, isFilterDict = false) {
    const JOINER = '-';
    let isExits = true;
    const resData = this.fieldsSort.reduce((total, item) => {
      const [itemKey, filterDictKey] = item;
      const value = srcData[isFilterDict ? filterDictKey : itemKey];
      value === undefined && (isExits = false);
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
  /** 变量是否支持多选 */
  get isMultiple() {
    return this.options?.variables?.multiple ?? false;
  }
}

export interface IDashbordConfig {
  id: string | number;
  panels: IPanelModel[];
}

export type DashboardColumnType = number | 'custom';
