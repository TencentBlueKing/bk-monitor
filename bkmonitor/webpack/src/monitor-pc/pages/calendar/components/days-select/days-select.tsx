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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ERepeatTypeId } from '../../types';

import './days-select.scss';

interface IOptionItem {
  checked?: boolean;
  id: number | string;
  name: string;
}
interface IProps {
  mode: ERepeatTypeId;
  vlaue?: Array<number | string>;
}
/**
 * 新增日历事项日期（周、月）选择器
 */
@Component
export default class DaysSelect extends tsc<IProps> {
  @Model('valueChange', { type: Array, default: () => [] }) value: IProps['vlaue'];
  @Prop({ type: String, default: 'weeks' }) mode: IProps['mode'];
  /** 是否必选一个 默认选中当前时间*/
  @Prop({ type: Boolean, default: true }) required: boolean;

  /** 日起可选项 */
  optionsList: IOptionItem[] = [];

  /** 选中ids */
  get checkedIds() {
    return this.optionsList.reduce((total, cur) => {
      if (cur.checked) total.push(cur.id);
      return total;
    }, []);
  }

  @Watch('value', { immediate: true })
  valueChange(val: IProps['vlaue']) {
    let checkedList = val;
    /** 默认选中当前时间 */
    if (!val?.length && this.required) {
      const map = {
        [ERepeatTypeId.weeks]: () => [new Date().getDay()],
        [ERepeatTypeId.months]: () => [new Date().getDate()],
        [ERepeatTypeId.years]: () => [new Date().getMonth() + 1],
      };
      checkedList = map[this.mode]?.();
    }
    /** 更新选中数据 */
    this.optionsList.forEach(item => {
      item.checked = checkedList.includes(item.id);
    });
    if (this.required) this.handleValueChange();
  }

  /** 创建可选列表 */
  @Watch('mode', { immediate: true })
  createOptionsList() {
    const map = {
      [ERepeatTypeId.weeks]: {
        count: 7,
        id: index => (index === 6 ? 0 : index + 1),
        name: index => {
          const mapList = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
          return this.$t(mapList[index]);
        },
      },
      [ERepeatTypeId.months]: { count: 31, name: index => `${index + 1}`, id: index => index + 1 },
      [ERepeatTypeId.years]: {
        count: 12,
        name: index => `${index + 1}月`,
        id: index => index + 1,
      },
    };
    const obj = map[this.mode];
    const list = new Array(obj.count).fill(null).map((item, index) => ({
      id: obj.id?.(index),
      name: obj.name(index),
      checked: this.value.includes(index),
    }));
    this.optionsList = list;
  }

  @Emit('valueChange')
  handleValueChange() {
    return this.checkedIds;
  }

  /**
   * 选择日期操作
   * @param index 索引
   */
  handleSelectItem(item: IOptionItem) {
    if (this.checkedIds.length < 2 && item.checked && this.required) return;
    item.checked = !item.checked;
    this.handleValueChange();
  }
  render() {
    return (
      <div class='days-select-wrap'>
        <div class='days-select-list'>
          {this.optionsList.map(item => (
            <span
              class={['days-item', this.mode, { checked: item.checked }]}
              onClick={() => this.handleSelectItem(item)}
            >
              {item.name}
            </span>
          ))}
        </div>
      </div>
    );
  }
}
