/* eslint-disable @typescript-eslint/naming-convention */
import { random } from 'monitor-common/utils/utils';

import { type IMetricDetail, MetricDetail } from '../../strategy-config/strategy-config-set-new/typings';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { TimeRangeType } from '../../../components/time-range/time-range';
import type { PanelHeaderType, PanelToolsType } from '../../monitor-k8s/typings';
import type { IFunctionItem } from '../../strategy-config/strategy-config-set-new/monitor-data/function-menu';
import type { IFunctionsValue } from '../../strategy-config/strategy-config-set-new/monitor-data/function-select';
import type { IIndexListItem } from '../index-list/index-list';
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
import type { TranslateResult } from 'vue-i18n';

export interface whereItem {
  condition: 'and' | 'or';
  key: string;
  method: string;
  value: string[];
}

export interface IOption {
  id: number | string;
  name: string | TranslateResult;
}
// 收藏列表
export declare namespace IFavList {
  interface favGroupList {
    name: string;
    id: number;
    editable: boolean;
    favorites: favList[];
  }
  interface favList {
    config: any;
    create_user: string;
    group_id: number | object;
    id: number;
    name: string;
    update_time: string;
    update_user: string;
  }
  interface groupList {
    group_name: string;
    group_id: number;
  }
  interface IProps {
    value: favList[];
    checkedValue: favList;
  }
  interface IEvent {
    deleteFav?: number;
    selectFav?: any;
  }
}

// 指标检索类型
export declare namespace IDataRetrieval {
  type tabId = 'event' | 'log' | 'monitor'; // 数据检索 | 日志检索 | 事件检索
  interface ITabList {
    id: tabId;
    name: string | TranslateResult;
  }

  type IOption = 'copy' | 'delete' | 'enable' | 'source'; // 对应的操作：源码、开启、复制、删除

  type ILocalValue = DataRetrievalQueryItem | IExpressionItem;

  interface IExpressionItem {
    key: string;
    isMetric: boolean;
    enable: boolean;
    alias?: string; // 别名
    value: string;
    functions: IFunctionsValue[];
    errMsg?: string;
  }
  interface queryConfigsParams {
    metric: string;
    method: string;
    alias: string;
    interval: number;
    table: string;
    data_label?: string;
    data_source_label: string;
    data_type_label: string;
    group_by: string[];
    where: whereItem[];
    functions: IFunctionItem[];
    index_set_id?: number | string;
    filter_dict?: Record<string, any>;
  }
  // 目前跳转检索的两种数据结构分类分别以 仪表盘grafana图表 | 主机详情图表 为代表，但不仅包含其一
  type fromRouteNameType = 'grafana' | 'performance-detail';

  type TargetType = 'DYNAMIC_GROUP' | 'INSTANCE' | 'SERVICE_TEMPLATE' | 'SET_TEMPLATE' | 'TOPO';
  interface ITarget {
    show: boolean;
    objectType: 'HOST';
    targetType: TargetType;
    value: any[];
    desc: string;
    mainlineObjectTopoList: any[];
  }
  type promEventType = 'blur' | 'enter'; // enter键触发 失焦触发

  // 周期单位对应的换算
  // 周期单位对应的换算
  interface IntervalUnitMap {
    s: 1;
    m: 30;
    h: 3600;
    d: 86400;
    M: 2592000;
    y: 31104000;
  }
}

// 查询项/表达式 类型
export declare namespace IDataRetrievalItem {
  type IValue = DataRetrievalQueryItem | IDataRetrieval.IExpressionItem;
  interface IAggMethodList {
    name: string;
    id: string;
  }
  interface IProps {
    value: IValue;
    scenarioList: any[];
    index: number;
    compareValue: IDataRetrievalView.ICompareValue;
  }
  interface IWhere {
    key: string;
    method: string;
    value: string[];
    condition: string;
  }
  interface onChange {
    value: DataRetrievalQueryItem;
    type: emitType;
  }

  // where: 条件值更新 where-clear-value: 清除条件值操作
  type emitType = 'where' | 'where-clear-value';

