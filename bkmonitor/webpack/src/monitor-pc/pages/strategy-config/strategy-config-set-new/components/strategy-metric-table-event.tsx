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
/*
 * @Date: 2021-06-17 19:16:02
 * @LastEditTime: 2021-06-23 16:11:05
 * @Description: 事件指标表格组件
 */
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { throttle } from 'throttle-debounce';

import { TMode } from './strategy-metric-wrap';

import './strategy-metric-table-event.scss';

const { i18n } = window;

interface IEventTable {
  data: any;
  type: string;
  mode: string;
  checked?: string[];
  readonly?: boolean;
}

interface IEvent {
  onScrollToEnd?: boolean;
  onCheckedChange?: any;
}

@Component
export default class StrategyMetricTable extends tsc<IEventTable, IEvent> {
  @Prop({ default: () => [], type: Array }) data: any;
  @Prop({ default: '', type: String }) type: any;
  @Prop({ default: 'event', type: String }) mode: TMode;
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: () => [], type: Array }) checked: string[];
  @Ref('metricTable') metricTable: any;

  eventTableColumnMap = {
    bk_monitor: [{ label: i18n.t('事件名称'), prop: 'metric_field_name', key: 'name' }],
    custom: [
      { label: i18n.t('事件名称'), prop: 'metric_field_name', key: 'name' },
      { label: i18n.t('数据ID'), prop: 'result_table_id', key: 'id' },
      { label: i18n.t('数据名称'), prop: 'result_table_name', key: 'dataName' }
    ],
    bk_fta: [{ label: i18n.t('告警名称'), prop: 'metric_field_name', key: 'name' }]
  };
  logTableColumnMap = {
    bk_monitor: [
      { label: i18n.t('采集项ID'), prop: 'related_id', key: 'id' },
      { label: i18n.t('采集项名称'), prop: 'metric_field_name', key: 'name' }
    ],
    bk_log_search: [
      { label: i18n.t('索引集'), prop: 'index_set_name', key: 'index_set_name' },
      { label: i18n.t('索引'), prop: 'result_table_id', key: 'result_table_id' },
      { label: i18n.t('数据源'), prop: 'scenario_name', key: 'scenario_name' }
    ],
    bk_apm: [
      { label: i18n.t('应用名称'), prop: 'name', key: 'name' },
      { label: i18n.t('结果表'), prop: 'result_table_id', key: 'result_table_id' }
    ]
  };
  scrollEl: HTMLElement = null;
  throttleScroll: any = () => {};

  get getCurTabTableColumn() {
    const map = {
      event: this.eventTableColumnMap[this.type],
      log: this.logTableColumnMap[this.type]
    };
    return map[this.mode];
  }

  @Emit('scrollToEnd')
  emitScrollToEnd(v: boolean) {
    return v;
  }
  @Emit('checkedChange')
  emitCheckedChange(v: number[], rows?: any[]) {
    return {
      ids: v,
      rows
    };
  }

  mounted() {
    this.handleBindScrollEvent();
  }

  handleBindScrollEvent() {
    this.scrollEl = this.metricTable.$el.querySelector('.bk-table-body-wrapper');
    this.throttleScroll = throttle(300, false, this.handleTableScroll);
    this.scrollEl.addEventListener('scroll', this.throttleScroll);
  }
  handleTableScroll(e) {
    const { scrollHeight } = e.target;
    const { scrollTop } = e.target;
    const { clientHeight } = e.target;
    const isEnd = scrollHeight - scrollTop === clientHeight && scrollTop;
    this.emitScrollToEnd(isEnd);
  }
  hendleRadioChnage(v: boolean, row) {
    if (!v) return this.emitCheckedChange([], []);
    this.emitCheckedChange([row.metric_id], [row]);
  }
  // getRowId(row) {
  //   if (this.mode === 'event') return row.id
  //   if (this.mode === 'log') return row.data_source_label === 'bk_monitor' ? row.id : row.index_set_id
  // }

  render() {
    const scopedSlots = {
      default: ({ row }) => (
        <bk-radio
          disabled={this.readonly}
          value={this.checked.includes(row.metric_id)}
          onChange={v => this.hendleRadioChnage(v, row)}
        ></bk-radio>
      )
    };
    const scopedSlotsLog = {
      default: ({ row }) => row?.extend_fields?.scenario_name || ''
    };
    return (
      <div class='strategy-metric-table-event'>
        <bk-table
          ref='metricTable'
          outer-border={false}
          height={397}
          max-height={397}
          data={this.data || []}
        >
          <bk-table-column
            width={48}
            scopedSlots={scopedSlots}
          ></bk-table-column>
          {this?.getCurTabTableColumn?.map(item => {
            // 日志平台数据源
            if (this.mode === 'log' && this.type === 'bk_log_search' && item.key === 'scenario_name') {
              return (
                <bk-table-column
                  label={item.label}
                  prop={item.prop}
                  width={item.width}
                  scopedSlots={scopedSlotsLog}
                ></bk-table-column>
              );
            }
            return (
              <bk-table-column
                label={item.label}
                prop={item.prop}
                width={item.width}
              ></bk-table-column>
            );
          })}
        </bk-table>
      </div>
    );
  }
}
