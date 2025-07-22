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
import {
  computed,
  defineComponent,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  toRefs,
  watch,
} from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { Checkbox, Loading, Message, Popover, ResizeLayout, Tab, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
import { traceDetail } from 'monitor-api/modules/apm_trace';
import { typeTools } from 'monitor-common/utils/utils';

import CompareSelect from '../../../components/compare-select/compare-select';
import MonitorTab from '../../../components/monitor-tab/monitor-tab';
import StatisticsTable, { type IFilterItem } from '../../../components/statistics-table/statistics-table';
import TraceView from '../../../components/trace-view';
import SearchBar from '../../../components/trace-view/search-bar';
import { formatDuration } from '../../../components/trace-view/utils/date';
// import FlameGraph from '../../../plugins/charts/flame-graph/flame-graph';
import FlameGraphV2 from '../../../plugins/charts/flame-graph-v2/flame-graph';
import SequenceGraph from '../../../plugins/charts/sequence-graph/sequence-graph';
import TopoSpanList from '../../../plugins/charts/span-list/topo-span-list';
import {
  DEFAULT_TRACE_DATA,
  QUERY_TRACE_RELATION_APP,
  SOURCE_CATEGORY_EBPF,
  TRACE_INFO_TOOL_FILTERS,
  VIRTUAL_SPAN,
} from '../../../store/constant';
import { useTraceStore } from '../../../store/modules/trace';
import {
  type DirectionType,
  ETopoType,
  type ISpanClassifyItem,
  type ITraceData,
  type ITraceTree,
} from '../../../typings';
import { COMPARE_DIFF_COLOR_LIST, updateTemporaryCompareTrace } from '../../../utils/compare';
import SpanDetails from '../span-details';
import NodeTopo from './node-topo';
import TraceDetailHeader from './trace-detail-header';

import type { Span } from '../../../components/trace-view/typings';

import './trace-detail.scss';

const { TabPanel } = Tab;

const TraceDetailProps = {
  isInTable: {
    type: Boolean,
    default: false,
  },
  appName: {
    type: String,
    default: true,
  },
  traceID: {
    type: String,
    default: '',
  },
};

type IPanelEnum = 'flame' | 'sequence' | 'statistics' | 'timeline' | 'topo';

interface ITabItem {
  id: string; // id
  name: string;
  icon: string;
}

interface IState {
  activePanel: IPanelEnum;
  searchKeywords: string[];
  selectClassifyFilters: { [key: string]: number | string };
  tabPanels: ITabItem[];
  matchedSpanIds: number;
  traceMainStyle: string;
  isClassifyFilter: boolean;
  filterSpanIds: string[];
  filterSpanSubTitle: string;
  isCollapsefilter: boolean;
  isCompareView: boolean;
  compareTraceID: string;
  compareSpanList: Span[];
}

const TOOLS_ROW_HEIGHT = 90; // 工具栏高度 90 第三期功能不显示 暂时改为 58
const VIEW_CONTAINER_MIN_HEIGHT = 620; // 详情面板最小高度

export default defineComponent({
  name: 'TraceDetail',
  props: TraceDetailProps,
  setup(props) {
    const route = useRoute();
    /** 取消请求方法 */
    let searchCancelFn = () => {};
    const { t } = useI18n();
    const store = useTraceStore();
    /** 缓存不同tab下的过滤选项 */
    const cacheFilterToolsValues = {
      waterFallAndTopo: ['duration'],
      sequenceAndFlame: [''],
      statistics: ['endpoint', 'service'],
    };
    let resizeObserver: any = null;
    const state = reactive<IState>({
      /** 当前tab */
      activePanel: 'timeline',
      /** 搜索关键字 */
      searchKeywords: [],
      /** Classify 过滤 */
      selectClassifyFilters: {},
      /** 搜索结果 spanId */
      matchedSpanIds: 0,
      /** 瀑布图动态样式 计算高度 */
      traceMainStyle: '',
      /** tab panel 配置 */
      tabPanels: [
        { id: 'timeline', name: t('瀑布列表'), icon: 'Waterfall' },
        { id: 'topo', name: t('节点拓扑'), icon: 'Component' },
        { id: 'statistics', name: t('表格统计'), icon: 'table' },
        { id: 'sequence', name: t('时序图'), icon: 'Sequence' },
        { id: 'flame', name: t('火焰图'), icon: 'Flame' },
      ],
      isClassifyFilter: false,
      filterSpanIds: [],
      filterSpanSubTitle: '',
      isCollapsefilter: false,
      isCompareView: false,
      compareTraceID: '',
      compareSpanList: [],
    });
    const traceView = ref(null);
    const traceDetailElem = ref(null);
    const traceMainElem = ref(null);
    const relationTopo = ref(null);
    const statisticsElem = ref(null);
    const searchBarElem = ref<InstanceType<typeof SearchBar>>(null);
    const baseMessage = ref<HTMLDivElement>();
    const isbaseMessageWrap = ref<boolean>(false);
    const isSticky = ref<boolean>(false); // 工具栏是否吸顶
    const showSpanDetails = ref(false); // span 详情弹窗
    const spanDetails = ref<null | Span>(null);
    const viewTool = ref(null);
    const traceGraphResize = ref(null);
    const compareSelect = ref(null);
    let resetFilterListFunc: (() => void) | null = null;
    /** span list 面板宽度 */
    const spanListWidth = ref(350);
    /** 记录 span list 面板关闭前宽度 由于组件参数执行顺序问题 需要记录关闭前重新打开后进行初始化 */
    const localSpanListWidth = ref(350);
    /** 工具栏输入框搜索内容 */
    const filterKeywords = ref<string[]>([]);
    const showCompareSelect = computed(() => {
      return ['topo', 'statistics', 'flame'].includes(state.activePanel) && topoType.value === ETopoType.time;
    });

    const isFullscreen = inject<boolean>('isFullscreen', false);
    const contentLoading = ref<boolean>(false);
    const traceData = computed<ITraceData>(() => store.traceData);
    const traceTree = computed<ITraceTree>(() => store.traceTree);
    const spanGroupTree = computed<Span[]>(() => store.spanGroupTree);
    const originCrossAppSpanMaps = computed(() => store.originCrossAppSpanMaps);
    const isLoading = computed<boolean>(() => store.traceLoading);
    const ellipsisDirection = computed(() => store.ellipsisDirection);
    const traceViewFilters = computed(() => store.traceViewFilters);
    const diffPercentList = computed(() => COMPARE_DIFF_COLOR_LIST.map(val => `${val.value}%`));
    const enabledTimeAlignment = ref(false);
    const curViewElem = computed(() => {
      switch (state.activePanel) {
        case 'timeline':
          return traceView.value as any;
        case 'topo':
          return relationTopo.value as any;
        case 'statistics':
          return statisticsElem.value as any;
      }
      return undefined;
    });
    const serviceCount = computed<number>(() =>
      traceData.value.span_classify.reduce((pre, cur) => {
        let total = pre;
        if (cur.type === 'service') {
          total += 1;
        }
        return total;
      }, 0)
    );
    // 层级数

    const spanDepth = computed<number>(
      () =>
        Math.max.apply(
          Math,
          traceTree.value.spans.map(item => item.depth)
        ) + 1
    );
    /** 工具栏过滤选项 */
    const filterToolList = computed(() =>
      TRACE_INFO_TOOL_FILTERS.filter(item => item.show && item.effect.includes(state.activePanel))
    );
    /** 是否展示 span list */
    const showSpanList = computed(() => ['sequence', 'topo'].includes(state.activePanel));

    /* 节点拓扑类型 时间/服务 */
    const topoType = ref<ETopoType>(ETopoType.time);

    /**
     * @description: 选择过滤条件
     * @param {ISpanClassifyItem} classify
     */
    const handleSelectFilters = async (classify: ISpanClassifyItem) => {
      const { filter_key: filterKey, filter_value: filterValue, app_name: appName } = classify;
      // 取消已选
      if (state.selectClassifyFilters[filterKey] === filterValue && appName === state.selectClassifyFilters.app_name) {
        state.selectClassifyFilters = {};
        state.searchKeywords.splice(0, state.searchKeywords.length);
        state.searchKeywords = [];
        state.selectClassifyFilters = {};
        await searchBarElem.value?.handleChange([]);
        clearSearch();
        return;
      }
      state.selectClassifyFilters = {};
      state.searchKeywords.splice(0, state.searchKeywords.length);

      let keyword = '';
      const matchesIds: any = [];
      const mathesTopoNodeIds: string[] = [];
      const { original_data: originalData, topo_nodes: topoNodes } = traceData.value;
      switch (classify.type) {
        case 'error':
          keyword = classify.name;
          if (state.activePanel === 'timeline') {
            originalData.forEach((data: any) => {
              if (
                data.status.code === classify.filter_value &&
                spanGroupTree.value.some(span => span.span_id === data.span_id)
              ) {
                matchesIds.push(data.span_id);
              }
            });
          } else if (state.activePanel === 'topo') {
            topoNodes.forEach(node => {
              if (node.error) {
                mathesTopoNodeIds.push(node.id);
              }
            });
          }
          break;
        case 'max_duration':
          keyword = classify.name;
          if (state.activePanel === 'timeline') {
            originalData.forEach((data: any) => {
              if (
                data.elapsed_time === classify.filter_value &&
                spanGroupTree.value.some(span => span.span_id === data.span_id)
              ) {
                matchesIds.push(data.span_id);
              }
            });
          } else if (state.activePanel === 'topo') {
            topoNodes.forEach(node => {
              if (node.duration === classify.filter_value) {
                mathesTopoNodeIds.push(node.id);
              }
            });
          }
          break;
        default:
          keyword = `service:${classify.name}`;
          if (state.activePanel === 'timeline') {
            (originCrossAppSpanMaps.value[classify.app_name as string] || []).forEach((data: any) => {
              if (
                data.resource['service.name'] === classify.filter_value &&
                spanGroupTree.value.some(span => span.span_id === data.span_id)
              ) {
                matchesIds.push(data.span_id);
              }
            });
          } else if (state.activePanel === 'topo') {
            topoNodes.forEach(node => {
              if (node.service_name === classify.filter_value) {
                mathesTopoNodeIds.push(node.id);
              }
            });
          }
          break;
      }
      state.searchKeywords.push(keyword);
      state.selectClassifyFilters[filterKey] = filterValue;
      if (classify.app_name) {
        state.selectClassifyFilters.app_name = classify.app_name;
      }
      state.isClassifyFilter = true;
      await searchBarElem.value?.handleChange([keyword]);

      if (state.activePanel === 'statistics') {
        // 统计过滤参数
        const filterDict: IFilterItem = {
          type: classify.type,
          value: classify.type === 'service' ? classify.filter_value : '',
        };
        (statisticsElem.value as any).handleKeywordFilter(filterDict);
      } else if (['timeline', 'topo'].includes(state.activePanel)) {
        const comps = curViewElem.value;
        const isTopo = state.activePanel === 'topo';
        comps?.handleClassifyFilter(isTopo ? mathesTopoNodeIds : new Set(matchesIds), classify);
        state.matchedSpanIds = isTopo ? mathesTopoNodeIds.length : matchesIds.length;
        if (state.activePanel === 'topo') {
          state.filterSpanIds = matchesIds;
          state.filterSpanSubTitle = classify.type === 'service' ? (classify.filter_value as string) : classify.name;
          state.isCollapsefilter = false;
        }
      }
    };
    // 切换视图
    const handleTabChange = (v: IPanelEnum) => {
      state.activePanel = v;
      state.filterSpanIds = [];
      state.filterSpanSubTitle = '';
      nextTick(() => {
        // 保证异步重新给过滤选项赋值
        if (v === 'statistics') {
          // 表格统计选项与其他tab视图不一致 重新从缓存中赋值
          store.updateTraceViewFilters(cacheFilterToolsValues.statistics);
        } else {
          // 时序图和火焰图需要过滤【耗时选项】
          const { waterFallAndTopo } = cacheFilterToolsValues;
          let newArr = ['flame', 'sequence'].includes(v)
            ? waterFallAndTopo.filter(val => val !== 'duration')
            : waterFallAndTopo;
          if (v !== 'timeline') {
            newArr = newArr.filter(val => val !== QUERY_TRACE_RELATION_APP);
          }
          store.updateTraceViewFilters(newArr);
        }
      });
      store.updateTraceViewFilterTab(v);
      (traceDetailElem.value as any).scrollTop = 0;
      handleResize();
      cancelFilter();

      // TODO 目前只有拓扑图和表格统计存在对比 对比时禁用显示过滤
      if (state.isCompareView) {
        if (['topo', 'statistics', 'flame'].includes(v)) {
          setTimeout(() => {
            handleCompare(state.compareTraceID);
          }, 10);
        }
      }
    };
    // 取消过滤
    const cancelFilter = async () => {
      state.searchKeywords = [];
      state.selectClassifyFilters = {};
      await searchBarElem.value?.handleChange([]);
      clearSearch();
    };
    // 搜索结果选择下一个
    const nextResult = () => {
      const comps = curViewElem.value;
      comps?.nextResult();
    };
    // 搜索结果选择上一个
    const prevResult = () => {
      const comps = curViewElem.value;
      comps?.prevResult();
    };
    // 清空搜索
    const clearSearch = () => {
      state.searchKeywords = [];
      state.selectClassifyFilters = {};
      state.matchedSpanIds = 0;
      const comps = curViewElem.value;
      if (state.activePanel === 'statistics') {
        searchBarElem.value?.handleChange([]);
        comps?.handleKeywordFilter(null);
      } else {
        comps?.clearSearch();
        if (state.activePanel === 'topo') {
          state.filterSpanIds = [];
          state.filterSpanSubTitle = '';
        }
      }
    };
    // 视图搜索
    const trackFilter = (val: string[]) => {
      filterKeywords.value = val;

      if (state.isClassifyFilter) {
        state.isClassifyFilter = false;
        return;
      }

      if (!val.length) {
        state.searchKeywords = [];
      }

      state.selectClassifyFilters = {};
      const comps = curViewElem.value;
      switch (state.activePanel) {
        case 'timeline':
          comps?.trackFilter(val);
          break;
        case 'topo':
          comps?.handleKeywordFilter(val);
          break;
        case 'statistics':
          {
            let filterDict: IFilterItem | null = null; // 统计内容搜索参数
            if (val.length) {
              filterDict = {
                type: 'keyword',
                value: val.toString(),
              };
            }
            comps?.handleKeywordFilter(filterDict);
          }
          break;
        default:
          break;
      }
    };
    // 根据窗口大小变化自适应视图高度
    const handleResize = () => {
      if (traceMainElem.value && !isLoading.value) {
        let containerHeight = document.querySelector('.trace-detail-wrapper')?.clientHeight as number; // 详情容器高度
        const { offsetTop, clientWidth } = traceMainElem.value as any; // 视图容器举例详情容器顶部高度
        const baseMessageRect = baseMessage.value?.getBoundingClientRect();
        if (containerHeight < VIEW_CONTAINER_MIN_HEIGHT) {
          // 浏览器窗口最小高度720情况下 详情容器的最小高度
          containerHeight = VIEW_CONTAINER_MIN_HEIGHT;
        }
        const toolRowHeight = TOOLS_ROW_HEIGHT;
        // 视图容器的最小高度
        const viewHeight = containerHeight - offsetTop - toolRowHeight - 12; // 12为padding大小
        const viewWidth =
          showSpanList.value && !contentLoading.value && ['topo', 'sequence', 'flame'].includes(state.activePanel)
            ? `${clientWidth - spanListWidth.value}px`
            : '100%';
        const isHaveHeight = ['topo', 'statistics', 'flame', 'sequence'].includes(state.activePanel);
        state.traceMainStyle = `width:${viewWidth};min-height: ${viewHeight}px${
          isHaveHeight ? `; height: ${viewHeight}px` : '; height: 100%'
        };padding-right:${showSpanList.value ? '0' : '16px'}`;
        if (baseMessageRect && baseMessageRect.height > 18) {
          // 基本信息是否换行 样式处理
          isbaseMessageWrap.value = true;
        } else {
          isbaseMessageWrap.value = false;
        }
        setTimeout(() => {
          setSpanListPosition();
        }, 10);
      }
    };
    // 监听滚动
    const handleScroll = (e: any) => {
      setSpanListPosition();
      const { offsetTop } = traceMainElem.value as any;
      isSticky.value = e.target.scrollTop >= offsetTop;
    };
    const updateMatchedSpanIds = (count: number) => {
      state.matchedSpanIds = count;
    };
    const updateEllipsisDirection = (val: DirectionType) => {
      store.updateEllipsisDirection(val);
    };
    // 获取两个数组差异元素
    const getArrDifference = (arr1: string[], arr2: string[]) => {
      return arr1.concat(arr2).filter((v, i, arr) => {
        return arr.indexOf(v) === arr.lastIndexOf(v);
      });
    };
    // Span 类型过滤
    const handleSpanKindChange = async (val: string[]) => {
      // 耗时选项只影响视图元素变化 不需要重新请求接口数据
      if (getArrDifference(val, traceViewFilters.value)?.[0] === 'duration') {
        store.updateTraceViewFilters(val);
        return;
      }

      store.updateTraceViewFilters(val);
      if (state.activePanel === 'statistics') {
        cacheFilterToolsValues.statistics = val;
      } else {
        searchCancelFn();
        const selects = val.filter(item => item !== 'duration' && item !== QUERY_TRACE_RELATION_APP); // 排除 耗时、跨应用 选项
        const displays = ['source_category_opentelemetry'].concat(selects);
        const { trace_id: traceId } = traceData.value;
        contentLoading.value = true;
        if (state.activePanel === 'topo') handleResize();
        const params = {
          bk_biz_id: window.bk_biz_id,
          app_name: props.appName,
          trace_id: traceId,
          displays,
          enabled_time_alignment: enabledTimeAlignment.value,
        };
        clearCrossApp();
        if (state.activePanel === 'timeline') {
          params[QUERY_TRACE_RELATION_APP] = val.includes(QUERY_TRACE_RELATION_APP);
        }
        await traceDetail(params, {
          cancelToken: new CancelToken((c: any) => (searchCancelFn = c)),
        }).then(async data => {
          await store.setTraceData({ ...data, appName: props.appName, trace_id: traceId });
          contentLoading.value = false;
        });
        if (['flame', 'sequence'].includes(state.activePanel)) {
          cacheFilterToolsValues.sequenceAndFlame = val;
          // 由于 瀑布图/拓扑图 和 时序图/火焰图 的选项有重叠部分 需要做差异同步
          cacheFilterToolsValues.waterFallAndTopo = [
            ...cacheFilterToolsValues.waterFallAndTopo.filter(item => item === 'duration'),
            ...val,
          ];
        } else cacheFilterToolsValues.waterFallAndTopo = val;
      }
    };

    /**
     * @description: 判断checkbox是否禁用
     * @param kindId 类型ID
     * @returns { boolean }
     */
    const disabledSpanKindById = (kindId: string) => {
      if (kindId === SOURCE_CATEGORY_EBPF && !traceData.value?.ebpf_enabled) {
        return true;
      }
      return (
        (state.activePanel === 'statistics' &&
          traceViewFilters.value.length === 1 &&
          traceViewFilters.value.includes(kindId)) ||
        (state.activePanel === 'topo' &&
          [SOURCE_CATEGORY_EBPF, VIRTUAL_SPAN].includes(kindId) &&
          topoType.value === ETopoType.service)
      );
    };

    // 回到顶部操作
    const handleBackTop = () => {
      document.querySelector('.trace-detail-wrapper')?.scrollTo({ top: 0 });
    };
    /** 侧栏查看 span 详情 */
    const handleShowSpanDetails = (span: Span | string) => {
      if (typeTools.isString(span)) {
        // 如果 span 为 string 类型 说明span为span_id 需要通过spanlist匹配
        spanDetails.value = (traceTree.value.spans.find(item => item.span_id === span) || {}) as Span;
      } else spanDetails.value = span as Span;
      showSpanDetails.value = true;
    };
    /** 计算 span list 赋值的定位 */
    const setSpanListPosition = () => {
      const rect = viewTool.value?.getBoundingClientRect();
      const width = traceMainElem.value?.getBoundingClientRect()?.width;
      if (traceGraphResize.value && rect) {
        traceGraphResize.value.$el.style.top = `${rect.bottom}px`;
        traceGraphResize.value.$el.style.width = `${width}px`;
        traceGraphResize.value.$el.style.right = `${state.activePanel === 'topo' ? 16 : 20}px`;
      }
    };
    /** 时序图过滤 span */
    // biome-ignore lint/style/useDefaultParameterLast: <explanation>
    const handleSpanListFilter = (spanList: string[], subTitle = '', filterFunc: () => void) => {
      !spanList?.length && resetFilterListFunc?.();
      resetFilterListFunc = filterFunc;
      state.filterSpanIds = spanList;
      state.filterSpanSubTitle = subTitle;
      state.isCollapsefilter = true;
    };
    /** span list 面板拖拽 */
    const handleSpanListResizing = (width: number) => {
      spanListWidth.value = width;
      localSpanListWidth.value = width;
      handleResize();
    };
    /** 收起/展开 span list 面板 */
    const handleSpanListCollapseChange = (val: boolean) => {
      spanListWidth.value = val ? 0 : localSpanListWidth.value;
      handleResize();
    };
    const resizeObsever = () => {
      resizeObserver = new ResizeObserver(() => {
        handleResize();
      });
      // const elem = document.querySelector('.trace-detail-wrapper');
      const elem = traceDetailElem.value.$el;
      elem && resizeObserver.observe(elem);
    };

    watch(
      () => props.traceID,
      () => {
        clearCompareParams();
        clearCrossApp();
      }
    );

    watch(
      () => traceData.value,
      () => {
        cancelFilter();
        state.filterSpanIds = [];
        state.filterSpanSubTitle = '';
        clearCompareParams();
        nextTick(() => handleResize());
        compareSelect.value?.handleCancelCompare();
      },
      { deep: true }
    );

    watch(
      () => traceData.value.span_classify,
      val => {
        if (val && route.query?.incident_query) {
          const data = val.filter(f => f.type === 'error');
          // 只有从故障详情页跳转过来才会触发
          handleSelectFilters(data[0]);
        }
      },
      { deep: true }
    );

    onMounted(() => {
      handleResize();
      resizeObsever();
      document.querySelector('.trace-detail-wrapper')?.addEventListener('scroll', handleScroll);
      setSpanListPosition();
    });

    onBeforeUnmount(() => {
      const elem = document.querySelector('.trace-detail-wrapper');
      elem && resizeObserver.unobserve(elem);
      document.querySelector('.trace-detail-wrapper')?.addEventListener('scroll', handleScroll);
      nextTick(() => store.setTraceData({ ...DEFAULT_TRACE_DATA }));
      store.updateTraceViewFilters(['duration']);
    });
    const contentLoadingChange = (val: boolean) => {
      contentLoading.value = val;
      setSpanListPosition();
      handleResize();
    };
    /** 对比 */
    const handleCompare = (traceID: string) => {
      if (traceData.value.trace_id === traceID) {
        // 相同的traceID不对比
        Message({
          message: t('对比的TraceID相同'),
          theme: 'warning',
          width: 200,
        });
        return;
      }
      if (['topo', 'statistics'].includes(state.activePanel)) {
        const comps = curViewElem.value;
        comps.viewCompare(traceID);
        state.isCompareView = true;
      }
      state.filterSpanSubTitle = '';
      state.filterSpanIds = [];
      state.compareSpanList = [];
      state.compareTraceID = traceID;
    };
    /** 取消对比 */
    const handleCancelCompare = () => {
      if (['topo', 'statistics'].includes(state.activePanel)) {
        const comps = curViewElem.value;
        comps.viewCompare('');
      }
      clearCompareParams();
    };
    /** 更新对比 span list */
    const handleCompareSpanListChange = (list: Span[]) => {
      if (list.length) {
        updateCompareStatus(true);
        state.compareSpanList = list;
      } else {
        clearCompareParams();
        compareSelect.value.clearCompareTarget();
      }
    };
    /** 清空对比模式下相关配置参数 */
    const clearCompareParams = () => {
      updateCompareStatus(false);
      state.compareSpanList = [];
      state.compareTraceID = '';
    };

    /** 从非timeline视图切换Trace ID，过滤跨应用checkbox */
    const clearCrossApp = () => {
      if (
        state.activePanel !== 'timeline' &&
        cacheFilterToolsValues.waterFallAndTopo.includes(QUERY_TRACE_RELATION_APP)
      ) {
        cacheFilterToolsValues.waterFallAndTopo = cacheFilterToolsValues.waterFallAndTopo.filter(
          item => item !== QUERY_TRACE_RELATION_APP
        );
      }
    };
    /** 更新对比状态 */
    const updateCompareStatus = (isCompare = true) => {
      state.isCompareView = isCompare;
      isCompare && updateTemporaryCompareTrace(state.compareTraceID);
    };

    /**
     * @description 切换拓扑图类型
     * @param value
     */
    function handleTopoChangeType(value: ETopoType) {
      topoType.value = value;
      const viewFilters = traceViewFilters.value.filter(item => item !== 'duration');
      if (value === ETopoType.service) {
        // service 默认不展示耗时面板
        store.updateTraceViewFilters(viewFilters);
      } else {
        store.updateTraceViewFilters([...viewFilters, 'duration']);
        if (state.isCompareView) {
          setTimeout(() => {
            handleCompare(state.compareTraceID);
          }, 10);
        }
      }
      state.filterSpanIds = [];
      state.filterSpanSubTitle = '';
      cancelFilter();
      // 服务topo禁用 SOURCE_CATEGORY_EBPF, VIRTUAL_SPAN
      const traceViewFiltersV = [];
      if (topoType.value === ETopoType.service) {
        for (const v of traceViewFilters.value) {
          if (![SOURCE_CATEGORY_EBPF, VIRTUAL_SPAN].includes(v)) {
            traceViewFiltersV.push(v);
          }
        }
        handleSpanKindChange(traceViewFiltersV);
      }
    }

    /**
     * @description 选中了服务topo的节点或者边
     * @param _keys
     */
    async function handleServiceTopoClickItem(_keys) {
      await searchBarElem.value?.handleChange([]);
      clearSearch();
    }
    async function handleChangeEnableTimeALignment(v: boolean) {
      contentLoading.value = true;
      const { trace_id: traceId } = traceData.value;
      enabledTimeAlignment.value = v;
      const params = {
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
        trace_id: traceId,
        enabled_time_alignment: enabledTimeAlignment.value,
      };
      const data = await traceDetail(params, {
        cancelToken: new CancelToken((c: any) => (searchCancelFn = c)),
      }).catch(() => false);
      data && (await store.setTraceData({ ...data, appName: props.appName, trace_id: traceId }));
      contentLoading.value = false;
    }
    return {
      ...toRefs(state),
      isLoading,
      contentLoading,
      traceView,
      relationTopo,
      showCompareSelect,
      traceDetailElem,
      traceMainElem,
      statisticsElem,
      searchBarElem,
      handleSelectFilters,
      handleTabChange,
      trackFilter,
      clearSearch,
      nextResult,
      prevResult,
      traceData,
      traceTree,
      enabledTimeAlignment,
      updateMatchedSpanIds,
      isFullscreen,
      baseMessage,
      isbaseMessageWrap,
      serviceCount,
      spanDepth,
      ellipsisDirection,
      updateEllipsisDirection,
      traceViewFilters,
      handleSpanKindChange,
      isSticky,
      contentLoadingChange,
      handleBackTop,
      showSpanDetails,
      spanDetails,
      handleShowSpanDetails,
      filterToolList,
      viewTool,
      traceGraphResize,
      handleSpanListFilter,
      handleSpanListResizing,
      handleSpanListCollapseChange,
      showSpanList,
      diffPercentList,
      handleCompare,
      handleCancelCompare,
      compareSelect,
      handleCompareSpanListChange,
      filterKeywords,
      updateCompareStatus,
      topoType,
      handleTopoChangeType,
      handleServiceTopoClickItem,
      handleChangeEnableTimeALignment,
      disabledSpanKindById,
      t,
    };
  },

  render() {
    const { trace_id: traceId, trace_info: traceInfo, span_classify: spanClassify } = this.traceData;
    const isStatisticsPanel = this.activePanel === 'statistics';

    return (
      <Loading
        ref='traceDetailElem'
        class={`trace-detail-wrapper is-fix ${this.isInTable ? 'is-table-detail' : ''} ${this.isSticky ? 'is-sticky' : ''}`}
        loading={this.isLoading}
        zIndex={99999}
      >
        {/* {this.isInTable && (
          <div
            class='fullscreen-btn toggle-full-screen'
            onClick={() => this.$emit('close')}
          >
            <div class='circle' />
            <span class='icon-monitor icon-mc-close icon-page-close' />
          </div>
        )} */}
        {!this.isInTable && (
          <TraceDetailHeader
            appName={this.appName}
            hasFullscreen={false}
            traceId={this.traceID || traceId}
          />
        )}

        <div
          ref='baseMessage'
          class={['base-message', { 'is-wrap': this.isbaseMessageWrap }]}
        >
          <div class='message-item'>
            <span>{this.t('产生时间')}</span>
            <span>{dayjs.tz(traceInfo?.product_time / 1e3).format('YYYY-MM-DD HH:mm:ss')}</span>
          </div>
          <div class='message-item'>
            <span>{this.t('总耗时')}</span>
            <span>{formatDuration(traceInfo?.trace_duration)}</span>
            {traceInfo?.time_error && [
              this.enabledTimeAlignment ? (
                <span
                  key={1}
                  style='color: #699DF4; margin-left: 5px'
                  class='icon-monitor icon-mc-time'
                />
              ) : undefined,
              <Popover
                key={2}
                v-slots={{
                  default: () => <span class='icon-monitor icon-tips' />,
                  content: () => (
                    <div class='trace-duration-pop'>
                      <span style='color: #313238'>{this.t('时间校准')}</span>
                      <Switcher
                        modelValue={this.enabledTimeAlignment}
                        size='small'
                        theme='primary'
                        onChange={this.handleChangeEnableTimeALignment}
                      />
                      <span class='icon-monitor icon-hint' />
                      {this.t('开启时间校准，可同步服务所在时钟')}
                    </div>
                  ),
                }}
                placement='top'
                theme='light'
              />,
            ]}
          </div>
          <div class='message-item'>
            <span>{this.t('耗时分布')}</span>
            <span>{`${formatDuration(traceInfo?.min_duration)} - ${formatDuration(traceInfo?.max_duration)}`}</span>
          </div>
          <div class='message-item'>
            <span>{this.t('服务数')}</span>
            <span>{this.serviceCount}</span>
          </div>
          <div class='message-item'>
            <span>{this.t('层级数')}</span>
            <span>{this.spanDepth}</span>
          </div>
          <div class='message-item'>
            <span>{this.t('span总数')}</span>
            <span>{this.traceTree?.spans?.length}</span>
          </div>
        </div>
        <div class='overview-content'>
          {spanClassify?.map((card, index) => (
            <div
              key={index}
              class={[
                'item-card',
                {
                  'is-service': card.type === 'service',
                  'is-selected':
                    this.selectClassifyFilters[card.filter_key] === card.filter_value &&
                    (this.selectClassifyFilters.app_name
                      ? this.selectClassifyFilters.app_name === card.app_name
                      : !card.app_name),
                },
              ]}
              onClick={() => this.handleSelectFilters(card)}
            >
              {card.type === 'service' && (
                <span
                  style={`background:${card.color}`}
                  class='service-mark'
                />
              )}
              {}
              {card.type === 'service' ? (
                card.icon ? (
                  <img
                    class='service-icon'
                    alt=''
                    src={card.icon}
                  />
                ) : (
                  ''
                )
              ) : (
                <span class={`card-icon icon-monitor icon-${card.icon}`} />
              )}
              <span class='card-text'>{card.name}</span>
              {card.type !== 'max_duration' && <span class='card-count'>{card.count}</span>}
            </div>
          ))}
        </div>
        <div
          ref='traceMainElem'
          class='trace-main'
        >
          <MonitorTab
            class='trace-main-tab'
            v-slots={{
              setting: () =>
                // 时序图暂不支持
                ['timeline', 'topo', 'statistics', 'flame'].includes(this.activePanel) ? (
                  <div class='tab-setting'>
                    {this.showCompareSelect ? (
                      <CompareSelect
                        ref='compareSelect'
                        appName={this.appName}
                        targetTraceID={this.compareTraceID}
                        onCancel={this.handleCancelCompare}
                        onCompare={this.handleCompare}
                      />
                    ) : (
                      ''
                    )}
                    <SearchBar
                      ref='searchBarElem'
                      clearSearch={this.clearSearch}
                      limitClassify={!!Object.keys(this.selectClassifyFilters).length}
                      nextResult={this.nextResult}
                      prevResult={this.prevResult}
                      resultCount={this.matchedSpanIds}
                      showResultCount={this.activePanel !== 'statistics'}
                      trackFilter={val => this.trackFilter(val)}
                    />
                    {['timeline', 'flame'].includes(this.activePanel) ? (
                      <div class='ellipsis-direction'>
                        <Popover
                          content={'Head first'}
                          popoverDelay={[500, 0]}
                        >
                          <div
                            class={`item ${this.ellipsisDirection === 'ltr' ? 'active' : ''}`}
                            onClick={() => this.updateEllipsisDirection('ltr')}
                          >
                            <i class='icon-monitor icon-AB' />
                          </div>
                        </Popover>
                        <Popover
                          content={'Tail first'}
                          popoverDelay={[500, 0]}
                        >
                          <div
                            class={`item ${this.ellipsisDirection === 'rtl' ? 'active' : ''}`}
                            onClick={() => this.updateEllipsisDirection('rtl')}
                          >
                            <i class='icon-monitor icon-YZ' />
                          </div>
                        </Popover>
                      </div>
                    ) : (
                      ''
                    )}
                  </div>
                ) : (
                  ''
                ),
            }}
            active={this.activePanel}
            onTabChange={this.handleTabChange}
          >
            {this.tabPanels.map(item => (
              <TabPanel
                key={item.id}
                v-slots={{
                  label: () => (
                    <span class='tab-label'>
                      <i class={`icon-monitor icon-${item.icon}`} />
                      {item.name}
                    </span>
                  ),
                }}
                label={item.name}
                name={item.id}
              />
            ))}
          </MonitorTab>
          {/* 工具栏 */}
          <div
            ref='viewTool'
            class='view-tools'
          >
            {
              /** 拓扑图、火焰图在对比模式下不显示节点过滤选项 */
              <div
                class={`span-kind-filters ${
                  ['topo', 'flame'].includes(this.activePanel) && this.isCompareView ? 'is-hidden' : ''
                }`}
              >
                <span class={`label ${isStatisticsPanel ? 'is-required' : ''}`}>
                  {`${isStatisticsPanel ? this.t('分组') : this.t('显示')}`}
                </span>
                :
                <Checkbox.Group
                  class='span-kind-checkbox'
                  v-model={this.traceViewFilters}
                  onChange={this.handleSpanKindChange}
                >
                  {this.filterToolList.map((kind, index) => (
                    <Checkbox
                      key={index}
                      disabled={this.disabledSpanKindById(kind.id)}
                      label={kind.id}
                      size='small'
                    >
                      {/* 增加特殊过滤类型说明 */}
                      <Popover
                        key={kind.id}
                        disabled={!kind.desc}
                        placement='top'
                        popoverDelay={[500, 50]}
                      >
                        {{
                          default: () => <span>{kind.label}</span>,
                          content: () => {
                            if (kind.id !== SOURCE_CATEGORY_EBPF) {
                              return kind.desc;
                            }
                            return this.traceData?.ebpf_enabled ? kind.desc : kind.disabledDesc;
                          },
                        }}
                      </Popover>
                    </Checkbox>
                  ))}
                </Checkbox.Group>
              </div>
            }
            {['topo', 'flame'].includes(this.activePanel) && this.isCompareView && this.showCompareSelect ? (
              <div class='compare-legend'>
                <span class='tag tag-new'>added</span>
                <div class='percent-queue'>
                  {this.diffPercentList.map((item, index) => (
                    <span
                      key={index}
                      class={`percent-tag tag-${index + 1}`}
                    >
                      {item}
                    </span>
                  ))}
                </div>
                <span class='tag tag-removed'>removed</span>
              </div>
            ) : (
              ''
            )}
          </div>
          {this.traceTree && (
            <div
              style={this.traceMainStyle}
              class='tab-panel-content'
            >
              <Loading
                loading={this.contentLoading}
                zIndex={9999999}
              >
                {/* 瀑布图 */}
                {this.activePanel === 'timeline' && (
                  <TraceView
                    ref='traceView'
                    updateMatchedSpanIds={this.updateMatchedSpanIds}
                  />
                )}
                {/* 拓扑视图 */}
                {this.activePanel === 'topo' && (
                  <NodeTopo
                    key={traceInfo?.root_span_id || ''}
                    ref='relationTopo'
                    compareTraceID={this.compareTraceID}
                    type={this.topoType}
                    updateMatchedSpanIds={this.updateMatchedSpanIds}
                    onCompareSpanListChange={this.handleCompareSpanListChange}
                    onServiceTopoClickItem={keys => this.handleServiceTopoClickItem(keys)}
                    onShowSpanDetail={this.handleShowSpanDetails}
                    onSpanListChange={this.handleSpanListFilter}
                    onTypeChange={this.handleTopoChangeType}
                    onUpdate:loading={this.contentLoadingChange}
                  />
                )}
                {/* 统计视图 */}
                {this.activePanel === 'statistics' && (
                  <div class='statistics-container'>
                    <StatisticsTable
                      ref='statisticsElem'
                      appName={this.appName}
                      compareTraceID={this.compareTraceID}
                      traceId={this.traceID || traceId}
                      onClearKeyword={() => this.clearSearch()}
                      onUpdate:loading={this.contentLoadingChange}
                    />
                  </div>
                )}
                {/* 火焰图 */}
                {this.activePanel === 'flame' && (
                  <FlameGraphV2
                    appName={this.appName}
                    diffTraceId={this.compareTraceID}
                    filterKeywords={this.filterKeywords}
                    filters={this.traceViewFilters}
                    textDirection={this.ellipsisDirection}
                    traceId={this.traceID || traceId}
                    onDiffTraceSuccess={this.updateCompareStatus}
                    onShowSpanDetail={this.handleShowSpanDetails}
                    onUpdate:loading={this.contentLoadingChange}
                  />
                )}
                {this.activePanel === 'sequence' && (
                  <SequenceGraph
                    appName={this.appName}
                    filters={this.traceViewFilters}
                    traceId={this.traceID || traceId}
                    onShowSpanDetail={this.handleShowSpanDetails}
                    onSpanListChange={this.handleSpanListFilter}
                    onUpdate:loading={this.contentLoadingChange}
                  />
                )}
              </Loading>
              <ResizeLayout
                key={this.activePanel}
                ref='traceGraphResize'
                class={`trace-graph-resize ${this.showSpanList && !this.contentLoading ? 'is-visibility' : ''}`}
                border={false}
                initialDivide={'350px'}
                placement='right'
                triggerWidth={12}
                collapsible
                immediate
                onCollapse-change={this.handleSpanListCollapseChange}
                onResizing={this.handleSpanListResizing}
              >
                {{
                  main: () => <div />,
                  aside: () => (
                    <TopoSpanList
                      compareSpanList={this.compareSpanList}
                      filterSpanIds={this.filterSpanIds}
                      isCompare={this.isCompareView}
                      subTitle={this.filterSpanSubTitle}
                      type={this.topoType}
                      onListChange={this.handleSpanListFilter}
                      onViewDetail={this.handleShowSpanDetails}
                    />
                  ),
                }}
              </ResizeLayout>
            </div>
          )}
        </div>
        {this.isSticky && (
          <div
            class='back-top'
            onClick={this.handleBackTop}
          >
            <i class='icon-monitor icon-back-up' />
          </div>
        )}
        <SpanDetails
          isFullscreen={this.isFullscreen}
          show={this.showSpanDetails}
          spanDetails={this.spanDetails as Span}
          onShow={v => (this.showSpanDetails = v)}
        />
      </Loading>
    );
  },
});
