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

import { deepClone } from 'monitor-common/utils/utils';

import type { CheckedboxListEvents, CheckedboxListProps, CheckedboxListVlaue, ICheckedboxList } from './typings';

import './checkedbox-list.scss';

@Component
export default class CheckedboxList extends tsc<CheckedboxListProps, CheckedboxListEvents> {
  @Prop({ type: Object, default: () => ({}) }) value: CheckedboxListVlaue;
  @Prop({ type: Array, default: () => [] }) list: ICheckedboxList[];

  localValue = {};

  get localList() {
    return this.list.map(group => {
      const value = this.localValue[group.id];
      this.$set(group, 'checked', value || []);
      group.children = group.children.map(item => {
        this.$set(item, 'show', item.count ? true : group.checked.includes(item.id));
        return item;
      });
      return group;
    });
  }

  @Watch('value', { immediate: true, deep: true })
  valueChange(val: CheckedboxListVlaue) {
    this.localValue = deepClone(val);
  }

  @Emit('change')
  handleCheckedChange() {
    const value = this.localList.reduce((data, item) => {
      item.checked.length && (data[item.id] = item.checked);
      return data;
    }, {});
    this.localValue = deepClone(value);
    return deepClone(value);
  }

  render() {
    return (
      <div class='checkedbox-list-wrap'>
        {this.localList.map(group => {
          const isShow = group.children.some(item => item.show);
          return (
            isShow && (
              <div class='checkedbox-group'>
                <div class='checkedbox-title'>{group.name}</div>
                <div class='checkedbox-list'>
                  <bk-checkbox-group
                    key={group.id}
                    v-model={group.checked}
                    onChange={this.handleCheckedChange}
                  >
                    {group.children.map(
                      item =>
                        item.show && (
                          <div class='checkedbox-item'>
                            <bk-checkbox
                              key={item.id}
                              value={item.id}
                            >
                              <span
                                class='item-name'
                                v-bk-overflow-tips={{ placement: 'right' }}
                              >
                                {item.name}
                              </span>
                            </bk-checkbox>
                            <span class='item-count'>{item.count}</span>
                          </div>
                        )
                    )}
                  </bk-checkbox-group>
                </div>
              </div>
            )
          );
        })}
      </div>
    );
  }
}
