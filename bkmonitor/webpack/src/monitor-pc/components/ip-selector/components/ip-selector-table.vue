<!--
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
-->
<template>
  <bk-table
    :key="maxHeight"
    :data="data"
    :outer-border="false"
    :header-border="false"
    :pagination="pagination"
    :max-height="maxHeight"
    :empty-text="emptyText"
    :cell-class-name="handleCellClass"
    :header-cell-class-name="handleCellClass"
    class="topo-table"
    @page-change="handlePageChange"
    @page-limit-change="handlePageLimitChange"
  >
    <div
      v-if="!!tableKeyword"
      slot="empty"
    >
      <EmptyStatus
        type="search-empty"
        @operation="handleOperation"
      />
    </div>
    <bk-table-column
      v-if="showSelectionColumn"
      :render-header="renderHeader"
      width="50"
      :resizable="false"
    >
      <template #default="{ row }">
        <bk-checkbox
          :key="`${JSON.stringify(row) + '_' + checkKey}`"
          :checked="getCheckedStatus(row)"
          :disabled="getDisabledStatus(row)"
          @change="handleRowCheckChange(row, $event)"
        />
      </template>
    </bk-table-column>
    <bk-table-column
      v-for="item in config.filter(item => !item.hidden)"
      :key="item.prop"
      :label="item.label"
      :prop="item.prop"
      :min-width="item.minWidth"
    >
      <template #default="{ row, column, $index }">
        <div v-if="item.render">
          <component :is="renderVnodeRow(item, row, column, $index)" />
        </div>
        <span v-else-if="typeof row[item.prop] === 'number'">
          {{ row[item.prop] }}
        </span>
        <span
          v-else
          v-bk-overflow-tips
          class="column-string"
        >
          {{ row[item.prop] || '--' }}
        </span>
      </template>
    </bk-table-column>
  </bk-table>
</template>
<script lang="ts">
import type { CreateElement } from 'vue';

import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import { random } from 'monitor-common/utils/utils';

import EmptyStatus from '../../empty-status/empty-status';
import SelectionColumn from '../components/selection-column.vue';

import type { EmptyStatusOperationType } from '../../empty-status/types';
import type { CheckType, CheckValue, IPagination, ITableConfig } from '../types/selector-type';

@Component({
  name: 'ip-selector-table',
  components: { EmptyStatus },
})
export default class IpSelectorTable extends Vue {
  @Prop({ default: () => [], type: Array }) private readonly data!: any[];
  @Prop({ default: () => [], type: Array }) private readonly config!: ITableConfig[];
  @Prop({ default: () => ({}), type: Object }) private readonly pagination!: IPagination;
  @Prop({ type: Number }) private readonly maxHeight!: number;
  @Prop({ default: () => [], type: Array }) private readonly defaultSelections!: any[];
  @Prop({ default: true, type: Boolean }) private readonly showSelectionColumn!: boolean;
  @Prop({ default: '', type: String }) private readonly emptyText!: string;
  @Prop({ default: '', type: String }) private readonly tableKeyword!: string;

  private selections: any[] = this.defaultSelections;
  private excludeData: any[] = [];
  private checkValue: CheckValue = 0;
  private checkType: CheckType = 'current';
  private checkKey: string = random(8);

  @Watch('defaultSelections')
  private handleDefaultSelectionsChange() {
    this.selections = this.defaultSelections;
    // 重新计算当前页未被check的数据
    this.excludeData = this.data.reduce<(number | string)[]>((pre, next) => {
      if (this.selections.indexOf(next) === -1) {
        pre.push(next);
      }
      return pre;
    }, []);
    this.updateCheckStatus();
    this.checkKey = random(8);
  }

  private renderVnodeRow(item: ITableConfig, row: any, column: any, $index: number) {
    return item.render(row, column, $index);
  }

  private renderHeader(h: CreateElement) {
    return h(SelectionColumn, {
      props: {
        value: this.checkValue,
        disabled: !this.data.length,
        defaultActive: this.checkType,
      },
      on: {
        'update-value': (v: CheckValue) => {
          this.checkValue = v;
        },
        change: this.handleSelectionChange,
      },
    });
  }
  // 全选和取消全选操作

  public handleSelectionChange({ value, type }: { type: CheckType; value: CheckValue }) {
    this.checkValue = value;
    this.checkType = type;
    this.excludeData = value === 0 ? [...this.data] : [];
    this.selections = value === 2 ? [...this.data] : [];
    this.handleCheckChange();
  }

  private handleRowCheckChange(row: any, checked: boolean) {
    this.setRowSelection(row, checked);
    this.handleCheckChange();
  }

  @Emit('check-change')
  private handleCheckChange() {
    return {
      excludeData: this.excludeData,
      selections: this.selections,
      checkType: this.checkType,
      checkValue: this.checkValue,
    };
  }

  @Emit('page-change')
  private handlePageChange(page: number) {
    this.checkType === 'current' && this.resetCheckedStatus();
    return page;
  }

  private getCheckedStatus(row: any) {
    if (this.checkType === 'current') {
      return this.selections.indexOf(row) > -1;
    }
    return this.excludeData.indexOf(row) === -1;
  }

  private getDisabledStatus() {}

  public resetCheckedStatus() {
    this.checkType = 'current';
    this.checkValue = 0;
    this.selections = [];
    this.excludeData = [];
  }

  // 设置当前行选中状态

  public setRowSelection(row: any, checked: boolean) {
    if (checked) {
      this.selections.push(row);
    } else {
      const index = this.selections.indexOf(row);
      index > -1 && this.selections.splice(index, 1);
    }

    if (this.checkType === 'current') {
      // 重新计算当前页未被check的数据
      this.excludeData = this.data.reduce<(number | string)[]>((pre, next) => {
        if (this.selections.indexOf(next) === -1) {
          pre.push(next);
        }
        return pre;
      }, []);
    } else {
      if (checked) {
        const index = this.excludeData.indexOf(row);
        index > -1 && this.excludeData.splice(index, 1);
      } else {
        this.excludeData.push(row);
      }
    }
    this.updateCheckStatus();
  }

  private updateCheckStatus() {
    // 设置当前check状态
    if (!this.data.length) {
      this.checkValue = 0;
    } else if (this.excludeData.length === 0) {
      // 未选
      this.checkValue = 2;
    } else if ([this.pagination.count, this.data.length].includes(this.excludeData.length)) {
      // 取消全选
      this.checkValue = 0;
      this.checkType = 'current';
      this.selections = [];
    } else {
      // 半选
      this.checkValue = 1;
    }
  }

  private handleCellClass({ columnIndex }: { columnIndex: number }) {
    if (this.showSelectionColumn && columnIndex === 0) {
      return 'selection-cell';
    }
  }

  @Emit('page-limit-change')
  private handlePageLimitChange(limit: number) {
    return limit;
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.$emit('clear-filter');
      return;
    }
  }
}
</script>
<style lang="scss" scoped>
.topo-table {
  &::before {
    height: 0;
  }

  :deep(th) {
    background-color: #f5f6fa;
  }

  :deep(.selection-cell .cell) {
    padding-right: 0;
    padding-left: 10px;
  }

  .column-string {
    display: block;
    overflow: hidden;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    direction: rtl;
  }
}
</style>
