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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './overflow-tags.scss';

interface ITag {
  id: string;
  name: string;
}

interface IProps {
  tags: ITag[];
  onSelect: (index: number) => void;
}

@Component
export default class OverflowTags extends tsc<IProps> {
  @Prop({ default: () => [] }) tags: ITag[];

  hideIndex = -1;

  mounted() {
    if (!this.$el) {
      return;
    }
    let total = 0;
    let hideIndex = -1;
    let hasHide = false;
    for (const el of Array.from(this.$el.children)) {
      if (el.classList.contains('overflow-tag-item')) {
        total += el.offsetWidth;
        total += 4;
        hideIndex += 1;
        if (total > this.$el.clientWidth || el.offsetTop >= 22) {
          hasHide = true;
          break;
        }
      }
    }
    if (hasHide) {
      this.hideIndex = hideIndex;
    }
  }

  handleClick(_e: Event, index: number) {
    this.$emit('select', index);
  }

  render() {
    return (
      <div class='strategy-list-overflow-tags'>
        {this.tags.map((tag, index) => {
          if (index === this.hideIndex) {
            return (
              <div
                class='overflow-count'
                v-bk-tooltips={{
                  placements: ['top'],
                  content: this.tags.map(item => item.id).join(','),
                }}
                onClick={e => this.handleClick(e, -1)}
              >
                <span class='item-name'>+{this.tags.length - this.hideIndex}</span>
              </div>
            );
          }
          return (
            <div
              key={tag.id}
              class='overflow-tag-item'
              v-bk-tooltips={{
                placements: ['top'],
                content: tag.id,
              }}
            >
              <span
                class='item-name'
                onClick={e => this.handleClick(e, index)}
              >
                {tag.name}
              </span>
            </div>
          );
        })}
      </div>
    );
  }
}
