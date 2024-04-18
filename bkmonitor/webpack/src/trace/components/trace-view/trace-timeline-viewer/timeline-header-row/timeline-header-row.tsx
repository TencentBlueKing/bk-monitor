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

import { useViewRangeInject } from '../../hooks';
import Ticks from '../ticks';
import TimelineRow from '../timeline-row';
import TimelineRowCell from '../timeline-row-cell';
import VerticalResizer from '../vertical-resizer';

import TimelineCollapser from './timeline-collapser';
import TimelineViewingLayer from './timeline-viewing-layer';

import './timeline-header-row.scss';

type TimelineHeaderRowProps = {
  duration: number;
  nameColumnWidth: number;
  minSpanNameColumnWidth: number;
  numTicks: number;
  onCollapseAll: () => void;
  onCollapseOne: () => void;
  onColummWidthChange: (width: number) => void;
  onExpandAll: () => void;
  onExpandOne: () => void;
  columnResizeHandleHeight: number;
};

const TimelineHeaderRow = (props: TimelineHeaderRowProps) => {
  const {
    duration,
    nameColumnWidth,
    minSpanNameColumnWidth,
    onCollapseAll,
    onCollapseOne,
    onExpandOne,
    onExpandAll,
    numTicks,
    onColummWidthChange,
    columnResizeHandleHeight,
  } = props;
  const viewRange = useViewRangeInject();
  const [viewStart, viewEnd] = viewRange?.viewRange.value.time.current as [number, number];

  return (
    <TimelineRow className='timeline-header-row'>
      <TimelineRowCell
        className='ub-flex ub-px2'
        width={nameColumnWidth}
      >
        <h3 class='timeline-header-row-title'>
          {window.i18n.t('服务')} &amp; {window.i18n.t('操作')}
        </h3>
        <TimelineCollapser
          onCollapseAll={onCollapseAll}
          onExpandAll={onExpandAll}
          onCollapseOne={onCollapseOne}
          onExpandOne={onExpandOne}
        />
      </TimelineRowCell>
      <TimelineRowCell width={1 - nameColumnWidth}>
        <TimelineViewingLayer boundsInvalidator={nameColumnWidth} />
        <Ticks
          numTicks={numTicks}
          startTime={viewStart * duration}
          endTime={viewEnd * duration}
          showLabels
          hideLine
        />
      </TimelineRowCell>
      <VerticalResizer
        position={nameColumnWidth}
        onChange={onColummWidthChange}
        min={Math.max(minSpanNameColumnWidth, 0.25)}
        max={0.85}
        columnResizeHandleHeight={columnResizeHandleHeight}
      />
    </TimelineRow>
  );
};

export default TimelineHeaderRow;
