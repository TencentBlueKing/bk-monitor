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

import { defineComponent, type PropType } from 'vue';

import { Tag } from 'bkui-vue';

import './description-card.scss';

interface DescriptionRow {
  label: string;
  value: string;
  type?: 'condition' | 'tags' | 'text';
}
export default defineComponent({
  name: 'DescriptionCard',
  props: {
    data: {
      type: Array as PropType<DescriptionRow[]>,
    },
    cardPrefixRender: {
      type: Function as PropType<(data: DescriptionRow[]) => JSX.Element>,
    },
  },
  setup() {
    return {};
  },
  render() {
    return (
      <div class='description-card'>
        {this.cardPrefixRender ? <div class='card-prefix'>{this.cardPrefixRender(this.data)}</div> : null}
        <div class='card-content'>
          <div class='description-row'>
            <div class='description-label'>
              <span>监控数据:</span>
            </div>
            <div class='description-value'>
              <span class='value'>磁盘空间使用率</span>
            </div>
          </div>
          <div class='description-row'>
            <div class='description-label'>
              <span>汇聚方法:</span>
            </div>
            <div class='description-value'>
              <span class='value'>AVG</span>
            </div>
          </div>
          <div class='description-row'>
            <div class='description-label'>
              <span>汇聚周期:</span>
            </div>
            <div class='description-value'>
              <span class='value'>10 秒</span>
            </div>
          </div>
          <div class='description-row'>
            <div class='description-label'>
              <span>汇聚周期:</span>
            </div>
            <div class='description-value tags-value'>
              <Tag class='tag-item'>云区域 ID</Tag>
              <Tag class='tag-item'>目标 IP</Tag>
            </div>
          </div>
          <div class='description-row'>
            <div class='description-label'>
              <span>过滤条件:</span>
            </div>
            <div class='description-value condition-value'>
              <div class='condition-item'>
                <div class='key-wrap'>
                  <span class='key-name'>云区域ID</span>
                  <span class='key-method'>=</span>
                </div>
                <div class='value-wrap'>
                  <span class='value'>xxxxxxxxx</span>
                </div>
              </div>
              <div class='condition-item'>
                <div class='key-wrap'>
                  <span class='key-name'>挂载点</span>
                  <span class='key-method'>=</span>
                </div>
                <div class='value-wrap'>
                  <span class='value'>/data</span>
                </div>
              </div>
            </div>
          </div>
          <div class='description-row'>
            <div class='description-label'>
              <span>函数:</span>
            </div>
            <div class='description-value'>
              <span class='value'>10 秒</span>
            </div>
          </div>
        </div>
      </div>
    );
  },
});
