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

import './big-kv-tag.scss';

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
export default class BigKvTag extends tsc<IProps> {
  @Prop({ default: () => null }) value: ITagListItem;
  @Prop({ default: false, type: Boolean }) active: boolean;

  valuesText = [];
  valuesTextHidden = [];
  delCount = 0;

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
        this.valuesText = this.valuesTextHidden.slice(0, 3);
        const delCount = this.value.values.length - 3;
        this.delCount = delCount > 0 ? delCount : 0;
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

  render() {
    return this.value ? (
      <div
        class={['filter-by-condition-tag___type-kv', { active: this.active }]}
        onClick={this.handleClickTag}
      >
        <div
          class='tag-content'
          v-bk-tooltips={{
            content: `<div style="max-width: 600px;">${this.value.id} = ${this.value.values.map(v => v.id).join(', ')}<div>`,
            delay: [300, 0],
            allowHTML: true,
          }}
        >
          <div class='tag-content-key'>
            <span class='key-name'>{this.value.name}</span>
            <span class='method'>=</span>
          </div>
          <div class='tag-content-values'>
            {this.valuesText.map((item, index) => [
              index > 0 && (
                <span
                  key={`${item.id}_${index},`}
                  class='split'
                >
                  ,
                </span>
              ),
              <span
                key={`${item.id}_${index}`}
                class='value-span'
              >
                {item.name}
              </span>,
            ])}
            {this.delCount > 0 && <span class='split'>+{this.delCount}</span>}
          </div>
        </div>
        <div
          class='delete-btn'
          onClick={e => this.handleDeleteTag(e)}
        >
          <span class='icon-monitor icon-mc-close-fill' />
        </div>
      </div>
    ) : undefined;
  }
}
