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

export interface IProps {
  value?: string[];
  dimensionOptions: string;
}

export interface IEvents {
  onChange: string[];
}
@Component
export default class GroupSelect extends tsc<IProps, IEvents> {
  /** 外部传入回来显值 */
  @Prop({ default: () => [], type: Array }) value: string[];
  /** 外部传入选项options数组 */
  @Prop({ type: Array }) dimensionOptions: IOption[];

  /** 可选项数据 */
  options: Array<IOption & { [key: string]: any }> = [];

  /** 添加、删除 */
  @Emit('change')
  handleValueChange(data) {
    return [...data];
  }

  @Watch('dimensionOptions')
  convertDimensionOptions() {
    // TODO: 处理转换options数据结构
  }

  /** 处理选中的名称展示 */
  handleDisplayName(id) {
    return this.options.find(item => item.id === id)?.name;
  }

  /** 删除操作 */
  handleDeleteItem(item) {
    // TODO: 删除逻辑
    const arr = this.value.filter(v => v !== item);
    this.handleValueChange(arr);
  }

  render() {
    return (
      <div class='group-by-wrap'>
        <span class='group-by-label'>Groups by</span>
        <span class='group-by-main'>
          {this.value.map((item, index) => (
            <span
              key={index}
              class='group-by-item'
            >
              {this.handleDisplayName(item)}
              <i
                class='icon-monitor icon-mc-close'
                onClick={() => this.handleDeleteItem(item)}
              />
            </span>
          ))}
          <CustomSelect
            class='group-by-select'
            // @ts-ignore
            extPopoverCls='group-by-select-popover'
            options={this.options}
            popoverMinWidth={140}
            searchable={false}
            value={this.value}
            multiple
            onSelected={this.handleValueChange}
          >
            <span
              class='group-by-add'
              slot='target'
            >
              <i class='icon-monitor icon-plus-line' />
            </span>
            {this.options.map(opt => (
              <bk-option
                id={opt.id}
                key={opt.id}
                name={opt.name}
              >
                <div class='group-by-option-item'>
                  <span class='item-label'>{opt.name}</span>
                  <span class='item-count'>{opt.children?.length || 0}</span>
                </div>
              </bk-option>
            ))}
          </CustomSelect>
        </span>
      </div>
    );
  }
}
