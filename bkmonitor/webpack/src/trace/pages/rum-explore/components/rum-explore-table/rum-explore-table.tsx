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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
import { type PropType, computed, defineComponent, nextTick, onBeforeUnmount, toRef, useTemplateRef, watch } from 'vue';

import { Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import ExploreFieldSetting from '../../../trace-explore/components/explore-field-setting/explore-field-setting';
import StatisticsList from '../../../trace-explore/components/statistics-list';
import ExploreConditionMenu from '../../../trace-explore/components/trace-explore-table/components/explore-condition-menu';
import { type IStatisticsFieldItem, useFieldStatisticsPopover } from '../../composables/use-field-statistics-popover';
import { RUM_EXPLORE_VIEW_CLASS } from '../../constants';
import { statisticsApi } from '../../services/rum-search';
import { useCellConditionMenu } from './hooks/use-cell-condition-menu';
import { useScenarioRenderer } from './hooks/use-scenario-renderer';
import { useTableScrollOptimize } from '@/hooks/use-table-scroll-optimize';
import CommonTable from '@/pages/alarm-center/components/alarm-table/components/common-table/common-table';
import ExploreTableEmpty from '@/pages/trace-explore/components/trace-explore-table/components/explore-table-empty';

import type { TimeRangeType } from '../../../../components/time-range/utils';
import type { BaseTableColumn } from '../../../trace-explore/components/trace-explore-table/typing';
import type { IRumCommonParams, IRumField, IRumSpanRecord, RumMode } from '../../typings';
import type { ConditionChangeEvent } from '@/pages/trace-explore/typing';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './rum-explore-table.scss';

export default defineComponent({
  name: 'RumExploreTable',
  props: {
    /** 检索视角，决定表格场景渲染器（span / view / session） */
    mode: {
      type: String as PropType<RumMode>,
      default: 'span',
    },
    /** 表格数据：当前分页/滚动已加载的 RUM Span 记录 */
    data: {
      type: Array as PropType<IRumSpanRecord[]>,
      default: () => [],
    },
    /** 基础列配置（含列宽覆盖），由上层 useRumColumnConfig 提供 */
    baseColumns: {
      type: Array as PropType<BaseTableColumn[]>,
      required: true,
    },
    /** 可作为列的字段全集，供字段设置使用 */
    displayableFields: {
      type: Array as PropType<IRumField[]>,
      default: () => [],
    },
    /** 是否显示列设置：span 视角选中具体类型（特殊态）时由类型决定列，隐藏设置入口 */
    showSettings: {
      type: Boolean,
      default: true,
    },
    /** 表格初始加载状态（用于展示全屏 loading） */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 触底加载中 */
    scrollLoading: {
      type: Boolean,
      default: false,
    },
    /** 是否还有更多数据，控制触底加载与 loading 提示展示 */
    hasMore: {
      type: Boolean,
      default: false,
    },
    /** 滚动容器选择器 */
    scrollContainerSelector: {
      type: String,
      default: `.${RUM_EXPLORE_VIEW_CLASS}`,
    },
    /** 表格排序信息,字符串格式，以id为例：倒序 => -id；正序 => id； */
    sort: {
      type: [String, Array] as PropType<string | string[]>,
    },
    /** 统计分析的查询上下文 */
    commonParams: {
      type: Object as PropType<IRumCommonParams>,
      default: () => ({}),
    },
    /** 当前检索的时间范围，用于字段统计分析 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
    /** 字段映射表：按字段名快速查找字段元数据（性能优化方案，非必填） */
    fieldMap: {
      type: Object as PropType<Map<string, IRumField>>,
      default: () => new Map(),
    },
    /** 表格空数据类型 */
    emptyType: {
      type: String as PropType<'empty' | 'search-empty'>,
      default: 'search-empty',
    },
  },
  emits: {
    /** 点击单元格筛选值或统计列表触发，回传检索条件 */
    conditionChange: (_condition: ConditionChangeEvent) => true,
    /** 字段设置变更，回传新的展示字段列表 */
    displayFieldChange: (_fields: string[]) => true,
    /** 列宽调整变更，回传各列宽覆盖 { colKey: width } */
    columnResizeChange: (_width: Record<string, number>) => true,
    /** 表格排序变更，回传排序字符串（正序/倒序） */
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
    /** 表格滚动触底，触发加载更多数据 */
    scrollToEnd: () => true,
    /** 点击清空检索条件 */
    clearFilter: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** CommonTable 组件实例 ref，用于滚动时禁用 pointerEvents、单元格事件委托 */
    const tableRef = useTemplateRef<InstanceType<typeof CommonTable>>('tableRef');
    /** 单元格检索条件菜单组件实例 ref，其 $el 作为 popover 内容 */
    const conditionMenuRef = useTemplateRef<InstanceType<typeof ExploreConditionMenu>>('conditionMenuRef');
    /** 触底加载前记录的滚动位置，数据追加后还原以避免仍停在底部重复触发 */
    let scrollTopBeforeLoad: null | number = null;
    /** 本地请求锁：从发起加载到数据渲染完成期间，忽略滚动事件，避免 scrollLoading 切换间隙重复触发 */
    let isRequestingLock = false;
    /** 可展示字段映射表：按字段名快速查找字段元数据 */
    const fieldMap = computed(() => {
      if (props.fieldMap?.size) {
        return props.fieldMap;
      }
      return new Map(props.displayableFields.map(field => [field.name, field]));
    });

    const { activeFieldName, selectField, showPopover, statisticsListRef, destroyPopover, openPopover } =
      useFieldStatisticsPopover('bottom');

    /** 场景渲染器：按检索模式选择场景实例，负责产出声明式列配置与表头渲染 */
    const { transformColumns, tableScenarioClassName, tableRowKey } = useScenarioRenderer(toRef(props, 'mode'), {
      fieldMap,
      onCellFilter: (colKey, value) => emit('conditionChange', { key: colKey, method: 'equal', value }),
      onFieldAnalysis: (trigger, field) => openPopover(trigger, field as unknown as IStatisticsFieldItem),
    });

    /**
     * 单元格检索条件菜单：普通单元格左键点击弹出菜单，CLICK 类型列（左键已用于直接加为检索条件）右键弹出同一个菜单。
     * 菜单项行为与 trace 检索完全一致（复制 / 添加到本次检索 / 从本次检索中排除 / 新建检索）。
     */
    const { activeConditionMenuTarget, cacheRows, clearCache, closeMenu, hideMenu } = useCellConditionMenu({
      delegationRoot: tableRef,
      menuRef: conditionMenuRef,
      rowKey: tableRowKey,
    });

    /** 列展示逻辑：基础列（含列宽覆盖）-> 场景渲染注入 -> 拼接设置列 */
    const columns = computed<BaseTableColumn[]>(() => transformColumns(props.baseColumns));

    /** 当前展示列的字段 key 列表，供字段设置组件使用 */
    const displayFieldKeys = computed(() => props.baseColumns.map(col => col.colKey));

    /**
     * @description 滚动触底加载更多
     * @param onlyNoScrollBar 为 true 时仅处理无滚动条场景（大屏内容未撑满视口），避免数据追加后仍粘在底部而重复触发
     */
    const handleScrollToEnd = (target?: HTMLElement, onlyNoScrollBar = false) => {
      if (!props.hasMore || !target) {
        return;
      }
      const { scrollHeight, scrollTop, clientHeight } = target;
      const isEnd = !!scrollTop && Math.abs(scrollHeight - scrollTop - clientHeight) < 1;
      const noScrollBar = scrollHeight < clientHeight + 1;
      const shouldRequest = onlyNoScrollBar ? noScrollBar : noScrollBar || isEnd;
      if (!shouldRequest) return;
      if (!(props.loading || props.scrollLoading || isRequestingLock)) {
        // 记录触底前的滚动位置，请求完成后还原
        if (isEnd) {
          scrollTopBeforeLoad = scrollTop;
        }
        // 加锁：在数据返回并渲染完成前，阻止滚动事件重复触发
        isRequestingLock = true;
        emit('scrollToEnd');
      }
    };

    /** 滚动时关闭统计 popover 与单元格条件菜单（避免 popover 与单元格错位），触底时触发加载更多 */
    useTableScrollOptimize({
      targetElement: tableRef,
      scrollContainerElement: props.scrollContainerSelector,
      onScroll: (event: Event) => {
        destroyPopover();
        hideMenu();
        handleScrollToEnd(event.target as HTMLElement);
      },
    });

    // 监听数据变化：追加数据后还原滚动位置，并兼容无滚动条自动补全场景
    watch(
      () => props.data,
      (newData, oldData) => {
        // 新查询（数据变少或从无到有）时清空记录的滚动位置，避免把旧位置恢复到新结果
        if (!oldData?.length || (newData?.length ?? 0) <= oldData.length) {
          scrollTopBeforeLoad = null;
          clearCache();
        }
        // 单元格条件菜单只能从 DOM 上拿到 rowId/colId，这里按行缓存以便回源取值
        cacheRows(newData);
        nextTick(() => {
          requestAnimationFrame(() => {
            // 数据已渲染完成，释放加载锁，允许下一次触底加载
            isRequestingLock = false;
            const container = document.querySelector(props.scrollContainerSelector) as HTMLElement | null;
            if (!container) return;
            // 触底加载完成后还原滚动位置，避免浏览器粘在底部继续触发下一页
            if (scrollTopBeforeLoad !== null) {
              const { scrollHeight, clientHeight } = container;
              const maxScrollTop = scrollHeight - clientHeight;
              // 预留安全边距，避免还原后仍满足触底条件而循环加载
              if (maxScrollTop > 0) {
                container.scrollTop = Math.max(1, Math.min(scrollTopBeforeLoad, maxScrollTop - 2));
              }
              scrollTopBeforeLoad = null;
            }
            // 仅无滚动条时自动补全，兼容屏幕过大或 dpr 很小的场景
            handleScrollToEnd(container, true);
          });
        });
      },
      { immediate: true }
    );

    onBeforeUnmount(() => {
      destroyPopover();
    });

    return {
      t,
      activeConditionMenuTarget,
      activeFieldName,
      closeMenu,
      columns,
      displayFieldKeys,
      selectField,
      showPopover,
      statisticsListRef,
      tableRef,
      tableRowKey,
      tableScenarioClassName,
      destroyPopover,
    };
  },
  render() {
    return (
      <div class='rum-explore-table-wrap'>
        <CommonTable
          ref='tableRef'
          class={`rum-explore-table ${this.tableScenarioClassName}`}
          columns={[
            ...this.columns,
            ...(this.showSettings
              ? ([
                  {
                    colKey: '__col_setting__',
                    width: 32,
                    minWidth: 32,
                    fixed: 'right',
                    align: 'center',
                    resizable: false,
                    thClassName: '__table-custom-setting-col__',
                    title: (() =>
                      (
                        <ExploreFieldSetting
                          class='table-field-setting'
                          sourceList={this.displayableFields}
                          targetList={this.displayFieldKeys}
                          onConfirm={fields => this.$emit('displayFieldChange', fields)}
                        />
                      ) as unknown as SlotReturnValue) as BaseTableColumn['title'],
                    cellRenderer: () => null,
                  },
                ] as BaseTableColumn[])
              : []),
          ]}
          empty={() =>
            (
              <ExploreTableEmpty
                showOperation={this.emptyType === 'search-empty'}
                type={this.emptyType}
                onClearFilter={() => this.$emit('clearFilter')}
              />
            ) as unknown as SlotReturnValue
          }
          headerAffixedTop={{
            container: this.scrollContainerSelector,
            // span 模式下表格上方有 RumSpanTypeFilter 吸顶区域（高度 56px：padding 12 + chip 32 + padding 12）
            offsetTop: this.mode === 'span' ? 56 : 0,
          }}
          horizontalScrollAffixedBottom={{
            container: this.scrollContainerSelector,
          }}
          lastFullRow={(): SlotReturnValue =>
            this.data?.length
              ? ((
                  <Loading
                    style={{ display: this.hasMore ? 'inline-flex' : 'none' }}
                    class='scroll-end-loading'
                    loading={true}
                    mode='spin'
                    size='mini'
                    theme='primary'
                    title={this.t('加载中...')}
                  />
                ) as unknown as SlotReturnValue)
              : null
          }
          autoFillSpace={!this.data?.length}
          data={this.data}
          loading={this.loading}
          rowKey={this.tableRowKey}
          sort={this.sort}
          onColumnResizeChange={(ctx: { columnsWidth: Record<string, number> }) =>
            this.$emit('columnResizeChange', ctx.columnsWidth)
          }
          onSortChange={(sort: string | string[]) => this.$emit('sortChange', sort)}
        />

        <StatisticsList
          ref='statisticsListRef'
          api={statisticsApi}
          commonParams={this.commonParams as any}
          fieldType={this.selectField?.type}
          isShow={this.showPopover}
          selectField={this.selectField?.name}
          timeRange={this.timeRange as any}
          unit={this.selectField?.field_unit}
          onConditionChange={(condition: ConditionChangeEvent) => this.$emit('conditionChange', condition)}
          onShowMore={this.destroyPopover}
        />

        <div style='display: none'>
          <ExploreConditionMenu
            ref='conditionMenuRef'
            conditionKey={this.activeConditionMenuTarget.colId}
            conditionValue={this.activeConditionMenuTarget.conditionValue}
            onConditionChange={(condition: ConditionChangeEvent) => this.$emit('conditionChange', condition)}
            onMenuClick={this.closeMenu}
          />
        </div>
      </div>
    );
  },
});
