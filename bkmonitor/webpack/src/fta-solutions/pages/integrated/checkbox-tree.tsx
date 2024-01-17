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

import { IGroupData } from './group';

import './checkbox-tree.scss';

interface ICheckboxTreeData extends IGroupData {
  id: string;
  value: string[];
  level: number;
  parent: string | null;
  indeterminate: boolean;
  child: any[];
  count: number;
}

export interface ICheckedData {
  id: string;
  values: string[];
}

interface ICheckboxTreeProps {
  data: IGroupData[];
}

interface ICheckboxTreeEvents {
  onChange: (data: ICheckedData[]) => void;
}

@Component({ name: 'CheckboxTree' })
export default class CheckboxTree extends tsc<ICheckboxTreeProps, ICheckboxTreeEvents> {
  @Prop({ type: Array, default: () => [] }) readonly data: IGroupData[];

  innerData: ICheckboxTreeData[] = [];

  @Watch('data', { immediate: true })
  handleDataChange(data) {
    this.innerData = this.recurrenceData(JSON.parse(JSON.stringify(data)), 0, null);
  }

  render() {
    return (
      <div class='checkbox-tree'>
        {this.innerData.map(item => (
          <bk-checkbox-group v-model={item.value}>{this.recursiveCheckbox(item, 0)}</bk-checkbox-group>
        ))}
      </div>
    );
  }

  /**
   * 递归创建checkbox组件
   * @param data
   * @param level 层级
   */
  recursiveCheckbox(data: ICheckboxTreeData, level: number) {
    return (
      <div style={{ marginLeft: `${level * 20}px` }}>
        <div class='mb10'>
          <bk-checkbox
            value={data.id}
            indeterminate={data.indeterminate}
            onChange={value => this.handleCheckChange(data, value)}
          >
            {data.name}
          </bk-checkbox>
          <span class='check-count'>{data.count}</span>
        </div>
        {data?.data?.map(item => this.recursiveCheckbox(item, level + 1))}
      </div>
    );
  }

  /**
   * 勾选事件
   * @param value
   */
  handleCheckChange(data: ICheckboxTreeData, value: boolean) {
    const parent = this.getParentData(data);

    this.$nextTick(() => {
      if (!parent) {
        data.value = value
          ? data.data.reduce(
              (pre, item) => {
                pre.push(item.id);
                return pre;
              },
              [data.id]
            )
          : [];
      } else {
        const allChildrenChecked = parent.data.every(item => parent.value?.includes?.(item.id));
        parent.indeterminate = !allChildrenChecked && !!parent.value.length;

        if (parent.indeterminate && parent.value.includes(parent.id)) {
          // 移除父元素勾选
          const index = parent.value.findIndex(value => value === parent.id);
          parent.value.splice(index, 1);
        } else if (allChildrenChecked && !parent.value.includes(parent.id)) {
          // 添加父元素勾选
          parent.value.push(parent.id);
        }
      }

      this.dispatchCheckChange();
    });
  }

  @Emit('change')
  dispatchCheckChange() {
    // 规整输出数据
    const outputData = this.innerData.reduce<ICheckedData[]>((pre, item) => {
      pre.push({
        id: item.id,
        values: item?.data?.length ? [...item.value].filter(id => id !== item.id) : [...item.value]
      });
      return pre;
    }, []);
    return outputData;
  }

  /**
   * 获取父节点
   * @param data
   * @returns
   */
  getParentData(data: ICheckboxTreeData): ICheckboxTreeData {
    if (data.parent === null) return null;

    return this.innerData.find(item => item.id === data.parent || data?.data?.find(() => this.getParentData(data)));
  }

  /**
   * 初始化数据的必须元信息
   * @param data
   * @param level
   * @returns
   */
  recurrenceData(data: ICheckboxTreeData[], level: number, parent: string) {
    return data.map(item => ({
      ...item,
      level,
      value: [],
      parent,
      indeterminate: false,
      data: item.child?.length ? this.recurrenceData(item.child, level + 1, item.id) : []
    }));
  }

  /**
   * 清空勾选状态
   */
  clearChecked() {
    this.innerData.forEach(item => {
      item.value = [];
      item.indeterminate = false;
    });
    this.dispatchCheckChange();
  }
}
