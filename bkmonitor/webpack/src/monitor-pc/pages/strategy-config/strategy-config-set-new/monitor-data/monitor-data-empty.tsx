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
 * @Date: 2021-06-13 10:55:07
 * @LastEditTime: 2021-07-08 10:35:08
 * @Description:
 */
import { Component, Emit, Inject } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import alertImg from '../../../../static/images/png/alert.png';
import eventImg from '../../../../static/images/png/event.png';
import intelligentImg from '../../../../static/images/png/intelligent.png';
import logImg from '../../../../static/images/png/log.png';
import metricImg from '../../../../static/images/png/metric.png';
import { MetricType, strategyType } from '../typings/index';

import './monitor-data-empty.scss';

const addLabelItems = {
  [MetricType.TimeSeries]: {
    name: window.i18n.tc('指标数据'),
    icon: metricImg,
    displayName: window.i18n.tc('时序数据')
  },
  [MetricType.EVENT]: {
    name: window.i18n.tc('事件数据'),
    icon: eventImg,
    displayName: `${window.i18n.tc('系统')}、${window.i18n.tc('自定义事件')}`
  },
  [MetricType.LOG]: {
    name: window.i18n.tc('日志数据'),
    icon: logImg,
    displayName: window.i18n.tc('多端日志匹配')
  },
  [MetricType.ALERT]: {
    name: window.i18n.tc('关联告警'),
    icon: alertImg,
    displayName: window.i18n.tc('关联多个策略判断')
  },
  [MetricType.MultivariateAnomalyDetection]: {
    name: window.i18n.tc('场景智能检测'),
    icon: intelligentImg,
    displayName: `${window.i18n.tc('主机')}、${window.i18n.tc('拨测')}、K8s、APM`
  }
};
interface IMonitorDataEmptyEvent {
  addMetric: { id: string; name: string };
  onHoverType: string;
}
@Component({ name: 'MonitorDataEmpty' })
export default class MonitorDataEmpty extends tsc<{}, IMonitorDataEmptyEvent> {
  @Inject('strategyType') strategyType: strategyType;

  tipsInstance: any = null;
  tipsRemindShow = false;
  get metricSetList() {
    // const isFta = this.strategyType === 'fta';
    const isFta = false;
    return [
      {
        name: this.$t('添加监控指标'),
        id: MetricType.TimeSeries,
        show: !isFta
      },
      {
        name: this.$t('添加事件'),
        id: MetricType.EVENT,
        show: true
      },
      {
        name: this.$t('添加日志关键字'),
        id: MetricType.LOG,
        show: !isFta
      },
      {
        name: this.$t('关联告警'),
        id: MetricType.ALERT,
        show: true
      },
      {
        name: this.$t('场景智能检测'),
        id: MetricType.MultivariateAnomalyDetection,
        show: true
      }
    ].filter(item => item.show);
  }
  mounted() {
    if (!localStorage.getItem(`${this.$store.getters.userName}-strategy-config-set-tips`)) {
      const timer = setTimeout(() => {
        this.handleShowRemindTips();
        localStorage.setItem(`${this.$store.getters.userName}-strategy-config-set-tips`, 'true');
        clearTimeout(timer);
      }, 1000);
    }
  }
  beforeDestroy() {
    if (this.tipsInstance) {
      this.tipsInstance.hide(0);
      this.tipsInstance.destroy();
      this.tipsInstance = null;
    }
  }
  @Emit('add-metric')
  handleAddMetric(item) {
    return item;
  }
  handleShowRemindTips() {
    this.tipsInstance = this.$bkPopover(this.$el, {
      content: this.$refs.remindTips,
      theme: 'light common-monitor strategy-remind',
      trigger: 'manual',
      placement: 'bottom-start',
      offset: '5, 0',
      arrow: true,
      zIndex: 999,
      onHide: () => !this.tipsRemindShow
    });
    this.tipsInstance?.show?.(100);
  }
  handleHideRemidTips() {
    this.tipsRemindShow = false;
    this?.tipsInstance?.hide?.(100);
  }

  handleMouseenter(type) {
    this.$emit('hoverType', type);
  }
  handleMouseleave() {
    this.$emit('hoverType', '');
  }

  render() {
    return (
      <div>
        <ul class='set-panel'>
          {this.metricSetList.map(item => (
            <li
              class='set-panel-item'
              id={`set-panel-item-${item.id}`}
              key={item.id}
              on-click={() => this.handleAddMetric({ type: item.id })}
              onMouseenter={() => this.handleMouseenter(item.id)}
              onMouseleave={() => this.handleMouseleave()}
            >
              <i class='icon-monitor icon-plus-line'></i>
              <img
                class='type-icon'
                src={addLabelItems[item.id].icon}
                alt=''
              />
              <div class='label'>
                <div class='label-top'>{addLabelItems[item.id].name}</div>
                {/* <div class='label-bottom'>{addLabelItems[item.id].displayName}</div> */}
              </div>
            </li>
          ))}
        </ul>
        <div style='display: none'>
          <div
            class='remind-tips'
            ref='remindTips'
          >
            <div class='remind-tips-title'>{this.$t('添加监控项')}</div>
            <div class='remind-tips-desc'>
              {this.$t('监控项为策略配置')}
              <span class='desc-strong'>{this.$t('核心内容')}</span>（<span class='desc-important'> * </span>），
              {this.$t('三类监控项可任选其一')}
            </div>
            <div class='remind-tips-content'>
              <span
                class='content-label'
                onClick={() => this.handleAddMetric({ type: MetricType.TimeSeries })}
              >
                {this.$t('监控指标')}
              </span>
              <span
                class='content-label'
                onClick={() => this.handleAddMetric({ type: MetricType.EVENT })}
              >
                {this.$t('事件')}
              </span>
              <span
                class='content-label'
                onClick={() => this.handleAddMetric({ type: MetricType.LOG })}
              >
                {this.$t('日志关键字')}
              </span>
            </div>
            <div
              class='remind-tips-footer'
              on-click={this.handleHideRemidTips}
            >
              {this.$t('知道了!')}
            </div>
          </div>
        </div>
      </div>
    );
  }
}
