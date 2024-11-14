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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import TextListOverview from './text-list-overview';

import './filter-by-condition.scss';

enum ETagType {
  add = 'add',
  condition = 'condition',
  kv = 'kv',
}

interface IValueItem {
  id: string;
  name: string;
}

interface ITagListItem {
  key: string;
  id: string;
  name: string;
  values: IValueItem[];
  type: ETagType;
}

@Component
export default class FilterByCondition extends tsc<object> {
  @Ref('selector') selectorRef: HTMLDivElement;
  // tags
  tagList: ITagListItem[] = [];
  popoverInstance = null;

  created() {
    this.tagList = [
      {
        type: ETagType.add,
        key: random(8),
        id: '',
        name: '',
        values: [],
      },
    ];
  }

  handleAdd(event: MouseEvent) {
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 20,
      zIndex: 9999,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        //
      },
    });
  }

  render() {
    return (
      <div class='filter-by-condition-component'>
        {this.tagList.map(item => {
          if (item.type === ETagType.condition) {
            return (
              <span
                key={item.key}
                class='filter-by-condition-tag'
              >
                AND
              </span>
            );
          }
          if (item.type === ETagType.add) {
            return (
              <span
                key={item.key}
                class='filter-by-condition-tag type-add'
                onClick={this.handleAdd}
              >
                <span class='icon-monitor icon-plus-line' />
              </span>
            );
          }
          return (
            <span
              key={item.key}
              class='filter-by-condition-tag'
            >
              <span>{item.name}</span>
              <span>=</span>
              <span>
                <TextListOverview textList={item.values} />
              </span>
            </span>
          );
        })}
        <div
          style={{
            display: 'none',
          }}
        >
          <div
            ref='selector'
            class='filter-by-condition-component-popover'
          >
            popover
          </div>
        </div>
      </div>
    );
  }
}
