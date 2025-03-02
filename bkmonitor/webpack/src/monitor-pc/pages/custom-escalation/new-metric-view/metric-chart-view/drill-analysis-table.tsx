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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils/utils';

import type { IDimensionItem, IColumnItem, IDataItem } from '../type';

import './drill-analysis-table.scss';

/** 下钻分析 - 聚合维度表格 */

interface IDrillAnalysisTableProps {
  dimensionsList?: IDimensionItem[];
  tableList?: any[];
}

interface IDrillAnalysisTableEvent {
  onUpdateDimensions: (v: IDimensionItem[]) => void;
}

@Component
export default class DrillAnalysisTable extends tsc<IDrillAnalysisTableProps, IDrillAnalysisTableEvent> {
  @Prop({ type: Array, default: () => [] }) dimensionsList: IDimensionItem[];
  @Prop({ type: Array, default: () => [] }) tableList: IDataItem[];
  /** 维度是否支持多选 */
  isMultiple = false;
  /** 选中的维度 */
  activeList = [];
  dimensionSearch = '';
  /** 展示的维度值 */
  showDimensionKeys = [];
  /** 下钻过滤列表 */
  drillList = [];
  /** 已经下钻了的维度值 */
  drillValue = '';

  /** 需要展示的维度列 */
  get dimensionsColumn() {
    const list: IColumnItem[] = [];
    this.showDimensionKeys = [];
    this.dimensionsList.map(item => {
      if (item.checked) {
        list.push({
          label: item.name,
          prop: item.key,
          renderFn: row => this.renderDimensionRow(row, item),
        });
        this.showDimensionKeys.push(item.key);
      }
    });
    return list;
  }

  /** 维度选择侧栏 start */
  renderDimensionList() {
    const baseView = (item: IDimensionItem) => [<span>{item.key}</span>, <span class='item-name'>{item.name}</span>];
    /** 单选 */
    if (!this.isMultiple) {
      return this.dimensionsList.map((item: IDimensionItem) => (
        <div
          key={item.key}
          class={['dimensions-list-item', { active: item.checked }]}
          onClick={() => this.handleDimensionChange([item.key])}
        >
          {baseView(item)}
        </div>
      ));
    }
    /** 多选 */
    return (
      <bk-checkbox-group
        value={this.activeList}
        onChange={v => this.handleDimensionChange(v)}
      >
        {this.dimensionsList.map(item => (
          <bk-checkbox
            key={item.key}
            class='dimensions-list-item'
            disabled={this.activeList.length === 1 && item.checked}
            value={item.key}
          >
            {baseView(item)}
          </bk-checkbox>
        ))}
      </bk-checkbox-group>
    );
  }

  /** 改变维度是否多选 */
  changeMultiple(val: boolean) {
    this.isMultiple = val;
    const index = this.dimensionsList.findIndex(item => item.checked);
    this.handleDimensionChange([this.dimensionsList[index].key]);
  }
  /** 选中维度的相关处理  */
  handleDimensionChange(checkedList: string[]) {
    this.activeList = checkedList;
    const list = this.dimensionsList.map((dimension: IDimensionItem) =>
      Object.assign(dimension, {
        checked: checkedList.includes(dimension.key),
      })
    );
    this.$emit('updateDimensions', list);
  }

  /** 维度选择侧栏 end */

  /** 维度表格 start  */

