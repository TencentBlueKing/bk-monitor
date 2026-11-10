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

import {
  type PropType,
  defineComponent,
  nextTick,
  onDeactivated,
  onMounted,
  onUnmounted,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { type TableSort, type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { debounce } from 'lodash';
import { useI18n } from 'vue-i18n';

import { useTable } from '../../../alarm-center/common-detail/components/panel-log/log-table/hooks/use-table';
import { DetailLoadStatus, DetailTableSkeleton } from '@/pages/alarm-center/common-detail/detail-loading';

import type {
  EClickMenuType,
  TClickMenuOpt,
} from '../../../alarm-center/common-detail/components/panel-log/log-table/typing';

import '../../../alarm-center/common-detail/components/panel-log/log-table/log-table-new.scss';

/** 距离滚动容器底部多少像素内开始请求下一页 */
const SCROLL_LOAD_GAP = 24;
/** 侧滑还没展开到可滚动高度时，不把“贴底”当成需要继续翻页 */
const MIN_SCROLL_CONTAINER_HEIGHT = 80;

/**
 * 是否继续请求下一页。
 * 容器还没有布局高度时返回 false，避免侧滑动画期间把全部页连续拉完。
 */
export const shouldLoadMoreLogs = (
  container: null | { clientHeight: number; scrollHeight: number; scrollTop: number }
) => {
  if (!container || container.clientHeight < MIN_SCROLL_CONTAINER_HEIGHT) return false;
  const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
  return distanceToBottom <= SCROLL_LOAD_GAP;
};

/**
 * 当前页是否已经没有更多数据。
 * 空页直接结束。有 total 时用已加载条数判断，否则本页不足一页就结束。
 */
export const isLogPageEnded = (loadedCount: number, pageCount: number, pageSize: number, rawTotal: unknown) => {
  if (pageCount <= 0) return true;
  const total =
    typeof rawTotal === 'number'
      ? rawTotal
      : typeof rawTotal === 'string' && rawTotal.trim() !== ''
        ? Number(rawTotal)
        : Number.NaN;
  if (Number.isFinite(total)) return loadedCount >= total;
  return pageCount < pageSize;
};

/**
 * 故障诊断日志侧滑表格。
 * 从告警中心 LogTableNew 拆出：侧滑有独立滚动容器和结束判断，不再改公共表格。
 */
export default defineComponent({
  name: 'TroubleShootingLogTable',
  props: {
    displayFields: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    getTableData: {
      type: Function,
      default: () => {},
    },
    getFieldsData: {
      type: Function,
      default: () => {},
    },
    scrollContainer: {
      type: Function as PropType<() => HTMLElement | null>,
      default: undefined,
    },
    refreshKey: {
      type: String,
      default: '',
    },
    headerAffixedTop: {
      type: Object as PropType<TdPrimaryTableProps['headerAffixedTop']>,
      default: () => null,
    },
    allowedMenuTypes: {
      type: Array as PropType<EClickMenuType[]>,
      default: () => undefined,
    },
  },
  emits: {
    clickMenu: (_opt: TClickMenuOpt) => true,
    removeField: (_fieldName: string) => true,
    addField: (_fieldName: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const wrapRef = useTemplateRef<HTMLDivElement>('wrap');
    const wrapWidth = shallowRef(800);
    const loading = shallowRef(true);
    const error = shallowRef(false);
    let requestId = 0;
    let fieldsRequestId = 0;
    const {
      tableData,
      tableColumns,
      expandedRow,
      originLogData,
      fieldsDataToColumns,
      setFieldsData,
      setWrapWidth,
      setDefaultFieldWidth,
    } = useTable({
      allowedMenuTypes: props.allowedMenuTypes,
      onClickMenu: opt => {
        emit('clickMenu', opt);
      },
      onRemoveField: fieldName => {
        emit('removeField', fieldName);
      },
      onAddField: fieldName => {
        emit('addField', fieldName);
      },
    });
    const offset = shallowRef(0);
    const limit = shallowRef(30);
    const fieldsData = shallowRef(null);
    const expandedRowKeys = shallowRef([]);
    const isEnd = shallowRef(false);
    const sortInfo = shallowRef(null);
    const scrollLoading = shallowRef(false);
    // 故障诊断侧滑始终传入滚动容器；未传入时再回退到侧滑 body
    const isCustomScroll = true;
    let scrollContainerElement: HTMLElement | null = null;
    const resizeObserver = shallowRef<ResizeObserver>();
    let containerResizeObserver: null | ResizeObserver = null;
    let debounceSetWrapWidth: null | ReturnType<typeof debounce> = null;
    // 记录滚动容器高度，用来区分“侧滑展开”和“容器被内容撑高”
    let lockedScrollContainerHeight = 0;
    let autoFillCount = 0;

    watch(
      () => props.displayFields,
      val => {
        if (!val.length) return;
        // 字段已就绪时只重排列，避免滚动过程中再次请求字段接口并把表格打成错误态
        if (fieldsData.value?.fields?.length) {
          fieldsDataToColumns(fieldsData.value.fields, val);
          return;
        }
        setTableColumns().catch(() => {
          error.value = true;
        });
      }
    );

    const setTableColumns = async () => {
      const current = ++fieldsRequestId;
      const data = await getFieldsData();
      if (current !== fieldsRequestId) return;
      fieldsData.value = data;
      setFieldsData(fieldsData.value);
      fieldsDataToColumns(fieldsData.value?.fields || [], props.displayFields);
    };

    const getTableData = async () => {
      const sort = sortInfo.value as null | {
        descending?: boolean;
        order?: string;
        prop?: string;
        sortBy?: string;
      };
      const sortBy = sort?.sortBy || sort?.prop;
      const descending = sort?.descending ?? (sort?.order === 'desc' || sort?.order === 'descending');
      const sortList = sortBy ? [[sortBy, descending ? 'desc' : 'asc']] : [];
      const res = await props.getTableData({
        offset: offset.value,
        size: limit.value,
        sortList,
      });
      return res;
    };

    const getFieldsData = async () => {
      const res = await props.getFieldsData();
      return res;
    };

    const handleExpandChange = (keys: (number | string)[]) => {
      expandedRowKeys.value = keys;
    };

    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });

    const handleContainerScroll = () => {
      if (shouldLoadMoreLogs(scrollContainerElement)) {
        handleScroll();
      }
    };

    const bindScrollContainer = () => {
      const nextContainer =
        props.scrollContainer?.() || wrapRef.value?.closest<HTMLElement>('.log-viewer-slider-body') || null;
      if (nextContainer === scrollContainerElement) return;
      scrollContainerElement?.removeEventListener('scroll', handleContainerScroll);
      containerResizeObserver?.disconnect();
      scrollContainerElement = nextContainer;
      if (!scrollContainerElement) return;
      scrollContainerElement.addEventListener('scroll', handleContainerScroll, { passive: true });
      // 侧滑展开后容器高度从 0 变为实际高度时，补一次“内容是否撑满”的检查
      containerResizeObserver = new ResizeObserver(() => {
        if (scrollContainerElement?.scrollTop === 0) {
          fillIfContentShorterThanContainer();
        }
      });
      containerResizeObserver.observe(scrollContainerElement);
    };

    /** 首屏未撑满时补下一页。用户滚到底触发的加载不在这里续拉，避免未完成布局时把后续页全部请求完。 */
    const fillIfContentShorterThanContainer = () => {
      bindScrollContainer();
      const container = scrollContainerElement;
      if (container?.scrollTop !== 0) return;
      const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      const containerExpanded =
        lockedScrollContainerHeight >= MIN_SCROLL_CONTAINER_HEIGHT &&
        container.clientHeight > lockedScrollContainerHeight + 1 &&
        distanceToBottom <= SCROLL_LOAD_GAP;
      // 已经自动补过页，容器还在跟着变高，说明高度没锁住，停止继续请求
      if (containerExpanded && autoFillCount > 0) {
        lockedScrollContainerHeight = container.clientHeight;
        return;
      }
      if (container.clientHeight >= MIN_SCROLL_CONTAINER_HEIGHT) {
        lockedScrollContainerHeight = container.clientHeight;
      }
      if (!shouldLoadMoreLogs(container)) return;
      autoFillCount += 1;
      handleScroll();
    };

    const handleScroll = async (isInit = false) => {
      if (isInit) {
        ++requestId;
        error.value = false;
        expandedRowKeys.value = [];
        offset.value = 0;
        tableData.value = [];
        originLogData.value = [];
        isEnd.value = false;
        scrollLoading.value = false;
        loading.value = false;
        autoFillCount = 0;
        lockedScrollContainerHeight = 0;
        if (scrollContainerElement) scrollContainerElement.scrollTop = 0;
      }
      if (error.value || isEnd.value || scrollLoading.value || loading.value) {
        return;
      }
      const current = ++requestId;
      if (offset.value) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }
      // 本次请求的起点。成功后按页大小前进，不能改成已加载行数，否则短页会重复请求同一页
      const requestOffset = offset.value;
      try {
        if (isInit) await setTableColumns();
        if (current !== requestId) return;
        const data = await getTableData();
        if (current !== requestId) return;
        const pageList = (data?.list || []).map((item, index) => ({
          ...item,
          // 详情接口不一定带 __id__，用页内序号兜底，避免翻页后行复用导致滚动跳动
          __id__: item?.__id__ ?? item?._meta?.__doc_id ?? `${requestOffset}-${index}`,
        }));
        tableData.value = [...tableData.value, ...pageList];
        originLogData.value = [...originLogData.value, ...(data?.origin_log_list || [])];
        isEnd.value = isLogPageEnded(
          tableData.value.length,
          pageList.length,
          limit.value,
          data?.query_config?.total ?? data?.total
        );
        offset.value = requestOffset + limit.value;
        nextTick(() => {
          requestAnimationFrame(() => {
            if (current !== requestId) return;
            if (isInit) {
              setDefaultFieldWidth();
              if (scrollContainerElement) scrollContainerElement.scrollTop = 0;
            }
            fillIfContentShorterThanContainer();
          });
        });
      } catch {
        if (current === requestId) error.value = true;
      } finally {
        if (current === requestId) {
          loading.value = false;
          scrollLoading.value = false;
        }
      }
    };
    const retry = () => {
      error.value = false;
      handleScroll(!tableData.value.length);
    };
    watch(
      () => props.refreshKey,
      val => {
        if (val) handleScroll(true);
      },
      { immediate: true }
    );

    const handleSortChange = (sort: TableSort) => {
      sortInfo.value = sort;
      handleScroll(true);
    };

    onMounted(() => {
      if (wrapRef.value) {
        wrapWidth.value = wrapRef.value.offsetWidth;
        debounceSetWrapWidth = debounce(() => {
          if (!wrapRef.value) return;
          wrapWidth.value = wrapRef.value.offsetWidth;
          setWrapWidth(wrapWidth.value);
        }, 200);
        resizeObserver.value = new ResizeObserver(() => {
          debounceSetWrapWidth?.();
        });
        resizeObserver.value.observe(wrapRef.value);
        setWrapWidth(wrapWidth.value);
        nextTick(fillIfContentShorterThanContainer);
      }
    });

    onUnmounted(() => {
      ++requestId;
      ++fieldsRequestId;
      scrollContainerElement?.removeEventListener('scroll', handleContainerScroll);
      scrollContainerElement = null;
      containerResizeObserver?.disconnect();
      containerResizeObserver = null;
      resizeObserver.value?.disconnect();
      debounceSetWrapWidth?.cancel();
    });
    onDeactivated(() => {
      expandedRowKeys.value = [];
    });

    return {
      error,
      retry,
      scrollLoading,
      tableData,
      fieldsData,
      tableColumns,
      loading,
      offset,
      expandedRowKeys,
      expandedRow,
      expandIcon,
      wrapWidth,
      isEnd,
      isCustomScroll,
      sortInfo,
      t,
      handleExpandChange,
      handleSortChange,
    };
  },
  render() {
    const loadingColumns: TdPrimaryTableProps['columns'] = this.tableColumns.length
      ? this.tableColumns
      : this.displayFields.length
        ? this.displayFields.map(colKey => ({ colKey, title: colKey }))
        : [
            { colKey: 'time', title: this.t('时间'), width: 200 },
            { colKey: 'log', title: this.t('日志内容') },
          ];
    const skeletonColumns: TdPrimaryTableProps['columns'] = this.isCustomScroll
      ? (loadingColumns.map(column => ({
          ...column,
          title: () => <span class='detail-loading-block log-table-skeleton-header' />,
        })) as unknown as TdPrimaryTableProps['columns'])
      : loadingColumns;
    const customAsyncLoadingFn = () => {
      return (
        <div
          ref='scrollRef'
          style={{
            width: `${this.wrapWidth}px`,
            position: 'sticky',
            left: 0,
          }}
          class='scroll-loading scroll-loading___observer'
        >
          <span>{this.isEnd ? this.t('到底了') : this.scrollLoading ? this.t('正加载更多内容…') : ''}</span>
        </div>
      );
    };
    return (
      <div
        ref='wrap'
        class='alarm-detail-log-table-new'
      >
        <DetailLoadStatus
          error={this.error}
          onRetry={this.retry}
        />
        {this.loading ? (
          <DetailTableSkeleton columns={skeletonColumns} />
        ) : this.tableData.length ? (
          <PrimaryTable
            class={'panel-log-log-table'}
            columns={[
              ...this.tableColumns,
              {
                width: '32px',
                minWidth: '32px',
                fixed: 'right',
                align: 'center',
                resizable: false,
                thClassName: '__table-custom-setting-col__',
                colKey: '__col_setting__',
                title: () => this.$slots.settingBtn?.(),
                cell: () => undefined,
              },
            ]}
            rowspanAndColspan={({ colIndex }) => {
              return {
                rowspan: 1,
                colspan: colIndex === this.tableColumns.length ? 2 : 1,
              };
            }}
            asyncLoading={(this.tableData.length && !this.error ? customAsyncLoadingFn : false) as any}
            data={this.tableData}
            expandedRow={this.expandedRow}
            expandedRowKeys={this.expandedRowKeys}
            expandIcon={this.expandIcon}
            expandOnRowClick={true}
            headerAffixedTop={this.headerAffixedTop}
            horizontalScrollAffixedBottom={this.headerAffixedTop}
            hover={true}
            needCustomScroll={false}
            resizable={true}
            rowKey={'__id__'}
            size={'small'}
            sort={this.sortInfo}
            tableLayout='fixed'
            onExpandChange={this.handleExpandChange}
            onSortChange={this.handleSortChange}
          />
        ) : (
          !this.error && this.$slots?.empty?.()
        )}
      </div>
    );
  },
});
