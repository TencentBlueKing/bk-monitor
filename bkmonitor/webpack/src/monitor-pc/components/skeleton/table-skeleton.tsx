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

import './table-skeleton.scss';

interface IConfigModel {
  colWidths: number[];
  config: (number | Record<string, string>)[][];
  rowGap?: number;
  rowHeights: number[];
}

function getSkeStyle(config) {
  if (typeof config === 'object') {
    return config;
  }
  return {};
}
function getWrapStyle(config) {
  if (typeof config === 'number') {
    return {
      paddingRight: `${config}px`,
    };
  }
  return {
    paddingRight: '40px',
  };
}
const config01 = {
  colWidths: [0.05, 0.15, 0.15, 0.16, 0.32, 0.1, 0.07],
  rowHeights: [20, 22, 22, 22, 22, 22, 22, 22, 22, 22],
  config: [
    [
      { width: '35px' },
      { width: '35px' },
      { width: '35px' },
      { width: '35px' },
      { width: '84px' },
      { width: '20px' },
      { width: '20px' },
    ],
    [{ width: '35px' }, 40, 40, 114, 40, 40, 0],
    [{ width: '35px' }, 40, 80, 92, 40, 40, 0],
    [{ width: '35px' }, 40, 40, 52, 40, 40, 0],
    [{ width: '35px' }, 40, 80, 40, 40, 40, 0],
    [{ width: '35px' }, 40, 40, 92, 40, 40, 0],
    [{ width: '35px' }, 40, 40, 52, 40, 40, 0],
    [{ width: '35px' }, 40, 73, 40, 40, 40, 0],
    [{ width: '35px' }, 40, 40, 92, 40, 40, 0],
    [{ width: '35px' }, 40, 60, 40, 40, 40, 0],
  ],
};
const config02 = {
  colWidths: [0.05, 0.15, 0.15, 0.16, 0.32, 0.1, 0.07],
  rowHeights: [20, 36, 36, 36, 36, 36, 36, 36, 36, 36],
  config: [
    [
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '81px' },
      { width: '19px' },
      { width: '19px' },
    ],
    [{ width: '34px' }, 40, 40, 114, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 92, 40, 40, 0],
    [{ width: '34px' }, 40, 40, 52, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 40, 40, 40, 0],
    [{ width: '34px' }, 40, 40, 92, 40, 40, 0],
    [{ width: '34px' }, 40, 40, 52, 40, 40, 0],
    [{ width: '34px' }, 40, 73, 40, 40, 40, 0],
    [{ width: '34px' }, 40, 40, 92, 40, 40, 0],
    [{ width: '34px' }, 40, 60, 40, 40, 40, 0],
  ],
};

const config03 = {
  colWidths: [0.05, 0.15, 0.15, 0.16, 0.32, 0.1, 0.07],
  rowHeights: [20, 36, 36, 36, 36, 36, 36, 36, 36, 36],
  config: [
    [
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '81px' },
      { width: '19px' },
      { width: '19px' },
    ],
    [{ width: '34px' }, 46, 46, 133, 46, 46, 0],
    [{ width: '34px' }, 46, 92, 107, 46, 46, 0],
    [{ width: '34px' }, 46, 46, 61, 46, 46, 0],
  ],
};

const config04 = {
  colWidths: [0.67, 0.33],
  rowHeights: new Array(12).fill(16),
  rowGap: 16,
  config: [
    [175, 0],
    [52, 40],
    [72, 49],
    [96, 58],
    [62, 45],
    [135, 75],
    [85, 70],
    [68, 47],
    [103, 60],
    [80, 50],
    [135, 74],
    [171, 88],
  ],
};

const config05 = {
  colWidths: [0.05, 0.15, 0.15, 0.16, 0.32, 0.1, 0.07],
  rowHeights: [20, 36, 36, 36, 36, 36, 36, 36, 36, 36],
  config: [
    [
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '81px' },
      { width: '19px' },
      { width: '19px' },
    ],
    [{ width: '34px' }, 40, 40, 114, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 92, 40, 40, 0],
    [{ width: '34px' }, 40, 40, 52, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 40, 40, 40, 0],
  ],
};

const config06 = {
  colWidths: [0.05, 0.15, 0.15, 0.16, 0.32, 0.1, 0.07],
  rowHeights: [20, 36, 36, 36, 36, 36, 36, 36, 36, 36],
  config: [
    [
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '34px' },
      { width: '81px' },
      { width: '19px' },
      { width: '19px' },
    ],
    [{ width: '34px' }, 40, 40, 114, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 92, 40, 40, 0],
    [{ width: '34px' }, 40, 40, 52, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 40, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 40, 40, 40, 0],
    [{ width: '34px' }, 40, 80, 40, 40, 40, 0],
  ],
};
interface IProps {
  type?: number;
}

@Component
export default class TableSkeleton extends tsc<IProps> {
  @Prop({ type: Number, default: 1 }) type: number;

  get config(): IConfigModel {
    if (this.type === 1) {
      return config01;
    }
    if (this.type === 2) {
      return config02;
    }
    if (this.type === 3) {
      return config03;
    }
    if (this.type === 4) {
      return config04;
    }
    if (this.type === 5) {
      return config05;
    }
    if (this.type === 6) {
      return config06;
    }
    return config01;
  }

  render() {
    return (
      <div class='common-table-skeleton'>
        {this.config.config.map((item, index) => (
          <div
            key={index}
            style={{
              marginBottom: `${this.config.rowGap || 22}px`,
            }}
            class='common-table-skeleton-row'
          >
            {item.map((pItem, pIndex) => (
              <div
                key={`${index}_${pIndex}`}
                style={{
                  width: `${this.config.colWidths[pIndex] * 100}%`,
                  height: `${this.config.rowHeights[index]}px`,
                  ...getWrapStyle(pItem),
                }}
                class='common-table-skeleton-row-item'
              >
                <div
                  style={{
                    ...getSkeStyle(pItem),
                  }}
                  class='skeleton-element'
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }
}
