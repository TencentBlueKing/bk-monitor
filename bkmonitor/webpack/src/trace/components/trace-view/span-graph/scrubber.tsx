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

import './scrubber.scss';

interface IScrubberProps {
  isDragging: boolean;
  position: number;
  onMouseDown: (evt: MouseEvent) => void;
  onMouseEnter: (evt: MouseEvent) => void;
  onMouseLeave: (evt: MouseEvent) => void;
}

const Scrubber = ({ isDragging, onMouseDown, onMouseEnter, onMouseLeave, position }: IScrubberProps) => {
  const xPercent = `${position * 100}%`;

  return (
    <g class={{ scrubber: isDragging }}>
      <g
        class='scrubber-handles'
        onMousedown={onMouseDown}
        onMouseenter={onMouseEnter}
        onMouseleave={onMouseLeave}
      >
        {/* handleExpansion is only visible when `isDragging` is true */}
        <rect
          style={{ transform: 'translate(-4.5px)' }}
          width='9'
          height='24'
          class='scrubber-handleExpansion'
          x={xPercent}
        />
        <rect
          style={{ transform: 'translate(-1.5px)' }}
          width='3'
          height='24'
          class='scrubber-handle'
          x={xPercent}
          y={20}
        />
      </g>
      <line
        class='scrubber-line'
        x1={xPercent}
        x2={xPercent}
        y2='100%'
      />
    </g>
  );
};

export default Scrubber;
