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
import { computed, defineComponent, ref, watch, onMounted, onBeforeUnmount, shallowRef, set, markRaw } from 'vue';
import useStore from '@/hooks/use-store';
import { moduleLargeDataCacheService, clusterTableWorkerService } from '@/storage';
import useLocale from '@/hooks/use-locale';
import MainHeader from './main-header';
import $http from '@/api';
import ClusteringLoader from '@/skeleton/clustering-loader.vue';
import ContentTable, { IPagination, GroupListState } from './content-table';
import { type LogPattern } from '@/services/log-clustering';
import { type IResponseData } from '@/services/type';

import useRetrieveEvent from '@/hooks/use-retrieve-event';
import { RetrieveEvent } from '@/views/retrieve-helper';

import { debounce } from 'lodash-es';
import useIntersectionObserver from '@/hooks/use-intersection-observer';
import ScrollTop from '@/views/retrieve-v2/components/scroll-top';
import ScrollXBar from '@/views/retrieve-v2/components/scroll-x-bar';
import useWheel from '@/hooks/use-wheel';
import {
  getOwnerList,
  toPlainOpenMap,
  type ClusterPipelineInput,
  type ClusterViewResult,
  type ITableItem,
  type WalkVisibleWindowOptions,
} from './cluster-table-pipeline';
import './index.scss';

export type { ITableItem } from './cluster-table-pipeline';

export interface TableInfo {
  group: string[];
  dataList: LogPattern[];
}

