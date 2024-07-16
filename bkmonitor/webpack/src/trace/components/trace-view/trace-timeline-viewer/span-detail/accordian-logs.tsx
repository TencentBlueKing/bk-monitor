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

import _sortBy from 'lodash/sortBy';

// import AccordianKeyValues from './AccordianKeyValues';
// import { formatDuration } from '../utils';
import type { KeyValuePair, Link, Log, TNil } from '../../typings';

import './accordian-logs.css';

type AccordianLogsProps = {
  interactive?: boolean;
  isOpen: boolean;
  linksGetter: ((pairs: KeyValuePair[], index: number) => Link[]) | TNil;
  logs: Log[];
  onItemToggle?: (log: Log) => void;
  onToggle?: () => void;
  openedItems?: Set<Log>;
  timestamp: number;
};

export default function AccordianLogs(props: AccordianLogsProps) {
  const {
    interactive,
    isOpen,
    // linksGetter,
    logs,
    // openedItems,
    // onItemToggle,
    onToggle,
    // timestamp
  } = props;
  let arrow;
  // eslint-disable-next-line @typescript-eslint/naming-convention
  let HeaderComponent: 'a' | 'span' = 'span';
  let headerProps: null | object = null;
  if (interactive) {
    arrow = isOpen
      ? // <IoIosArrowDown className="u-align-icon" />
        'down'
      : // <IoIosArrowRight className="u-align-icon" />
        'right';
    HeaderComponent = 'a';
    headerProps = {
      'aria-checked': isOpen,
      onClick: onToggle,
      role: 'switch',
    };
  }

  return (
    <div class='accordian-logs'>
      <HeaderComponent
        class={['accordian-logs-header', { 'is-open': isOpen }]}
        {...headerProps}
      >
        {arrow} <strong>Logs</strong> ({logs.length})
      </HeaderComponent>
      {isOpen && (
        <div class='accordian-logs-content'>
          {/* {_sortBy(logs, 'timestamp').map((log, i) => (
            <AccordianKeyValues
              // `i` is necessary in the key because timestamps can repeat
              // eslint-disable-next-line react/no-array-index-key
              key={`${log.timestamp}-${i}`}
              className={i < logs.length - 1 ? 'ub-mb1' : null}
              data={log.fields || []}
              highContrast
              interactive={interactive}
              isOpen={openedItems ? openedItems.has(log) : false}
              label={`${formatDuration(log.timestamp - timestamp)}`}
              linksGetter={linksGetter}
              onToggle={interactive && onItemToggle ? () => onItemToggle(log) : null}
            />
          ))} */}
          <small class='accordian-logs-footer'>Log timestamps are relative to the start time of the full trace.</small>
        </div>
      )}
    </div>
  );
}

AccordianLogs.defaultProps = {
  interactive: true,
  linksGetter: undefined,
  onItemToggle: undefined,
  onToggle: undefined,
  openedItems: undefined,
};
