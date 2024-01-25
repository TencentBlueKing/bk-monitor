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
  watch
} from 'vue';
import { useI18n } from 'vue-i18n';
import { Checkbox, Loading, Message, Popover, ResizeLayout, Tab } from 'bkui-vue';
import dayjs from 'dayjs';

import { CancelToken } from '../../../../monitor-api/index';
import { traceDetail } from '../../../../monitor-api/modules/apm_trace';
import { copyText, typeTools } from '../../../../monitor-common/utils/utils';
import CompareSelect from '../../../components/compare-select/compare-select';
import MonitorTab from '../../../components/monitor-tab/monitor-tab';
import RelationTopo from '../../../components/relation-topo/relation-topo';
import StatisticsTable, { IFilterItem } from '../../../components/statistics-table/statistics-table';
import TraceView from '../../../components/trace-view';
import SearchBar from '../../../components/trace-view/search-bar';
import { Span } from '../../../components/trace-view/typings';
import { formatDuration } from '../../../components/trace-view/utils/date';
// import FlameGraph from '../../../plugins/charts/flame-graph/flame-graph';
import FlameGraphV2 from '../../../plugins/charts/flame-graph-v2/flame-graph';
import SequenceGraph from '../../../plugins/charts/sequence-graph/sequence-graph';
import SpanList from '../../../plugins/charts/span-list/span-list';
import { DEFAULT_TRACE_DATA, TRACE_INFO_TOOL_FILTERS } from '../../../store/constant';
import { useTraceStore } from '../../../store/modules/trace';
import { DirectionType, ISpanClassifyItem, ITraceData, ITraceTree } from '../../../typings';
import { COMPARE_DIFF_COLOR_LIST, updateTemporaryCompareTrace } from '../../../utils/compare';
import SpanDetails from '../span-details';

import './trace-detail.scss';

const { TabPanel } = Tab;

const TraceDetailProps = {
  isInTable: {
    type: Boolean,
    default: false
  },
  appName: {
    type: String,
    default: true
  },
  traceID: {
    type: String,
    default: ''
  }
};

type IPanelEnum = 'timeline' | 'topo' | 'statistics' | 'flame' | 'sequence';

interface ITabItem {
  id: string;
  name: string;
  icon: string;
}

