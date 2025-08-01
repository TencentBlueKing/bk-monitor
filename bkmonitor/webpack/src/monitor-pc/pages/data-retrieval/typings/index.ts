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

export interface IOption {
  id: number | string;
  name: string | TranslateResult;
}

export interface whereItem {
  condition: 'and' | 'or';
  key: string;
  method: string;
  value: string[];
}
// 收藏列表
export declare namespace IFavList {
  interface favGroupList {
    editable: boolean;
    favorites: favList[];
    id: number;
    name: string;
  }
  interface favList {
    config: any;
    create_user: string;
    disabled?: boolean;
    group_id: number | object;
    groupName?: string;
    id: number;
    name: string;
    update_time: string;
    update_user: string;
  }
  interface favTableList extends favList {
    editGroup?: boolean;
    editName?: boolean;
    groupName?: string;
  }
  interface groupList {
    group_id: number;
    group_name: string;
  }
  interface IEvent {
    deleteFav?: number;
    selectFav?: any;
  }

  interface IProps {
    checkedValue: favList;
    value: favList[];
  }
}

// 指标检索类型
export declare namespace IDataRetrieval {
  // 目前跳转检索的两种数据结构分类分别以 仪表盘grafana图表 | 主机详情图表 为代表，但不仅包含其一
  type fromRouteNameType = 'grafana' | 'performance-detail';
  interface IExpressionItem {
    alias?: string; // 别名
    enable: boolean;
    errMsg?: string;
    functions: IFunctionsValue[];
    isMetric: boolean;
    key: string;
    value: string;
  }

  type ILocalValue = DataRetrievalQueryItem | IExpressionItem;

  // 周期单位对应的换算
  // 周期单位对应的换算
  interface IntervalUnitMap {
    d: 86400;
    h: 3600;
    m: 30;
    M: 2592000;
    s: 1;
    y: 31104000;
  }

  type IOption = 'copy' | 'delete' | 'enable' | 'source'; // 对应的操作：源码、开启、复制、删除
  interface ITabList {
    id: tabId;
    name: string | TranslateResult;
  }
  interface ITarget {
    desc: string;
    mainlineObjectTopoList: any[];
    objectType: 'HOST';
    show: boolean;
    targetType: TargetType;
    value: any[];
  }

  type promEventType = 'blur' | 'enter'; // enter键触发 失焦触发
  interface queryConfigsParams {
    alias: string;
    data_label?: string;
    data_source_label: string;
    data_type_label: string;
    filter_dict?: Record<string, any>;
    functions: IFunctionItem[];
    group_by: string[];
    index_set_id?: number | string;
    interval: number;
    method: string;
    metric: string;
    table: string;
    where: whereItem[];
  }
  type tabId = 'event' | 'log' | 'monitor'; // 数据检索 | 日志检索 | 事件检索

  type TargetType = 'DYNAMIC_GROUP' | 'INSTANCE' | 'SERVICE_TEMPLATE' | 'SET_TEMPLATE' | 'TOPO';
}

// 查询项/表达式 类型
export declare namespace IDataRetrievalItem {
  // where: 条件值更新 where-clear-value: 清除条件值操作
  type emitType = 'where' | 'where-clear-value';
  interface IAggMethodList {
    id: string;
    name: string;
  }
  interface IEvent {
    onChange?: onChange;
    onLoadingChange?: boolean;
    onClearMetric?: () => void;
    onShowMetricSelector?: () => void;
  }
  interface IProps {
    compareValue: IDataRetrievalView.ICompareValue;
    index: number;
    scenarioList: any[];
    value: IValue;
  }
  type IValue = DataRetrievalQueryItem | IDataRetrieval.IExpressionItem;

  interface IWhere {
    condition: string;
    key: string;
    method: string;
    value: string[];
  }

  interface onChange {
    type: emitType;
    value: DataRetrievalQueryItem;
  }
}

// 视图部分类型
export declare namespace IDataRetrievalView {
  type chartType = 0 | 1 | 2 | 3 | 4 | number;

