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
import { getStrLengOfPx } from '../../../../utils';

import type { K8sGroupDimension } from '../../k8s-dimension';
import type { IOption } from '../../typings';
import type { K8sTableColumnResourceKey } from '../k8s-table-new/k8s-table-new';

import './group-by-condition.scss';

export interface IGroupOption extends IOption {
  id: K8sTableColumnResourceKey;
  count?: number;
  children?: IGroupOption[];
}
export interface IGroupByChangeEvent {
  id: K8sTableColumnResourceKey;
  option?: IGroupOption;
  checked: boolean;
}

export interface GroupByConditionProps {
  title: string;
  groupInstance: K8sGroupDimension;
  dimensionOptions?: IGroupOption[];
}

export interface GroupByConditionEvents {
  onChange: (item: IGroupByChangeEvent) => void;
}
@Component
export default class GroupByCondition extends tsc<GroupByConditionProps, GroupByConditionEvents> {
  /** 选择器 label 名称 */
  @Prop({ type: String, default: '' }) title: string;
  /** 外部已选择数组 */
  @Prop({ type: Object }) groupInstance: K8sGroupDimension;
  /** 外部传入选项options数组 */
  @Prop({ type: Array }) dimensionOptions: IGroupOption[];

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
    return (
      this.groupInstance.dimensions?.filter(v => !this.groupInstance.hasGroupFilter(v as K8sTableColumnResourceKey)) ||
      []
    );
  }

  /** 添加、删除 */
  @Emit('change')
  handleValueChange(id, option, checked) {
    return { id, option, checked };
  }

  handleSelect(ids) {
    const changeId = ids[ids.length - 1];
    const changeItem = this.dimensionOptionsMap?.[changeId];
    this.handleValueChange(changeId, changeItem, !this.groupInstance.hasGroupFilter(changeId));
    nextTick(() => {
      if (!this.options?.length) {
        this.customSelectRef?.handleHideDropDown?.();
      }
    });
  }

  /** 删除操作 */
  handleDeleteItem(groupId: K8sTableColumnResourceKey) {
    this.handleValueChange(groupId, this.dimensionOptionsMap[groupId], false);
    this.customSelectRef?.handleShowDropDown?.();
  }

  /** 动态计算弹层宽度 单位: px
   * @param options 可选项数据
   * @param padding padding量 单位: px
   * @param min 最小值 单位: px
   * @return number 宽度值 单位: px
   */
  getPopoverWidth = (options, padding = 32, min?: number) => {
    const width = options.reduce((width, item) => {
      const curWidth = getStrLengOfPx(item as string, 6, 13) + padding;
      return Math.max(curWidth, width);
    }, 0);
    return min ? Math.max(width, min) : width;
  };

  groupTagRender() {
    return this.groupInstance.groupFilters.map(id => {
      const verifyRes = this.groupInstance.verifyDeleteGroupFilter(id);
      const canDelete = typeof verifyRes === 'number';
      return (
        <span
          key={id}
          class={['group-by-item', !this.groupInstance.isDefaultGroupFilter(id) ? 'can-delete' : '']}
        >
          {id || '--'}
          {!this.groupInstance.isDefaultGroupFilter(id) ? (
            <i
              class='icon-monitor icon-mc-close'
              v-bk-tooltips={{
                content: this.$t(canDelete ? '' : verifyRes),
                disabled: canDelete,
              }}
              onClick={() => this.handleDeleteItem(id)}
            />
          ) : null}
        </span>
      );
    });
  }

  render() {
    return (
      <div class='group-by-wrap'>
        <span class='group-by-label'>{this.title}</span>
        <span class='group-by-main'>
          {this.groupTagRender()}
          <CustomSelect
            ref='customSelectRef'
            class='group-by-select'
            // @ts-ignore
            extPopoverCls='k8s-group-by-select-popover'
            popover-width={this.getPopoverWidth(this.options) || void 0}
            popoverMinWidth={140}
            searchable={false}
            value={this.groupInstance.groupFilters}
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
                id={opt}
                key={opt}
                name={opt}
              >
                <div class='group-by-option-item'>
                  <span class='item-label'>{opt}</span>
                  <span class='item-count'>{this.dimensionOptionsMap?.[opt]?.count || 0}</span>
                </div>
              </bk-option>
            ))}
          </CustomSelect>
        </span>
      </div>
    );
  }
}