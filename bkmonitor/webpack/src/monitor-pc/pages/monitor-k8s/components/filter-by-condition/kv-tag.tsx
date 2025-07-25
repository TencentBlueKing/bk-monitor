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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './kv-tag.scss';

interface IProps {
  active?: boolean;
  value?: ITagListItem;
  onClickTag?: (e: any) => void;
  onDeleteTag?: () => void;
}
interface ITagListItem {
  id: string;
  key: string;
  name: string;
  values: IValue[];
}

interface IValue {
  id: string;
  name: string;
}

@Component
export default class KvTag extends tsc<IProps> {
  @Prop({ default: () => null }) value: ITagListItem;
  @Prop({ default: false, type: Boolean }) active: boolean;

  valuesText = [];
  valuesTextHidden = [];
  delCount = 0;
  overflowLoading = false;

  @Watch('value', { immediate: true, deep: true })
  handleWatchVale() {
    if (this.value) {
      const valuesTextHidden = this.value.values.map(item => {
        let name = item.name;
        if (item.name.length > 20) {
          name = `${name.slice(0, 20)}...`;
        }
        return {
          ...item,
          name,
        };
      });
      if (JSON.stringify(valuesTextHidden) !== JSON.stringify(this.valuesTextHidden)) {
        this.valuesTextHidden = valuesTextHidden;
        this.handleOverflowCount();
      }
    }
  }

  handleDeleteTag(event: MouseEvent) {
    event.stopPropagation();
    this.$emit('deleteTag');
  }
  handleClickTag(event: MouseEvent) {
    let target = event.target as any | HTMLElement;
    while (target) {
      if (target.classList.contains('filter-by-condition-tag___type-kv')) {
        break;
      }
      target = target.parentNode;
    }
    this.$emit('clickTag', target);
  }

  async handleOverflowCount() {
    await this.$nextTick();
    const hiddenWrap = this.$el.querySelector('.tag-content-hidden');
    const wrapWidth = hiddenWrap.clientWidth;
    let delCount = 0;
    if (wrapWidth > 400) {
      const textWrap = hiddenWrap.querySelector('.values');
      const textListEl = Array.from(textWrap.children);
      let tempW = wrapWidth;
      for (let i = textListEl.length - 1; i >= 0; i--) {
        const textEl = textListEl[i];
        tempW -= textEl.clientWidth;
        delCount += 1;
        if (tempW < 400) {
          break;
        }
      }
    }
    this.delCount = delCount;
    this.valuesText = this.valuesTextHidden.slice(0, this.valuesTextHidden.length - this.delCount);
  }

  render() {
    return this.value ? (
      <div
        class={['filter-by-condition-tag___type-kv', { active: this.active }]}
        onClick={this.handleClickTag}
      >
        <div
          class='tag-content'
          v-bk-tooltips={{
            content: `${this.value.id} = ${this.value.values.map(v => v.id).join(', ')}`,
            delay: [300, 0],
          }}
        >
          <span>{this.value.name}</span>
          <span class='method'>=</span>
          <span class='values'>
            {this.valuesText.map((item, index) => (
              <span key={`${item.id}_${index}_index`}>
                {index > 0 && <span class='split'>, </span>}
                <span
                  key={`${item.id}_${index}`}
                  class='text'
                >
                  {item.name}
                </span>
              </span>
            ))}
          </span>
          {this.delCount ? <span class='overflow-count'>,&nbsp;&nbsp;{`+${this.delCount}`}</span> : undefined}
          <span
            class='icon-monitor icon-mc-close'
            onClick={e => this.handleDeleteTag(e)}
          />
        </div>

        <div class='tag-content-hidden'>
          <span>{this.value.name}</span>
          <span class='method'>=</span>
          <span class='values'>
            {this.valuesTextHidden.map((item, index) => (
              <span key={`${item.id}_${index}_index`}>
                {index > 0 && <span class='split'>, </span>}
                <span
                  key={`${item.id}_${index}`}
                  class='text'
                >
                  {item.name}
                </span>
              </span>
            ))}
          </span>
          <span class='icon-monitor icon-mc-close' />
        </div>
      </div>
    ) : undefined;
  }
}