  type compareType = 'metric' | 'none' | 'target' | 'time';
  interface ICompare {
    type: compareType;
    value?: boolean | string | string[];
  }
  interface ICompareComChange {
    compare: ICompare;
    tools: ITools;
    type: 'compare' | 'interval' | 'timeRange';
  }
  interface ICompareValue {
    compare: ICompare;
    tools: ITools;
  }
  interface IEmptyView {
    emptyStatus: EmptyStatusType;
    eventMetricParams?: object;
    onClickEventBtn?: any;
    queryLoading: boolean;
    showType: typeOfView;
  }
  interface IEvent {
    onAddEventStrategy: IFilterCondition.VarParams;
    onCompareChange: ICompareValue;
    onCompareValueChange: PanelToolsType.Compare;
    onDeleteFav: number;
    onDrillKeywordsSearch: string;
    onEventIntervalChange: EventRetrievalViewType.intervalType;
    onSelectFav: IDataRetrieval.ILocalValue[];
    onShowLeft: boolean;
    onSplitChange: boolean;
    onTimeRangeChange: PanelHeaderType.TimeRangeValue;
    onTimeRangeChangeEvent: EventRetrievalViewType.IEvent['onTimeRangeChange'];
    onAddStrategy: () => void;
  }
  interface IOptionItem {
    id?: string;
    name: string | TranslateResult;
    value?: number | string;
  }
  interface IProps {
    canAddStrategy: boolean;
    compareValue: ICompareValue;
    emptyStatus: EmptyStatusType;
    eventChartInterval: EventRetrievalViewType.intervalType;
    eventChartTitle?: string;
    eventCount?: number;
    // eventFieldList: FieldValue[];
    eventMetricParams: IFilterCondition.VarParams;
    favCheckedValue?: IFavList.favList;
    favoritesList?: IFavList.favList[];
    indexList?: IIndexListItem[];
    leftShow: boolean;
    needCompare?: boolean;
    queryLoading?: boolean;
    queryResult: any[];
    queryTimeRange: number;
    refleshNumber?: number;
    retrievalType: IDataRetrieval.tabId;
  }
  interface ISearchTipsObj {
    show: boolean;
    showAddStrategy: boolean;
    showSplit: boolean;
    time: number;
    value: boolean;
  }
  interface ITools {
    refreshInterval: number;
    timeRange: TimeRangeType;
    timezone: string;
  }
  type typeOfView = 'event' | 'monitor' | 'trace';
}

interface IDataRetrievalPromqlItem {
  alias: string;
  code: string;
  enable: boolean;
  filter_dict?: Record<string, string>;
  key: string;
  step: number | string;
}

