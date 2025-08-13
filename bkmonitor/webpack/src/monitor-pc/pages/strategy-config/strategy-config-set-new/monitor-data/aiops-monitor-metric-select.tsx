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

import { Debounce, random } from '../../../../../monitor-common/utils';
import MetricSelector from '../../../../components/metric-selector/metric-selector';
import { type IScenarioItem, MetricDetail, MetricType } from '../typings';

import './aiops-monitor-metric-select.scss';

interface IProps {
  defaultScenario?: string;
  metrics?: MetricDetail[];
  scenarioList?: IScenarioItem[];
  value?: string[];
  onChange?: (v: string[]) => void;
}

@Component
export default class AiopsMonitorMetricSelect extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: string[];
  @Prop({ type: Array, default: () => [] }) metrics: MetricDetail[];
  @Prop({ type: Array, default: () => [] }) scenarioList: IScenarioItem[];
  /* 默认选择的监控对象 */
  @Prop({ type: String, default: '' }) defaultScenario: string;

  localValue = [];
  tags: MetricDetail[] = [];

  showSelector = false;
  selectTargetId = '';

  showAll = false;

  observer = null;

  countInstance = null;

  created() {
    this.selectTargetId = `aiops-monitor-metric-select-component-id-${random(8)}`;
    this.observer = new ResizeObserver(entries => {
      entries.forEach(() => {
        // const { width } = entry.contentRect;
        this.handleWatchWidth();
      });
    });
  }

  mounted() {
    this.observer.observe(this.$el);
  }

  @Watch('value', { immediate: true })
  handleWatchValue(value: string[]) {
    if (JSON.stringify(value) !== JSON.stringify(this.localValue)) {
      this.localValue = this.value;
      this.handleGetMetricTag();
    }
  }
  @Watch('metrics', { immediate: true })
  handleWatchMetrics(value) {
    if (value.length) {
      this.handleGetMetricTag();
    }
  }

  @Debounce(300)
  handleWatchWidth() {
    this.getOverflowHideCount();
  }

  /**
   * @description 获取tag数据
   */
  handleGetMetricTag() {
    const metricMap = new Map();
    this.metrics.forEach(item => {
      metricMap.set(item.metric_id, item);
    });
    const tags = [];
    this.localValue.forEach(id => {
      const metric = metricMap.get(id);
      if (metric) {
        tags.push(metric);
      }
    });
    this.tags = tags;
    this.$nextTick(() => {
      this.getOverflowHideCount();
    });
  }
  /**
   * @description 点击当前组件
   */
  handleClick() {
    this.showAll = !this.showAll;
    this.$nextTick(() => {
      this.getOverflowHideCount();
      if (this.showAll) {
        this.showSelector = true;
      }
    });
  }

  /**
   * @description 获取隐藏的数据
   */
  getOverflowHideCount() {
    const tagsWrap = this.$el.querySelector('.tag-select-wrap');
    const countClassName = 'overflow-count';
    const dels = tagsWrap.querySelectorAll(`.${countClassName}`);
    dels.forEach(el => {
      el.parentNode.removeChild(el);
    });
    if (this.showAll) {
      return;
    }
    const tagsEl = tagsWrap.querySelectorAll('.tag-item');
    if ((tagsWrap as HTMLElement).offsetHeight < (this.$el as HTMLElement).offsetHeight) {
      return;
    }
    // 容器宽度
    const wrapWidth = (this.$el as HTMLElement).offsetWidth - 24;
    // 隐藏的数量tag宽度
    const countWrapWidth = 36;
    let countWidth = 0;
    let overflowCount = 0;
    let insertIndex = 0;
    for (let i = 0; i < tagsEl.length; i++) {
      const width = (tagsEl[i] as HTMLElement).offsetWidth;
      countWidth += width + 4;
      if (countWidth > wrapWidth - countWrapWidth && countWidth !== wrapWidth) {
        if (!insertIndex) {
          insertIndex = i;
        }
        overflowCount += 1;
      }
    }
    if (overflowCount) {
      const countEl = document.createElement('span');
      countEl.className = countClassName;
      countEl.innerHTML = `+${overflowCount}`;
      this.countInstance?.hide?.();
      this.countInstance?.destroy?.();
      setTimeout(() => {
        this.countInstance = this.$bkPopover(countEl, {
          content: this.$t('显示完整信息'),
          arrow: true,
          delay: [300, 0],
        });
      }, 50);
      tagsWrap.insertBefore(countEl, tagsWrap.children[insertIndex]);
    }
  }

  /**
   * @description 展示指标选择器
   * @param v
   */
  handleShowSelector(v: boolean) {
    this.showSelector = v;
    if (!v) {
      this.showAll = false;
      this.$nextTick(() => {
        this.getOverflowHideCount();
      });
    }
  }
  /**
   * @description 删除
   * @param event
   * @param index
   */
  handleDel(event: Event, index: number) {
    event.stopPropagation();
    this.tags.splice(index, 1);
    this.handleChange();
    this.$nextTick(() => {
      this.getOverflowHideCount();
    });
  }

  handleChange() {
    this.localValue = this.tags.map(item => item.metric_id);
    this.$emit('change', this.localValue);
    this.dispatch('bk-form-item', 'form-change');
  }

  /**
   * @description 选中
   * @param v
   */
  handleChecked(v: { checked: boolean; id: string }) {
    const fIndex = this.localValue.findIndex(id => v.id === id);
    if (v.checked) {
      fIndex < 0 && this.localValue.push(v.id);
    } else {
      fIndex >= 0 && this.localValue.splice(fIndex, 1);
    }
    this.$emit('change', this.localValue);
    this.dispatch('bk-form-item', 'form-change');
    this.handleGetMetricTag();
    this.$nextTick(() => {
      this.getOverflowHideCount();
    });
  }

  dispatch(componentName: string, eventName: string) {
    let parent = this.$parent || this.$root;
    let name = parent.$options.name;

    while (parent && (!name || name !== componentName)) {
      parent = parent.$parent;

      if (parent) {
        name = parent.$options.name;
      }
    }
    if (parent) {
      parent.$emit.apply(parent, [eventName]);
    }
  }

  /**
   * @description 清空所有
   * @param e
   */
  handleClearAll(e: Event) {
    e.stopPropagation();
    this.localValue = [];
    this.handleGetMetricTag();
    this.handleChange();
    this.$nextTick(() => {
      this.getOverflowHideCount();
    });
  }

  getMetricData(params: Record<string, any>) {
    return new Promise((resolve, reject) => {
      try {
        const search = params.search || '';
        let metrics = [];
        if (!params.tag.length) {
          metrics = this.metrics
            .filter(
              item =>
                item.metric_field_name.indexOf(search) >= 0 ||
                item.metric_field.indexOf(search) >= 0 ||
                item.metric_id.toString().indexOf(search) >= 0
            )
            .map(item => new MetricDetail(item));
        }
        resolve({ metricList: metrics });
      } catch (err) {
        reject(err);
      }
    });
  }

  render() {
    return (
      <span
        id={this.selectTargetId}
        class={['aiops-monitor-metric-select-component', { 'show-all': this.showAll }]}
        onClick={this.handleClick}
      >
        <div class='tag-select-wrap'>
          {this.tags.map((item, index) => (
            <div
              key={item.metric_id}
              class='tag-item'
            >
              <span>{item.name}</span>
              <span
                class='icon-monitor icon-mc-close'
                onClick={e => this.handleDel(e, index)}
              />
            </div>
          ))}
        </div>
        <div class='icon-monitor icon-arrow-down' />
        <div
          class='icon-monitor icon-mc-close-fill'
          onClick={e => this.handleClearAll(e)}
        />
        <MetricSelector
          defaultScenario={this.defaultScenario}
          getMetricData={this.getMetricData}
          metricIds={this.localValue}
          multiple={true}
          scenarioList={this.scenarioList}
          show={this.showSelector}
          targetId={`#${this.selectTargetId}`}
          type={MetricType.TimeSeries}
          onChecked={val => this.handleChecked(val)}
          onShowChange={val => this.handleShowSelector(val)}
        />
      </span>
    );
  }
}
