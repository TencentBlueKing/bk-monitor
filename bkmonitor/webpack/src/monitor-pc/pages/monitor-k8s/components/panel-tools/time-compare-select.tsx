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
import { modifiers, Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils/utils';

import { type PanelToolsType, COMPARE_TIME_OPTIONS } from '../../typings/panel-tools';

import './time-compare-select.scss';

interface IProps {
  timeValue?: string[];
  onTimeChange?: (v: string[]) => void;
}

@Component
export default class TimeCompareSelect extends tsc<IProps> {
  /** 时间对比可选列表 */
  @Prop({
    default: () => COMPARE_TIME_OPTIONS,
    type: Array,
  })
  compareTimeOptions: PanelToolsType.ICompareListItem[];
  /** 时间对比值 */
  @Prop({ default: () => [], type: Array }) timeValue: string[];

  /** 时间对比值 */
  localTimeValue: string[] = [];
  /** 自定义时间输入框展示 */
  showCustomTime = false;
  /** 自定义时间 */
  customTimeVal = '';
  /** 自定义添加的时间可选列表 */
  compareTimeCustomList = [];

  /** 时间可选项的下拉数据 */
  get compareTimeList() {
    const allList = [...this.compareTimeOptions, ...this.compareTimeCustomList];
    const allListMap = new Map();
    for (const item of allList) {
      allListMap.set(item.id, item.name);
    }
    const value = this.localTimeValue;
    for (const item of value) {
      if (!allListMap.has(item))
        allList.push({
          id: item,
          name: item,
        });
    }
    return allList;
  }

  @Watch('timeValue', { immediate: true })
  timeValueChange() {
    this.localTimeValue = deepClone(this.timeValue);
  }

  @Emit('timeChange')
  handleTimeChange(list: string[]) {
    return list;
  }

  /**
   * @description: 时间下拉收起
   * @param {boolean} val
   */
  handleSelectToggle(val: boolean) {
    if (!val) {
      this.customTimeVal = '';
      this.showCustomTime = false;
    }
  }

  /**
   * @description: 处理bk-input事件不触发vue-tsx-support的modifiers问题
   * @param {Event} evt 事件
   * @param {*} handler 要执行的执行的方法
   */
  handleModifiers(evt: Event, handler: (evt: Event) => void) {
    modifiers.enter(handler).call(this, evt);
  }

  /**
   * @description: 自定义按下回车
   */
  handleAddCustomTime() {
    const regular = /^([1-9][0-9]+)+(m|h|d|w|M|y)$/;
    const str = this.customTimeVal.trim();
    if (regular.test(str)) {
      this.handleAddCustom(str);
    } else {
      this.$bkMessage({
        theme: 'warning',
        message: this.$t('按照提示输入'),
        offsetY: 40,
      });
    }
  }

  /**
   * @description: 添加自定义时间对比
   * @param {*} str
   */
  handleAddCustom(str) {
    const timeValue = this.localTimeValue;
    if (this.compareTimeList.every(item => item.id !== str)) {
      this.compareTimeCustomList.push({
        id: str,
        name: str,
      });
    }
    !timeValue.includes(str) && timeValue.push(str);
    this.showCustomTime = false;
    this.customTimeVal = '';
    this.handleTimeChange(this.localTimeValue);
  }

  render() {
    return (
      <span class='k8s__time-compare-select'>
        <bk-select
          class='bk-select-simplicity compare-select time-compare-select'
          v-model={this.localTimeValue}
          behavior='simplicity'
          multiple
          onClear={() => this.handleTimeChange([])}
          onSelected={list => this.handleTimeChange(list)}
          onToggle={this.handleSelectToggle}
        >
          {this.compareTimeList.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            />
          ))}
          <div class='k8s__compare-time-select-custom'>
            {this.showCustomTime ? (
              <span class='time-input-wrap'>
                <bk-input
                  v-model={this.customTimeVal}
                  size='small'
                  onKeydown={(_, evt) => this.handleModifiers(evt, this.handleAddCustomTime)}
                />
                <span
                  class='help-icon icon-monitor icon-mc-help-fill'
                  v-bk-tooltips={this.$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')}
                />
              </span>
            ) : (
              <span
                class='custom-text'
                onClick={() => {
                  this.showCustomTime = !this.showCustomTime;
                }}
              >
                {this.$t('自定义')}
              </span>
            )}
          </div>
        </bk-select>
      </span>
    );
  }
}
