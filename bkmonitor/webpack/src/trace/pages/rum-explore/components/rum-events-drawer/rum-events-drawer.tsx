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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import {
  type PropType,
  computed,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { Exception, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import VerticalDrawer from '../../../../components/vertical-drawer/vertical-drawer';
import { useTableScrollOptimize } from '../../../../hooks/use-table-scroll-optimize';
import CommonTable from '../../../alarm-center/components/alarm-table/components/common-table/common-table';
import ExploreConditionMenu from '../../../trace-explore/components/trace-explore-table/components/explore-condition-menu';
import {
  EVENTS_FIELD_PREFIX,
  RUM_EVENTS_ACTIVE_COLUMN_CLASS,
  RUM_EVENTS_COLUMN_WIDTH,
  RUM_EVENTS_MIN_SKELETON_DURATION,
} from '../../constants';
import { buildEventsListRows, formatArrayItem, resolveArrayItemFormatter } from '../../utils';
import { useCellConditionMenu } from '../rum-explore-table/hooks/use-cell-condition-menu';
import RumEventsSkeleton, { renderEventsLoadingCell } from './rum-events-skeleton';

import type { BaseTableColumn } from '../../../trace-explore/components/trace-explore-table/typing';
import type { ConditionChangeEvent } from '../../../trace-explore/typing';
import type { IEventsListColumn, IRumField, IRumSpanRecord } from '../../typings';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './rum-events-drawer.scss';

/** 抽屉表格的滚动容器：CommonTable 内容区（横向 / 纵向滚动都发生在这里） */
const DRAWER_SCROLL_CONTAINER_SELECTOR = '.t-table__content';

export default defineComponent({
  name: 'RumEventsDrawer',
  props: {
    /** 是否展示抽屉 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 触发抽屉的行数据 */
    row: {
      type: Object as PropType<IRumSpanRecord | null>,
      default: null,
    },
    /** 当前选中的列键，抽屉中该列整列高亮 */
    colKey: {
      type: String,
      default: '',
    },
    /** 可作为列的字段全集，用于推导 events.* 字段 */
    fields: {
      type: Array as PropType<IRumField[]>,
      default: () => [],
    },
    /** 主表当前显示的字段（顺序即列顺序），默认态只展示其中的 events.* 字段 */
    displayFieldKeys: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    /** 点击右上角关闭，透传垂直抽屉的 v-model 更新 */
    'update:isShow': (value: boolean) => typeof value === 'boolean',
    /** 点击单元格检索条件菜单（添加到本次检索 / 从本次检索中排除），回传检索条件 */
    conditionChange: (_condition: ConditionChangeEvent) => true,
  },
  setup(props) {
    const { t } = useI18n();
    /**
     * 表格事件委托根节点：位于 VerticalDrawer 的插槽内、随抽屉显隐重建，用函数 ref 记录当前节点
     * （字符串 ref 在插槽内会绑定到子组件实例上）
     */
    const tableWrapEl = shallowRef<HTMLElement | null>(null);
    /** 单元格检索条件菜单组件实例 ref，其 $el 作为 popover 内容 */
    const conditionMenuRef = useTemplateRef<InstanceType<typeof ExploreConditionMenu>>('conditionMenuRef');
    /** 抽屉行缓存：菜单据 data-row-id / data-col-id 回源取单元格原始值（行内即原始值） */
    const { activeConditionMenuTarget, cacheRows, clearCache, closeMenu, hideMenu, rebindListeners } =
      useCellConditionMenu({
        delegationRoot: tableWrapEl,
        menuRef: conditionMenuRef,
        rowKey: 'rowId',
      });
    /**
     * 表格滚动时收起条件菜单，与主表共用同一条封装；
     * 滚动容器在抽屉根节点内部，随抽屉显隐重建，重建时由下方 watch 重新绑定。
     */
    const { addScrollListener, removeScrollListener } = useTableScrollOptimize({
      rootElement: tableWrapEl,
      scrollContainerElement: DRAWER_SCROLL_CONTAINER_SELECTOR,
      onScroll: () => hideMenu(),
    });
    /** 过渡序号，用于丢弃被新过渡覆盖的收尾 */
    let transitionSeq = 0;
    /** 是否展示全部字段（含主表隐藏的 events.* 字段） */
    const showAllFields = shallowRef(false);
    /** 骨架类型：table=整体骨架（含表头，列集合变化）；cell=仅单元格骨架（列集合不变，只换行数据）；none=无 */
    const skeletonType = shallowRef<'cell' | 'none' | 'table'>('table');

    /** 可作为列的 events.* 字段全集 */
    const eventFields = computed(() => props.fields.filter(field => field.name.startsWith(EVENTS_FIELD_PREFIX)));
    /** 主表已显示的 events.* 字段，顺序沿用主表列顺序 */
    const displayedEventFields = computed(() => {
      const fieldMap = new Map(eventFields.value.map(field => [field.name, field]));
      /** 按主表列顺序取字段，天然保持顺序，主表未显示或非 events.* 的键被过滤 */
      return props.displayFieldKeys.map(key => fieldMap.get(key)).filter(Boolean);
    });
    /** 抽屉列：默认态用主表已显示的 events.* 字段，开「查看全部字段」后用全集，逐列推导格式化方法 */
    const eventColumns = computed<IEventsListColumn[]>(() =>
      (showAllFields.value ? eventFields.value : displayedEventFields.value).map(field => ({
        alias: field.alias,
        formatter: resolveArrayItemFormatter(field),
        name: field.name,
      }))
    );
    /** 抽屉行：随当前行数据转置，列集合不变时复用 */
    const rows = computed(() => buildEventsListRows(props.row, eventColumns.value));

    /**
     * 表格列：下标列 + 各 events.* 字段列，命中主表当前列的列整列高亮。
     * 其余（表头、省略 popover、条件菜单类名与 data 属性）走 CommonTable 内建列渲染；
     * 下标列不是检索字段，用纯文本渲染以避免挂上条件菜单。
     */
    const columns = computed<BaseTableColumn[]>(() => [
      /** 序号列左固定：events 字段较多时表格横向滚动，下标列需常驻，否则行与下标无法对应 */
      {
        colKey: 'index',
        title: '#',
        width: 64,
        fixed: 'left',
        cellRenderer: row => (<span>{String(row.index)}</span>) as unknown as SlotReturnValue,
      },
      ...eventColumns.value.map((column): BaseTableColumn => {
        const activeClassName = column.name === props.colKey ? RUM_EVENTS_ACTIVE_COLUMN_CLASS : '';
        return {
          className: activeClassName,
          colKey: column.name,
          /** 空值（含数组长度不足补位）格式化为空占位符，原始值保持为空串，菜单点击不会产生检索条件 */
          getRenderValue: row => formatArrayItem(row[column.name], column.formatter),
          thClassName: activeClassName,
          title: column.alias,
          width: RUM_EVENTS_COLUMN_WIDTH,
        };
      }),
    ]);

    /**
     * @description 骨架过渡：先挂载骨架并等浏览器绘制一帧，再同步渲染真实表格。
     *              大数组表格的同步渲染会阻塞主线程，若与抽屉动画同帧执行会卡顿；
     *              骨架先上屏后，阻塞发生在骨架阶段，动画不受影响。
     * @param {'cell' | 'table'} mode 骨架类型：列集合变化用 table，只换行数据用 cell
     */
    async function transitionWithSkeleton(mode: 'cell' | 'table') {
      const seq = ++transitionSeq;
      skeletonType.value = mode;
      /** 双 rAF：第一帧 Vue 提交 DOM，第二帧浏览器完成绘制，确保骨架可见 */
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      /** 最短展示时长，避免骨架一闪而过 */
      await new Promise<void>(resolve => setTimeout(resolve, RUM_EVENTS_MIN_SKELETON_DURATION));
      /** 期间已发起新过渡时收尾交给新的一次，避免提前收掉骨架 */
      if (seq === transitionSeq) skeletonType.value = 'none';
    }

    /**
     * 切换「查看全部字段」：先同步切换列集合，使骨架屏按目标列数渲染（骨架与真实表格同态），
     * 再走整体骨架过渡；与骨架类型同一 tick 赋值，本次 flush 仍只渲染骨架，不会闪现真实表格
     */
    function handleShowAllChange(value: boolean) {
      showAllFields.value = value;
      transitionWithSkeleton('table');
    }

    /**
     * 骨架触发：打开抽屉（含 immediate 首帧）列集合可能变化，走整体骨架；
     * 抽屉已打开时切换目标行（点击其他行的 events 单元格）列集合不变，只走单元格骨架。
     */
    watch(
      [() => props.isShow, () => props.row],
      ([isShow, row], [prevShow, prevRow]) => {
        /** 抽屉关闭 / 切换目标行会重建单元格，触发元素消失后菜单需同步收起 */
        hideMenu();
        if (!isShow) {
          /** 关闭时复位为下次打开做准备，并作废进行中的过渡，否则它会在超时后把骨架收成 none */
          transitionSeq++;
          skeletonType.value = 'table';
          return;
        }
        if (!prevShow) transitionWithSkeleton('table');
        else if (row?.span_id !== prevRow?.span_id) transitionWithSkeleton('cell');
      },
      { immediate: true }
    );

    /** 抽屉行变化（目标行 / 列集合变化）：重建行缓存 */
    watch(
      rows,
      value => {
        clearCache();
        cacheRows(value);
      },
      { immediate: true }
    );

    /**
     * 滚动容器是抽屉表格内部的节点，会随根节点重建、列集合切换一起重建，
     * 因此在这两类时机都要重新解析并绑定（nextTick 保证新节点已渲染）。
     */
    function rebindScrollListener() {
      removeScrollListener();
      nextTick(() => addScrollListener());
    }

    /** 表格根节点随抽屉显隐重建后，重新绑定事件委托与滚动监听 */
    watch(
      tableWrapEl,
      (el, oldEl) => {
        if (oldEl) removeScrollListener();
        if (!el) return;
        rebindListeners();
        rebindScrollListener();
      },
      { flush: 'post' }
    );

    /** 骨架结束（表格重新渲染完成）后重绑滚动监听；期间触发元素消失，菜单需同步收起 */
    watch(skeletonType, value => {
      hideMenu();
      if (value === 'none') rebindScrollListener();
    });

    /** 卸载后作废进行中的过渡，避免 rAF / 定时器收尾继续写状态 */
    onBeforeUnmount(() => {
      transitionSeq++;
    });

    return {
      activeConditionMenuTarget,
      closeMenu,
      columns,
      eventColumns,
      handleShowAllChange,
      rows,
      showAllFields,
      skeletonType,
      t,
      tableWrapEl,
    };
  },
  render() {
    return (
      <>
        <VerticalDrawer
          v-slots={{
            'header-actions': () => (
              <div class='rum-events-drawer-actions'>
                <Switcher
                  size='small'
                  theme='primary'
                  value={this.showAllFields}
                  onChange={this.handleShowAllChange}
                />
                <span class='show-all-label'>{this.t('查看全部字段')}</span>
              </div>
            ),
            default: () => (
              <div
                ref={(el: unknown) => {
                  this.tableWrapEl = el as HTMLElement;
                }}
                class={['events-table-wrap', { 'is-empty': !this.rows.length }]}
              >
                {this.skeletonType === 'table' ? (
                  <RumEventsSkeleton
                    columnCount={this.eventColumns.length}
                    columnWidth={RUM_EVENTS_COLUMN_WIDTH}
                  />
                ) : (
                  <CommonTable
                    class='events-table'
                    empty={() =>
                      (
                        <Exception
                          class='events-empty'
                          description={this.t('暂无数据')}
                          scene='part'
                          type='empty'
                        />
                      ) as unknown as SlotReturnValue
                    }
                    loadingCell={(column, rowIndex) =>
                      renderEventsLoadingCell(column.colKey, rowIndex) as unknown as SlotReturnValue
                    }
                    activeRowType=''
                    autoFillSpace={!this.rows.length}
                    bordered={true}
                    columns={this.columns}
                    data={this.rows}
                    loading={this.skeletonType === 'cell'}
                    maxHeight='100%'
                    resizable={false}
                    rowKey='rowId'
                    tableSize='small'
                  />
                )}
              </div>
            ),
          }}
          isShow={this.isShow}
          subtitle={String(this.row?.span_name || this.row?.span_id || '')}
          title={this.t('查看数组列表')}
          onUpdate:isShow={(value: boolean) => this.$emit('update:isShow', value)}
        />

        {/* 条件菜单作为 popover 内容挂在页面外的隐藏容器，由单元格点击时通过 tippy 搬出展示 */}
        <div style='display: none'>
          <ExploreConditionMenu
            ref='conditionMenuRef'
            conditionKey={this.activeConditionMenuTarget.colId}
            conditionValue={this.activeConditionMenuTarget.conditionValue}
            onConditionChange={(condition: ConditionChangeEvent) => this.$emit('conditionChange', condition)}
            onMenuClick={this.closeMenu}
          />
        </div>
      </>
    );
  },
});
