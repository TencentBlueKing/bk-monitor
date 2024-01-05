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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../monitor-common/utils/utils';
import { secToString } from '../../components/cycle-input/utils';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import CommonTable from '../monitor-k8s/components/common-table';
import { ITableColumn, ITablePagination, TableRow } from '../monitor-k8s/typings/table';
import { IMetricDetail } from '../strategy-config/strategy-config-set-new/typings';

import MetricDetailSide from './metric-detail-side';

import './metrics-table.scss';

export const dataSouceLabes = [
  { id: 'bk_monitor', name: window.i18n.tc('监控采集指标') },
  { id: 'bk_data', name: window.i18n.tc('计算平台指标') },
  { id: 'custom', name: window.i18n.tc('自定义指标') },
  { id: 'bk_log_search', name: window.i18n.tc('日志平台指标') },
  { id: 'bk_apm', name: window.i18n.tc('应用监控Trace指标') }
];

interface IProps {
  tableData?: IMetricDetail[];
  pagination?: ITablePagination;
  emptyStatusType?: EmptyStatusType;
}
interface IEvents {
  onPageChange?: number;
  onLimitChange?: number;
  onConditionChange?: { key: string; value: string }[];
  onDataRetrieval?: string;
  onDataSourceChange?: string[][];
  onEnableChange?: (value: string) => void;
  onClearFilter?: void;
  onRefresh?: void;
}

const tableSettingsKey = 'METRICS_MANAGER_TABLE_SETTINGS';
@Component
export default class MetricsTable extends tsc<IProps, IEvents> {
  /* 表格数据 */
  @Prop({ type: Array, default: () => [] }) tableData: IMetricDetail[] | TableRow[];
  /* 分页数据 */
  @Prop({
    type: Object,
    default: () => ({
      current: 1,
      count: 0,
      limit: 10
    })
  })
  pagination: ITablePagination;
  // 表格查询结果所对应的状态
  @Prop({ type: String, default: 'empty' })
  emptyStatusType: EmptyStatusType;
  /* 列表字段 */
  columns: ITableColumn[] = [];
  /* 指标id搜索及关键字搜索 */
  filter = {
    metric_id: '',
    query: ''
  };
  /* 表头筛选弹出层 */
  filterPopover: {
    instance: any;
    list: { name: string; value: string; checked: string; cancel: string }[];
    checkedList: { column: string; list: string[]; tempList: string[] }[];
    column: string;
  } = {
    instance: null,
    list: [], // 弹出的选项
    checkedList: [], // 已选中的选项
    column: '' // 当前弹出的字段
  };
  /* 详情 */
  details: {
    show: boolean;
    data: IMetricDetail;
  } = {
    data: null,
    show: false
  };
  /* 是否显示搜索栏 */
  showSearch = true;

  created() {
    this.columns = [
      {
        id: 'metricName',
        name: window.i18n.t('指标名') as string,
        type: 'scoped_slots',
        checked: true,
        disabled: true
      },
      { id: 'alias', name: window.i18n.t('指标别名') as string, type: 'scoped_slots', checked: true },
      {
        id: 'dataSourceLabel',
        name: window.i18n.t('数据来源') as string,
        type: 'scoped_slots',
        checked: true,
        renderHeader: () => this.renderHeader('data_source_label')
      },
      {
        id: 'unit',
        name: window.i18n.t('单位') as string,
        type: 'string',
        checked: true /* renderHeader: () => this.renderHeader('unit') */
      },
      { id: 'resultTableName', name: window.i18n.t('指标分组') as string, type: 'scoped_slots', checked: false },
      { id: 'interval', name: window.i18n.t('数据步长') as string, type: 'scoped_slots', checked: false },
      { id: 'description', name: window.i18n.t('描述') as string, type: 'scoped_slots', checked: false },
      { id: 'resultTableLabelName', name: window.i18n.t('监控对象') as string, type: 'scoped_slots', checked: false },
      {
        id: 'enable',
        name: window.i18n.t('启/停') as string,
        type: 'scoped_slots',
        renderHeader: () => this.renderHeader('enable'),
        checked: true,
        disabled: true
      },
      { id: 'operate', name: window.i18n.t('操作') as string, type: 'scoped_slots', checked: true, disabled: true }
    ];
    const tableSettingsStr = localStorage.getItem(tableSettingsKey);
    if (tableSettingsKey && Array.isArray(JSON.parse(tableSettingsStr))) {
      const tableSettings = JSON.parse(tableSettingsStr);
      this.columns.forEach(item => {
        if (!item?.disabled) {
          item.checked = tableSettings.includes(item.id);
        }
      });
    }
  }

  handleDetailShow(row: IMetricDetail) {
    this.details.data = row;
    this.details.show = true;
  }

