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

import { ref, shallowRef } from 'vue';

import { deepClone } from 'monitor-common/utils';
import { defineStore } from 'pinia';

import transformTraceTree from '../../components/trace-view/model/transform-trace-data';
import { formatDuration } from '../../components/trace-view/utils/date';
import { handleToggleCollapse, handleTraceTreeGroup } from '../../components/trace-view/utils/group';
import { mergeTraceTree, transformTraceInfo } from '../../components/trace-view/utils/info';
import {
  interfaceStatisticsSetting,
  serviceStatisticsSetting,
  spanListSetting,
  traceListSetting,
} from '../../pages/main/inquire-content/table-settings';
import { DEFAULT_TRACE_DATA } from '../constant';

import type { Span, TraceData } from '../../components/trace-view/typings';
import type {
  DirectionType,
  IServiceSpanListItem,
  ISpanDetail,
  ISpanListItem,
  ITraceData,
  ITraceListItem,
  ITraceTree,
  OriginCrossAppSpanMap,
} from '../../typings';

export type IInterfaceStatisticsType = {
  selectedInterfaceStatisticsType?: [];
  selectedInterfaceTypeInInterfaceStatistics?: [];
  selectedSourceTypeInInterfaceStatistics?: [];
};
export type IServiceStatisticsType = { contain: any[]; interfaceType: any[] };

export type ListType = 'interfaceStatistics' | 'serviceStatistics' | 'span' | 'trace' | string;

export type TraceListMode = 'origin' | 'pre_calculation';

