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

import AcrossPageSelection from 'monitor-pc/components/across-page-selection/across-page-selection';
import { type SelectTypeEnum, SelectType } from 'monitor-pc/components/across-page-selection/typing';

import type { IRelationService } from './typings';

import './relation-service-table.scss';

const { i18n } = window;

interface IProps {
  relationService: IRelationService[];
}

@Component
export default class RelationServiceTable extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) relationService: IRelationService[];

  searchValue = '';

  tableData: IRelationService[] = [];
  tableColumns = [
    {
      label: i18n.t('服务名称'),
      prop: 'service_name',
      minWidth: 230,
      width: 230,
      props: { 'show-overflow-tooltip': true },
      formatter: () => {},
    },
    {
      label: i18n.t('当前已关联其他模版'),
      prop: 'service_type',
      minWidth: 150,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: () => {},
    },
  ];
  pagination = {
    current: 1,
    limit: 10,
    count: 10,
  };

  pageSelection: SelectTypeEnum = SelectType.UN_SELECTED;

  @Watch('relationService', { immediate: true })
  handleWatchRelationService(newVal: IRelationService[]) {
    if (newVal.length) {
      this.tableData = newVal;
    }
  }

  handleSearchChange(v: string) {
    console.log(v);
  }

  handlePageChange(v: number) {
    this.pagination.current = v;
  }
  handleLimitChange(v: number) {
    this.pagination.current = 1;
    this.pagination.limit = v;
  }

  handlePageSelectionChange(v: SelectTypeEnum) {
    this.pageSelection = v;
  }

  render() {
    return (
      <div class='template-details-relation-service-table'>
        <div class='left-table'>
          <bk-input
            class='search-input'
            v-model={this.searchValue}
            placeholder={`${this.$t('搜索')} ${this.$t('服务名称')}`}
            right-icon='bk-icon icon-search'
            clearable
            onChange={this.handleSearchChange}
          />
          <bk-table data={this.tableData}>
            <bk-table-column
              width={60}
              render-header={() => {
                return (
                  <AcrossPageSelection
                    value={this.pageSelection}
                    onChange={this.handlePageSelectionChange}
                  />
                );
              }}
              type='selection'
            />
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
          <bk-pagination
            align='right'
            count={this.pagination.count}
            current={this.pagination.current}
            limit={this.pagination.limit}
            show-total-count
            on-change={this.handlePageChange}
            on-limit-change={this.handleLimitChange}
          />
        </div>
        <div class='right-preview'>xxx</div>
      </div>
    );
  }
}
