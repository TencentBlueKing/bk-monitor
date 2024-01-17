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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getStrategyListV2 } from '../../../monitor-api/modules/strategies';
import { secToString } from '../../components/cycle-input/utils';
import MonitorTab from '../../components/monitor-tab/monitor-tab';
// import InputConfirm from './input-confirm';
import { IMetricDetail } from '../strategy-config/strategy-config-set-new/typings';

import HandleExperience from './components/handle-experiences';
import DimensionTable from './dimension-table';
import { dataSouceLabes } from './metrics-table';

import './metric-detail-side.scss';

interface IProps {
  show?: boolean;
  detail?: IMetricDetail;
}

interface IEvents {
  onShowChange?: boolean;
}

@Component
export default class MetricDetailSide extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => null }) detail: IMetricDetail;

  localShow = false;

  title = '';

  metricData = {
    statistics: {
      strategyCount: 0
    },
    info: {
      left: [],
      right: []
    }
  };

  tabData = {
    active: '',
    list: [
      { id: 'dimension', name: window.i18n.t('维度') },
      { id: 'handleExperience', name: window.i18n.t('处理经验') }
    ]
  };

  @Watch('show')
  handleShow(show: boolean) {
    this.localShow = show;
    if (show) {
      this.$nextTick(() => {
        this.tabData.active = 'dimension';
      });
      this.init();
    } else {
      this.tabData.active = '';
    }
  }

  init() {
    const metricName =
      `${this.detail.data_source_label}_${this.detail.data_type_label}` === 'log_time_series'
        ? `${this.detail.related_name}.${this.detail.metric_field}`
        : this.detail.result_table_id
          ? `${this.detail.result_table_id}.${this.detail.metric_field}`
          : this.detail.metric_field;
    const alias = this.detail.metric_field_name;
    this.title = `${metricName}${this.$t('指标详情')}`;
    const collectInterval = this.detail.collect_interval < 5 ? 60 : this.detail.collect_interval;
    const interalObj = secToString({ value: collectInterval, unit: '' });
    const interval = `${interalObj?.value}${interalObj?.unit}`;
    this.metricData.info.left = [
      { label: this.$tc('指标名'), value: metricName },
      { label: this.$tc('指标别名'), value: alias },
      // { label: this.$tc('指标类型'), value: '--' },
      { label: this.$tc('指标分组'), value: this.detail.result_table_name || '--' },
      // { label: this.$tc('数值类型'), value: '--' },
      { label: this.$tc('单位'), value: this.detail.unit || '--' },
      { label: this.$tc('数据步长'), value: interval }
    ];
    this.metricData.info.right = [
      {
        label: this.$tc('数据来源'),
        value: dataSouceLabes.find(item => item.id === this.detail.data_source_label)?.name
      },
      { label: '描述', value: this.detail.description || '--' },
      { label: '监控对象', value: this.detail.result_table_label_name || '--' },
      // { label: '创建时间', value: '--' },
      // { label: '标签', value: '--' },
      {
        label: '启/停',
        value: (
          <bk-switcher
            value={true}
            theme='primary'
            disabled
            size={'small'}
          ></bk-switcher>
        )
      }
    ];
    this.getStrategyCount();
  }

  @Emit('showChange')
  emitShow(show: boolean) {
    return show;
  }

  handleTabChange(id: string) {
    this.tabData.active = id;
  }

  /* 获取策略数 */
  async getStrategyCount() {
    const dataSourceList = await getStrategyListV2({
      conditions: [{ key: 'metric_id', value: [this.detail.metric_id] }],
      page: 1,
      page_size: 1
    })
      .then(data => data.data_source_list)
      .catch(() => []);
    this.metricData.statistics.strategyCount = dataSourceList.reduce((total, item) => total + item.count, 0);
  }

  handleToDataRetrieval() {
    window.open(
      `${location.origin}${location.pathname}${location.search}#/data-retrieval/?metric_id=${this.detail.metric_id}`
    );
  }

  render() {
    const infoItem = (label, content) => (
      <div class='info-item'>
        <span class='label'>{label}</span>
        <span class='content'>{content || '--'}</span>
      </div>
    );
    return (
      <bk-sideslider
        extCls='metric-detail-side-component'
        isShow={this.localShow}
        width={960}
        quickClose
        transfer
        beforeClose={() => this.emitShow(false)}
      >
        <div
          slot='header'
          class='side-header'
        >
          <span class='left'>{this.title}</span>
          <span
            class='right'
            onClick={this.handleToDataRetrieval}
          >
            <span>{this.$t('检索')}</span>
            <span class='icon-monitor icon-fenxiang'></span>
          </span>
        </div>
        <div
          slot='content'
          class='side-content'
        >
          <div class='content-bg'>
            <div class='statistics'>
              <span>
                {this.$t('策略数')} : {this.metricData.statistics.strategyCount}
              </span>
            </div>
            <div class='info'>
              <div class='title'>{this.$t('指标信息')}</div>
              <div class='info-content'>
                <div class='left'>{this.metricData.info.left.map(item => infoItem(item.label, item.value))}</div>
                <div class='right'>{this.metricData.info.right.map(item => infoItem(item.label, item.value))}</div>
              </div>
            </div>
            <MonitorTab
              active={this.tabData.active}
              type='unborder-card'
              extCls='content-tab'
              on-tab-change={this.handleTabChange}
            >
              {this.tabData.list.map(item => (
                <bk-tab-panel
                  name={item.id}
                  label={item.name}
                  key={item.id}
                ></bk-tab-panel>
              ))}
            </MonitorTab>
          </div>
          <div class='tab-container'>
            <DimensionTable
              show={this.tabData.active === 'dimension'}
              detail={this.detail}
            ></DimensionTable>
            <HandleExperience
              show={this.tabData.active === 'handleExperience'}
              metricData={this.detail}
            ></HandleExperience>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
