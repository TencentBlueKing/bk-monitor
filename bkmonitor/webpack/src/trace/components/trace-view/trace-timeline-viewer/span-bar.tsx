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
import { type PropType, defineComponent, ref } from 'vue';

import _groupBy from 'lodash/groupBy';

// import AccordianLogs from './span-detail/accordian-logs';
// import { ViewedBoundsFunctionType } from './utils';
import type { Span } from '../typings';

import './span-bar.scss';

const SpanBarProps = {
  color: {
    type: String,
  },
  hintSide: {
    type: String,
  },
  // onClick: (evt: React.MouseEvent<any>) => void;
  viewEnd: {
    type: Number,
    default: 1,
  },
  viewStart: {
    type: Number,
    default: 0,
  },
  // getViewedBounds: Function as PropType<ViewedBoundsFunctionType>,
  rpc: {
    type: Object,
  },
  // traceStartTime: {
  //   type: Number
  // },
  span: {
    type: Object as PropType<Span>,
  },
  label: {
    type: String,
    default: '',
  },
  longLabel: {
    type: String,
    default: '',
  },
  shortLabel: {
    type: String,
    default: '',
  },
};

function toPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default defineComponent({
  name: 'SpanBar',
  props: SpanBarProps,
  setup(props) {
    const label = ref<string>(props.shortLabel);

    const setShortLabel = () => {
      label.value = props.shortLabel;
    };

    const setLongLabel = () => {
      label.value = props.longLabel;
    };

    return {
      label,
      setShortLabel,
      setLongLabel,
    };
  },
  render() {
    const {
      viewEnd,
      viewStart,
      // getViewedBounds,
      color,
      hintSide,
      onClick,
      rpc,
      // traceStartTime,
      span,
    } = this.$props;
    // group logs based on timestamps
    // const logGroups = _groupBy(span.logs, (log) => {
    //   const posPercent = getViewedBounds(log.timestamp, log.timestamp).start;
    //   // round to the nearest 0.2%
    //   return toPercent(Math.round(posPercent * 500) / 500);
    // });
    const { kind, is_virtual: isVirtual } = span as Span;
    const spanKindIcon = () => {
      if (isVirtual) return '';

      switch (kind) {
        case 1: // 内部调用
          return 'neibutiaoyong';
        case 4: // 异步主调
        case 5: // 异步被调
          return 'yibu';
        default:
          return '';
      }
    };

    return (
      <div
        class='span-bar-wrapper'
        aria-hidden
        onClick={onClick}
        onMouseout={this.setShortLabel}
        onMouseover={this.setLongLabel}
      >
        <div
          style={{
            backgroundColor: color,
            left: toPercent(viewStart),
            width: toPercent(viewEnd - viewStart),
          }}
          class={{ 'span-bar': true, 'is-infer': isVirtual }}
          aria-label={this.label}
        >
          <div class={`span-bar-label is-${hintSide}`}>
            {hintSide === 'right' && spanKindIcon && (
              <i class={`icon-monitor icon-${spanKindIcon()} icon-span-kind is-right`} />
            )}
            {this.label}
            {hintSide === 'left' && spanKindIcon && (
              <i class={`icon-monitor icon-${spanKindIcon()} icon-span-kind is-left`} />
            )}
          </div>
        </div>
        {/* <div>
          {Object.keys(logGroups).map(positionKey => (
            <Popover
              key={positionKey}
              arrowPointAtCenter
              overlayClassName="span-bar-logHint"
              placement="topLeft"
              content={
                <AccordianLogs
                  interactive={false}
                  isOpen
                  logs={logGroups[positionKey]}
                  timestamp={traceStartTime}
                />
              }
            >
              <div class="span-bar-logMarker" style={{ left: positionKey }} />
            </Popover>
          ))}
        </div> */}
        {rpc && (
          <div
            style={{
              background: rpc.color,
              left: toPercent(rpc.viewStart),
              width: toPercent(rpc.viewEnd - rpc.viewStart),
            }}
            class='span-bar-rpc'
          />
        )}
      </div>
    );
  },
});