  /** 绘制下钻下拉列表 */
  renderOperation(row: IDataItem) {
    return (
      <bk-dropdown-menu
        ref='dropdown'
        ext-cls='table-drill-down-popover'
        trigger='click'
        position-fixed
      >
        <div
          class='table-drill-down-btn'
          slot='dropdown-trigger'
        >
          <span>{this.$t('下钻')}</span>
          <i class='icon-monitor icon-mc-arrow-down' />
        </div>
        <ul
          class='table-drill-down-list'
          slot='dropdown-content'
        >
          {(this.dimensionsList || []).map(option => {
            const isActive = this.drillValue === option.key;
            return (
              <li
                key={option.key}
                class={['table-drill-down-item', { active: isActive }]}
                onClick={() => this.chooseDrill(option, row)}
              >
                {option.name}
              </li>
            );
          })}
        </ul>
      </bk-dropdown-menu>
    );
  }
  /** 绘制颜色块 */
  renderColorBlock(row: IDataItem) {
    return (
      <div
        style={{ backgroundColor: row.color }}
        class='color-box'
      ></div>
    );
  }
  /** 绘制维度列 */
  renderDimensionRow(row, item: IDimensionItem) {
    return (
      <span class='dimensions-value'>
        {row[item.key]}
        <i
          class='icon-monitor icon-mc-copy tab-row-icon'
          onClick={() => this.copyValue(row[item.key])}
        />
      </span>
    );
  }

  /** 绘制表格内容 */
  renderTableColumn() {
    const colorColumn: IColumnItem[] = [
      {
        label: '',
        prop: 'color',
        width: 30,
        renderFn: row => this.renderColorBlock(row),
      },
    ];
    const baseColumn: IColumnItem[] = [
      {
        label: '操作',
        prop: 'operation',
        renderFn: row => this.renderOperation(row),
      },
      { label: '值', prop: 'value', sortable: true },
      { label: '占比', prop: 'proportion', sortable: true },
      { label: '波动', prop: 'fluctuation', sortable: true },
    ];
    const columnList = [...colorColumn, ...this.dimensionsColumn, ...baseColumn];
    return columnList.map((item: IColumnItem, ind: number) => {
      return (
        <bk-table-column
          key={`${item.prop}_${ind}`}
          width={item.width}
          scopedSlots={{
            default: ({ row }) => {
              /** 自定义 */
              if (item?.renderFn) {
                return item?.renderFn(row);
              }
              return row[item.prop];
            },
          }}
          label={this.$t(item.label)}
          prop={item.prop}
          sortable={item.sortable}
        ></bk-table-column>
      );
    });
  }

  /** 复制内容 */
  copyValue(text: string) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }
  /** 下钻操作 */
  chooseDrill(item: IDimensionItem, row: IDataItem) {
    this.drillValue = item.key;
    this.isMultiple = false;
    this.handleDimensionChange([item.key]);
    this.showDimensionKeys.map(key => {
      this.drillList.push({
        key,
        value: row[key],
      });
    });
  }

  /**  清空下钻过滤条件  */
  clearDrillFilter(item: IDimensionItem) {
    this.drillList = this.drillList.filter(drill => item.key !== drill.key);
  }
  /** 维度表格 end */

  render() {
    return (
      <div class='drill-analysis-table'>
        <div class='table-left'>
          <div class='table-left-header'>
            {this.$t('聚合维度')}
            <bk-checkbox
              class='header-checkbox'
              value={this.isMultiple}
              onChange={this.changeMultiple}
            >
              {this.$t('多选')}
            </bk-checkbox>
          </div>
          <bk-input
            placeholder={this.$t('搜索 维度')}
            right-icon={'bk-icon icon-search'}
            value={this.dimensionSearch}
          ></bk-input>
          <div class='dimensions-list'>{this.renderDimensionList()}</div>
        </div>
        <div class='table-right'>
          {this.drillList.length > 0 && (
            <div class='dimensions-filter'>
              {this.drillList.map(item => (
                <bk-tag
                  class='drill-tag'
                  kry={item.key}
                  closable
                  onClose={() => this.clearDrillFilter(item)}
                >
                  <span>{item.key}</span>
                  <span class='tag-eq'>=</span>
                  <span class='tag-value'>{item.value}</span>
                </bk-tag>
              ))}
            </div>
          )}
          <bk-table
            ext-cls='dimensions-table'
            data={this.tableList}
            header-border={false}
            outer-border={false}
            stripe={true}
          >
            {this.renderTableColumn()}
          </bk-table>
        </div>
      </div>
    );
  }
}