interface IDataRetrievalQueryItem {
  consistency?: boolean;
  enable?: boolean;
  errMsg?: string;
  filter_dict?: Record<string, any>;
  key?: string;
  showSource?: boolean;
  sourceCode?: string;
  sourceCodeCache?: string;
  sourceCodeIsNullMetric?: boolean;
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
    this.enable = data.enable ?? true;
    this.alias = data.alias || 'a';
    this.step = (data.step as any) || 'auto';
    this.filter_dict = data?.filter_dict;
    this.errMsg = '';
  }
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
  constructor(data?: IDataRetrievalQueryItem & IMetricDetail) {
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

// 事件检索组件
export declare namespace IEventRetrieval {
  interface EventTypeChange {
    data_source_label: 'bk_monitor' | 'custom';
    data_type_label: 'event' | 'log';
  }
  interface IEvent {
    onAddFav: HandleBtnType.IEvent['onAddFav'];
    onChartTitleChange: string;
    onCountChange: number;
    onEventTypeChange: EventTypeChange;
    onQuery: IFilterCondition.VarParams;
    onWhereChange: IFilterCondition.localValue[];
    onAutoQueryChange?: (v: boolean) => void;
    onChange?: (value: ILocalValue) => void;
    onClearDrillKeywords: () => void;
    onEmptyStatusChange: (val: EmptyStatusType) => void;
  }

  type IEventTypeList = IOption;

  interface ILocalValue {
    eventType: 'bk_monitor_log' | 'custom_event';
    query_string: string;
    result_table_id: string;
    where: IFilterCondition.localValue[];
  }

  interface IProps {
    autoQuery: boolean;
    chartTimeRange: EventRetrievalViewType.IEvent['onTimeRangeChange'];
    compareValue: IDataRetrievalView.ICompareValue;
    drillKeywords?: string;
    eventInterval: EventRetrievalViewType.intervalType;
    favCheckedValue: IFavList.favList;
    isFavoriteUpdate: boolean;
    queryConfig: IFilterCondition.VarParams;
    where: IFilterCondition.localValue[];
  }

  interface ITipsContentListItem {
    label: string | TranslateResult;
    value: string[];
  }

  interface SourceAndTypeLabelMap {
    bk_monitor_log: {
      data_source_label: 'bk_monitor';
      data_type_label: 'log';
    };
    custom_event: {
      data_source_label: 'custom';
      data_type_label: 'event';
    };
  }
}

export declare namespace IFilterCondition {
  type AddType = 'add' | 'edit';
  type GroupbyType = 'number' | 'string';
  interface IConditonOption extends IOption {
    placeholder?: string;
  }
  interface IEvent {
    onChange: localValue[];
  }
  type IGroupBy = IOption & {
    type: GroupbyType;
  };
  interface IProps {
    groupBy: IGroupBy[];
    value: localValue[];
    varParams: VarParams;
  }
  interface localValue {
    condition: 'and' | 'or';
    key: number | string;
    method: string;
    value: number[] | string[];
  }

  interface VarParams {
    data_source_label: string;
    data_type_label: string;
    filter_dict?: { [propName: string]: string[] };
    group_by?: string[];
    method?: string;
    metric_field: string;
    metric_field_cache?: string; // 新增策略的metric_field
    query_string?: string;
    result_table_id: string;
    where?: any[];
  }
}

export declare namespace FieldFilteringType {
  enum FieldDataType {
    date = 'date',
    number = 'number',
    string = 'string',
    text = 'text',
  }
  interface IEvent {
    onAddCondition: IFilterCondition.localValue;
    onChange: FieldValue[];
  }
  interface IFieldTypeValue {
    aggVal: string;
    fieldType: string;
  }
  interface IFieldValue {
    count: number;
    id: string;
  }

  interface IProps {
    total: number;
    value: FieldValue[];
  }
}

export interface FieldValueDimension {
  count?: number;
  id: string;
  percent: number;
}
export interface IFieldDimensions {
  number: number;
  percentage: number;
  value: string;
}
export interface IFieldValueType {
  dimensions: IFieldDimensions[];
  field: string;
  total: number;
  type?: string;
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
  type AddConditionType = 'AND' | 'NOT';
  interface IEvent {
    onAddCondition: IFilterCondition.localValue;
    onCheckedChange: { checked: boolean; field: string; index: number };
  }
  interface IProp {
    total: number;
    value: FieldValue[];
  }
}

export declare namespace EventRetrievalViewType {
  interface IDrill {
    data: object;
    onDrillSearch: (v: string) => string;
  }
  interface IEvent {
    onAddStrategy?: IFilterCondition.VarParams;
    onIntervalChange: intervalType;
    onTimeRangeChange: [number, number];
    onExportDataRetrieval?: () => void;
  }
  type intervalType = 'auto' | number;
  interface IProps {
    chartInterval: intervalType;
    chartOption?: any;
    // count?: number;
    chartTitle?: string;
    // fieldList: FieldValue[];
    compareValue: IDataRetrievalView.ICompareValue;
    emptyStatus: EmptyStatusType;
    eventMetricParams: IFilterCondition.VarParams;
    extCls?: string;
    intervalList?: IOption[];
    moreChecked?: string[];
    queryLoading?: boolean;
    showTip?: boolean;
    toolChecked?: string[];
  }
  interface ITextSegment {
    content: string;
    fieldType: string;
    onMenuClick: object;
  }
}

export declare namespace HandleBtnType {
  interface IEvent {
    onAddFav: boolean;
    onQueryTypeChange?: boolean;
    onClear: () => void;
    onQuery: () => void;
  }
  interface IProps {
    autoQuery: boolean;
    canFav?: boolean;
    canQuery: boolean;
    favCheckedValue?: IFavList.favList;
    isFavoriteUpdate?: boolean;
    queryLoading?: boolean;
  }
}

export declare namespace FavoriteIndexType {
  interface IContainerProps {
    collectItem?: IFavList.favGroupList;
    collectLoading?: boolean;
    dataList?: IFavList.favGroupList[];
    emptyStatusType: EmptyStatusType;
    favCheckedValue: IFavList.favList;
    groupList: IFavList.groupList[];
    isSearchFilter: boolean;
    onChange?: object;
    onHandleOperation?(type: EmptyStatusOperationType);
  }
  interface IDropProps {
    data: IFavList.favGroupList | IFavList.favList;
    dropType?: string;
    groupList: IFavList.groupList[];
    groupName?: string;
    isHoverTitle?: boolean;
  }
  interface IEvent {
    onClose(): void;
    onGetFavoritesList();
    onOperateChange: {
      operate: string;
      value: any;
    };
  }
  interface IProps {
    dataId?: string;
    favCheckedValue: IFavList.favList;
    favoriteLoading: boolean;
    favoriteSearchType: string;
    favoritesList: IFavList.favGroupList[];
    isShowFavorite: boolean;
  }
}

export type TEditMode = 'PromQL' | 'UI';
