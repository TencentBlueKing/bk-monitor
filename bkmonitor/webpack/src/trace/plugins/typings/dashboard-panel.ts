/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { typeTools } from 'monitor-common/utils/utils';

import type { TimeSeriesType } from './time-series';
import type { MonitorEchartOptions } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
// 图例呈现模式
export type LegendDisplayMode = 'hidden' | 'list' | 'table';
// 图例展示位置
export type LegendPlacement = 'bottom' | 'right';
// 图例计算配置
export type LegendCalcs = 'avg' | 'max' | 'min' | 'sum';

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
    echart_option?: MonitorEchartOptions;
    markLine?: Record<string, any>;
    markArea?: Record<string, any>;
    custom_timerange?: boolean;
  };
}

export interface ITimeSeriesListOption {
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
    search_type?: 'input' | 'search_select'; // 普通搜索 | search select组件
    json_viewer_data_key?: string; // 显示json格式数据的key show_expand=true生效
    show_expand?: boolean; // 是否需要点击展开内容
    query_update_url?: boolean; // 是否更新表格搜索条件到url
  };
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
}
export interface IDataQuery {
  datasource?: null | string;
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

  handleCreateFilterDictValue?: (
    item: object,
    isFilterDict?: boolean,
    fieldsSort?: FieldsSortType
  ) => Record<string, any>;
}

export class DataQuery implements IDataQuery {
  // 别名 用于图例 设置有变量
  alias?: string;
  // 数据api
  api?: string;
  /** 目标对比的字段映射 */
  compareFieldsSort?: FieldsSortType = [];
  // 查询图表配置
  data: any;
  datasource?: null | string;
  // 数据类型 table time_series ...
  dataType?: string;
  field?: Record<string, string> = {};
  // 变量的映射关系
  fields?: Record<string, string> = {};
  fieldsKey?: string = '';
  /** fields的拼接顺序 */
  fieldsSort?: FieldsSortType = [];
  isMultiple?: boolean;
  options?: DataQueryOptions;
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
  /** 生成一个唯一的key */
  handleCreateFieldsKey(fieldsSort) {
    return fieldsSort.reduce((total, cur, index) => {
      const joiner = !index ? '' : '-';
      return (total = `${total}${joiner}${cur[1]}`);
    }, '');
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
  /** 根据接口数据提取对应的filter_dict值 */
  handleCreateFilterDictValue(data: object, isFilterDict = false, fieldsSort?: FieldsSortType) {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const result = localFieldsSort.reduce((total, cur) => {
      const [itemKey, filterDictKey] = cur;
      let value = data[isFilterDict ? filterDictKey : itemKey];
      value === undefined && isExist && (isExist = false);

      value = this.isMultiple ? (Array.isArray(value) ? value : [value]) : value;
      total[filterDictKey] = value;
      return total;
    }, {});
    return isExist ? result : null;
  }
  /** 根据当前请求接口数据的映射规则生成id */
  handleCreateItemId(item: object, isFilterDict = false, fieldsSort?: FieldsSortType) {
    const localFieldsSort = fieldsSort || this.fieldsSort;
    let isExist = true;
    const itemIds = [];
    localFieldsSort.forEach(set => {
      const [itemKey, filterDictKey] = set;
      const key = isFilterDict ? filterDictKey : itemKey;
      let value = item[key];
      value === undefined && isExist && (isExist = false);

      value = this.isMultiple ? (Array.isArray(value) ? value : [value]) : value;
      itemIds.push(item[key]);
    });
    return isExist ? itemIds.filter(item => item !== undefined).join('-') : null;
  }
}

export interface IRatioRingChartOption {
  hideLabel?: boolean; // 是否隐藏圆环中间label
}

interface IApmTimeSeriesOption {
  apm_time_series?: {
    unit?: string; // 详情单位
    metric?: string;
    app_name?: string;
    service_name?: string;
    enableSeriesContextmenu?: boolean; // 是否开启series的右键菜单
    enableContextmenu?: boolean; // 是否开启全局的右键菜单
    xAxisSplitNumber?: number;
    disableZoom?: boolean;
    sceneType?: string;
  };
}

// 视图特殊配置
export type PanelOption = { legend?: ILegendOption } & ISelectorList &
  IDashboardCommon &
  IVariablesOption &
  ITopoTreeOption &
  ITimeSeriesOption &
  ITargetListOption &
  ITableChartOption &
  ITimeSeriesListOption &
  ITimeSeriesForecastOption &
  IRatioRingChartOption &
  IApmTimeSeriesOption;

export interface IPanelModel {
  id: number | string;
  // 图表位置
  gridPos?: IGridPos;
  // 图表类型 如 line-chart bar-chart status-chart group
  type: string;
  // 图表title
  title: string;
  // 图表subTitle
  subTitle?: string;
  // 是否折叠
  collapsed?: boolean;
  // 图表数据源
  targets: IDataQuery[];
  // 图表配置
  options?: PanelOption;
  // 图表dashboard id
  dashboardId?: number | string;
  // 组内视图列表
  panels?: IPanelModel[];
  // 是否显示
  show?: boolean;
  // 组id
  groupId?: number | string;
  // 是否实时
  instant?: boolean;
  // 数据步长
  collect_interval?: number;
}

export class PanelModel implements IPanelModel {
  // 是否被勾选
  checked?: boolean = false;
  // 是否折叠
  collapsed?: boolean = false;
  collect_interval: number;
  // dashbordId
  dashboardId?: string;
  // 是否正在drag中
  draging = false;
  // 图表位置
  gridPos!: IGridPos;
  // 组id
  groupId?: number | string;
  // 图表id
  id!: number | string;
  // 是否为实时
  instant = false;
  // 图表配置
  options?: PanelOption;
  panels?: PanelModel[];
  // 是否显示
  show?: boolean = true;
  subTitle!: string;
  // 图表数据源
  targets: DataQuery[];
  // 图表title
  title!: string;