  interface IEvent {
    onChange?: onChange;
    onShowMetricSelector?: () => void;
    onClearMetric?: () => void;
    onLoadingChange?: boolean;
  }
}

// 视图部分类型
export declare namespace IDataRetrievalView {
  type chartType = 0 | 1 | 2 | 3 | 4 | number;

  type compareType = 'metric' | 'none' | 'target' | 'time';
  type typeOfView = 'event' | 'monitor' | 'trace';
  interface ICompare {
    type: compareType;
    value?: boolean | string | string[];
  }
  interface ITools {
    refleshInterval: number;
    timeRange: TimeRangeType;
    timezone: string;
  }
  interface ICompareValue {
    compare: ICompare;
    tools: ITools;
  }
  interface ICompareComChange {
    type: 'compare' | 'interval' | 'timeRange';
    compare: ICompare;
    tools: ITools;
  }
  interface ISearchTipsObj {
    show: boolean;
    time: number;
    showSplit: boolean;
    value: boolean;
    showAddStrategy: boolean;
  }
  interface IEmptyView {
    showType: typeOfView;
    queryLoading: boolean;
    eventMetricParams?: object;
    onClickEventBtn?: any;
    emptyStatus: EmptyStatusType;
  }
  interface IEvent {
    onCompareChange: ICompareValue;
    onShowLeft: boolean;
    onDeleteFav: number;
    onSplitChange: boolean;
    onSelectFav: IDataRetrieval.ILocalValue[];
    onAddStrategy: () => void;
    onEventIntervalChange: EventRetrievalViewType.intervalType;
    onTimeRangeChangeEvent: EventRetrievalViewType.IEvent['onTimeRangeChange'];
    onAddEventStrategy: IFilterCondition.VarParams;
    onCompareValueChange: PanelToolsType.Compare;
    onTimeRangeChange: PanelHeaderType.TimeRangeValue;
    onDrillKeywordsSearch: string;
  }
  interface IProps {
    compareValue: ICompareValue;
    favoritesList?: IFavList.favList[];
    favCheckedValue?: IFavList.favList;
    leftShow: boolean;
    queryResult: any[];
    queryTimeRange: number;
    canAddStrategy: boolean;
    retrievalType: IDataRetrieval.tabId;
    refleshNumber?: number;
    queryLoading?: boolean;
    // eventFieldList: FieldValue[];
    eventMetricParams: IFilterCondition.VarParams;
    eventChartInterval: EventRetrievalViewType.intervalType;
    eventCount?: number;
    eventChartTitle?: string;
    indexList?: IIndexListItem[];
    needCompare?: boolean;
    emptyStatus: EmptyStatusType;
  }
  interface IOptionItem {
    id?: string;
    name: string | TranslateResult;
    value?: number | string;
  }
}

interface IDataRetrievalQueryItem {
  enable?: boolean;
  sourceCode?: string;
  sourceCodeCache?: string;
  showSource?: boolean;
  key?: string;
  sourceCodeIsNullMetric?: boolean;
  consistency?: boolean;
  filter_dict?: Record<string, any>;
  errMsg?: string;
}

// 查询项数据结构
export class DataRetrievalQueryItem extends MetricDetail {
  agg_interval: any = 'auto'; // 源码
  consistency = true; // 源码缓存
  enable = true; // 记录源码转换出现空指标
  errMsg = ''; // 展示源码
  filter_dict: Record<string, any> = {}; // 源码报错
  isMetric = true; // ui与source一致性标记
  key = random(8); // 是否生效
  loading = false; // 初始化指标数据标记
  showSource = false; // 唯一key值
  sourceCode = '';
  sourceCodeCache = ''; // 将切换ui
  sourceCodeError = false;
  sourceCodeIsNullMetric = false;
  switchToUI = false; /* 转换为promql时的报错信息 */
  constructor(data?: IMetricDetail & IDataRetrievalQueryItem) {
    super(data);
    if (!data) return;
    this.key = data.key || random(8);
    this.enable = data.enable ?? true;
    this.showSource = data.showSource ?? false;
    this.sourceCode = data.sourceCode || '';
    this.sourceCodeCache = data.sourceCodeCache || '';
    this.sourceCodeIsNullMetric = data.sourceCodeIsNullMetric ?? false;
    this.consistency = data.consistency ?? true;
    this.filter_dict = data.filter_dict ?? {};
    this.agg_interval = data.agg_interval ?? 'auto';
    this.errMsg = '';
  }
}

