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
import { Component, Emit, Model, Watch } from 'vue-property-decorator';
import { modifiers, Component as tsc } from 'vue-tsx-support';

import './sort-button.scss';

export enum SortType {
  asc = 'asc' /** 升序 */,
  desc = 'desc' /** 降序 */,
  none = '' /** 无排序 */,
}
interface IEvents {
  onChange: SortType;
}
interface IProps {
  value: SortType;
}
/**
 * 表格排序按钮
 */
@Component
export default class SortButton extends tsc<IProps, IEvents> {
  @Model('change', { type: String, default: SortType.none }) value: SortType;

  /** 排序状态 */
  localSort: SortType = SortType.none;

  @Watch('value', { immediate: true })
  sortChange(val: SortType) {
    this.localSort = val;
  }
  /**
   * 切换排序状态
   * @param sort 排序状态
   */
  @Emit('change')
  handleChangeSort(sort: SortType) {
    if (!!this.localSort && this.localSort === sort) {
      this.localSort = SortType.none;
      return this.localSort;
    }
    this.localSort = sort;
    return this.localSort;
  }

  render() {
    return (
      <span class='sort-button-wrap'>
        <i
          class={['sort-button-item is-asc', { active: this.localSort === SortType.asc }]}
          onClick={modifiers.stop(() => this.handleChangeSort(SortType.asc))}
        />
        <i
          class={['sort-button-item is-desc', { active: this.localSort === SortType.desc }]}
          onClick={modifiers.stop(() => this.handleChangeSort(SortType.desc))}
        />
      </span>
    );
  }
}