  // 图表类型 如 line-chart bar-chart status-chart group
  type!: string;

  constructor(model: IPanelModel & { panelIds?: (number | string)[] }) {
    this.id = model.id;
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
    return ['graph'].includes(this.type);
  }
  public updateChecked(v: boolean) {
    this.checked = v;
  }
  public updateCollapsed(v: boolean) {
    this.collapsed = v;
    this.panels?.length && this.panels.forEach(item => item.updateShow(v));
  }
  public updateDraging(v: boolean) {
    this.draging = v;
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
  public updateShow(v: boolean) {
    this.show = v;
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
}

export interface IDashbordConfig {
  id: number | string;
  panels: IPanelModel[];
}

export type DashboardColumnType = 'custom' | number;
export interface IAddition {
  key: string;
  value: string[];
  method: string;
  condition?: 'and' | 'or';
}

export interface ILogUrlParams {
  bizId: string;
  time_range?: 'customized'; // 带了时间start_time end_time必填
  keyword: string; // 搜索关键字
  addition: IAddition[]; // 搜索条件 即监控的汇聚条件
  start_time?: string; // 起始时间
  end_time?: string; // 终止时间
}
export interface IViewOptions {
  // 对比数据 如 目标对比 集成等
  compares?: Record<'targets', any>;
  // filter 数据 视图最侧栏定位数据使用
  filters?: Record<string, any>;
  // 变量数据 视图变量
  variables?: Record<string, any>;
  // 汇聚方法
  method?: string;
  // 汇聚周期
  interval?: 'auto' | number | string;
  // 数据组 维度 指标组
  groups?: string[];
  // 特殊数据组  主机监控使用 主机ip 云区域id
  group_by?: string[];
  // 当前选中的目标 主机和容器监控特殊使用
  current_target?: Record<string, any>;
  // 对比目标 主机监控特殊使用
  compare_targets?: Record<string, any>[];
  bk_target_cloud_id?: string;
  bk_target_ip?: string;
  // 用于动态判断panel是否显示
  matchFields?: Record<string, any>;
  // 策略id 用于hostIntelligenAnomalyRange接口
  strategy_id?: number | string;
}
