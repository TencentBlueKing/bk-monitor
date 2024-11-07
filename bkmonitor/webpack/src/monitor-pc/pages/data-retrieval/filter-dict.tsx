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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './filter-dict.scss';
interface IFilterDictProps {
  filterDict: Record<string, string>;
}
@Component
export default class FilterDict extends tsc<
  IFilterDictProps,
  {
    onDelete: () => void;
  }
> {
  @Prop({
    default: () => ({}),
    type: Object,
  })
  filterDict: Record<string, string>;
  render() {
    return (
      <div class='filter-dict-wrap'>
        <div class='collapse-item-title'>
          <span class='title-left'>{this.$t('维度信息')}</span>
          <span class='title-center' />
          <span class='title-right'>
            <i
              class={['icon-monitor icon-mc-delete-line']}
              v-bk-tooltips_top={this.$t('删除')}
              onClick={() => this.$emit('delete')}
            />
          </span>
        </div>
        <div class='filter-dict'>
          {Object.entries(this.filterDict).map(([key, value]) => (
            <bk-tag
              key={key}
              class='filter-dict-item'
              v-bk-overflow-tips
              closable={false}
            >
              {key}({value})
            </bk-tag>
          ))}
        </div>
      </div>
    );
  }
}
