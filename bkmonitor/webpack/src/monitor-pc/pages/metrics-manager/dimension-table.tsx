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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getVariableValue } from '../../../monitor-api/modules/grafana';
import { Debounce } from '../../../monitor-common/utils/utils';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import TagList from '../../components/table-tag-list/table-tag-list';
import CommonTable from '../monitor-k8s/components/common-table';
import { ITableColumn } from '../monitor-k8s/typings';
import { IMetricDetail } from '../strategy-config/strategy-config-set-new/typings';

import './dimension-table.scss';

/* 维度tab字段 */
const dimensionsColumns: ITableColumn[] = [
  { id: 'id', name: window.i18n.tc('维度名'), type: 'string' },
  { id: 'name', name: window.i18n.tc('维度别名'), type: 'string' },
  { id: 'type', name: window.i18n.tc('维度类型'), type: 'string' },
  { id: 'value', name: window.i18n.tc('维度值'), showOverflowTooltip: false, type: 'scoped_slots' }
];

interface IProps {
  show?: boolean;
  detail?: IMetricDetail;
}

@Component
export default class DimensionTable extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => null }) detail: IMetricDetail;

  tableData = [];
  pagination = {
    current: 1,
    count: 0,
    limit: 10,
    showTotalCount: true
  };
  search = '';

  dimensionValues = new Map();

  emptyStatusType: EmptyStatusType = 'empty';

  @Watch('show')
  handleShow(v: boolean) {
    if (v) {
      this.getTableData();
    }
  }

  getTableData() {
    const filterDimension = this.detail.dimensions.filter(item => !!item.is_dimension);
    const dimension = this.search
      ? filterDimension.filter(
          item => String(item.id).indexOf(this.search) > -1 || String(item.name).indexOf(this.search) > -1
        )
      : filterDimension;
    this.pagination.count = dimension.length;
    this.tableData = dimension
      .slice((this.pagination.current - 1) * this.pagination.limit, this.pagination.current * this.pagination.limit)
      .map(item => ({ ...item, values: [] }));
    this.getDimsionValues(this.tableData.map(item => item.id));
  }

  handlePageChange(v: number) {
    this.pagination.current = v;
    this.getTableData();
  }
  handleLimitChange(v: number) {
    this.pagination.current = 1;
    this.pagination.limit = v;
    this.getTableData();
  }

  @Debounce(300)
  handleSearch() {
    this.emptyStatusType = 'search-empty';
    this.pagination.current = 1;
    this.getTableData();
  }

  async getDimsionValues(ids: string[]) {
    const promistList = [];
    const params = id => ({
      bk_biz_id: this.$store.getters.bizId,
      type: 'dimension',
      params: Object.assign(
        {
          data_source_label: this.detail.data_source_label,
          data_type_label: this.detail.data_type_label,
          field: id,
          metric_field: this.detail.metric_field,
          result_table_id: this.detail.result_table_id,
          where: []
        },
        this.detail.data_source_label === 'bk_log_search'
          ? {
              index_set_id: this.detail.index_set_id
            }
          : {}
      )
    });
    const promisFn = id =>
      new Promise((resolve, reject) => {
        const data = this.dimensionValues.get(id);
        if (data) {
          resolve(data);
          return;
        }
        getVariableValue(params(id))
          .then(data => {
            this.dimensionValues.set(id, data);
            resolve(data);
          })
          .catch(() => {
            reject();
          });
      });
    ids.forEach(id => {
      promistList.push(promisFn(id));
    });
    await Promise.all(promistList);
    this.tableData.forEach(item => {
      item.values = this.dimensionValues.get(item.id) || [];
    });
  }

  showMoreTag(values) {
    this.$bkInfo({
      title: '',
      extCls: 'dimension-table-dimension-values-dialog',
      subHeader: this.$createElement('div', { class: 'dimension-values-content' }, [
        this.$createElement('div', { class: 'title' }, this.$tc('维度值')),
        this.$createElement(
          'div',
          { class: 'content-wrap' },
          this.$createElement(
            'div',
            { class: 'content' },
            values.map(item => this.$createElement('span', { class: 'label' }, item.label))
          )
        ),
        this.$createElement('div', { class: 'bottom' }, this.$tc('当前仅展示{0}条数据', [values.length]))
      ]),
      showFooter: false,
      width: 640
    });
  }

  // 处理搜索结果。由于数据是来自于父组件，这里不需要考虑返回异常的情况。
  handleOperation(val: EmptyStatusOperationType) {
    switch (val) {
      // 当搜索结果为空时则提供清空所有筛选的操作。
      case 'clear-filter':
        this.search = '';
        this.handleSearch();
        break;
      default:
        break;
    }
  }

  render() {
    return (
      <div class={['metrics-manager-dimension-table', { displaynone: !this.show }]}>
        <bk-input
          class='dimension-search'
          v-model={this.search}
          clearable
          placeholder={this.$t('输入')}
          rightIcon='bk-icon icon-search'
          on-change={this.handleSearch}
        ></bk-input>
        <CommonTable
          class='dimension-table'
          data={this.tableData}
          columns={dimensionsColumns}
          checkable={false}
          hasColnumSetting={false}
          pagination={this.pagination}
          onPageChange={this.handlePageChange}
          onLimitChange={this.handleLimitChange}
          scopedSlots={{
            value: row =>
              row.values.length ? (
                <TagList
                  list={row.values.map(item => item.label)}
                  onShowMore={() => this.showMoreTag(row.values)}
                ></TagList>
              ) : (
                '--'
              )
          }}
        >
          <EmptyStatus
            type={this.emptyStatusType}
            slot='empty'
            onOperation={this.handleOperation}
          />
        </CommonTable>
      </div>
    );
  }
}
