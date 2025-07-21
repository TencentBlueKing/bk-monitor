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
import { Component, Mixins, Prop } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { secToString } from '../../../../components/cycle-input/utils';
import metricTipsContentMixin from '../../../../mixins/metricTipsContentMixinTsx';
import WhereDisplay from './where-display';

import type { IFunctionsValue } from '../../strategy-config-set-new/monitor-data/function-select';
import type { MetricDetail } from '../../strategy-config-set-new/typings';

import './metric-list-item.scss';

interface IProps {
  metric?: MetricDetail;
  expression?: string;
  expFunctions?: IFunctionsValue[];
}

interface IConfigsItem {
  key: 'function' | 'groupBy' | 'interval' | 'localQueryString' | 'logMetricName' | 'method' | 'metricName' | 'where';
  label: string;
  value: string | VueTsxSupport.JSX.Element | VueTsxSupport.JSX.Element[];
  format?: (val: any) => any;
  enabled: boolean;
}

/**
 * 策略详情的指标项展示组件
 */
@Component
class MetricListItem extends Mixins(metricTipsContentMixin) {
  /** 指标数据 */
  @Prop({ type: Object }) metric: MetricDetail;
  /** 是否为表达式 */
  @Prop({ default: '', type: String }) expression: string;
  /** 表达式函数 */
  @Prop({ default: () => [], type: Array }) expFunctions: IFunctionsValue[];

  popoverInstance = null;

  confisList: IConfigsItem[] = [
    {
      key: 'metricName',
      label: window.i18n.tc('指标'),
      enabled: true,
      value: '',
    },
    {
      key: 'localQueryString',
      label: window.i18n.tc('检索语句'),
      enabled: false,
      value: '',
    },
    {
      key: 'method',
      label: window.i18n.tc('汇聚'),
      enabled: false,
      value: '',
    },
    {
      key: 'logMetricName',
      label: window.i18n.tc('指标'),
      enabled: false,
      value: '',
    },
    {
      key: 'interval',
      label: window.i18n.tc('周期'),
      enabled: false,
      value: '',
    },
    {
      key: 'groupBy',
      label: window.i18n.tc('维度'),
      enabled: false,
      value: '',
    },
    {
      key: 'where',
      label: window.i18n.tc('条件'),
      enabled: true,
      value: '',
      format: null,
    },
    {
      key: 'function',
      label: window.i18n.tc('函数'),
      enabled: false,
      value: '',
    },
  ];

  get currentConfigsList() {
    return this.confisList.filter(item => item.enabled);
  }

  get isRealTimeModel() {
    return this.metric.agg_method === 'REAL_TIME';
  }

  created() {
    !this.expression && this.handleConfigsList();
  }

  beforeDestroy() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /** 处理指标展示数据 */
  handleConfigsList() {
    const { metric } = this;
    this.confisList.forEach(item => {
      /** 检索语句 */
      if (item.key === 'localQueryString' && this.metric.canSetQueryString) item.enabled = true;
      /** 汇聚方法 */
      if (item.key === 'method' && this.metric.canSetAggMethod && !this.isRealTimeModel) item.enabled = true;
      /** 汇聚周期 */
      if (item.key === 'interval' && this.metric.canSetAggInterval && !this.isRealTimeModel) item.enabled = true;
      /** 维度 */
      if (item.key === 'groupBy' && this.metric.canSetDimension && !this.isRealTimeModel) item.enabled = true;
      /** 函数 */
      if (item.key === 'function' && this.metric.canSetFunction && !this.isRealTimeModel) item.enabled = true;
      /** 日志关键字指标 */
      if (item.key === 'logMetricName' && this.metric.curRealMetric) item.enabled = true;
      if (item.enabled) {
        switch (item.key) {
          case 'metricName':
            item.value = (
              <span onMouseenter={e => this.handleMetricMouseenter(e)}>
                {metric.metric_field_name || (metric.metric_id as any)}
              </span>
            );
            item.label = this.metricNameLabel();
            break;
          case 'logMetricName':
            item.value = metric.curRealMetric?.metric_field_name || String(metric.curRealMetric?.metric_id);
            break;
          case 'localQueryString':
            item.value = metric.localQueryString;
            break;
          case 'method':
            item.value = metric.agg_method;
            break;
          case 'interval': {
            const unitMap = {
              m: 'min',
              s: 's',
            };

            const interalObj = secToString({ value: metric.agg_interval, unit: '' });
            item.value = `${interalObj?.value} ${unitMap[interalObj?.unit]}`;
            break;
          }
          case 'groupBy':
            item.value = this.handleGroupByTpl();
            break;
          case 'function':
            item.value = this.handleFunctionsTpl();
            break;
          case 'where':
            item.value = this.handleWhereTps();
            break;
          default:
            break;
        }
      }
    });
  }

