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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import type { IStrategiesItem } from './typings';
import type { EmptyStatusOperationType } from 'monitor-pc/components/empty-status/types';

import './alert-service-table.scss';

interface IProps {
  strategies?: IStrategiesItem[];
  onGoAlarm?: (id: string) => void;
  onGoService?: (serviceName: string) => void;
  onGoStrategy?: (strategyId: number | string) => void;
  onGoTemplatePush?: () => void;
  onUnApply?: (params: { service_names: string[]; strategy_ids: number[] }) => void;
}

const Columns = {
  service_name: 'service_name',
  alert_number: 'alert_number',
  operator: 'operator',
} as const;

@Component
export default class AlertServiceTable extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) strategies: IStrategiesItem[];

  searchValue = '';

  tableData = [];
  tableColumns = [
    {
      label: window.i18n.t('关联服务名称'),
      prop: Columns.service_name,
      minWidth: 216,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: (row: IStrategiesItem) => {
        return this.tableFormatter(row, Columns.service_name);
      },
    },
    {
      label: window.i18n.t('告警数量'),
      prop: Columns.alert_number,
      minWidth: 100,
      width: null,
      props: { 'show-overflow-tooltip': true, sortable: 'custom' },
      formatter: (row: IStrategiesItem) => {
        return this.tableFormatter(row, Columns.alert_number);
      },
    },
    {
      label: window.i18n.t('告警数量'),
      prop: Columns.operator,
      minWidth: 187,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: (row: IStrategiesItem) => {
        return this.tableFormatter(row, Columns.operator);
      },
    },
  ];
  sortInfo = {
    column: null,
    prop: null,
    order: null,
  };

  @Watch('strategies', { immediate: true })
  handleWatchStrategies(val) {
    if (val.length) {
      this.tableData = [...val];
    }
  }

  @Debounce(300)
  handleSearchChange() {
    this.getFilterTableData();
  }

  handleSortChange({ column, prop, order }) {
    this.sortInfo = {
      column,
      prop,
      order,
    };
    this.getFilterTableData();
  }

  handleGoServiceDetail(serviceName: string) {
    this.$emit('goService', serviceName);
  }
  handleGoAlarm(id) {
    this.$emit('goAlarm', id);
  }
  handleGoTemplatePush() {
    this.$emit('goTemplatePush');
  }
  handleGoStrategy(strategyId: number | string) {
    this.$emit('goStrategy', strategyId);
  }
  handleUnApply(row: IStrategiesItem) {
    this.$emit('unApply', {
      strategy_ids: [row.strategy_id],
      service_names: [row.service_name],
    });
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchValue = '';
      this.getFilterTableData();
    }
  }

  getFilterTableData() {
    const { prop, order } = this.sortInfo;
    const searchTable = this.searchValue
      ? [...this.strategies].filter(item => {
          const searchLower = this.searchValue.toLocaleLowerCase();
          return item.service_name.toLocaleLowerCase().includes(searchLower);
        })
      : [...this.strategies];
    if (prop === Columns.alert_number && order) {
      this.tableData = searchTable.sort((a, b) => {
        if (order === 'ascending') {
          return a[prop] - b[prop];
        }
        return b[prop] - a[prop];
      });
    } else {
      this.tableData = searchTable;
    }
  }

  tableFormatter(row: IStrategiesItem, prop: string) {
    switch (prop) {
      case Columns.service_name:
        return (
          <span
            class='table-link'
            onClick={() => this.handleGoServiceDetail(row.service_name)}
          >
            {row.service_name}
          </span>
        );
      case Columns.alert_number:
        return (
          <span
            class='table-link'
            onClick={() => this.handleGoAlarm(row.strategy_id)}
          >
            {row.alert_number}
          </span>
        );
      case Columns.operator:
        return (
          <span>
            <span
              style='margin-right: 8px;'
              class='table-link'
              onClick={() => this.handleUnApply(row)}
            >
              {this.$t('解除关联')}
            </span>
            <span
              style='margin-right: 8px;'
              class='table-link'
              onClick={() => this.handleGoStrategy(row.strategy_id)}
            >
              {this.$t('查看策略')}
            </span>
          </span>
        );
      default:
        return '';
    }
  }

  render() {
    return (
      <div class='template-details-alert-service-table'>
        <div class='top-tips'>
          <span class='icon-monitor icon-hint' />
          <i18n path='可以通过 {0} 来关联更多的服务。'>
            <span
              class='link'
              onClick={this.handleGoTemplatePush}
            >
              {this.$t('策略下发')}
            </span>
          </i18n>
        </div>
        <bk-input
          class='search-input'
          v-model={this.searchValue}
          placeholder={`${this.$t('搜索')} ${this.$t('服务名称')}`}
          right-icon='bk-icon icon-search'
          clearable
          onChange={this.handleSearchChange}
        />
        <bk-table
          default-sort={{
            prop: Columns.alert_number,
            order: 'descending',
          }}
          data={this.tableData}
          on-sort-change={this.handleSortChange}
        >
          <div slot='empty'>
            <EmptyStatus
              type={this.searchValue ? 'search-empty' : 'empty'}
              onOperation={this.handleOperation}
            />
          </div>
          {this.tableColumns.map(item => (
            <bk-table-column
              key={item.prop}
              label={item.label}
              prop={item.prop}
              {...{ props: item.props }}
              width={item.width}
              formatter={item.formatter}
              min-width={item.minWidth}
            />
          ))}
        </bk-table>
      </div>
    );
  }
}
