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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../../../monitor-common/utils/utils';
import { xssFilter } from '../../../../../monitor-common/utils/xss';
import DimensionLine from '../../../../../monitor-ui/chart-plugins/plugins/aiops-dimension-point/aiops-dimension-point';

import { EventReportType, IAnomalyDimensions } from './types';

import './dimension.table.scss';

const setTooltips = (content: string, placement = 'left', disabled = false) => ({
  boundary: document.body,
  appendTo: document.body,
  placement,
  content: `${content}`,
  delay: 0,
  zIndex: 9000,
  disabled
});

interface IProps {
  tableData: IAnomalyDimensions[];
  dimensionDrillDownErr?: string;
}

@Component
export default class DimensionTable extends tsc<IProps> {
  @Prop({ type: String, default: '' }) dimensionDrillDownErr: string;

  @Prop({ type: Array, default: () => [] }) tableData: IAnomalyDimensions[];
  @Inject('reportEventLog') reportEventLog: Function;
  /** tips实例 */
  popperInstance: any = null;

  /** 默认全选 */
  isSelectedInit = false;
  selection = [];

  @Watch('tableData')
  handleTableDataChange() {
    !this.isSelectedInit && this.$refs?.dimensionTable?.toggleAllSelection();
    this.isSelectedInit = true;
    this.selection = this.tableData;
  }
  /** JS散度表头 */
  renderHeader(title, content) {
    return (
      <span
        class='js-table-head'
        v-bk-tooltips={{
          content: this.$t(content),
          maxWidth: 188,
          allowHTML: false,
          onShown: () => {
            this.reportEventLog?.(EventReportType.Tips);
          }
        }}
      >
        {this.$t(title)}
      </span>
    );
  }
  getWidth(anomaly_score) {
    const W = anomaly_score * 200;
    return (W < 5 ? 2 + W : W) + 24;
  }
  /** top10集群列表 */
  renderDimensionColumn(row) {
    let labelHtml = '';
    let contentHtml = '';
    row.anomaly_score_top10.forEach(item => {
      const W = this.getWidth(item.anomaly_score);
      labelHtml += `<li onclick="handleTipsItem(${item.is_anomaly},'${item.id}')">
        <span class="label ${item.is_anomaly ? 'is-anomaly-label' : ''}">
        ${xssFilter(item.dimension_value)}
        </span>
        <i class="icon-monitor icon-mc-position-tips"></i>
        <span class='num num-position' style='right: -${
          item.anomaly_score === 0 ? 24 : W
        }px;margin-left: 0px'>${xssFilter(item.anomaly_score)}</span>
        </li>`;
      contentHtml += `<li>
        <span style='width:${W}px' class='progress ${item.is_anomaly ? 'is-abnormal' : ''}'>
          <span class="progress-bar" style='width: ${item.anomaly_score === 0 ? 0 : 100}%' ></span>
          <span class='num'>${xssFilter(item.anomaly_score)}</span>
        </span>
        </li>`;
    });
    const content = `<div class='aiops-dimension-tips-content'>
      <p>${this.$t('异常分值')}（${xssFilter(row.anomaly_dimension_alias)}）</p>
      <div class='aiops-dimension-tips-content-msg'>
        <ul class='label-content'>${labelHtml}</ul>
        <ul class='content'>${contentHtml}</ul>
      </div>
     </div>`;
    return (
      <div class='dimension-num'>
        <span
          v-bk-tooltips={{
            extCls: 'aiops-dimension-tips',
            allowHTML: true,
            ...setTooltips(content, 'bottom'),
            delay: 0,
            onShown: v => {
              this.reportEventLog?.(EventReportType.Tips);
              this.popperInstance = v;
            },
            onHide: () => {
              this.popperInstance = null;
            }
          }}
        >
          {row.dimension_anomaly_value_count} / {row.dimension_value_total_count}
        </span>
      </div>
    );
  }
  percentageText(text) {
    return `${text}%`;
  }
  /** 异常分布点击 */
  @Emit('tipsClick')
  handleDimensionClick(_, id) {
    this.popperInstance?.hide?.();
    return id;
  }
  created() {
    (window as any).handleTipsItem = this.handleTooltipItem;
  }
  beforeDestroy() {
    (window as any).handleTipsItem = null;
  }

