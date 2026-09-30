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

import { type PropType, computed, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { Exception, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import VerticalDrawer from '../../../../components/vertical-drawer/vertical-drawer';
import CommonTable from '../../../alarm-center/components/alarm-table/components/common-table/common-table';
import {
  EVENTS_FIELD_PREFIX,
  RUM_EVENTS_ACTIVE_COLUMN_CLASS,
  RUM_EVENTS_COLUMN_WIDTH,
  RUM_EVENTS_MIN_SKELETON_DURATION,
} from '../../constants';
import { buildEventsListRows, resolveArrayItemFormatter } from '../../utils';
import RumEventsSkeleton, { renderEventsLoadingCell } from './rum-events-skeleton';

import type { BaseTableColumn } from '../../../trace-explore/components/trace-explore-table/typing';
import type { IEventsListColumn, IRumField, IRumSpanRecord } from '../../typings';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './rum-events-drawer.scss';

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
  },
  setup(props) {
    const { t } = useI18n();
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
      const displayKeys = props.displayFieldKeys ?? [];
      /** filter 已产生新数组，sort 不会改动 eventFields 的缓存 */
      return eventFields.value
        .filter(field => displayKeys.includes(field.name))
        .sort((a, b) => displayKeys.indexOf(a.name) - displayKeys.indexOf(b.name));
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

    /** 表格列：下标列 + 各 events.* 字段列，命中主表当前列的列整列高亮；单元格与表头走 CommonTable 默认渲染（省略、popover 内建） */
    const columns = computed<BaseTableColumn[]>(() => [
      /** 序号列左固定：events 字段较多时表格横向滚动，下标列需常驻，否则行与下标无法对应 */
      { colKey: 'index', title: '#', width: 64, fixed: 'left' },
      ...eventColumns.value.map((column): BaseTableColumn => {
        const activeClassName = column.name === props.colKey ? RUM_EVENTS_ACTIVE_COLUMN_CLASS : '';
        return {
          className: activeClassName,
          colKey: column.name,
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
      await nextTick();
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
        if (!isShow) {
          /** 关闭时复位为下次打开做准备，并作废进行中的过渡，否则它会在超时后把骨架收成 none */
          transitionSeq++;
          skeletonType.value = 'table';
          return;
        }
        if (!prevShow) transitionWithSkeleton('table');
        else if (row !== prevRow) transitionWithSkeleton('cell');
      },
      { immediate: true }
    );

    return { columns, eventColumns, handleShowAllChange, rows, showAllFields, skeletonType, t };
  },
  render() {
    return (
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
            <div class={['events-table-wrap', { 'is-empty': !this.rows.length }]}>
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
                  bordered={true}
                  columns={this.columns}
                  data={this.rows}
                  loading={this.skeletonType === 'cell'}
                  maxHeight='100%'
                  resizable={false}
                  rowKey='index'
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
    );
  },
});
