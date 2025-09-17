/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { THRESHOLD_METHOD_LIST } from 'monitor-pc/constant/constant';

import { type AlgorithmItem, AlgorithmEnum, LevelMap } from '../typing';

import './threshold.scss';

interface ruleDataItem extends AlgorithmItem {
  show: boolean;
}

interface ThresholdEvents {
  onChange: (value: AlgorithmItem[]) => void;
}

interface ThresholdProps {
  data: AlgorithmItem[];
}

@Component
export default class Threshold extends tsc<ThresholdProps, ThresholdEvents> {
  @Prop({ default: () => [] }) data: AlgorithmItem[];

  methodInstancePopover = null;

  localData: ruleDataItem[] = [
    { level: 1, show: false, type: AlgorithmEnum.Threshold, method: 'lte', threshold: 0 },
    { level: 2, show: false, type: AlgorithmEnum.Threshold, method: 'lte', threshold: 0 },
    { level: 3, show: false, type: AlgorithmEnum.Threshold, method: 'lte', threshold: 0 },
  ];

  @Watch('data')
  watchData(val: AlgorithmItem[]) {
    for (const item of this.localData) {
      const data = val.find(i => i.level === item.level);
      if (data) {
        item.show = true;
        item.method = data.method;
        item.threshold = data.threshold;
      }
    }
  }

  get methodMap() {
    return THRESHOLD_METHOD_LIST.reduce((acc, cur) => {
      acc[cur.id] = cur.name;
      return acc;
    });
  }

  handleShowChange(item: ruleDataItem) {
    item.show = !item.show;
    this.handleChange();
  }

  handleValueChange(item: ruleDataItem, value: number) {
    item.threshold = value;
    this.handleChange();
  }

  handleChange() {
    this.$emit(
      'change',
      this.localData
        .filter(item => item.show)
        .map(item => {
          delete item.show;
          return item;
        })
    );
  }

  handleMethodClick(e: Event) {
    e.stopPropagation();
  }

  render() {
    return (
      <div class='threshold-wrapper'>
        {this.localData.map(item => (
          <div
            key={item.level}
            class='threshold-item'
          >
            <bk-switcher
              size='small'
              theme='primary'
              value={item.show}
              onChange={() => {
                this.handleShowChange(item);
              }}
            />
            <span class='level-icon'>
              <i class={['icon-monitor', ['icon-danger', 'icon-mind-fill', 'icon-tips'][item.level - 1]]} />
              <span>{LevelMap[item.level]}：</span>
            </span>
            {item.show && [
              <div
                key='method'
                class='method'
                onClick={this.handleMethodClick}
              >
                {this.methodMap[item.method]}
              </div>,
              <bk-input
                key='threshold'
                class='value-input'
                behavior='simplicity'
                max={100}
                min={0}
                show-controls={false}
                type='number'
                value={item.threshold}
                onBlur={value => {
                  this.handleValueChange(item, value);
                }}
                onEnter={value => {
                  this.handleValueChange(item, value);
                }}
              />,
              <span
                key='unit'
                class='unit'
              >
                %
              </span>,
            ]}
          </div>
        ))}
      </div>
    );
  }
}
