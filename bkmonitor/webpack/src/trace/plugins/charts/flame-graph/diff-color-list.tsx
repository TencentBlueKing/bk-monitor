/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { defineComponent } from 'vue';

import './diff-color-list.scss';

const ColorList = [
  {
    value: -100,
    color: '#30B897',
  },
  {
    value: -80,
    color: '#55C2A9',
  },
  {
    value: -60,
    color: '#7BCCBB',
  },
  {
    value: -40,
    color: '#9FD7CC',
  },
  {
    value: -20,
    color: '#C5E1DE',
  },
  {
    value: 0,
    color: '#DDDFE3',
  },
  {
    value: +20,
    color: '#E9D3D7',
  },
  {
    value: +40,
    color: '#E8BBBE',
  },
  {
    value: +60,
    color: '#E8A4A6',
  },
  {
    value: +80,
    color: '#E88C8D',
  },
  {
    value: +100,
    color: '#E77474',
  },
];
export default defineComponent({
  render() {
    return (
      <div class='diff-color-list'>
        <div class='pre-color'>new</div>
        <ul class='color-list'>
          {ColorList.map(item => (
            <li
              key={item.value}
              style={{ background: item.color }}
              class='color-item'
            >
              {item.value > 0 ? '+' : ''}
              {item.value}%
            </li>
          ))}
        </ul>
        <div class='next-color'>removed</div>
      </div>
    );
  },
});
