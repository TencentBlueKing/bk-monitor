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
import { Component as tsc } from 'vue-tsx-support';

import CustomSelect from '../../../../components/custom-select/custom-select';

import type { IOption } from '../../typings';

import './group-by-condition.scss';

export interface IGroupOptions extends IOption {
  checked: boolean;
  count: number;
  list?: {
    id: string;
    name: string;
    checked: boolean;
  }[];
}

export interface IProps {
  value?: string[];
  dimensionOptions?: IGroupOptions[];
}

export interface IEvents {
  onChange: (item: { option: IGroupOptions; checked: boolean }) => void;
}
@Component
export default class GroupSelect extends tsc<IProps, IEvents> {
  /** 外部传入选项options数组 */
  @Prop({ type: Array }) dimensionOptions: IGroupOptions[];

  localValue: string[] = [];

  dimensionOptionsMap: Record<string, IGroupOptions> = {};

  @Watch('dimensionOptions', { immediate: true })
  convertDimensionOptions(newOptions: IGroupOptions[]) {
    this.$set(this, 'dimensionOptionsMap', {});
    for (const item of newOptions) {
      this.$set(this.dimensionOptionsMap, item.id, item);
    }
  }
  /** 可选项数据 */
  get options() {
    return this.dimensionOptions.reduce(
      (prev, curr) => {
        if (curr.checked) {
          prev.checkedArr.push(curr);
        } else {
          prev.unCheckedArr.push(curr);
        }
        return prev;
      },
      { checkedArr: [], unCheckedArr: [] }
    );
  }

  /** 添加、删除 */
  @Emit('change')
  handleValueChange(option, checked: boolean) {
    return { option, checked };
  }

  handleSelect(arr) {
    let changeId = null;
    this.localValue = arr;
    if (arr?.length > this.options.checkedArr?.length) {
      changeId = arr[arr.length - 1];
    } else {
      changeId = this.options.checkedArr.filter(v => !arr.includes(v.id))?.[0]?.id;
    }
    const changeItem = this.dimensionOptionsMap[changeId];
    this.handleValueChange(changeItem, !changeItem?.checked);
  }

  /** 删除操作 */
  handleDeleteItem(item: IGroupOptions) {
    // TODO: 删除逻辑
    this.localValue = this.localValue.filter(v => v !== item.id);
    this.handleValueChange(item, false);
  }

  render() {
    return (
      <div class='group-by-wrap'>
        <span class='group-by-label'>Groups by</span>
        <span class='group-by-main'>
          {this.localValue.map((id, index) => (
            <span
              key={index}
              class='group-by-item'
            >
              {this.dimensionOptionsMap[id].name}
              <i
                class='icon-monitor icon-mc-close'
                onClick={() => this.handleDeleteItem(this.dimensionOptionsMap[id])}
              />
            </span>
          ))}
          <CustomSelect
            class='group-by-select'
            // @ts-ignore
            extPopoverCls='group-by-select-popover'
            options={this.options.unCheckedArr}
            popoverMinWidth={140}
            searchable={false}
            value={this.localValue}
            multiple
            onSelected={this.handleSelect}
          >
            <span
              class='group-by-add'
              slot='target'
            >
              <i class='icon-monitor icon-plus-line' />
            </span>
            {this.options.unCheckedArr.map(opt => (
              <bk-option
                id={opt.id}
                key={opt.id}
                name={opt.name}
              >
                <div class='group-by-option-item'>
                  <span class='item-label'>{opt.name}</span>
                  <span class='item-count'>{opt.list?.length || 0}</span>
                </div>
              </bk-option>
            ))}
          </CustomSelect>
        </span>
      </div>
    );
  }
}
