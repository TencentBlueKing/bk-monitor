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
import {
  computed,
  defineComponent,
  ref,
  watch,
  onMounted,
  shallowRef,
  set,
} from 'vue';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';
import MainHeader from './main-header';
import $http from '@/api';
import ClusteringLoader from '@/skeleton/clustering-loader.vue';
import AiAssitant from '@/global/ai-assitant.tsx';
import ContentTable, { IPagination, GroupListState } from './content-table';
import { type LogPattern } from '@/services/log-clustering';
import { type IResponseData } from '@/services/type';

import useRetrieveEvent from '@/hooks/use-retrieve-event';
import { RetrieveEvent } from '@/views/retrieve-helper';

import { orderBy, debounce } from 'lodash-es';
import useIntersectionObserver from '@/hooks/use-intersection-observer';
import ScrollTop from '@/views/retrieve-v2/components/scroll-top';
import ScrollXBar from '@/views/retrieve-v2/components/scroll-x-bar';
import useWheel from '@/hooks/use-wheel';
import './index.scss';

export interface TableInfo {
  group: string[];
  dataList: LogPattern[];
}

export interface ITableItem {
  groupKey: string;
  hashKey: string;
  isGroupRow: boolean;
  index: number;
  group?: string[];
  data?: LogPattern;
  childCount?: number;
  hidden?: boolean;
}