export const useTraceStore = defineStore('trace', () => {
  const loading = ref(false);
  const traceLoading = ref(false); // trace 详情loading
  const showTraceDetail = ref(false); // 展示 trace 详情
  const traceData = shallowRef<ITraceData>(DEFAULT_TRACE_DATA);
  const traceList = shallowRef<ITraceListItem[]>([]);
  const spanList = shallowRef<ISpanListItem[]>([]);
  const interfaceStatisticsList = shallowRef([]);
  const serviceStatisticsList = shallowRef([]);
  // const interfaceStatisticsType = ref<IInterfaceStatisticsType>({});
  const interfaceStatisticsType = ref([]);
  const serviceStatisticsType = ref<IServiceStatisticsType>({ contain: [], interfaceType: [] });
  const filterTraceList = shallowRef<ITraceListItem[]>([]); // 通过左侧查询结果统计过滤的列表 为空则表示未过滤
  const filterSpanList = shallowRef<ISpanListItem[]>([]); // 作用如上
  const totalCount = ref(0);
  const traceTree = shallowRef<ITraceTree>({ spans: [] }); // 当前展示的 trace 数据
  const spanGroupTree = shallowRef<Span[]>([]); // 基于 traceTree 折叠展示的 span tree
  const originTraceTree = shallowRef<ITraceTree>({ spans: [] }); // 转换格式之前的 trace 数据 用于跨级应用
  const originCrossAppSpanMaps = shallowRef<OriginCrossAppSpanMap>({}); // 跨应用场景下 条件搜索跨应用名称的映射
  const ellipsisDirection = ref<DirectionType>('ltr'); // 省略号头部/尾部显示
  const traceViewFilters = ref<string[]>(['duration']); // 工具栏过滤 span 条件
  // Trace / Span list 切换标志
  const listType = ref<ListType>('trace');
  const traceType = ref([]);
  const isTraceLoading = ref(false);
  const spanType = ref([]);
  const selectedTraceViewFilterTab = ref('');
  const traceListMode = ref<TraceListMode>('pre_calculation');
  const compareTraceOriginalData = ref([]); // 对比 baseline 原始数据 用于查看 span详情原始数据
  const tableSettings = ref({
    trace: traceListSetting,
    span: spanListSetting,
    interfaceStatistics: interfaceStatisticsSetting,
    serviceStatistics: serviceStatisticsSetting,
  });
  const serviceSpanList = shallowRef<IServiceSpanListItem[]>([]);

  /** 更新页面 loading */
  function setPageLoading(v: boolean) {
    loading.value = v;
  }
  /** 更新 trace detail loading */
  function setTraceLoaidng(v: boolean) {
    traceLoading.value = v;
  }
  /** 展开/收起 trace 弹窗 */
  function setTraceDetail(isShow: boolean) {
    showTraceDetail.value = isShow;
  }
  /** 更新当前展示的 trace 数据 */
  function setTraceData(data: ITraceData) {
    const { trace_tree: tree, ...rest } = data;

    const { nodes, edges } = rest?.streamline_service_topo || { nodes: [], edges: [] };
    const rootNode = nodes.find(item => item.is_root);
    const firstEdge = edges.find(item => item.source === rootNode?.key);
    setServiceSpanList(firstEdge?.spans || []);

    if (data.appName) {
      originCrossAppSpanMaps.value[data.appName] = rest.original_data;
    } else {
      originCrossAppSpanMaps.value = {};
    }
    traceData.value = {
      ...rest,
      span_classify: rest.span_classify?.length
        ? rest.span_classify.map(val => ({
            ...val,
            app_name: data.appName,
          }))
        : [],
    };
    originTraceTree.value = { ...(tree as ITraceTree) };
    traceTree.value = tree
      ? (transformTraceTree(deepClone(tree as TraceData & { spans: Span[] })) as ITraceTree)
      : { spans: [] };
    spanGroupTree.value = handleTraceTreeGroup(traceTree.value?.spans);
  }
  /** 更新当前拉取 trace 的总数 */
  function setTraceTotalCount(count: number) {
    totalCount.value = count;
  }
  /** 更新 trace 列表 */
  function setTraceList(data: ITraceListItem[]) {
    traceList.value =
      data?.map(item => ({
        ...item,
        traceID: item.trace_id,
        // 修改结构
        // duration: formatDuration(item.trace_info.trace_duration, ' '),
        duration: formatDuration(item.trace_duration, ' '),
        // 修改结构
        // time: `${formatDate(item.trace_info.product_time)} ${formatTime(item.trace_info.product_time)}`,
        time: item?.time,
        // 修改结构
        // entryService: item.trace_info.root_service,
        entryService: item.root_service,
        // 修改结构、key
        // entryEndpoint: item.trace_info.root_endpoint,
        entryEndpoint: item.root_span_name,
        // 修改结构、key
        // statusCode: item.trace_info.status_code?.value,
        statusCode: item.root_status_code?.value,
        // 修改结构、key（TODO：缺少了 key）
        // status: item.trace_info.status_code?.type,
        status: item.root_status_code?.type,
        // 修改结构、key
        // type: item.trace_info.category
        type: item.root_category,
      })) || [];
  }

  function setTraceType(v) {
    traceType.value = v;
  }

  /** 四个表格的 loading 状态，使用骨架屏 */
  function setTraceLoading(v) {
    isTraceLoading.value = v;
  }

  function setServiceSpanList(spanList: IServiceSpanListItem[]) {
    serviceSpanList.value = spanList;
  }

  /** 更新 trace 过滤列表 */
  function setFilterTraceList(data: ITraceListItem[]) {
    filterTraceList.value = data;
  }
  function setFilterSpanList(data: ISpanListItem[]) {
    filterSpanList.value = data;
  }

  function setSpanList(data: ISpanListItem[]) {
    spanList.value = data;
  }

  function setSpanType(v) {
    spanType.value = v;
  }

  function setInterfaceStatisticsList(v) {
    interfaceStatisticsList.value = v;
  }

  function setServiceStatisticsList(v) {
    serviceStatisticsList.value = v;
  }

  /** 跨应用信息设置 */
  function setAcrossAppTraceInfo(data: ITraceData) {
    const { trace_tree: tree, ...rest } = data;
    const newTree = mergeTraceTree(originTraceTree.value, tree as ITraceTree);
    const {
      original_data: originalData,
      trace_info: { app_name: appName = 'd' },
    } = rest;

    // 生成跨应用span 原始数据的 appName 映射
    if (originCrossAppSpanMaps.value[appName]) {
      originCrossAppSpanMaps.value[appName].push(...originalData);
    } else {
      originCrossAppSpanMaps.value[appName] = originalData;
    }

    /** 合并原始 trace_tree */
    originTraceTree.value = { ...(newTree as ITraceTree) };
    /** 合并 trace_tree */
    traceTree.value = transformTraceTree(deepClone(newTree as TraceData & { spans: Span[] })) as ITraceTree;
    spanGroupTree.value = handleTraceTreeGroup(traceTree.value?.spans);
    /** 合并处理 trace_info 和 span_classify */
    traceData.value = transformTraceInfo(rest, traceData.value) as ITraceData;
  }

  function updateEllipsisDirection(val: DirectionType) {
    ellipsisDirection.value = val;
  }

  // 切换 Trace 或 Span 列表时，需要重置为默认状态。
  function resetTable() {
    loading.value = false;
    traceLoading.value = false;
    showTraceDetail.value = false;
    totalCount.value = 0;
    traceList.value = [];
    spanList.value = [];
    interfaceStatisticsList.value = [];
    serviceStatisticsList.value = [];
    traceType.value.length = 0;
    spanType.value.length = 0;
    interfaceStatisticsType.value.length = 0;
    serviceStatisticsType.value.contain.length = 0;
    serviceStatisticsType.value.interfaceType.length = 0;
  }

  function updateTraceViewFilters(val: string[]) {
    traceViewFilters.value = val;
    setSpanKindFilters();
  }

  // 按照过滤条件过滤span
  function setSpanKindFilters() {
    // const spans = traceTree.value.spans.filter((span: Span) => {
    //   const curkind: number[] = [0, 2, 3]; // 默认都显示未定义、同步调用 其中 0-未定义 2-同步被调 3-同步主调
    //   traceViewFilters.value.forEach((val) => {
    //     switch (val) {
    //       case 'async':
    //         curkind.push(...[4, 5]); // 4-异步主调 5-异步被调
    //         break;
    //       case 'internal':
    //         curkind.push(1);
    //         break;
    //       case 'infer':
    //         curkind.push(6);
    //         break;
    //       default:
    //         break;
    //     }
    //   });
    //   return curkind.includes(span.kind as number);
    // });
    // traceTree.value = { ...traceTree.value, spans };
  }

  function setListType(v: ListType) {
    listType.value = v;
  }

  // TODO：这里是东凑西凑出来的数据，代码并不严谨，后期需要调整。
  function setSpanDetailData(v: ISpanDetail) {
    traceData.value.original_data = [];
    traceData.value.original_data.push(v.origin_data);
    traceData.value.appName = v?.trace_tree?.spans?.[0]?.app_name;
  }

  function updateTraceViewFilterTab(v) {
    selectedTraceViewFilterTab.value = v;
  }

  function setInterfaceStatisticsType(v: string[]) {
    interfaceStatisticsType.value = v;
  }

  function setServiceStatisticsType(v: IServiceStatisticsType) {
    serviceStatisticsType.value = v;
  }

  function setTraceListMode(v: TraceListMode) {
    traceListMode.value = v;
  }

  /** 切换瀑布图节点折叠状态 */
  function updateSpanGroupCollapse(groupID, status) {
    traceTree.value.spans = handleToggleCollapse(traceTree.value.spans, groupID, status);
    spanGroupTree.value = handleTraceTreeGroup(traceTree.value?.spans);
  }

  function updateCompareTraceOriginalData(list) {
    compareTraceOriginalData.value = list;
  }

  function updateTableCheckedSettings(key: ListType, checked: string[]) {
    tableSettings[key].checked = checked;
  }

  /** Trace、Span 列表表头设置固定记住用户的选择 */
  function setTableSetting() {
    const traceCheckedSettings = window.localStorage.getItem('traceCheckedSettings');
    const spanCheckedSettings = window.localStorage.getItem('spanCheckedSettings');
    if (traceCheckedSettings) {
      tableSettings.value.trace.checked = JSON.parse(traceCheckedSettings);
    }
    if (spanCheckedSettings) {
      tableSettings.value.span.checked = JSON.parse(spanCheckedSettings);
    }
  }
  setTableSetting();

  return {
    loading,
    traceLoading,
    showTraceDetail,
    traceData,
    traceList,
    filterTraceList,
    totalCount,
    traceTree,
    originTraceTree,
    originCrossAppSpanMaps,
    serviceSpanList,
    setServiceSpanList,
    setPageLoading,
    setTraceLoaidng,
    setTraceDetail,
    setTraceData,
    setTraceTotalCount,
    setTraceList,
    setFilterTraceList,
    setAcrossAppTraceInfo,
    ellipsisDirection,
    updateEllipsisDirection,
    resetTable,
    traceViewFilters,
    updateTraceViewFilters,
    setSpanKindFilters,
    listType,
    setListType,
    spanList,
    setSpanList,
    spanType,
    setSpanType,
    filterSpanList,
    setFilterSpanList,
    setSpanDetailData,
    selectedTraceViewFilterTab,
    updateTraceViewFilterTab,
    setInterfaceStatisticsList,
    interfaceStatisticsList,
    serviceStatisticsList,
    setServiceStatisticsList,
    interfaceStatisticsType,
    setInterfaceStatisticsType,
    serviceStatisticsType,
    setServiceStatisticsType,
    traceListMode,
    setTraceListMode,
    spanGroupTree,
    updateSpanGroupCollapse,
    traceType,
    setTraceType,
    compareTraceOriginalData,
    updateCompareTraceOriginalData,
    tableSettings,
    updateTableCheckedSettings,
    isTraceLoading,
    setTraceLoading,
  };
});