  /** 隐藏tips */
  @Debounce(10)
  hideTooltip() {
    this.popperInstance?.hide?.();
  }
  /** tips 单个数据点点击回调 */
  handleTooltipItem(is_anomaly: Boolean, id: string) {
    is_anomaly && this.handleDimensionClick(is_anomaly, id);
  }
  /** 异常分布绘制 */
  renderDistributed({ data, ...info }) {
    return (
      <DimensionLine
        chartData={data}
        info={info}
        {...{
          on: {
            tipsClick: this.handleDimensionClick
          }
        }}
      ></DimensionLine>
    );
  }

  /** 排序 */
  @Emit('sortChange')
  handleSortChange({ column, prop, order }) {
    // this.reportEventLog?.(EventReportType.Click);
    return { column, prop, order };
  }
  /** 表格选择 */
  @Emit('selectionChange')
  handleSelectionChange(selection) {
    this.reportEventLog?.(EventReportType.Click);
    this.selection = selection;
    return selection;
  }
  /** 是否可选择 */
  handleBeforeSelectChange(selected, { store }) {
    if (selected && store.states.selection.length === 1) return false;
  }
  handleBeforeSelectAllChange(selected) {
    if (selected) return false;
  }
  renderTable() {
    return (
      <bk-table
        default-sort={{ order: 'descending', prop: 'dim_surprise' }}
        class={this.selection.length === 1 ? 'disabled-select' : ''}
        ref='dimensionTable'
        outer-border={true}
        col-border={true}
        data={this.tableData}
        {...{
          on: {
            'sort-change': this.handleSortChange,
            'selection-change': this.handleSelectionChange
          }
        }}
        header-border={true}
      >
        <bk-table-column
          type='selection'
          width={32}
          before-select-change={this.handleBeforeSelectChange}
          before-select-all-change={this.handleBeforeSelectAllChange}
        ></bk-table-column>
        <bk-table-column
          label={this.$t('异常维度')}
          show-overflow-tooltip={true}
          scopedSlots={{ default: props => props.row.anomaly_dimension_alias }}
        ></bk-table-column>
        <bk-table-column
          min-width={120}
          label={this.$t('异常维度值个数/维度值总数')}
          scopedSlots={{ default: props => this.renderDimensionColumn(props.row) }}
        ></bk-table-column>
        <bk-table-column
          show-overflow-tooltip={true}
          label={this.$t('异常维度值占比')}
          scopedSlots={{ default: props => this.percentageText(props.row.dimension_value_percent) }}
        ></bk-table-column>
        <bk-table-column
          width={340}
          label={this.$t('异常分值分布')}
          render-header={this.renderHeader.bind(
            this,
            '异常分值分布',
            '异常分值范围从0到1，分值越大，说明该维度值的指标异常程度越高。'
          )}
          scopedSlots={{ default: props => this.renderDistributed(props.row.anomaly_score_distribution) }}
        ></bk-table-column>
        <bk-table-column
          sortable
          sort-orders={['ascending', 'descending']}
          label={this.$t('JS散度')}
          prop='dim_surprise'
          show-overflow-tooltip={true}
          render-header={this.renderHeader.bind(
            this,
            'JS散度',
            'JS散度越大，说明该维度内各维度值的异常分值越离散，越值得排查'
          )}
          scopedSlots={{ default: props => props.row.dim_surprise }}
        ></bk-table-column>
      </bk-table>
    );
  }
  render() {
    return (
      <div class={['dimension-table', !this.tableData.length && 'min-260']}>
        {this.tableData.length > 0 ? (
          this.renderTable()
        ) : (
          <bk-exception
            type={this.dimensionDrillDownErr ? '500' : 'empty'}
            scene='part'
            slot='empty'
          >
            <span>{this.dimensionDrillDownErr ? this.dimensionDrillDownErr : this.$t('暂无数据')}</span>
          </bk-exception>
        )}
      </div>
    );
  }
}