  /* 选中表头筛选项 */
  handleCheckTabelHeader(id = '') {
    const setData = (list: string[]) => {
      this.filterPopover.list.forEach(item => {
        if (list.includes(item.checked)) {
          item.value = item.checked;
        } else {
          item.value = '';
        }
      });
    };
    const checkedItem = this.filterPopover.checkedList.find(item => item.column === this.filterPopover.column);
    if (!id) {
      setData(checkedItem.tempList);
      return;
    }
    if (checkedItem) {
      const index = checkedItem.tempList.findIndex(item => item === id);
      if (index < 0) {
        checkedItem.tempList.push(id);
      } else {
        checkedItem.tempList.splice(index, 1);
      }
      setData(checkedItem.tempList);
    } else {
      this.filterPopover.checkedList.push({
        column: this.filterPopover.column,
        list: [],
        tempList: [id]
      });
      setData([id]);
    }
  }

  /* 表头筛选项弹出层dom */
  getLabelMenu() {
    const changeFn = () => {
      if (this.filterPopover.column === 'data_source_label') {
        this.handleEnableChange();
      } else if (this.filterPopover.column === 'enable') {
        this.handleEnableChange();
      }
    };
    const confirm = () => {
      const checkedItem = this.filterPopover.checkedList.find(item => item.column === this.filterPopover.column);
      if (checkedItem) {
        checkedItem.list = [...checkedItem.tempList];
      }
      this.filterPopover.instance.destroy();
      this.filterPopover.instance = null;
      changeFn();
    };
    const cancel = () => {
      const checkedItem = this.filterPopover.checkedList.find(item => item.column === this.filterPopover.column);
      if (checkedItem) {
        checkedItem.tempList = [];
        checkedItem.list = [];
      }
      this.filterPopover.instance.destroy();
      this.filterPopover.instance = null;
      changeFn();
    };
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='labelMenu'
          class='metrics-manager-label-menu-wrapper'
        >
          <ul class='label-menu-list'>
            {this.filterPopover.list.map(item => (
              <li
                class='item'
                key={item.checked}
              >
                <bk-checkbox
                  value={item.value}
                  trueValue={item.checked}
                  falseValue={item.cancel}
                  on-change={() => this.handleCheckTabelHeader(item.checked)}
                ></bk-checkbox>
                <span class='name'>{item.name}</span>
              </li>
            ))}
          </ul>
          <div class='footer'>
            <div class='btn-group'>
              <bk-button
                text
                onClick={() => confirm()}
              >
                {window.i18n.t('确定')}
              </bk-button>
              <bk-button
                text
                onClick={() => cancel()}
              >
                {window.i18n.t('重置')}
              </bk-button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* 指标类型filterheader */
  renderHeader(id: string) {
    const handleShow = e => {
      this.filterPopover.column = id;
      if (id === 'enable') {
        this.filterPopover.list = [
          { name: window.i18n.tc('启用'), value: '', checked: 'enable', cancel: '' },
          { name: window.i18n.tc('停用'), value: '', checked: 'un_enable', cancel: '' }
        ];
      }
      if (id === 'data_source_label') {
        this.filterPopover.list = dataSouceLabes.map(item => ({
          name: item.name,
          value: '',
          checked: item.id,
          cancel: ''
        }));
      }
      const checkedItem = this.filterPopover.checkedList.find(item => item.column === this.filterPopover.column);
      if (checkedItem) {
        checkedItem.tempList = [...checkedItem.list];
        this.handleCheckTabelHeader();
      }
      if (!this.filterPopover.instance) {
        this.filterPopover.instance = this.$bkPopover(e.target, {
          content: this.$refs.labelMenu,
          trigger: 'click',
          arrow: false,
          theme: 'light common-monitor shield',
          maxWidth: 520,
          offset: '0, -11',
          sticky: true,
          duration: [275, 0],
          interactive: true,
          onHidden: () => {
            this.filterPopover.instance.destroy();
            this.filterPopover.instance = null;
            this.filterPopover.checkedList.forEach(item => {
              item.tempList = [];
            });
          }
        });
      }
      this.filterPopover.instance?.show?.(100);
    };
    const names = {
      data_source_label: window.i18n.t('数据来源'),
      enable: window.i18n.t('启/停')
    };
    const active = !!this.filterPopover.checkedList.find(item => item.column === id)?.list?.length;
    return (
      <span
        onClick={e => handleShow(e)}
        class={['custom-label', { active }]}
      >
        {names[id]}
        <i class='icon-monitor icon-filter-fill'></i>
      </span>
    );
  }

  handleShowSearch() {
    this.showSearch = !this.showSearch;
  }

  @Emit('pageChange')
  handlePageChange(page: number) {
    return page;
  }
  @Emit('limitChange')
  handleLimitChange(limit: number) {
    return limit;
  }

  @Debounce(300)
  @Emit('conditionChange')
  handleConditionChange() {
    const condition = [];
    if (this.filter.query) {
      condition.push({
        key: 'query',
        value: this.filter.query
      });
    }
    if (this.filter.metric_id) {
      condition.push({
        key: 'metric_id',
        value: this.filter.metric_id
      });
    }
    return condition;
  }

  @Emit('dataSourceChange')
  handleDataSourceChange() {
    let dataSource = [];
    if (this.filterPopover.checkedList.length) {
      this.filterPopover.checkedList.forEach(item => {
        if (item.column === 'data_source_label') {
          if (item.list.length) {
            dataSource = item.list.map(value => [value, 'time_series']);
          }
        }
      });
    }
    return dataSource;
  }
  @Emit('enableChange')
  handleEnableChange() {
    let enableTypes = [];
    if (this.filterPopover.checkedList.length) {
      this.filterPopover.checkedList.forEach(item => {
        if (item.column === 'enable') {
          enableTypes = item.list;
        }
      });
    }
    return enableTypes;
  }

  @Emit('dataRetrieval')
  handleToDataRetrieval(metricId: string) {
    return metricId;
  }

  handleColumnSettingChange(value) {
    localStorage.setItem(tableSettingsKey, JSON.stringify(value));
  }

  // 处理搜索结果
  handleOperation(val: EmptyStatusOperationType) {
    switch (val) {
      // 当搜索结果为空时则提供清空所有筛选的操作，这里父组件也已进行清空。
      case 'clear-filter':
        this.$emit('clearFilter');
        this.filter.metric_id = '';
        this.filter.query = '';
        this.filterPopover.checkedList.length = 0;
        break;
      // 当服务端返回异常时，让用户点击刷新，重新请求一次。
      case 'refresh':
        this.$emit('refresh');
        break;
      default:
        break;
    }
  }

  render() {
    return (
      <div class='metrics-table-component'>
        {/* <div class="header">
          <div class="left">
            {this.$slots?.headerLeft}
            <bk-button class="left-button">{window.i18n.t('分位数统计')}</bk-button>
            <bk-button>{window.i18n.t('多指标计算')}</bk-button>
          </div>
          <div class="right">
            <div class={['filter-btn', { active: this.showSearch }]} onClick={this.handleShowSearch}>
              <span class="icon-monitor icon-filter"></span>
            </div>
          </div>
        </div> */}
        {this.showSearch && (
          <div class='search-header'>
            {this.$slots?.headerLeft}
            <bk-input
              class='metric-input'
              v-model={this.filter.metric_id}
              clearable
              placeholder={window.i18n.t('输入指标id搜索')}
              rightIcon={'bk-icon icon-search'}
              on-change={this.handleConditionChange}
            >
              <div
                slot='prepend'
                class='group-text'
              >
                {window.i18n.t('指标')}
              </div>
            </bk-input>
            <bk-input
              v-model={this.filter.query}
              right-icon='bk-icon icon-search'
              placeholder={this.$t('输入')}
              clearable
              on-change={this.handleConditionChange}
            ></bk-input>
          </div>
        )}
        <div class={['content', { 'show-search': this.showSearch }]}>
          <CommonTable
            columns={this.columns}
            data={this.tableData}
            pagination={this.pagination}
            checkable={false}
            scopedSlots={{
              metricName: row => {
                const name = (() => {
                  if (`${row.data_source_label}_${row.data_type_label}` === 'log_time_series') {
                    return `${row.related_name}.${row.metric_field}`;
                  }
                  if (row.result_table_id) {
                    return `${row.result_table_id}.${row.metric_field}`;
                  }
                  return row.metric_field;
                })();
                return (
                  <span
                    class='link'
                    onClick={() => this.handleDetailShow(row)}
                  >
                    {name}
                  </span>
                );
              },
              alias: row => {
                const alias =
                  !row.metric_field_name || row.metric_field_name === row.metric_field ? '' : row.metric_field_name;
                return <span>{alias || '--'}</span>;
              },
              dataSourceLabel: row => dataSouceLabes.find(item => item.id === row.data_source_label)?.name || '--',
              resultTableName: row => row.result_table_name || '--',
              interval: row => {
                const collectInterval = row.collect_interval < 5 ? 60 : row.collect_interval;
                const interalObj = secToString({ value: collectInterval, unit: '' });
                const interval = `${interalObj?.value}${interalObj?.unit}`;
                return interval;
              },
              description: row => row.description || '--',
              resultTableLabelName: row => row.result_table_label_name || '--',
              enable: () => this.$t('启用'),
              operate: row => [
                <bk-button
                  text
                  onClick={() => this.handleToDataRetrieval(row.metric_id)}
                >
                  {this.$t('检索')}
                </bk-button>
              ]
            }}
            onPageChange={this.handlePageChange}
            onLimitChange={this.handleLimitChange}
            onColumnSettingChange={this.handleColumnSettingChange}
          >
            <EmptyStatus
              type={this.emptyStatusType}
              slot='empty'
              onOperation={this.handleOperation}
            />
          </CommonTable>
        </div>
        {this.getLabelMenu()}
        <MetricDetailSide
          show={this.details.show}
          detail={this.details.data}
          onShowChange={(v: boolean) => (this.details.show = v)}
        ></MetricDetailSide>
      </div>
    );
  }
}