export default defineComponent({
  name: 'LogTable',
  components: {
    MainHeader,
    ClusteringLoader,
    ContentTable,
  },
  props: {
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    requestData: {
      type: Object,
      require: true,
      default: () => ({}),
    },
    indexId: {
      type: String,
      require: true,
      default: undefined,
    },
  },
  setup(props, { expose, emit }) {
    const store = useStore();
    const { t } = useLocale();

    const initFilterSortMap = () => ({
      filter: {
        owners: [],
        remark: [],
      },
      sort: {
        count: '',
        percentage: '',
        year_on_year_count: '',
        year_on_year_percentage: '',
      },
    });

    const logTableRef = ref<HTMLElement>();
    const tablesRef = ref<any>(null);
    const mainHeaderRef = ref<any>();
    // const aiAssitantRef = ref<any>(null);
    const tableLoading = ref(false);
    const widthList = ref<Record<string, string>>({});
    const filterSortMap = ref(initFilterSortMap());
    const displayType = ref('group');
    const paginationRef = ref<HTMLElement>();

    const rootElement = ref<HTMLElement>();
    const scrollXBarOuterWidth = ref(0);
    const scrollXBarInnerWidth = ref(0);
    const refScrollXBar = ref<any>();

    const pagination = ref<IPagination>({
      current: 1,
      limit: 50,
      count: 0,
      groupCount: 0,
      childCount: 0,
      visibleCount: 0,
    });

    const tableList = shallowRef<ITableItem[]>([]);
    const groupListState = ref<GroupListState>({});
    const rawDataScope = ref(''); // 原始接口数据 IndexedDB 分块缓存 scope
    const rawDataCount = ref(0);
    const { addEvent } = useRetrieveEvent();
    let rawSnapshot: LogPattern[] = [];
    let pipelineToken = 0;

    const buildPipelineInput = (): ClusterPipelineInput => ({
      displayType: displayType.value,
      filterSort: {
        filter: {
          owners: [...(filterSortMap.value.filter.owners ?? [])],
          remark: [...(filterSortMap.value.filter.remark ?? [])],
        },
        sort: { ...filterSortMap.value.sort },
      },
      groupBy: [...(props.requestData?.group_by ?? [])],
      raw: rawSnapshot,
    });

    const getWindowOptions = (): WalkVisibleWindowOptions => ({
      displayType: displayType.value,
      groupByLength: props.requestData?.group_by?.length ?? 0,
      limit: Math.max(pagination.value.current, 1) * pagination.value.limit,
      openMap: toPlainOpenMap(groupListState.value),
    });

    const syncGroupStateFromMeta = (
      openMap: ClusterViewResult['openMap'] = {},
    ) => {
      const next: GroupListState = {};
      Object.keys(groupListState.value).forEach((key) => {
        if (groupListState.value[key]?.isOpen) {
          next[key] = { isOpen: true };
        }
      });
      Object.keys(openMap).forEach((key) => {
        if (openMap[key]?.isOpen) {
          next[key] = { isOpen: true };
        }
      });
      groupListState.value = next;
    };

    const applyViewResult = (view: ClusterViewResult) => {
      pagination.value.groupCount = view.groupCount;
      pagination.value.childCount = view.childCount;
      pagination.value.visibleCount = view.visibleCount;
      setPaginationCount();
      syncGroupStateFromMeta(view.openMap);
      tableList.value = (view.window ?? []).map(item => markRaw(item));
    };

    const ensureRawSnapshot = async () => {
      if (rawSnapshot.length) return rawSnapshot;
      if (!rawDataScope.value || !rawDataCount.value) return [];
      rawSnapshot = await moduleLargeDataCacheService.getSlice(rawDataScope.value, 0, rawDataCount.value);
      return rawSnapshot;
    };

    const applyWindow = async () => {
      const { view, viaWorker } = await clusterTableWorkerService.walk(getWindowOptions());
      if (!viaWorker && !(view.window ?? []).length) {
        await ensureRawSnapshot();
        if (rawSnapshot.length) {
          await runPipeline(false);
          return;
        }
      }
      tableList.value = (view.window ?? []).map(item => markRaw(item));
    };

    const runPipeline = async (resetWindow = true) => {
      const token = ++pipelineToken;
      if (resetWindow) {
        pagination.value.current = 1;
      }
      const input = buildPipelineInput();
      const { view, viaWorker } = await clusterTableWorkerService.run(input, getWindowOptions());
      if (token !== pipelineToken) return;
      if (!viaWorker && !(view.window ?? []).length && !input.raw?.length) {
        await ensureRawSnapshot();
        if (rawSnapshot.length && token === pipelineToken) {
          await runPipeline(resetWindow);
          return;
        }
      }
      if (viaWorker) {
        rawSnapshot = [];
      }
      applyViewResult(view);
    };

    const retrieveParams = computed(() => store.getters.retrieveParams);
    const showGroupBy = computed(() => props.requestData?.group_by.length > 0 && displayType.value === 'group');

    const smallLoaderWidthList = computed(() => {
      return props.requestData?.year_on_year_hour > 0 ? loadingWidthList.compared : loadingWidthList.notCompared;
    });

    const tableColumnWidth = computed(() => (store.getters.isEnLanguage ? enTableWidth : cnTableWidth));

    const loadingWidthList = {
      // loading表头宽度列表
      global: [''],
      notCompared: [150, 90, 90, ''],
      compared: [150, 90, 90, 100, 100, ''],
    };

    const enTableWidth = {
      number: '110',
      percentage: '116',
      year_on_year_count: '171',
      year_on_year_percentage: '171',
    };
    const cnTableWidth = {
      number: '91',
      percentage: '96',
      year_on_year_count: '101',
      year_on_year_percentage: '101',
    };

    watch(
      () => props.requestData,
      () => {
        filterSortMap.value = initFilterSortMap();
      },
      {
        deep: true,
      },
    );

    /**
     * 加载更多触发元素隐藏操作
     */
    const debounceHiddenPaginationLoading = debounce(() => {
      (paginationRef.value?.childNodes[0] as HTMLElement)?.style?.setProperty('visibility', 'hidden');
    }, 180);

    /**
     * 分页器观察器
     */
    useIntersectionObserver(paginationRef, (entry) => {
      if (entry.isIntersecting) {
        (paginationRef.value?.childNodes[0] as HTMLElement)?.style?.setProperty('visibility', 'visible');
        if (pagination.value.current * pagination.value.limit < pagination.value.count) {
          pagination.value.current += 1;
          void applyWindow();
        }
      }

      debounceHiddenPaginationLoading();
    });

    /**
     * 计算自定义横向滚动条宽度
     */
    const computedScrollXWidth = () => {
      scrollXBarInnerWidth.value = tablesRef.value?.$el?.scrollWidth;
      scrollXBarOuterWidth.value = tablesRef.value?.$el?.offsetWidth;
    };

    /**
     * 排序 | 过滤时更新列表数据
     */
    const updateTableList = () => {
      void runPipeline(true);
    };

    /**
     * 设置分页器计数
     * @returns
     */
    const setPaginationCount = () => {
      if (displayType.value === 'group') {
        pagination.value.count = pagination.value.groupCount + pagination.value.childCount;
        return;
      }

      pagination.value.count = pagination.value.childCount;
    };

    const getClusterSearchAddition = () => {
      return (retrieveParams.value.addition ?? []).reduce((list: any[], item) => {
        if (!item.disabled) {
          list.push({
            field: item.field,
            operator: item.operator,
            value:
              item.hidden_values && item.hidden_values.length > 0
                ? item.value.filter(value => !item.hidden_values.includes(value))
                : item.value,
          });
        }
        return list;
      }, []);
    };

    const getClusterSearchData = (overrides: Record<string, any> = {}) => {
      const {
        start_time,
        end_time,
        size,
        keyword = '*',
        ip_chooser,
        host_scopes,
        interval,
        timezone,
      } = retrieveParams.value;

      return {
        bk_biz_id: store.state.bkBizId,
        addition: getClusterSearchAddition(),
        size,
        keyword,
        ip_chooser,
        host_scopes,
        interval,
        timezone,
        start_time,
        end_time,
        ...props.requestData,
        ...overrides,
      };
    };

    const getPatternOriginLog = async (row: LogPattern) => {
      const signature = row.signature?.toString();
      if (!signature) {
        return '';
      }
      const addition = [
        ...getClusterSearchAddition(),
        {
          field: `__dist_${props.requestData?.pattern_level}`,
          operator: 'is',
          value: signature,
        },
      ];
      const res = (await $http.request(
        '/logClustering/clusterSearch',
        {
          params: {
            index_set_id: props.indexId,
          },
          data: getClusterSearchData({
            addition,
            size: 1,
            include_origin_log: true,
            show_new_pattern: false,
            filter_not_clustering: false,
          }),
        },
        { catchIsShowMessage: false },
      )) as IResponseData<LogPattern[]>;

      return res.data?.[0]?.origin_log ?? '';
    };

    const refreshTable = () => {
      // loading中，或者没有开启数据指纹功能，或当前页面初始化或者切换索引集时不允许起请求
      if (tableLoading.value || !props.clusterSwitch || !props.isClusterActive) {
        return;
      }
      tableList.value = [];
      tableLoading.value = true;
      pagination.value.current = 1;
      pagination.value.count = 0;
      (
        $http.request(
          '/logClustering/clusterSearch',
          {
            params: {
              index_set_id: props.indexId,
            },
            data: getClusterSearchData(),
          },
          { cancelWhenRouteChange: false },
        ) as Promise<IResponseData<LogPattern[]>>
      ) // 由于回填指纹的数据导致路由变化，故路由变化时不取消请求
        .then(async (res) => {
          // 原始接口数据不再 structuredClone 到响应式内存，分块镜像到 IndexedDB，下载时按需读取。
          const responseList = (Array.isArray(res.data) ? res.data : []).map((item) => {
            const nextItem = {
              ...item,
              owners: getOwnerList(item.owners),
            };
            return markRaw(nextItem);
          });
          const nextScope = moduleLargeDataCacheService.createScope('log-clustering', {
            indexId: props.indexId,
            requestData: props.requestData,
          });
          const prevScope = rawDataScope.value;
          rawDataScope.value = nextScope;
          rawDataCount.value = responseList.length;
          moduleLargeDataCacheService.replaceList(nextScope, responseList, 50).catch(error => {
            console.warn('[cluster-cache] persist raw data failed', error);
          });
          if (prevScope) {
            moduleLargeDataCacheService.clear(prevScope).catch(() => {});
          }
          rawSnapshot = responseList;
          await runPipeline(true);
          setTimeout(computedScrollXWidth);
        })
        .catch(() => {})
        .finally(() => {
          tableLoading.value = false;
        });
    };

    addEvent(
      [RetrieveEvent.SEARCH_VALUE_CHANGE, RetrieveEvent.SEARCH_TIME_CHANGE, RetrieveEvent.AUTO_REFRESH],
      refreshTable,
    );

    const handleColumnFilter = (field: string, value: any) => {
      filterSortMap.value.filter[field] = value;
      updateTableList();
    };

    const handleColumnSort = (field: string, order: string) => {
      Object.keys(filterSortMap.value.sort).forEach((key) => {
        if (key !== field) {
          filterSortMap.value.sort[key] = '';
        }
      });
      filterSortMap.value.sort[field] = order;
      updateTableList();
    };

    /**
     * 拖拽改变列宽
     */
    const handleHeaderResizeColumn = () => {
      const columnWidth = mainHeaderRef.value.getColumnWidthList() ?? [];
      columnWidth.forEach(([name, width]) => {
        if (name !== null && name !== 'null') {
          set(widthList.value, name, width);
        }
      });
      setTimeout(computedScrollXWidth);
    };

    const handleScrollTop = () => {
      pagination.value.current = 1;
    };

    const handleScrollXChange = (event) => {
      const scrollLeft = (event.target as HTMLElement)?.scrollLeft || 0;
      for (const element of rootElement.value.querySelectorAll('.bklog-fill-offset-x')) {
        element.scrollLeft = scrollLeft;
      }
    };

    let isAnimating = false;

    useWheel({
      target: rootElement,
      callback: (event: WheelEvent) => {
        const maxOffset = scrollXBarInnerWidth.value - scrollXBarOuterWidth.value;
        let scrollLeft = 0;
        // 检查是否按住 shift 键
        if (event.shiftKey) {
          // 当按住 shift 键时，让 refScrollXBar 执行系统默认的横向滚动能力
          if (maxOffset > 0 && refScrollXBar.value) {
            event.stopPropagation();
            event.stopImmediatePropagation();
            event.preventDefault();

            // 使用系统默认的滚动行为，通过 refScrollXBar 执行横向滚动
            const currentScrollLeft = refScrollXBar.value.getScrollLeft?.() || 0;
            const scrollStep = event.deltaY || event.deltaX;
            const newScrollLeft = Math.max(0, Math.min(maxOffset, currentScrollLeft + scrollStep));

            refScrollXBar.value.scrollLeft(newScrollLeft);
            scrollLeft = newScrollLeft;
            handleScrollXChange({ target: { scrollLeft } });
          }
          return;
        }

        if (event.deltaX !== 0 && maxOffset > 0) {
          event.stopPropagation();
          event.stopImmediatePropagation();
          event.preventDefault();
          if (!isAnimating) {
            isAnimating = true;
            requestAnimationFrame(() => {
              isAnimating = false;
              const nextOffset = scrollLeft + event.deltaX;
              if (nextOffset <= maxOffset && nextOffset >= 0) {
                scrollLeft += event.deltaX;
                refScrollXBar.value?.scrollLeft(nextOffset);
                handleScrollXChange({ target: { scrollLeft } });
              }
            });
          }
        }
      },
    });

    const handleDisplayTypeChange = (value: string) => {
      tableLoading.value = true;
      pagination.value.current = 1;
      pagination.value.count = 0;
      setTimeout(() => {
        displayType.value = value;
        updateTableList();
        setPaginationCount();
        tableLoading.value = false;
      });
    };

    /**
     * 分组展开收起功能回调函数
     * @param row
     */
    const handleGroupStateChange = (row: ITableItem) => {
      const isOpen = !groupListState.value[row.hashKey]?.isOpen;
      if (isOpen) {
        set(groupListState.value, row.hashKey, { isOpen: true });
      } else {
        const next = { ...groupListState.value };
        delete next[row.hashKey];
        groupListState.value = next;
      }
      void applyWindow();
    };

    const handleRowUpdated = () => {
      tableList.value = tableList.value.slice();
    };

    onMounted(() => {
      refreshTable();
    });

    onBeforeUnmount(() => {
      if (rawDataScope.value) {
        moduleLargeDataCacheService.clear(rawDataScope.value).catch(() => {});
      }
      void clusterTableWorkerService.clear();
      tableList.value = [];
      rawSnapshot = [];
      groupListState.value = {};
      rawDataCount.value = 0;
    });

    expose({
      refreshTable,
      isLoading: () => tableLoading.value,
      getRawData: async () => {
        // 返回原始接口数据：从 IndexedDB 分块读取，避免组件长期持有大数组。
        if (!rawDataScope.value) return [];
        return moduleLargeDataCacheService.getSlice(rawDataScope.value, 0, rawDataCount.value);
      },
      getRawDataCount: () => rawDataCount.value,
      getDisplayMode: () => displayType.value,
    });

    /**
     * 可渲染结果为空的时候展示错误文本和类型
     * @returns
     */
    const getExceptionOption = () => {
      const owners = filterSortMap.value.filter.owners;
      const remark = filterSortMap.value.filter.remark;
      const option = {
        type: 'empty',
        text: t('暂无数据'),
      };

      if (retrieveParams.value.addition.length > 0 || owners.length > 0 || remark.length > 0) {
        option.type = 'search-empty';
        option.text = t('搜索结果为空');
      }

      return (
        <bk-exception
          type={option.type}
          scene='part'
          style='margin-top: 80px'
        >
          <span>{option.text}</span>
        </bk-exception>
      );
    };

    return () => (
      <div
        class='log-table-main'
        ref={rootElement}
      >
        {props.requestData?.group_by.length > 0 && (
          <bk-radio-group
            class='display-type-main'
            value={displayType.value}
            on-change={handleDisplayTypeChange}
          >
            <bk-radio value='flatten'>{t('平铺模式')}</bk-radio>
            <bk-radio value='group'>{t('分组模式')}</bk-radio>
          </bk-radio-group>
        )}
        <main-header
          class='bklog-fill-offset-x'
          ref={mainHeaderRef}
          requestData={props.requestData}
          tableColumnWidth={tableColumnWidth.value}
          indexId={props.indexId}
          displayMode={displayType.value}
          on-column-filter={handleColumnFilter}
          on-column-sort={handleColumnSort}
          on-resize-column={handleHeaderResizeColumn}
        />
        <div
          ref={logTableRef}
          class='table-list-content'
          style={{ padding: showGroupBy.value ? '0 12px' : '0px' }}
          v-bkloading={{ isLoading: tableLoading.value }}
        >
          {tableLoading.value ? (
            <clustering-loader
              width-list={smallLoaderWidthList.value}
              is-loading
            />
          ) : pagination.value.visibleCount > 0 ? (
            [
              <ContentTable
                ref={tablesRef}
                class='bklog-fill-offset-x'
                tableList={tableList.value}
                widthList={widthList.value}
                displayMode={displayType.value}
                requestData={props.requestData}
                tableColumnWidth={tableColumnWidth.value}
                groupListState={groupListState.value}
                pagination={pagination.value}
                indexId={props.indexId}
                getPatternOriginLog={getPatternOriginLog}
                on-open-cluster-config={() => emit('open-cluster-config')}
                on-group-state-change={handleGroupStateChange}
                on-row-updated={handleRowUpdated}
              />,
            ]
          ) : (
            getExceptionOption()
          )}
        </div>
        <div
          ref={paginationRef}
          style='width: 100%;'
        >
          <div style='display: flex; justify-content: center;width: 100%; padding: 4px; visibility: hidden;'>
            <span>loading ...</span>
          </div>
        </div>
        <ScrollTop on-scroll-top={handleScrollTop}></ScrollTop>
        <ScrollXBar
          ref={refScrollXBar}
          outerWidth={scrollXBarOuterWidth.value}
          innerWidth={scrollXBarInnerWidth.value}
          right={26}
          on-scroll-change={handleScrollXChange}
        ></ScrollXBar>
      </div>
    );
  },
});
