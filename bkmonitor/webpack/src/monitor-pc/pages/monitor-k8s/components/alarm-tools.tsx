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

import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './alarm-tools.scss';

interface IAlarmToolProps {
  filters?: Record<string, any>;
  isShowStrategy?: boolean;
  panel?: PanelModel;
  variables?: Record<string, any>;
}
@Component
export default class AlarmTools extends tsc<IAlarmToolProps> {
  /** 接口数据 */
  @Prop() panel: PanelModel;
  /** 目标主机、节点数据 */
  @Prop() filters: Record<string, any>;
  @Prop() variables: Record<string, any>;
  @Prop({ default: true }) isShowStrategy: boolean;

  /** 告警数 */
  alarmNum = 0;
  /** 策略数 */
  strategyNum = 0;
  /** 当前请求的参数 */
  currentParams: Record<string, any> = {};

  get apiData() {
    return this.panel?.targets?.[0];
  }

  created() {
    this.panel && this.handleGetAlarmCount();
  }

  @Watch('variables', { deep: true })
  showVariablesChange(val) {
    if (!val.length) {
      this.handleGetAlarmCount();
    }
  }

  /** 跳转策略列表 / 事件中心 */
  handleToStrategyListAndEvnetCenter(toEvent = false) {
    let params = {};
    const { scene_id, target } = this.currentParams;
    /** 拨测列表 */
    if (scene_id === 'uptime_check') {
      params = toEvent
        ? {
            condition: JSON.stringify({ category: ['uptimecheck'] }),
            activeFilterId: 'NOT_SHIELDED_ABNORMAL',
          }
        : {
            scenario: 'uptimecheck',
            strategyState: 'ON',
          };
      /** 拨测任务 */
      if (target?.task_id !== undefined) {
        params = toEvent
          ? { queryString: `tags.task_id : "${target.task_id}"`, activeFilterId: 'NOT_SHIELDED_ABNORMAL' }
          : {
              taskId: target.task_id,
              strategyState: 'ON',
            };
      }
      /** 主机列表 */
    } else if (scene_id === 'host') {
      params = toEvent
        ? {
            condition: JSON.stringify({
              category: ['hosts', 'host_process', 'os', 'host_device'],
            }),
            activeFilterId: 'NOT_SHIELDED_ABNORMAL',
          }
        : {
            scenario: ['host_process', 'os', 'host_device'],
            strategyState: 'ON',
          };
      /** 主机、进程详情 */
      if (target?.bk_target_cloud_id !== undefined && target?.bk_target_ip !== undefined) {
        params = toEvent
          ? {
              queryString: `目标IP : ${target.bk_target_ip} AND 目标云区域ID : ${target.bk_target_cloud_id}`,
              activeFilterId: 'NOT_SHIELDED_ABNORMAL',
            }
          : {
              ip: target.bk_target_ip,
              bkCloudId: target.bk_target_cloud_id,
              strategyState: 'ON',
              scenario: ['host_process', 'os', 'host_device'],
            };
      }
    }
    /** 容器概览 */
    if (scene_id === 'kubernetes') {
      params = toEvent
        ? {
            condition: JSON.stringify({
              category: ['kubernetes'],
            }),
            activeFilterId: 'NOT_SHIELDED_ABNORMAL',
          }
        : {
            scenario: 'k8s',
            strategyState: 'ON',
          };
    }

    if (scene_id === 'apm') {
      // apm应用监控跳转需要通过hash方式 目前暂无跳转参数
      const hash = toEvent ? '#/event-center' : '#/strategy-config';
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    } else {
      this.$router.push({
        name: toEvent ? 'event-center' : 'strategy-config',
        params: toEvent ? {} : params,
        query: toEvent ? params : {},
      });
    }
  }
  /** 获取告警、策略数据 */
  handleGetAlarmCount() {
    const variablesService = new VariablesService({
      ...this.filters,
      ...this.variables,
    });
    const { target, ...arg } = this.apiData.data;
    const params = variablesService.transformVariables({
      ...arg,
      target: {
        ...target,
        ...this.filters,
      },
    });
    this.currentParams = params;
    this.$api[this.apiData.apiModule][this.apiData.apiFunc](params).then(result => {
      this.alarmNum = result.event_counts ?? 0;
      this.strategyNum = result.strategy_counts ?? 0;
    });
  }
  render() {
    return (
      <div class='alarm-tools'>
        {this.isShowStrategy ? (
          <span
            class='alarm-tools-strategy'
            v-bk-tooltips={{ content: this.$t('策略'), delay: 200, boundary: 'window', placement: 'bottom' }}
            onClick={() => this.handleToStrategyListAndEvnetCenter()}
          >
            <i class='icon-monitor icon-mc-strategy tool-icon' />
            {this.strategyNum}
          </span>
        ) : null}
        <span
          class={`alarm-tools-alarm ${!this.alarmNum ? 'is-disabled' : ''}`}
          v-bk-tooltips={{
            content: this.alarmNum < 1 ? this.$t('无告警事件') : this.$t('当前有{0}个告警事件', [this.alarmNum]),
            delay: 200,
            boundary: 'window',
            placement: 'bottom',
            allowHTML: false,
          }}
          onClick={() => (this.alarmNum ? this.handleToStrategyListAndEvnetCenter(true) : false)}
        >
          <i class='icon-monitor icon-mc-chart-alert tool-icon' />
          {this.alarmNum}
        </span>
      </div>
    );
  }
}