export default defineComponent({
  name: 'LogTable',
  components: {
    MainHeader,
    ClusteringLoader,
    ContentTable,
    AiAssitant,
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
    const aiAssitantRef = ref<any>(null);
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
    const { addEvent } = useRetrieveEvent();

    const retrieveParams = computed(() => store.getters.retrieveParams);
    const showGroupBy = computed(
      () =>
        props.requestData?.group_by.length > 0 && displayType.value === 'group',
    );

    const smallLoaderWidthList = computed(() => {
      return props.requestData?.year_on_year_hour > 0
        ? loadingWidthList.compared
        : loadingWidthList.notCompared;
    });

    const tableColumnWidth = computed(() =>
      store.getters.isEnLanguage ? enTableWidth : cnTableWidth,
    );

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
      (paginationRef.value?.childNodes[0] as HTMLElement)?.style?.setProperty(
        'visibility',
        'hidden',
      );
    }, 180);

    /**
     * 分页器观察器
     */
    useIntersectionObserver(paginationRef, (entry) => {
      if (entry.isIntersecting) {
        (paginationRef.value?.childNodes[0] as HTMLElement)?.style?.setProperty(
          'visibility',
          'visible',
        );
        if (
          pagination.value.current * pagination.value.limit <
          pagination.value.count
        ) {
          pagination.value.current += 1;
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
     * 快速哈希
     * @param text
     * @param length
     * @returns
     */
    function fastHash(text, length = 16) {
      let h1 = 0xdeadbeef;
      let h2 = 0x41c6ce57;

      for (let i = 0; i < text.length; i++) {
        const char = text.charCodeAt(i);
        h1 = Math.imul(h1 ^ char, 2654435761);
        h2 = Math.imul(h2 ^ char, 1597334677);

        // 32 位循环移位
        h1 = (h1 << 13) | (h1 >>> 19);
        h2 = (h2 << 17) | (h2 >>> 15);
      }

      // 组合为 53 位整数（JavaScript 安全整数范围）
      const combined = (h1 & 0x1fffff) * 0x1000000000 + (h2 & 0xfffffff);
      return combined.toString(36).padStart(length, '0').slice(-length);
    }

    /**
     * 分组模式排序
     */
    const sortGroupList = (
      targetList: ITableItem[],
      filterFn: (_arg: ITableItem) => boolean,
    ) => {
      const groupList: ITableItem[] = [];
      const sortObj = Object.entries(filterSortMap.value.sort).find(
        (item) => !!item[1],
      );
      const groupMap = new Map<string, ITableItem[]>();
      pagination.value.visibleCount = 0;

      for (const item of targetList) {
        if (!groupMap.has(item.hashKey)) {
          groupMap.set(item.hashKey, []);
        }
        if (item.isGroupRow) {
          groupList.push(item);
        } else {
          groupMap.get(item.hashKey).push(item);
        }
      }

      const resultList: ITableItem[] = [];
      for (const group of groupList) {
        resultList.push(group);
        let childList = groupMap.get(group.hashKey);

        if (sortObj) {
          const [field, order] = sortObj;
          const sortField = order === 'none' ? 'index' : `data.${field}`;
          const orders = (order === 'none' ? 'asc' : order) as 'asc' | 'desc';
          childList = orderBy(childList, [sortField], orders);
        }

        let isHiddenGroup = true;
        for (const c of childList) {
          c.hidden = !filterFn(c);
          resultList.push(c);

          if (!c.hidden) {
            isHiddenGroup = false;
            pagination.value.visibleCount += 1;
          }
        }
        group.hidden = isHiddenGroup;
      }

      groupMap.clear();
      return resultList;
    };

    /**
     * 平铺模式排序
     * @param targetList
     * @param filterFn
     */
    const sortFlattenList = (
      targetList: ITableItem[],
      filterFn: (_arg: ITableItem) => boolean,
    ) => {
      const copyList = [];
      let childList = [];
      pagination.value.visibleCount = 0;

      const sortObj = Object.entries(filterSortMap.value.sort).find(
        (item) => !!item[1],
      );

      for (let i = 0; i < targetList.length; i++) {
        const item = targetList[i];
        if (item.isGroupRow) {
          copyList.push(item);
        } else {
          childList.push(item);
        }
      }

      if (sortObj) {
        const [field, order] = sortObj;
        const sortField = order === 'none' ? 'index' : `data.${field}`;
        const orders = (order === 'none' ? 'asc' : order) as 'asc' | 'desc';

        childList = orderBy(childList, [sortField], orders);
      }

      for (const c of childList) {
        c.hidden = !filterFn(c);
        copyList.push(c);

        if (!c.hidden) {
          pagination.value.visibleCount += 1;
        }
      }

      return copyList;
    };

    /**
     * 排序 | 过滤时更新列表数据
     * @param list
     */
    const updateTableList = (list?: ITableItem[]) => {
      const targetList = list ?? tableList.value;
      const owners = filterSortMap.value.filter.owners;
      const remark = filterSortMap.value.filter.remark;
      const isRemarked = remark[0] === 'remarked';
      const ownersMap = owners.reduce<Record<string, boolean>>(
        (map, item) => Object.assign(map, { [item]: true }),
        {},
      );

      const filterOwners = owners.length > 0;
      const filterRemark = remark.length > 0;
      const noOwner = owners.length === 1 && owners[0] === 'no_owner';

      /**
       * 检索当前行是否满足过滤条件
       * @param item
       * @returns
       */
      const filterFn = (item: ITableItem) => {
        let result = true;
        if (filterOwners) {
          result = noOwner
            ? (item.data?.owners?.value.length ?? 0) > 0
            : (item.data?.owners.value ?? []).some((item) => !!ownersMap[item]);
        }

        if (filterRemark && result) {
          result = isRemarked
            ? (item.data?.remark ?? []).length > 0
            : !item.data?.remark.length;
        }

        return result;
      };

      if (
        displayType.value === 'group' &&
        props.requestData.group_by?.length > 0
      ) {
        tableList.value = sortGroupList(targetList, filterFn);
        return;
      }

      tableList.value = sortFlattenList(targetList, filterFn);
    };

    /**
     * 设置分页器计数
     * @returns
     */
    const setPaginationCount = () => {
      if (displayType.value === 'group') {
        pagination.value.count =
          pagination.value.groupCount + pagination.value.childCount;
        return;
      }

      pagination.value.count = pagination.value.childCount;
    };

    const refreshTable = () => {
      // loading中，或者没有开启数据指纹功能，或当前页面初始化或者切换索引集时不允许起请求
      if (
        tableLoading.value ||
        !props.clusterSwitch ||
        !props.isClusterActive
      ) {
        return;
      }
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
      const addition = retrieveParams.value.addition.reduce((list, item) => {
        if (!item.disabled) {
          list.push({
            field: item.field,
            operator: item.operator,
            value:
              item.hidden_values && item.hidden_values.length > 0
                ? item.value.filter(
                    (value) => !item.hidden_values.includes(value),
                  )
                : item.value,
          });
        }
        return list;
      }, []);
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
            data: {
              addition,
              size,
              keyword,
              ip_chooser,
              host_scopes,
              interval,
              timezone,
              start_time,
              end_time,
              ...props.requestData,
            },
          },
          { cancelWhenRouteChange: false },
        ) as Promise<IResponseData<LogPattern[]>>
      ) // 由于回填指纹的数据导致路由变化，故路由变化时不取消请求
        .then((res) => {
          let listMap = new Map<string, LogPattern[]>();
          let groupKeys = [];

          res.data.forEach((item) => {
            const groupList = item.group?.map(
              (g, i) => `${props.requestData?.group_by[i] ?? '#'}=${g}`,
            ) ?? ['#'];

            const groupKey = groupList.length ? groupList.join(' | ') : '#';
            if (!listMap.has(groupKey)) {
              listMap.set(groupKey, []);
              groupKeys.push(groupKey);
            }

            listMap.get(groupKey).push(item);
          });

          let index = 0;
          const groupState: GroupListState = {};
          const tempList: ITableItem[] = [];
          let hasOpenedGroup = false;

          groupKeys.forEach((key) => {
            const children = listMap.get(key) ?? [];
            const hashKey = fastHash(key);
            index += 1;
            tempList.push({
              groupKey: key,
              isGroupRow: true,
              group: children[0].group,
              childCount: children.length,
              hashKey,
              index,
            });

            const isOpen = groupListState.value[hashKey]?.isOpen ?? false;
            Object.assign(groupState, {
              [hashKey]: {
                isOpen,
              },
            });

            if (isOpen) {
              hasOpenedGroup = true;
            }

            children.forEach((item) => {
              index += 1;
              tempList.push({
                groupKey: key,
                hashKey,
                isGroupRow: false,
                data: Object.assign(item, {
                  id: index,
                  owners: ref(item.owners),
                }),
                index,
              });
            });
          });

          updateTableList(tempList);

          if (!hasOpenedGroup) {
            groupState[tempList[0].hashKey]!.isOpen = true;
          }

          groupListState.value = groupState;
          pagination.value.groupCount = groupKeys.length;
          pagination.value.childCount = res.data.length;
          setPaginationCount();
          setTimeout(computedScrollXWidth);
          listMap.clear();
          listMap = null;
          groupKeys = null;
        })
        .finally(() => {
          tableLoading.value = false;
        });
    };

    addEvent(
      [RetrieveEvent.SEARCH_VALUE_CHANGE, RetrieveEvent.SEARCH_TIME_CHANGE,RetrieveEvent.AUTO_REFRESH],
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

    const handleOpenAi = (row: LogPattern, index: number) => {
      aiAssitantRef.value.open(true, {
        space_uid: store.getters.spaceUid,
        index_set_id: store.getters.indexId,
        log_data: row,
        index,
      });
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
      for (const element of rootElement.value.querySelectorAll(
        '.bklog-fill-offset-x',
      )) {
        element.scrollLeft = scrollLeft;
      }
    };

    let isAnimating = false;

    useWheel({
      target: rootElement,
      callback: (event: WheelEvent) => {
        const maxOffset =
          scrollXBarInnerWidth.value - scrollXBarOuterWidth.value;
        let scrollLeft = 0;
        // 检查是否按住 shift 键
        if (event.shiftKey) {
          // 当按住 shift 键时，让 refScrollXBar 执行系统默认的横向滚动能力
          if (maxOffset > 0 && refScrollXBar.value) {
            event.stopPropagation();
            event.stopImmediatePropagation();
            event.preventDefault();

            // 使用系统默认的滚动行为，通过 refScrollXBar 执行横向滚动
            const currentScrollLeft =
              refScrollXBar.value.getScrollLeft?.() || 0;
            const scrollStep = event.deltaY || event.deltaX;
            const newScrollLeft = Math.max(
              0,
              Math.min(maxOffset, currentScrollLeft + scrollStep),
            );

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
        setPaginationCount();
        tableLoading.value = false;
      });
    };

    /**
     * 分组展开收起功能回调函数
     * @param row
     */
    const handleGroupStateChange = (row: ITableItem) => {
      if (groupListState.value[row.hashKey] === undefined) {
        set(groupListState.value, row.hashKey, {
          isOpen: false,
        });
      }

      groupListState.value[row.hashKey].isOpen =
        !groupListState.value[row.hashKey].isOpen;
    };

    onMounted(() => {
      refreshTable();
    });

    expose({
      refreshTable,
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

      if (
        retrieveParams.value.addition.length > 0 ||
        owners.length > 0 ||
        remark.length > 0
      ) {
        option.type = 'search-empty';
        option.text = t('搜索结果为空');
      }

      return (
        <bk-exception type={option.type} scene='part' style='margin-top: 80px'>
          <span>{option.text}</span>
        </bk-exception>
      );
    };

    return () => (
      <div class='log-table-main' ref={rootElement}>
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
                on-open-ai={handleOpenAi}
                on-open-cluster-config={() => emit('open-cluster-config')}
                on-group-state-change={handleGroupStateChange}
              />,
            ]
          ) : (
            getExceptionOption()
          )}
        </div>
        <div ref={paginationRef} style='width: 100%;'>
          <div style='display: flex; justify-content: center;width: 100%; padding: 4px; visibility: hidden;'>
            <span>loading ...</span>
          </div>
        </div>
        <AiAssitant ref={aiAssitantRef} on-close='handleAiClose' />
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
