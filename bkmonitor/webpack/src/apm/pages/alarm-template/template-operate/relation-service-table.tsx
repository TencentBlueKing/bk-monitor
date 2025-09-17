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

import { Debounce, random } from 'monitor-common/utils';
import AcrossPageSelection from 'monitor-pc/components/across-page-selection/across-page-selection';
import { type SelectTypeEnum, SelectType } from 'monitor-pc/components/across-page-selection/typing';

import type { IRelationService } from './typings';

import './relation-service-table.scss';

const { i18n } = window;

interface IProps {
  relationService: IRelationService[];
}

const Columns = {
  service_name: 'service_name',
  relation: 'relation',
} as const;

const RelationStatus = {
  relation: 'relation',
  unRelation: 'unRelation',
} as const;

@Component
export default class RelationServiceTable extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) relationService: IRelationService[];

  /* 搜索值 */
  searchValue = '';
  /* tab列表 */
  tabList = [];
  activeTab: string = RelationStatus.relation;
  relationServiceObj = {
    list: [],
    checked: [],
    selectKeys: new Set(),
    searchTableData: [],
    pagination: {
      current: 1,
      limit: 10,
      count: 0,
    },
  };
  unRelationServiceObj = {
    list: [],
    checked: [],
    selectKeys: new Set(),
    searchTableData: [],
    pagination: {
      current: 1,
      limit: 10,
      count: 0,
    },
  };
  /* 表格数据 */
  tableData: IRelationService[] = [];
  tableColumns = [
    {
      label: i18n.t('服务名称'),
      prop: Columns.service_name,
      minWidth: 230,
      width: 230,
      props: { 'show-overflow-tooltip': true },
      formatter: (row: IRelationService) => {
        return this.tableFormatter(row, Columns.service_name);
      },
    },
    {
      label: i18n.t('当前已关联其他模版'),
      prop: Columns.relation,
      minWidth: 150,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: (row: IRelationService) => {
        return this.tableFormatter(row, Columns.relation);
      },
      renderHeader: () => {
        return this.tableRenderHeader(Columns.relation);
      },
    },
  ];
  /* 标头跨页多选 */
  pageSelection: SelectTypeEnum = SelectType.UN_SELECTED;
  selectionKey = random(8);
  /* 展开行 */
  expandRowKeys = [];
  /* 下发对象预览 */
  previewData: {
    list: IRelationService[];
    type: (typeof RelationStatus)[keyof typeof RelationStatus];
  }[] = [];

  @Watch('relationService', { immediate: true })
  handleWatchRelationService(newVal: IRelationService[]) {
    if (newVal.length) {
      this.relationServiceObj.list = newVal.filter(item => item.same_origin_strategy_template);
      this.unRelationServiceObj.list = newVal.filter(item => !item.same_origin_strategy_template);
      this.tabList = [
        {
          name: RelationStatus.relation,
          label: this.$t('已关联的服务'),
          count: this.relationServiceObj.list.length,
        },
        {
          name: RelationStatus.unRelation,
          label: this.$t('未关联的服务'),
          count: this.unRelationServiceObj.list.length,
        },
      ];
      this.getTableData();
    }
  }

  getTableData() {
    let tableData: IRelationService[] = [];
    tableData = [...this.getCurServiceObj().list];
    this.getCurServiceObj().pagination.count = tableData.length;
    if (this.searchValue) {
      const searchLower = this.searchValue.toLocaleLowerCase();
      tableData = tableData.filter(item => {
        const serviceNameLower = item.service_name.toLocaleLowerCase();
        return serviceNameLower.includes(searchLower);
      });
    }
    this.getCurServiceObj().searchTableData = [...tableData];
    tableData = tableData.slice(
      this.getCurServiceObj().pagination.current * this.getCurServiceObj().pagination.limit -
        this.getCurServiceObj().pagination.limit,
      this.getCurServiceObj().pagination.current * this.getCurServiceObj().pagination.limit
    );
    this.tableData = tableData;
    this.setAcrossPageSelection();
  }

  @Debounce(300)
  handleSearchChange() {
    this.resetPageCurrent();
    this.getTableData();
  }

  handlePageChange(v: number) {
    this.getCurServiceObj().pagination.current = v;
    this.getTableData();
  }
  handleLimitChange(v: number) {
    this.getCurServiceObj().pagination.current = 1;
    this.getCurServiceObj().pagination.limit = v;
    this.getTableData();
  }

  handlePageSelectionChange(v: SelectTypeEnum) {
    this.pageSelection = v;
    switch (v) {
      case SelectType.ALL_SELECTED: {
        this.getCurServiceObj().selectKeys = new Set(this.getCurServiceObj().searchTableData.map(item => item.key));
        break;
      }
      case SelectType.SELECTED: {
        this.getCurServiceObj().selectKeys = new Set(this.tableData.map(item => item.key));
        break;
      }
      case SelectType.UN_SELECTED: {
        this.getCurServiceObj().selectKeys.clear();
        break;
      }
    }
  }

  handleTableRowClick(row: IRelationService) {
    if (this.expandRowKeys.includes(row.key)) {
      this.expandRowKeys = [];
    } else {
      this.expandRowKeys = [row.key];
    }
  }

  handleCheckRow(v: boolean, row: IRelationService) {
    if (v) {
      this.getCurServiceObj().selectKeys.add(row.key);
    } else {
      this.getCurServiceObj().selectKeys.delete(row.key);
    }
    this.setAcrossPageSelection();
  }

  getCurServiceObj() {
    if (this.activeTab === RelationStatus.relation) {
      return this.relationServiceObj;
    } else {
      return this.unRelationServiceObj;
    }
  }

  handleChangeTab(v: string) {
    this.activeTab = v;
    this.resetPageCurrent();
    this.getTableData();
    this.selectionKey = random(8);
  }

  resetPageCurrent() {
    this.getCurServiceObj().pagination.current = 1;
  }

  setAcrossPageSelection() {
    if (this.getCurServiceObj().selectKeys.size) {
      if (this.getCurServiceObj().selectKeys.size === this.tableData.length) {
        this.pageSelection = SelectType.SELECTED;
      } else if (this.getCurServiceObj().selectKeys.size === this.getCurServiceObj().searchTableData.length) {
        this.pageSelection = SelectType.ALL_SELECTED;
      } else {
        this.pageSelection = SelectType.HALF_SELECTED;
      }
    } else {
      this.pageSelection = SelectType.UN_SELECTED;
    }
    this.getCurServiceObj().pagination.current = 1;
  }

  tableFormatter(row: IRelationService, prop: string) {
    switch (prop) {
      case Columns.service_name:
        return <span>{row.service_name}</span>;
      case Columns.relation:
        return (
          <span class='relation-strategy-content'>
            {(() => {
              if (row.same_origin_strategy_template) {
                return [
                  <span
                    key={'01'}
                    class='strategy-name'
                  >
                    {row.same_origin_strategy_template?.name}
                  </span>,
                  <span
                    key={'02'}
                    class='strategy-link'
                  >
                    {this.$t('查看策略')}
                  </span>,
                  <span
                    key={'03'}
                    class='diff-btn'
                  >
                    <span>{this.$t('差异对比')}</span>
                    <span class='icon-monitor icon-double-down' />
                  </span>,
                ];
              }
              return <span class='no-data'>{this.$t('暂无关联')}</span>;
            })()}
          </span>
        );
      default:
        return '';
    }
  }
  tableRenderHeader(prop: string) {
    switch (prop) {
      case Columns.service_name:
        return <span>{this.$t('服务名称')}</span>;
      case Columns.relation:
        return (
          <span class='table-relation-header'>
            {this.$t('当前已关联其他模版')}
            <span class='icon-monitor icon-hint' />
            <span class='tips'>{this.$t('下发将被覆盖')}</span>
          </span>
        );
      default:
        return '';
    }
  }

  render() {
    return (
      <div class='template-details-relation-service-table'>
        <div class='left-table'>
          <bk-tab
            active={this.activeTab}
            on-tab-change={this.handleChangeTab}
          >
            {this.tabList.map(item => (
              <bk-tab-panel
                key={item.name}
                name={item.name}
              >
                <template slot='label'>
                  <span>{item.label}</span>
                  <span>{`(${item.count})`}</span>
                </template>
              </bk-tab-panel>
            ))}
          </bk-tab>
          <div class='left-table-content'>
            <bk-input
              class='search-input'
              v-model={this.searchValue}
              placeholder={`${this.$t('搜索')} ${this.$t('服务名称')}`}
              right-icon='bk-icon icon-search'
              clearable
              onChange={this.handleSearchChange}
            />
            <bk-table
              data={this.tableData}
              expand-row-keys={this.expandRowKeys}
              header-border={false}
              outer-border={false}
              row-key={row => row.key}
              on-row-click={this.handleTableRowClick}
            >
              <bk-table-column
                width={50}
                formatter={row => {
                  return (
                    <span
                      onClick={e => {
                        e.stopPropagation();
                      }}
                    >
                      <bk-checkbox
                        key={`${this.selectionKey}${row.key}`}
                        value={this.getCurServiceObj().selectKeys.has(row.key)}
                        onChange={v => this.handleCheckRow(v, row)}
                      />
                    </span>
                  );
                }}
                render-header={() => {
                  return (
                    <AcrossPageSelection
                      key={`${this.selectionKey}`}
                      value={this.pageSelection}
                      onChange={this.handlePageSelectionChange}
                    />
                  );
                }}
              />
              <bk-table-column
                width={0}
                scopedSlots={{
                  default: () => {
                    return <div>xxxxxx</div>;
                  },
                }}
                type='expand'
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
                  render-header={item?.renderHeader}
                />
              ))}
            </bk-table>
            <bk-pagination
              class='mt-14'
              align='right'
              count={this.getCurServiceObj().pagination.count}
              current={this.getCurServiceObj().pagination.current}
              limit={this.getCurServiceObj().pagination.limit}
              size={'small'}
              show-total-count
              on-change={this.handlePageChange}
              on-limit-change={this.handleLimitChange}
            />
          </div>
        </div>
        <div class='right-preview'>
          <div class='right-preview-header'>{this.$t('下发对象预览')}</div>
        </div>
      </div>
    );
  }
}
