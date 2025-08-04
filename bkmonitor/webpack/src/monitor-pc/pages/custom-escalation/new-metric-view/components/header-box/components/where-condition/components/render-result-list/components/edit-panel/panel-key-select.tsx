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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';

import { formatTipsContent } from '../../../../../../../../metric-chart-view/utils';

import type { IMetrics } from './index';

import './panel-key-select.scss';

interface IEmit {
  onChange: (value: string) => void;
}

interface IProps {
  metricsList: IMetrics[];
  value?: string;
}

@Component
export default class PanelKeySelect extends tsc<IProps, IEmit> {
  @Prop({ type: Array, required: true }) readonly metricsList: IProps['metricsList'];
  @Prop({ type: String, default: '' }) readonly value: IProps['value'];

  @Ref('rootRef') rootRef: HTMLDivElement;
  @Ref('wrapperRef') wrapperRef: HTMLDivElement;
  @Ref('inputRef') inputRef: any;

  isFocused = false;
  activeIndex = -1;
  filterKey = '';
  renderMetricsList: Readonly<IProps['metricsList']> = [];

  handleFilter: () => void;

  get isFilterEmpty() {
    return _.every(this.renderMetricsList, item => item.dimensions.length < 1);
  }

  @Watch('metricsList', { immediate: true })
  metricsListChange() {
    this.filterKey = '';
    this.renderMetricsList = Object.freeze(this.metricsList);
  }

  handleInputFocus() {
    this.activeIndex = -1;
    this.isFocused = true;
  }

  handleInputBlur() {
    this.isFocused = false;
  }

  handleChange(value: string) {
    this.$emit('change', value);
  }

  handleMouseleave() {
    setTimeout(() => {
      const eleList = Array.from(this.wrapperRef.querySelectorAll('.is-hover'));
      for (const ele of eleList) {
        ele.classList.remove('is-hover');
      }
    }, 100);
  }

  created() {
    this.handleFilter = _.throttle(() => {
      this.renderMetricsList = Object.freeze(
        this.metricsList.map(metricsItem => ({
          ...metricsItem,
          dimensions: _.filter(metricsItem.dimensions, item => {
            const filterKey = this.filterKey.toLocaleLowerCase();
            return (
              item.name.toLocaleLowerCase().includes(filterKey) || item.alias.toLocaleLowerCase().includes(filterKey)
            );
          }),
        }))
      );
    }, 300);
  }

  mounted() {
    const handleKeydown = _.throttle((event: KeyboardEvent) => {
      if (!this.rootRef || (this.value && !this.isFocused)) {
        return;
      }

      this.activeIndex = -1;

      const resultItemElList = Array.from(this.rootRef.querySelectorAll('.key-item'));
      if (resultItemElList.length < 1) {
        return;
      }

      const index = _.findIndex(resultItemElList, el => el.classList.contains('is-hover'));
      if (event.code === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        event.stopPropagation();
        if (index > -1) {
          (resultItemElList[index] as HTMLElement).click();
        }
        return;
      }

      let nextIndex = 0;

      if (event.code === 'ArrowDown') {
        nextIndex = index + 1;
        if (nextIndex >= resultItemElList.length) {
          return;
        }
      } else if (event.code === 'ArrowUp') {
        nextIndex = index - 1;
        nextIndex = Math.max(nextIndex, 0);
      } else {
        // 除上下键外，其他按键不应该选中
        return;
      }

      this.activeIndex = nextIndex;
      for (const ele of resultItemElList) {
        ele.classList.remove('is-hover');
      }
      if (nextIndex > -1) {
        resultItemElList[nextIndex].classList.add('is-hover');
      }

      // 选中的自动出现视窗中
      const wraperHeight = this.rootRef.getBoundingClientRect().height;

      setTimeout(() => {
        const activeOffsetTop = (this.rootRef?.querySelector('.is-hover') as HTMLElement).offsetTop;

        if (activeOffsetTop + 32 > wraperHeight) {
          this.wrapperRef.scrollTop = activeOffsetTop - wraperHeight + 64;
        } else if (activeOffsetTop <= 42) {
          this.wrapperRef.scrollTop = 0;
        }
      });
    }, 30);

    const handleMousemove = _.throttle((event: Event) => {
      const target = event.target as HTMLElement;
      if (target.classList.contains('key-item')) {
        const resultItemElList = Array.from(this.rootRef.querySelectorAll('.key-item'));
        for (const ele of resultItemElList) {
          ele.classList.remove('is-hover');
        }
        target.classList.add('is-hover');
        this.activeIndex = _.findIndex(resultItemElList, ele => ele === target);
      }
    }, 100);

    document.body.addEventListener('keydown', handleKeydown);
    this.rootRef?.addEventListener('mousemove', handleMousemove);

    this.$once('hook:beforeDestroy', () => {
      document.body.removeEventListener('keydown', handleKeydown);
      this.rootRef?.removeEventListener('mousemove', handleMousemove);
    });
    setTimeout(() => {
      this.inputRef.focus();
    }, 100);
  }

  render() {
    return (
      <div
        ref='rootRef'
        class={{
          'edit-panel-key-select': true,
          'is-single': this.metricsList.length < 2,
        }}
      >
        <div style='padding: 4px 8px 0;'>
          <bk-input
            ref='inputRef'
            v-model={this.filterKey}
            behavior='simplicity'
            onBlur={this.handleInputBlur}
            onChange={this.handleFilter}
            onFocus={this.handleInputFocus}
          />
        </div>
        <div
          ref='wrapperRef'
          class='wrapper'
          onMouseleave={this.handleMouseleave}
        >
          {!this.isFilterEmpty &&
            this.renderMetricsList.map(metricsItem => (
              <div key={metricsItem.metric_name}>
                <div class='key-title'>
                  {metricsItem.metric_name} ({metricsItem.dimensions.length})
                </div>
                {metricsItem.dimensions.map(dimensionItem => (
                  <div
                    key={dimensionItem.name}
                    class={{
                      'key-item': true,
                      'is-selected': this.value === dimensionItem.name,
                    }}
                    v-bk-tooltips={{
                      content: formatTipsContent(dimensionItem.name, dimensionItem.alias),
                      placement: 'left',
                    }}
                    onClick={() => this.handleChange(dimensionItem.name)}
                  >
                    {dimensionItem.alias || dimensionItem.name}
                    {/* {dimensionItem.alias && <span class='dimension-name'>{dimensionItem.name}</span>} */}
                  </div>
                ))}
              </div>
            ))}
          {this.isFilterEmpty && (
            <bk-exception
              key='search-empty'
              style='margin-top: 80px'
              scene='part'
              type='search-empty'
            />
          )}
        </div>
      </div>
    );
  }
}