interface IState {
  activePanel: IPanelEnum;
  searchKeywords: string[];
  selectClassifyFilters: { [key: string]: string | number };
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
  emits: ['close'],
  setup(props) {
    /** 取消请求方法 */
    let searchCancelFn = () => {};
    const { t } = useI18n();
    const store = useTraceStore();
    /** 缓存不同tab下的过滤选项 */
    const cacheFilterToolsValues = {
      waterFallAndTopo: ['duration'],
      sequenceAndFlame: [''],
      statistics: ['endpoint', 'service']
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
        { id: 'flame', name: t('火焰图'), icon: 'Flame' }
      ],
      isClassifyFilter: false,
      filterSpanIds: [],
      filterSpanSubTitle: '',
      isCollapsefilter: false,
      isCompareView: false,
      compareTraceID: '',
      compareSpanList: []
    });
    const traceView = ref(null);
    const traceDetailElem = ref(null);
    const traceMainElem = ref(null);
    const relationTopo = ref(null);
    const statisticsElem = ref(null);
    const searchBarElem = ref(null);
    const baseMessage = ref<HTMLDivElement>();
    const isbaseMessageWrap = ref<boolean>(false);
    const isSticky = ref<boolean>(false); // 工具栏是否吸顶
    const showSpanDetails = ref(false); // span 详情弹窗
    const spanDetails = ref<Span | null>(null);
    const viewTool = ref(null);
    const traceGraphResize = ref(null);
    const compareSelect = ref(null);
    let resetFilterListFunc: Function | null = null;
    /** span list 面板宽度 */
    const spanListWidth = ref(350);
    /** 记录 span list 面板关闭前宽度 由于组件参数执行顺序问题 需要记录关闭前重新打开后进行初始化 */
    const localSpanListWidth = ref(350);
    /** 工具栏输入框搜索内容 */
    const filterKeywords = ref<string[]>([]);

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
        if (cur.type === 'service') pre += 1;
        return pre;
      }, 0)
    );
    // 层级数
    // eslint-disable-next-line prefer-spread
    const spanDepth = computed<number>(
      () =>
        Math.max.apply(
          Math,
          traceTree.value.spans.map(item => item.depth)
        ) + 1
    );
    /** 工具栏过滤选项 */
    // eslint-disable-next-line max-len
    const filterToolList = computed(() =>
      TRACE_INFO_TOOL_FILTERS.filter(item => item.show && item.effect.includes(state.activePanel))
    );
    /** 是否展示 span list */
    const showSpanList = computed(() => ['sequence', 'topo'].includes(state.activePanel));

    // 复制操作
    const handleCopy = (content: string) => {
      let text = '';
      const { trace_id: traceId } = traceData.value;
      if (content === 'text') {
        text = traceId;
      } else {
        const hash = `#${window.__BK_WEWEB_DATA__?.baseroute || '/'}home/?app_name=${
          props.appName
        }&search_type=accurate&trace_id=${traceId}`;
        text = location.href.replace(location.hash, hash);
      }
      copyText(
        text,
        (msg: string) => {
          Message({
            message: msg,
            theme: 'error'
          });
          return;
        },
        props.isInTable ? '.trace-content-table-wrap' : ''
      );
      Message({
        message: t('复制成功'),
        theme: 'success',
        width: 200
      });
    };
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
        await (searchBarElem.value as any).handleChange([]);
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
      await (searchBarElem.value as any).handleChange([keyword]);

      if (state.activePanel === 'statistics') {
        // 统计过滤参数
        const filterDict: IFilterItem = {
          type: classify.type,
          value: classify.type === 'service' ? classify.filter_value : ''
        };
        (statisticsElem.value as any).handleKeywordFliter(filterDict);
      } else if (['timeline', 'topo'].includes(state.activePanel)) {
        const comps = curViewElem.value;
        const isTopo = state.activePanel === 'topo';
        comps?.handleClassifyFilter(isTopo ? mathesTopoNodeIds : new Set(matchesIds));
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
          const newArr = ['flame', 'sequence'].includes(v)
            ? waterFallAndTopo.filter(val => val !== 'duration')
            : waterFallAndTopo;
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
      await (searchBarElem.value as any)?.handleChange([]);
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
        comps?.handleKeywordFliter(null);
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
          comps?.handleKeywordFliter(val);
          break;
        case 'statistics':
          // eslint-disable-next-line no-case-declarations
          let filterDict: IFilterItem | null = null; // 统计内容搜索参数
          if (val.length) {
            filterDict = {
              type: 'keyword',
              value: val.toString()
            };
          }
          comps?.handleKeywordFliter(filterDict);
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
      return arr1.concat(arr2).filter(function (v, i, arr) {
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
        const selects = val.filter(item => item !== 'duration'); // 排除 耗时 选贤
        const displays = ['source_category_opentelemetry'].concat(selects);
        const { trace_id: traceId } = traceData.value;
        contentLoading.value = true;
        if (state.activePanel === 'topo') handleResize();
        const params = {
          bk_biz_id: window.bk_biz_id,
          app_name: props.appName,
          trace_id: traceId,
          displays
        };

        await traceDetail(params, {
          cancelToken: new CancelToken((c: any) => (searchCancelFn = c))
        }).then(async data => {
          await store.setTraceData({ ...data, appName: props.appName, trace_id: traceId });
          contentLoading.value = false;
        });
        if (['flame', 'sequence'].includes(state.activePanel)) {
          cacheFilterToolsValues.sequenceAndFlame = val;
          // 由于 瀑布图/拓扑图 和 时序图/火焰图 的选项有重叠部分 需要做差异同步
          cacheFilterToolsValues.waterFallAndTopo = [
            ...cacheFilterToolsValues.waterFallAndTopo.filter(item => item === 'duration'),
            ...val
          ];
        } else cacheFilterToolsValues.waterFallAndTopo = val;
      }
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
    const handleSpanListFilter = (spanList: string[], subTitle = '', filterFunc: Function) => {
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
      const elem = document.querySelector('.trace-detail-wrapper');
      elem && resizeObserver.observe(elem);
    };

    watch(
      () => props.traceID,
      () => {
        clearCompareParams();
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
          width: 200
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
    /** 更新对比状态 */
    const updateCompareStatus = (isCompare = true) => {
      state.isCompareView = isCompare;
      isCompare && updateTemporaryCompareTrace(state.compareTraceID);
    };
    return {
      ...toRefs(state),
      isLoading,
      contentLoading,
      traceView,
      relationTopo,
      traceDetailElem,
      traceMainElem,
      statisticsElem,
      searchBarElem,
      handleCopy,
      handleSelectFilters,
      handleTabChange,
      trackFilter,
      clearSearch,
      nextResult,
      prevResult,
      traceData,
      traceTree,
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
      updateCompareStatus
    };
  },

  render() {
    const { isInTable, appName } = this.$props;
    const { trace_id: traceId, trace_info: traceInfo, span_classify: spanClassify } = this.traceData;
    const isStatisticsPanel = this.activePanel === 'statistics';

    return (
      <Loading
        zIndex={99999}
        loading={this.isLoading}
        class={`trace-detail-wrapper is-fix ${isInTable ? 'is-table-detail' : ''} ${this.isSticky ? 'is-sticky' : ''}`}
        ref='traceDetailElem'
      >
        {this.isInTable && (
          <div
            class='fullscreen-btn toggle-full-screen'
            onClick={() => this.$emit('close')}
          >
            <div class='circle'></div>
            <span class='icon-monitor icon-mc-close icon-page-close' />
          </div>
        )}
        <div class='header'>
          <span class='trace-id'>{traceId}</span>
          <Popover
            theme='light'
            placement='right'
            content={this.$t('复制 TraceID')}
          >
            <span
              class='icon-monitor icon-mc-copy'
              onClick={() => this.handleCopy('text')}
            />
          </Popover>
          <Popover
            theme='light'
            placement='right'
            content={this.$t('复制链接')}
          >
            <span
              class='icon-monitor icon-copy-link'
              onClick={() => this.handleCopy('link')}
            />
          </Popover>
        </div>
        <div
          class={['base-message', { 'is-wrap': this.isbaseMessageWrap }]}
          ref='baseMessage'
        >
          <div class='message-item'>
            <label>{this.$t('产生时间')}</label>
            <span>{dayjs.tz(traceInfo?.product_time / 1e3).format('YYYY-MM-DD HH:mm:ss')}</span>
          </div>
          <div class='message-item'>
            <label>{this.$t('总耗时')}</label>
            <span>{formatDuration(traceInfo?.trace_duration)}</span>
            {traceInfo?.time_error && (
              <Popover
                placement='top'
                content={this.$t('时间经过校准，注意服务所在时钟是否同步')}
              >
                <span class='icon-monitor icon-tips'></span>
              </Popover>
            )}
          </div>
          <div class='message-item'>
            <label>{this.$t('时间区间')}</label>
            <span>{`${formatDuration(traceInfo?.min_duration)} - ${formatDuration(traceInfo?.max_duration)}`}</span>
          </div>
          <div class='message-item'>
            <label>{this.$t('服务数')}</label>
            <span>{this.serviceCount}</span>
          </div>
          <div class='message-item'>
            <label>{this.$t('层级数')}</label>
            <span>{this.spanDepth}</span>
          </div>
          <div class='message-item'>
            <label>{this.$t('span总数')}</label>
            <span>{this.traceTree?.spans?.length}</span>
          </div>
        </div>
        <div class='overview-content'>
          {spanClassify?.map(card => (
            <div
              class={[
                'item-card',
                {
                  'is-service': card.type === 'service',
                  'is-selected':
                    this.selectClassifyFilters[card.filter_key] === card.filter_value &&
                    (this.selectClassifyFilters.app_name
                      ? this.selectClassifyFilters.app_name === card.app_name
                      : !card.app_name)
                }
              ]}
              // eslint-disable-next-line @typescript-eslint/no-misused-promises
              onClick={() => this.handleSelectFilters(card)}
            >
              {card.type === 'service' && (
                <span
                  class='service-mark'
                  style={`background:${card.color}`}
                />
              )}
              {/* eslint-disable-next-line no-nested-ternary */}
              {card.type === 'service' ? (
                card.icon ? (
                  <img
                    class='service-icon'
                    src={card.icon}
                    alt=''
                  />
                ) : (
                  ''
                )
              ) : (
                <span class={`card-icon icon-monitor icon-${card.icon}`}></span>
              )}
              <span class='card-text'>{card.name}</span>
              {card.type !== 'max_duration' && <span class='card-count'>{card.count}</span>}
            </div>
          ))}
        </div>
        <div
          class='trace-main'
          ref='traceMainElem'
        >
          <MonitorTab
            class='trace-main-tab'
            active={this.activePanel}
            onTabChange={this.handleTabChange}
            v-slots={{
              setting: () =>
                // 时序图暂不支持
                ['timeline', 'topo', 'statistics', 'flame'].includes(this.activePanel) ? (
                  <div class='tab-setting'>
                    {['topo', 'statistics', 'flame'].includes(this.activePanel) ? (
                      <CompareSelect
                        ref='compareSelect'
                        appName={this.appName}
                        targetTraceID={this.compareTraceID}
                        onCompare={this.handleCompare}
                        onCancel={this.handleCancelCompare}
                      />
                    ) : (
                      ''
                    )}
                    <SearchBar
                      ref='searchBarElem'
                      limitClassify={!!Object.keys(this.selectClassifyFilters).length}
                      trackFilter={val => this.trackFilter(val)}
                      resultCount={this.matchedSpanIds}
                      nextResult={this.nextResult}
                      prevResult={this.prevResult}
                      clearSearch={this.clearSearch}
                      showResultCount={this.activePanel !== 'statistics'}
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
                )
            }}
          >
            {this.tabPanels.map(item => (
              <TabPanel
                key={item.id}
                name={item.id}
                label={item.name}
                v-slots={{
                  label: () => (
                    <span class='tab-label'>
                      <i class={`icon-monitor icon-${item.icon}`}></i>
                      {item.name}
                    </span>
                  )
                }}
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
                  {`${isStatisticsPanel ? this.$t('分组') : this.$t('显示')}`}
                </span>
                :
                <Checkbox.Group
                  class='span-kind-checkbox'
                  v-model={this.traceViewFilters}
                  onChange={this.handleSpanKindChange}
                >
                  {this.filterToolList.map(kind => (
                    <Checkbox
                      label={kind.id}
                      size='small'
                      disabled={
                        this.activePanel === 'statistics' &&
                        this.traceViewFilters.length === 1 &&
                        this.traceViewFilters.includes(kind.id)
                      }
                    >
                      {/* 增加特殊过滤类型说明 */}
                      <Popover
                        placement='top'
                        key={kind.id}
                        content={kind.desc}
                        popoverDelay={[500, 0]}
                        disabled={!kind.desc}
                      >
                        <span>{kind.label}</span>
                      </Popover>
                    </Checkbox>
                  ))}
                </Checkbox.Group>
              </div>
            }
            {['topo', 'flame'].includes(this.activePanel) && this.isCompareView ? (
              <div class='compare-legend'>
                <span class='tag tag-new'>added</span>
                <div class='percent-queue'>
                  {this.diffPercentList.map((item, index) => (
                    <span class={`percent-tag tag-${index + 1}`}>{item}</span>
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
              class='tab-panel-content'
              style={this.traceMainStyle}
            >
              <Loading
                zIndex={9999999}
                loading={this.contentLoading}
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
                  <RelationTopo
                    ref='relationTopo'
                    onUpdate:loading={this.contentLoadingChange}
                    key={traceInfo?.root_span_id || ''}
                    compareTraceID={this.compareTraceID}
                    updateMatchedSpanIds={this.updateMatchedSpanIds}
                    onShowSpanDetail={this.handleShowSpanDetails}
                    onSpanListChange={this.handleSpanListFilter}
                    onCompareSpanListChange={this.handleCompareSpanListChange}
                  />
                )}
                {/* 统计视图 */}
                {this.activePanel === 'statistics' && (
                  <div class='statistics-container'>
                    <StatisticsTable
                      ref='statisticsElem'
                      onUpdate:loading={this.contentLoadingChange}
                      appName={appName}
                      traceId={traceId}
                      compareTraceID={this.compareTraceID}
                    />
                  </div>
                )}
                {/* 火焰图 */}
                {this.activePanel === 'flame' && (
                  <FlameGraphV2
                    onUpdate:loading={this.contentLoadingChange}
                    traceId={traceId}
                    appName={appName}
                    diffTraceId={this.compareTraceID}
                    filters={this.traceViewFilters}
                    textDirection={this.ellipsisDirection}
                    filterKeywords={this.filterKeywords}
                    onShowSpanDetail={this.handleShowSpanDetails}
                    onDiffTraceSuccess={this.updateCompareStatus}
                  />
                )}
                {this.activePanel === 'sequence' && (
                  <SequenceGraph
                    onUpdate:loading={this.contentLoadingChange}
                    traceId={traceId}
                    appName={appName}
                    onSpanListChange={this.handleSpanListFilter}
                    onShowSpanDetail={this.handleShowSpanDetails}
                    filters={this.traceViewFilters}
                  />
                )}
              </Loading>
              <ResizeLayout
                ref='traceGraphResize'
                class={`trace-graph-resize ${this.showSpanList && !this.contentLoading ? 'is-visibility' : ''}`}
                key={this.activePanel}
                immediate
                border={false}
                placement='right'
                collapsible
                triggerWidth={12}
                initialDivide={'350px'}
                onResizing={this.handleSpanListResizing}
                onCollapse-change={this.handleSpanListCollapseChange}
              >
                {{
                  main: () => <div></div>,
                  aside: () => (
                    <SpanList
                      subTitle={this.filterSpanSubTitle}
                      filterSpanIds={this.filterSpanIds}
                      isCollapsed={this.isCollapsefilter}
                      onViewDetail={this.handleShowSpanDetails}
                      onListChange={this.handleSpanListFilter}
                      isCompare={this.isCompareView}
                      compareSpanList={this.compareSpanList}
                    />
                  )
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
            <i class='icon-monitor icon-back-up'></i>
          </div>
        )}
        <SpanDetails
          show={this.showSpanDetails}
          isFullscreen={this.isFullscreen}
          spanDetails={this.spanDetails as Span}
          onShow={v => (this.showSpanDetails = v)}
        />
      </Loading>
    );
  }
});
