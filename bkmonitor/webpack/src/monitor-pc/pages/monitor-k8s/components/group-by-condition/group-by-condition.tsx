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
import { nextTick } from 'vue';
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import CustomSelect from '../../../../components/custom-select/custom-select';

import type { IOption } from '../../typings';

import './group-by-condition.scss';

export interface IGroupOption extends IOption {
  checked?: boolean;
  count?: number;
  children?: IGroupOption[];
}
export interface IGroupByChangeEvent {
  id: number | string;
  option: IGroupOption;
  ids: Array<number | string>;
  checked: boolean;
}

export interface GroupByConditionProps {
  title: string;
  groupFilters: Array<number | string>;
  dimensionOptions?: IGroupOption[];
  defaultFixedFilter: Array<number | string>;
}

export interface GroupByConditionEvents {
  onChange: (item: IGroupByChangeEvent) => void;
}
@Component
export default class GroupByCondition extends tsc<GroupByConditionProps, GroupByConditionEvents> {
  /** 选择器 label 名称 */
  @Prop({ type: String, default: '' }) title: string;
  /** 外部已选择数组 */
  @Prop({ type: Array, default: () => [] }) groupFilters: Array<number | string>;
  /** 外部传入选项options数组 */
  @Prop({ type: Array }) dimensionOptions: IGroupOption[];
  /** 默认必须得有的选项元素 */
  @Prop({ type: Array, default: () => [] }) defaultFixedFilter: Array<number | string>;

  @Ref() customSelectRef: any;

  dimensionOptionsMap: Record<string, IGroupOption> = {};

  @Watch('dimensionOptions', { immediate: true })
  convertDimensionOptions(newOptions: IGroupOption[]) {
    this.$set(this, 'dimensionOptionsMap', {});
    for (const item of newOptions) {
      this.$set(this.dimensionOptionsMap, item.id, item);
    }
  }
  /** 可选项数据 */
  get options() {
    const set = new Set(this.groupFilters);
    return this.dimensionOptions?.filter(v => !set.has(v.id)) || [];
  }

  /** 默认必须得有的选项元素 -- 数组结构转换为 Set */
  get defaultFilterSet() {
    return new Set(this.defaultFixedFilter);
  }

  /** 添加、删除 */
  @Emit('change')
  handleValueChange(id, option, ids, checked) {
    return { id, option, ids, checked };
  }

  handleSelect(ids) {
    const changeId = ids[ids.length - 1];
    const changeItem = this.dimensionOptionsMap?.[changeId];
    this.handleValueChange(changeId, changeItem, ids, !changeItem?.checked);
    nextTick(() => {
      if (!this.options?.length) {
        this.customSelectRef?.handleHideDropDown?.();
      }
    });
  }

  /** 删除操作 */
  handleDeleteItem(item: IGroupOption) {
    const ids = this.groupFilters.filter(v => v !== item.id);
    this.handleValueChange(item.id, item, ids, false);
    this.customSelectRef?.handleShowDropDown?.();
  }

  render() {
    return (
      <div class='group-by-wrap'>
        <span class='group-by-label'>{this.title}</span>
        <span class='group-by-main'>
          {this.groupFilters.map(id => (
            <span
              key={id}
              class={['group-by-item', !this.defaultFilterSet.has(id) ? 'can-delete' : '']}
            >
              {this.dimensionOptionsMap[id]?.name || '--'}
              {!this.defaultFilterSet.has(id) ? (
                <i
                  class='icon-monitor icon-mc-close'
                  onClick={() => this.handleDeleteItem(this.dimensionOptionsMap[id])}
                />
              ) : null}
            </span>
          ))}
          <CustomSelect
            ref='customSelectRef'
            class='group-by-select'
            // @ts-ignore
            extPopoverCls='group-by-select-popover'
            options={this.options}
            popoverMinWidth={140}
            searchable={false}
            value={this.groupFilters}
            multiple
            onSelected={this.handleSelect}
          >
            <div slot='target'>
              {this.options.length ? (
                <span class='group-by-add'>
                  <i class='icon-monitor icon-plus-line' />{' '}
                </span>
              ) : null}
            </div>

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