  handleMetricMouseenter(e) {
    if (this.$refs.metricTipsContent) {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.$refs.metricTipsContent,
        placement: 'right',
        theme: 'monitor-metric-popover',
        arrow: true,
        interactive: true,
        flip: false,
      });
      this.popoverInstance?.show?.(100);
    }
  }

  /** 指标名label */
  metricNameLabel() {
    const { metricMetaId, data_source_label: dataSourceLabel, data_type_label } = this.metric;
    if (metricMetaId === 'bk_monitor|log') {
      return this.$tc('关键字');
    }
    if (dataSourceLabel === 'bk_log_search') {
      return this.$tc('索引集');
    }
    if (metricMetaId === 'custom|event') {
      return this.$tc('自定义事件');
    }
    if (metricMetaId === 'bk_monitor|event') {
      return this.$tc('系统事件');
    }
    if (data_type_label === 'alert' || metricMetaId === 'bk_fta|event') {
      return this.$tc('告警名称');
    }
    return this.$tc('指标');
  }

  /** 维度 */
  handleGroupByTpl() {
    return this.metric.agg_dimension?.length ? (
      <span class='groupby-list'>
        {this.metric.agg_dimension.map(id => {
          const groupByItem = this.metric.dimensions.find(item => item.id === id);
          const name = groupByItem?.name ?? id;
          return (
            <span
              class='groupby-item'
              v-bk-tooltips={{
                content: id,
                trigger: 'mouseenter',
                zIndex: 9999,
                offset: '0, 6',
                boundary: document.body,
                allowHTML: false,
              }}
            >
              {name}
            </span>
          );
        })}
      </span>
    ) : undefined;
  }

  /** 函数 */
  handleFunctionsTpl(functions: IFunctionsValue[] = this.metric.functions) {
    return functions
      .reduce((total, func) => {
        const paramsStr = `${func.params.map(item => item.value).toString()}`;
        const funcStr = `${func.id}${paramsStr ? `(${paramsStr})` : ''}`;
        total.push(funcStr);
        return total;
      }, [])
      .join('; ');
  }

  /** 条件 */
  handleWhereTps() {
    return this.metric.agg_condition?.length ? (
      <WhereDisplay
        groupByList={this.metric.dimensions}
        metric={this.metric}
        value={this.metric.agg_condition}
      />
    ) : undefined;
  }

  render() {
    return (
      <div class='metirc-list-item-wrap'>
        <div class='metric-alias'>
          {this.expression ? <i class='icon-monitor icon-arrow-turn' /> : this.metric.alias?.toLocaleUpperCase?.()}
        </div>
        <div class={['metric-main', { 'is-expression': this.expression }]}>
          {this.expression ? (
            <div class='metric-configs-list'>
              <span class='configs-item'>
                <span class='configs-label'>{this.$t('表达式')} : </span>
                <span class='configs-value configs-expression'>{this.expression?.toLocaleUpperCase?.()}</span>
              </span>
              <span class='configs-item'>
                <span class='configs-label'>{this.$t('函数')} : </span>
                <span class='configs-value configs-expression'>
                  {this.expFunctions.length ? this.handleFunctionsTpl(this.expFunctions) : '--'}
                </span>
              </span>
            </div>
          ) : (
            <div class='metric-configs-list'>
              {this.currentConfigsList.map(item => (
                <span class='configs-item'>
                  <span class='configs-label'>{item.label} : </span>
                  <span class='configs-value'>{item.value || '--'}</span>
                </span>
              ))}
              <span class='flex-item' />
            </div>
          )}
        </div>

        <div style='display:none'>
          {this.metric && <div ref='metricTipsContent'>{this.handleGetMetricTipsContent(this.metric)}</div>}
        </div>
      </div>
    );
  }
}

export default ofType<IProps>().convert(MetricListItem);
