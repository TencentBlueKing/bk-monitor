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
import { Component, Model, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';

import type { IMetrics } from './edit-panel';

import './panel-key-select.scss';

interface IProps {
  value?: string;
  metricsList: IMetrics[];
}

interface IEmit {
  onChange: (value: string) => void;
}

@Component
export default class KeySelect extends tsc<IProps, IEmit> {
  @Prop({ type: Array, required: true }) readonly metricsList: IProps['metricsList'];
  @Prop({ type: String, default: '' }) readonly value: IProps['value'];

  @Ref('rootRef') rootRef: HTMLDivElement;
  @Ref('wrapperRef') wrapperRef: HTMLInputElement;

  activeIndex = -1;
  filterKey = '';
  renderMetricsList: Readonly<IProps['metricsList']> = [];

  handleFilter: () => void;

  get isFilterEmpty() {
    return _.every(this.renderMetricsList, item => item.dimensions.length < 1);
  }

  @Watch('metricsList')
  metricsListChange() {
    this.filterKey = '';
    this.renderMetricsList = Object.freeze(this.metricsList);
  }

  handleChange(value: string) {
    this.$emit('change', value);
  }

  handleMouseleave() {
    console.log('handleMouseleave');
    this.wrapperRef.querySelectorAll('.is-hover').forEach(ele => {
      ele.classList.remove('is-hover');
    });
  }

  created() {
    this.handleFilter = _.throttle(() => {
      this.renderMetricsList = Object.freeze(
        this.metricsList.map(metricsItem => ({
          ...metricsItem,
          dimensions: _.filter(metricsItem.dimensions, item =>
            item.name.toLocaleLowerCase().includes(this.filterKey.toLocaleLowerCase())
          ),
        }))
      );
    }, 300);
  }

  mounted() {
    const handleKeydown = _.throttle((event: KeyboardEvent) => {
      if (!this.rootRef || this.value) {
        return;
      }

      this.activeIndex = -1;

      const resultItemElList = this.rootRef.querySelectorAll('.key-item');
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
      resultItemElList.forEach(ele => ele.classList.remove('is-hover'));
      if (nextIndex > -1) {
        resultItemElList[nextIndex].classList.add('is-hover');
      }

      // 选中的自动出现视窗中
      const wraperHeight = this.rootRef.getBoundingClientRect().height;

      setTimeout(() => {
        const activeOffsetTop = (this.rootRef!.querySelector('.is-hover') as HTMLElement).offsetTop;

        if (activeOffsetTop + 32 > wraperHeight) {
          this.wrapperRef!.scrollTop = activeOffsetTop - wraperHeight + 64;
        } else if (activeOffsetTop <= 42) {
          this.wrapperRef!.scrollTop = 0;
        }
      });
    }, 30);

    const handleMousemove = _.throttle((event: Event) => {
      const target = event.target as HTMLElement;
      if (target.classList.contains('key-item')) {
        const resultItemElList = this.rootRef!.querySelectorAll('.key-item');
        resultItemElList.forEach(ele => ele.classList.remove('is-hover'));
        target.classList.add('is-hover');
        this.activeIndex = _.findIndex(resultItemElList, ele => ele === target);
      }
    }, 100);

    document.body.addEventListener('keydown', handleKeydown);
    this.rootRef!.addEventListener('mousemove', handleMousemove);

    this.$once('hook:beforeDestroy', () => {
      document.body.removeEventListener('keydown', handleKeydown);
      this.rootRef!.removeEventListener('mousemove', handleMousemove);
    });
  }

  render() {
    return (
      <div
        ref='rootRef'
        class='edit-panel-key-select'
      >
        <div style='padding: 4px 8px 0;'>
          <bk-input
            v-model={this.filterKey}
            behavior='simplicity'
            onChange={this.handleFilter}
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
                {metricsItem.dimensions.map(dimesionItem => (
                  <div
                    key={dimesionItem.name}
                    class={{
                      'key-item': true,
                      'is-selected': this.value === dimesionItem.name,
                    }}
                    onClick={() => this.handleChange(dimesionItem.name)}
                  >
                    {dimesionItem.name}
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
