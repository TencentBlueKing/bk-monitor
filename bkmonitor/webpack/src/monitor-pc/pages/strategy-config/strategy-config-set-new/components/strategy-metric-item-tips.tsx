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

import type { MetricDetail } from '../typings/index';

interface StrategyMetricItemTipsProps {
  data: MetricDetail;
  scenarioType: string;
}

@Component({
  name: 'StrategyMetricItemTips',
})
export default class StrategyMetricItemTips extends tsc<StrategyMetricItemTipsProps> {
  @Prop({ default: () => {}, type: Object }) data: MetricDetail;
  @Prop({ default: '', type: String }) scenarioType: string;

  public popoverInstance = null;
  public uptimeCheckTaskId = -1;
  public hoverTimer = null;
  public sourceType = '';

  handleNameEnter(e: Event, data) {
    if (this.scenarioType === 'uptimecheck' && data.disabled) {
      this.uptimeCheckTaskId = Number(data.related_id);
    }
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.hoverTimer = setTimeout(() => {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.handleTips(data),
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'auto',
        boundary: 'window',
      });
      this.popoverInstance.show();
    }, 1000);
  }
  handleNameLeave() {
    this.handleTipsLeave();
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
  }

  //  跳转拨测任务
  handleToUptimcheck() {
    this.handleTipsLeave();
    this.$router.push({
      name: 'uptime-check',
      params: {
        taskId: this.uptimeCheckTaskId.toString(),
      },
    });
  }

  getUptimecheckTips() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='uptimecheckTips'
          class='uptimecheck-tips'
          on-mouseleave={this.handleTipsLeave}
        >
          {this.$t('该指标需设置期望返回码/期望响应信息后才可选取')}
          <span
            style={{ color: ' #3a9eff', cursor: 'pointer' }}
            class='set-uptimecheck'
            on-click={this.handleToUptimcheck}
          >
            {' '}
            {this.$t('前往设置')}{' '}
          </span>
        </div>
      </div>
    );
  }
  // 去除指标tip
  handleTipsLeave() {
    if (this.popoverInstance) {
      this.popoverInstance.hide(0);
      this.popoverInstance.destroy();
      this.popoverInstance = null;
    }
  }

  handleTips(data) {
    this.sourceType =
      data.data_source_label === 'bk_log_search' && data.data_type_label === 'time_series'
        ? 'log_time_series'
        : `${data.data_source_label}_${data.data_type_label}`;
    if (this.scenarioType === 'uptimecheck' && data.default_condition) {
      const response = data.default_condition.find(item => item.key === 'response_code' || item.key === 'message');
      if (response && !response.value) {
        return this.$refs.uptimecheckTips;
      }
    }
    const options = [
      // 公共展示项
      { val: data.metric_field, label: this.$t('指标名') },
      { val: data.metric_field_name, label: this.$t('指标别名') },
    ];
    const elList = {
      bk_monitor_time_series: [
        // 监控采集指标
        ...options,
        { val: data.related_id, label: this.$t('插件ID') },
        { val: data.related_name, label: this.$t('插件名') },
        { val: data.result_table_id, label: this.$t('分类ID') },
        { val: data.result_table_name, label: this.$t('分类名') },
        { val: data.description, label: this.$t('含义') },
      ],
      log_time_series: [
        // 日志平台指标
        ...options,
        { val: data.related_name, label: this.$t('索引集') },
        { val: data.result_table_id, label: this.$t('索引') },
        { val: data?.extend_fields?.scenario_name, label: this.$t('数据源类别') },
        { val: data?.extend_fields?.storage_cluster_name, label: this.$t('数据源名') },
      ],
      bk_data_time_series: [
        // 计算平台指标
        ...options,
        { val: data.result_table_id, label: this.$t('表名') },
      ],
      custom_time_series: [
        // 自定义指标
        ...options,
        { val: data?.extend_fields?.bk_data_id, label: this.$t('数据ID') },
        { val: data.result_table_name, label: this.$t('数据名') },
      ],
      custom_event: [
        // 自定义事件
        ...options,
      ],
      bk_monitor_event: [
        // 系统事件
        ...options,
      ],
    };
    // 拨测指标融合后不需要显示插件id插件名
    const resultTableLabel = data.result_table_label;
    const relatedId = data.related_id;
    if (resultTableLabel === 'uptimecheck' && !relatedId) {
      const list = elList.bk_monitor_time_series;
      elList.bk_monitor_time_series = list.filter(
        item => item.label !== this.$t('插件ID') && item.label !== this.$t('插件名')
      );
    }
    const curElList = elList[this.sourceType];
    let content =
      this.sourceType === 'log_time_series'
        ? `<div class="item">${data.related_name}.${data.metric_field}</div>\n`
        : `<div class="item">${data.result_table_id}.${data.metric_field}</div>\n`;
    if (data.collect_config) {
      const collectorConfig = data.collect_config
        .split(';')
        .map(item => `<div>${item}</div>`)
        .join('');
      curElList.splice(0, 0, { label: this.$t('采集配置'), val: collectorConfig });
    }

    if (data.metric_field === data.metric_field_name) {
      curElList.forEach((item, index) => {
        if (item.label === this.$t('指标别名')) {
          curElList.splice(index, 1);
        }
      });
    }
    curElList.forEach(item => {
      content += `<div class="item"><div>${item.label}：${item.val || '--'}</div></div>\n`;
    });
    return content;
  }

  protected render() {
    return (
      <div
        on-mouseenter={() => this.handleNameEnter(event, this.data)}
        on-mouseleave={this.handleNameLeave}
      >
        {this.$slots.default}
        {this.getUptimecheckTips()}
      </div>
    );
  }
}