interface IDataRetrievalPromqlItem {
  key: string;
  code: string;
  enable: boolean;
  alias: string;
  step: number | string;
  filter_dict?: Record<string, string>;
}
export class DataRetrievalPromqlItem {
  alias = '';
  code = '';
  enable = true;
  errMsg = '';
  filter_dict?: Record<string, string> = undefined;
  key = random(8);
  step = 'auto';
  constructor(data?: IDataRetrievalPromqlItem) {
    if (!data) return;
    this.key = data.key || random(8);
    this.code = data.code || '';
    this.enable = data.enable || true;
    this.alias = data.alias || 'a';
    this.step = (data.step as any) || 'auto';
    this.filter_dict = data?.filter_dict;
    this.errMsg = '';
  }
}

// 事件检索组件
export declare namespace IEventRetrieval {
  interface IEvent {
    onEventTypeChange: EventTypeChange;
    onWhereChange: IFilterCondition.localValue[];
    onQuery: IFilterCondition.VarParams;
    onAddFav: HandleBtnType.IEvent['onAddFav'];
    onCountChange: number;
    onChartTitleChange: string;
    onAutoQueryChange?: (v: boolean) => void;
    onClearDrillKeywords: () => void;
    onEmptyStatusChange: (val: EmptyStatusType) => void;
    onChange?: (value: ILocalValue) => void;
  }
  interface IProps {
    where: IFilterCondition.localValue[];
    autoQuery: boolean;
    isFavoriteUpdate: boolean;
    drillKeywords?: string;
    compareValue: IDataRetrievalView.ICompareValue;
    queryConfig: IFilterCondition.VarParams;
    eventInterval: EventRetrievalViewType.intervalType;
    favCheckedValue: IFavList.favList;
    chartTimeRange: EventRetrievalViewType.IEvent['onTimeRangeChange'];
  }

  type IEventTypeList = IOption;

  interface ILocalValue {
    eventType: 'bk_monitor_log' | 'custom_event';
    result_table_id: string;
    query_string: string;
    where: IFilterCondition.localValue[];
  }

  interface ITipsContentListItem {
    label: string | TranslateResult;
    value: string[];
  }

  interface EventTypeChange {
    data_source_label: 'bk_monitor' | 'custom';
    data_type_label: 'event' | 'log';
  }

  interface SourceAndTypeLabelMap {
    custom_event: {
      data_source_label: 'custom';
      data_type_label: 'event';
    };
    bk_monitor_log: {
      data_source_label: 'bk_monitor';
      data_type_label: 'log';
    };
  }
}

export declare namespace IFilterCondition {
  interface IProps {
    value: localValue[];
    groupBy: IGroupBy[];
    varParams: VarParams;
  }
  interface IEvent {
    onChange: localValue[];
  }
  type GroupbyType = 'number' | 'string';
  type IGroupBy = IOption & {
    type: GroupbyType;
  };
  interface VarParams {
    data_source_label: string;
    data_type_label: string;
    metric_field: string;
    result_table_id: string;
    where?: any[];
    query_string?: string;
    group_by?: string[];
    filter_dict?: { [propName: string]: string[] };
    method?: string;
    metric_field_cache?: string; // 新增策略的metric_field
  }
  interface localValue {
    key: number | string;
    method: string;
    value: number[] | string[];
    condition: 'and' | 'or';
  }
  type AddType = 'add' | 'edit';

  interface IConditonOption extends IOption {
    placeholder?: string;
  }
}

export declare namespace FieldFilteringType {
  interface IProps {
    value: FieldValue[];
    total: number;
  }
  interface IEvent {
    onAddCondition: IFilterCondition.localValue;
    onChange: FieldValue[];
  }
  enum FieldDataType {
    date = 'date',
    number = 'number',
    string = 'string',
    text = 'text',
  }
  interface IFieldValue {
    id: string;
    count: number;
  }

