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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
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
  defaultUnit?: string;
}

@Component
export default class Threshold extends tsc<ThresholdProps, ThresholdEvents> {
  @Prop({ default: () => [] }) data: AlgorithmItem[];

  @Prop({ default: '' }) defaultUnit: string;

  @Ref('methodList') methodListRef;

  methodInstancePopover = null;

  localData: ruleDataItem[] = [
    { level: 1, show: false, type: AlgorithmEnum.Threshold, unit_prefix: '', config: { method: 'lte', threshold: 0 } },
    { level: 2, show: false, type: AlgorithmEnum.Threshold, unit_prefix: '', config: { method: 'lte', threshold: 0 } },
    { level: 3, show: false, type: AlgorithmEnum.Threshold, unit_prefix: '', config: { method: 'lte', threshold: 0 } },
  ];

  popoverIndex = 0;

  /**
   * @description 监听 data 变化，用于控制各个级别开关是否开启
   * @param val 已选择的检测规则
   */
  @Watch('data', { immediate: true })
  watchData(val: AlgorithmItem[]) {
    const defaultUnit = this.defaultUnit || val.find(item => item.unit_prefix)?.unit_prefix;
    for (const item of this.localData) {
      const data = val.find(i => i.level === item.level);
      if (data) {
        item.show = true;
        item.config = JSON.parse(JSON.stringify(data.config));
        item.unit_prefix = data.unit_prefix || defaultUnit;
      } else {
        item.show = false;
        item.config = { method: 'lte', threshold: 0 };
        item.unit_prefix = defaultUnit;
      }
    }
  }

  get methodMap() {
    return THRESHOLD_METHOD_LIST.reduce((acc, cur) => {
      acc[cur.id] = cur.name;
      return acc;
    }, {});
  }

  handleShowChange(item: ruleDataItem) {
    item.show = !item.show;
    this.handleChange();
  }

  handleValueChange(item: ruleDataItem, value: number) {
    item.config.threshold = value;
    this.handleChange();
  }

  handleChange() {
    const data = this.localData.filter(item => item.show).map(({ show, ...arg }) => arg);
    this.$emit('change', JSON.parse(JSON.stringify(data)));
  }

  handleMethodClick(e: Event, index: number) {
    e.stopPropagation();
    if (this.methodInstancePopover) {
      this.destroyPopover();
    }
    this.methodInstancePopover = this.$bkPopover(e.target, {
      content: this.methodListRef,
      trigger: 'click',
      arrow: false,
      placement: 'bottom-start',
      theme: 'light common-monitor',
      distance: 5,
      duration: [275, 0],
      followCursor: false,
      flip: true,
      flipBehavior: ['bottom', 'top'],
      flipOnUpdate: true,
      onHidden: () => {
        this.destroyPopover();
      },
    });
    this.popoverIndex = index;
    this.methodInstancePopover.show(200);
  }

  handleMethodChange(id: string) {
    this.localData[this.popoverIndex].config.method = id;
    this.handleChange();
  }

  /**
   * 校验格式是否正确
   * @returns 返回错误信息，如果为空则表示格式正确
   */
  validate() {
    const showRules = this.localData.filter(item => item.show);
    if (showRules.length === 0) return this.$t('检测规则必须开启一个级别');
    if (showRules.some(item => !item.config.threshold && item.config.threshold !== 0))
      return this.$t('检测算法填写不完整，请完善后添加');
    return '';
  }

  destroyPopover() {
    this.methodInstancePopover?.hide();
    this.methodInstancePopover?.destroy();
    this.methodInstancePopover = null;
  }

  render() {
    return (
      <div class='threshold-wrapper'>
        {this.localData.map((item, index) => (
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
              <span class='text'>{LevelMap[item.level]}：</span>
            </span>
            {item.show && [
              <div
                key='method'
                class='method'
                onClick={e => {
                  this.handleMethodClick(e, index);
                }}
              >
                {this.methodMap[item.config.method]}
              </div>,
              <bk-input
                key='threshold'
                class='value-input'
                behavior='simplicity'
                min={0}
                show-controls={false}
                type='number'
                value={item.config.threshold}
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
                {item.unit_prefix}
              </span>,
            ]}
          </div>
        ))}
        {}
        <div style='display: none'>
          <div
            ref='methodList'
            class='method-list'
          >
            {THRESHOLD_METHOD_LIST.map(item => (
              <div
                key={item.id}
                class='method-item'
                onClick={() => {
                  this.handleMethodChange(item.id);
                }}
              >
                {item.name}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
