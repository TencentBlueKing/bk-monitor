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
  computed,
  defineComponent,
  h,
  nextTick,
  onMounted,
  onScopeDispose,
  shallowRef,
  watch,
} from 'vue';

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { sortTableGraph } from 'monitor-ui/chart-plugins/plugins/profiling-graph/table-graph/utils';
import { useI18n } from 'vue-i18n';

import { diffTextColor, formatDiff, formatProfileValue, frameColor, rowValue } from '../../utils/flame-layout';
import ProfileDetails from './profile-details';
import ProfilePopup from './profile-popup';

import type { ProfileRow, ProfileViewState } from '../../types';

export default defineComponent({
  name: 'ProfileFunctionTable',
  props: {
    rows: { type: Array as PropType<ProfileRow[]>, default: () => [] },
    sort: {
      type: Object as PropType<ProfileViewState['sort']>,
      default: () => ({ sortBy: 'total', descending: true }),
    },
    compared: Boolean,
    dataType: { type: String, default: '' },
    rootTotal: { type: Number, default: 0 },
    keyword: { type: String, default: '' },
    highlight: { type: String, default: '' },
    direction: { type: String, default: 'ltr' },
    unit: { type: String, default: '' },
  },
  emits: { select: (_name: string) => true, sortChange: (_sort: ProfileViewState['sort']) => true },
  setup(props) {
    const { t } = useI18n();
    const tip = shallowRef<null | { row: ProfileRow; x: number; y: number }>(null);
    const table = shallowRef<{ scrollToElement: (options: { index: number; top: number }) => void }>();
    const container = shallowRef<HTMLElement>();
    const height = shallowRef(460);
    let hoverRow: null | ProfileRow = null;
    let pendingRow: null | ProfileRow = null;
    let hoverTimer: ReturnType<typeof setTimeout>;
    let scrollBlockedUntil = 0;
    let pointer: null | { x: number; y: number } = null;
    function hideTip() {
      clearTimeout(hoverTimer);
      pendingRow = null;
      tip.value = null;
    }
    function handleScroll() {
      scrollBlockedUntil = Date.now() + 180;
      hideTip();
    }
    function handleLeave() {
      hoverRow = null;
      pointer = null;
      hideTip();
    }
    function handleRowHover({ row }: { row: ProfileRow }) {
      hoverRow = row;
    }
    function handlePointerMove(event: MouseEvent) {
      // 虚拟行在滚动复用时也会触发 mouseover；仅真实移鼠且滚动冷却结束后才展示提示。
      const { clientX: x, clientY: y } = event;
      if (pointer?.x === x && pointer?.y === y) return;
      pointer = { x, y };
      if (Date.now() < scrollBlockedUntil || !hoverRow || pendingRow === hoverRow || tip.value?.row === hoverRow)
        return;
      hideTip();
      const row = hoverRow;
      pendingRow = row;
      hoverTimer = setTimeout(() => {
        pendingRow = null;
        tip.value = { row, x, y };
      }, 200);
    }
    let observer: ResizeObserver;
    onMounted(() => {
      observer = new ResizeObserver(([entry]) => {
        // 虚拟表格需要确定的视口高度；扣除边框后让滚动留在表格内部。
        height.value = Math.floor(entry.contentRect.height) - 2;
      });
      observer.observe(container.value);
    });
    onScopeDispose(() => {
      observer?.disconnect();
      clearTimeout(hoverTimer);
    });
    watch(() => props.rows, handleLeave);
    watch(
      () => props.keyword,
      () => {
        handleLeave();
        nextTick(() => table.value?.scrollToElement({ index: 0, top: 0 }));
      }
    );
    const maximums = computed(() => {
      const max = { self: 0, total: 0, baseline: 0, comparison: 0 };
      for (const row of props.rows) {
        for (const key of Object.keys(max)) max[key] = Math.max(max[key], rowValue(row as ProfileRow, key));
      }
      return max;
    });
    const data = computed(() => {
      const keyword = props.keyword.trim().toLowerCase();
      const rows = props.rows.filter(row => !keyword || row.name.toLowerCase().includes(keyword));
      const { sortBy, descending } = props.sort || { sortBy: 'total', descending: true };
      if (sortBy === 'diff') return sortTableGraph(rows, sortBy, descending ? 'desc' : 'asc');
      return rows.sort((a, b) => {
        const difference = sortBy === 'name' ? a.name.localeCompare(b.name) : rowValue(a, sortBy) - rowValue(b, sortBy);
        return difference * (descending ? -1 : 1);
      });
    });
    const columns = computed<TableProps['columns']>(() => {
      const valueColumn = (key: string, title: string): TableProps['columns'][number] => ({
        colKey: key,
        title,
        width: props.compared ? 94 : 120,
        align: 'center',
        sorter: true,
        cell: (_h, { row }) =>
          h('div', { class: 'profile-value-cell' }, [
            !props.compared &&
              h('span', {
                class: 'profile-value-bar',
                style: {
                  width: `${maximums.value[key] && rowValue(row as ProfileRow, key) > 0 ? Math.max(2, (rowValue(row as ProfileRow, key) / maximums.value[key]) * 100) : 0}%`,
                  backgroundColor: props.compared ? '#dcdee5' : frameColor(row.name),
                },
              }),
            h('span', { class: 'profile-value' }, formatProfileValue(rowValue(row as ProfileRow, key), props.unit)),
          ]),
      });
      return [
        {
          colKey: 'name',
          title: 'Location',
          minWidth: 200,
          sorter: true,
          cell: (_h, { row }) =>
            h(
              'div',
              {
                class: ['profile-function-name', { selected: props.highlight === row.name }],
                style: { direction: props.direction },
              },
              [h('i', { style: { backgroundColor: props.compared ? '#dcdee5' : frameColor(row.name) } }), row.name]
            ),
        },
        ...(props.compared
          ? [
              valueColumn('baseline', t('查询项')),
              valueColumn('comparison', t('对比项')),
              {
                colKey: 'diff',
                title: 'Diff',
                width: 94,
                align: 'center' as const,
                sorter: true,
                cell: (_h, { row }) => h('span', { style: { color: diffTextColor(row) } }, formatDiff(row)),
              },
            ]
          : [valueColumn('self', 'Self'), valueColumn('total', 'Total')]),
      ];
    });
    return {
      t,
      columns,
      data,
      tip,
      table,
      container,
      height,
      handleRowHover,
      handlePointerMove,
      handleScroll,
      handleLeave,
    };
  },
  render() {
    return (
      <div
        ref='container'
        class='profile-table-container'
        onMouseleave={this.handleLeave}
        onMousemove={this.handlePointerMove}
        onWheel={this.handleScroll}
      >
        <PrimaryTable
          ref='table'
          height={this.height}
          class='profile-function-table'
          columns={this.columns}
          data={this.data}
          empty={this.t('暂无数据')}
          needCustomScroll={false}
          rowClassName={({ row }) => (row.name === this.highlight ? 'profile-row-selected' : '')}
          rowKey='id'
          scroll={{ type: 'virtual', rowHeight: 32, bufferSize: 10 }}
          size='small'
          sort={this.sort}
          hover
          stripe
          onRowClick={({ row }) => this.$emit('select', row.name)}
          onRowMouseleave={this.handleLeave}
          onRowMouseover={({ row }) => this.handleRowHover({ row: row as ProfileRow })}
          onScroll={this.handleScroll}
          onSortChange={sort => {
            this.$emit('sortChange', (sort as ProfileViewState['sort']) || { sortBy: 'total', descending: true });
          }}
        />
        <ProfilePopup point={this.tip}>
          {this.tip && (
            <ProfileDetails
              dataType={this.dataType}
              diff={this.compared ? this.tip.row : null}
              name={this.tip.row.name}
              rootTotal={this.rootTotal}
              self={this.tip.row.self}
              total={rowValue(this.tip.row, 'total')}
              unit={this.unit}
              table
            />
          )}
        </ProfilePopup>
      </div>
    );
  },
});
