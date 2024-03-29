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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './table-skeleton.scss';

const widths = [0.05, 0.15, 0.15, 0.16, 0.31, 0.1, 0.07];
const padings = [
  [34, 34, 34, 34, 81, 19, 19],
  [32, 40, 40, 114, 40, 40, 0],
  [32, 40, 80, 92, 40, 40, 0],
  [32, 40, 40, 92, 40, 40, 0],
  [32, 40, 40, 52, 40, 40, 0],
  [32, 40, 40, 114, 40, 40, 0],
  [32, 40, 80, 92, 40, 40, 0],
  [32, 40, 40, 92, 40, 40, 0],
  [32, 40, 40, 52, 40, 40, 0]
];

@Component
export default class TableSkeleton extends tsc<{}> {
  render() {
    return (
      <div class='common-table-skeleton'>
        {padings.map((item, index) => {
          if (index === 0) {
            return (
              <div
                key={index}
                class='common-table-skeleton-row'
              >
                {item.map((pItem, pIndex) => (
                  <div
                    key={`${index}_${pIndex}`}
                    style={{
                      width: `${widths[pIndex] * 100}%`
                    }}
                  >
                    <div
                      class='skeleton-element'
                      style={{
                        height: '20px',
                        width: `${pItem}px`
                      }}
                    ></div>
                  </div>
                ))}
              </div>
            );
          }
          return (
            <div
              key={index}
              class='common-table-skeleton-row'
            >
              {item.map((pItem, pIndex) => (
                <div
                  key={`${index}_${pIndex}`}
                  style={{
                    width: `${widths[pIndex] * 100}%`,
                    paddingRight: `${pItem}px`
                  }}
                >
                  <div
                    class='skeleton-element'
                    style={{
                      height: '36px'
                    }}
                  ></div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    );
  }
}