  interface IFieldTypeValue {
    aggVal: string;
    fieldType: string;
  }
}

export interface IFieldValueType {
  field: string;
  type?: string;
  total: number;
  dimensions: IFieldDimensions[];
}
export interface IFieldDimensions {
  value: string;
  number: number;
  percentage: number;
}
export interface FieldValueDimension {
  id: string;
  percent: number;
  count?: number;
}
export class FieldValue {
  checked = true;
  dimensions: FieldValueDimension[] = []; // 数据类型
  field = ''; // 字段
  fieldName = ''; // 字段名
  key = random(8); // 值
  showMore = false; // 是否选中
  total = 0;
  type = 'string'; // 是否展开更多的条件

  constructor(data: IFieldValueType) {
    if (!data) return;
    this.type = data.type ?? 'string';
    this.field = data.field ?? '';
    this.fieldName = data.field ?? '';
    this.total = data.total ?? 0;
    this.dimensions = data.dimensions?.map(item => ({
      id: item.value,
      count: item.number,
      percent: item.percentage,
    }));
  }
}

export declare namespace FieldListType {
  interface IProp {
    value: FieldValue[];
    total: number;
  }
  interface IEvent {
    onAddCondition: IFilterCondition.localValue;
    onCheckedChange: { index: number; checked: boolean; field: string };
  }
  type AddConditionType = 'AND' | 'NOT';
}

export declare namespace EventRetrievalViewType {
  type intervalType = 'auto' | number;
  interface IProps {
    // fieldList: FieldValue[];
    compareValue: IDataRetrievalView.ICompareValue;
    eventMetricParams: IFilterCondition.VarParams;
    chartInterval: intervalType;
    intervalList?: IOption[];
    showTip?: boolean;
    extCls?: string;
    queryLoading?: boolean;
    // count?: number;
    chartTitle?: string;
    chartOption?: any;
    toolChecked?: string[];
    moreChecked?: string[];
    emptyStatus: EmptyStatusType;
  }
  interface IEvent {
    onIntervalChange: intervalType;
    onAddStrategy?: IFilterCondition.VarParams;
    onTimeRangeChange: [number, number];
    onExportDataRetrieval?: () => void;
  }
  interface IDrill {
    data: object;
    onDrillSearch: (v: string) => string;
  }
  interface ITextSegment {
    content: string;
    fieldType: string;
    onMenuClick: object;
  }
}

export declare namespace HandleBtnType {
  interface IProps {
    canQuery: boolean;
    autoQuery: boolean;
    isFavoriteUpdate?: boolean;
    queryLoading?: boolean;
    canFav?: boolean;
    favCheckedValue?: IFavList.favList;
  }
  interface IEvent {
    onQuery: () => void;
    onClear: () => void;
    onQueryTypeChange?: boolean;
    onAddFav: boolean;
  }
}

export declare namespace FavoriteIndexType {
  interface IProps {
    favoriteSearchType: string;
    favoritesList: IFavList.favList[];
    favoriteLoading: boolean;
    isShowFavorite: boolean;
    favCheckedValue: IFavList.favList;
  }
  interface IEvent {
    onOperateChange: {
      operate: string;
      value: any;
    };
    onGetFavoritesList();
  }
  interface IContainerProps {
    dataList?: IFavList.favGroupList[];
    collectItem?: IFavList.favGroupList;
    groupList: IFavList.groupList[];
    favCheckedValue: IFavList.favList;
    emptyStatusType: EmptyStatusType;
    isSearchFilter: boolean;
    collectLoading?: boolean;
    onChange?: object;
    onHandleOperation?(type: EmptyStatusOperationType);
  }
  interface IDropProps {
    dropType?: string;
    groupList: IFavList.groupList[];
    isHoverTitle?: boolean;
    groupName?: string;
    data: IFavList.favGroupList | IFavList.favList;
  }
}

export type TEditMode = 'PromQL' | 'UI';
