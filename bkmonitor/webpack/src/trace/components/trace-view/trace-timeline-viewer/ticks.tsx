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

import { formatDuration } from '../utils/date';

import type { TNil } from '../typings';

import './ticks.scss';

type TicksProps = {
  endTime?: number | TNil;
  hideLine?: boolean;
  numTicks: number;
  showLabels?: boolean | TNil;
  startTime?: number | TNil;
};

const Ticks = (props: TicksProps) => {
  const { endTime, numTicks, showLabels, startTime, hideLine } = props;

  let labels: string[] | undefined;
  if (showLabels) {
    labels = [];
    const viewingDuration = (endTime || 0) - (startTime || 0);
    for (let i = 0; i < numTicks; i++) {
      const durationAtTick = (startTime || 0) + (i / (numTicks - 1)) * viewingDuration;
      labels.push(formatDuration(durationAtTick));
    }
  }
  const ticks = [];
  for (let i = 0; i < numTicks; i++) {
    const portion = i / (numTicks - 1);
    ticks.push(
      <div
        key={portion}
        style={{
          left: `${portion * 100}%`,
          'background-color': `${hideLine ? '' : '#DCDEE5'}`,
        }}
        class='ticks-tick'
      >
        {labels && (
          <span class={`ticks-tickLabel ${portion >= 1 ? 'isEndAnchor' : ''} ${hideLine ? 'hide-line-label' : ''}`}>
            {labels[i]}
          </span>
        )}
      </div>
    );
  }
  return <div class='ticks'>{ticks}</div>;
};

Ticks.defaultProps = {
  endTime: null,
  showLabels: null,
  startTime: null,
};

export default Ticks;
