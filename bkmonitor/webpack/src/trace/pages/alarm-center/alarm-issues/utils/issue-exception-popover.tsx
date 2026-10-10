/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Button } from 'bkui-vue';
import VueJsonPretty from 'vue-json-pretty';

import { isEllipsisActiveLine } from '../../../../utils/dom-helper';
import { getIssueExceptionText, getIssueLogDatetimePrefix } from './issue-log-content';

import type { IUsePopoverTools } from '../../components/alarm-table/hooks/use-popover';
import type { TippyContent, TippyOptions } from 'vue-tippy';

import './issue-exception-popover.scss';
import 'vue-json-pretty/lib/styles.css';

/** 表格与合并明细共用的异常文案来源 */
export interface IssueExceptionPopoverSource {
  anomaly_message?: string;
  log_content?: string;
}

interface ShowIssueExceptionPopoverOptions {
  /** 侧栏等场景覆盖浮层挂载位置和层级，不改变内容 */
  popoverOptions?: Partial<TippyOptions>;
  source: IssueExceptionPopoverSource;
  /** 有关联日志时，「查看更多」打开该 Issue 的日志 */
  onViewMore: () => void;
  t: (key: string) => string;
}

const createJsonLogPopoverContent = (
  source: IssueExceptionPopoverSource,
  t: ShowIssueExceptionPopoverOptions['t'],
  onViewMore: () => void,
  hidePopover: () => void
) => {
  const text = getIssueExceptionText(source);
  // biome-ignore lint/suspicious/noExplicitAny: VueJsonPretty third-party data prop
  const data = JSON.parse(text) as any;
  return (
    <div class='issues-log-popover-wrapper'>
      <div class='issues-log-popover-header' />
      <div class='issues-log-popover-content'>
        <VueJsonPretty
          data={data}
          showDoubleQuotes={false}
          showLine={false}
        />
      </div>
      <div class='issues-log-popover-footer'>
        <Button
          theme='primary'
          text
          onClick={() => {
            hidePopover();
            onViewMore();
          }}
        >
          {t('查看更多')}
        </Button>
      </div>
    </div>
  );
};

const createStringLogPopoverContent = (
  source: IssueExceptionPopoverSource,
  t: ShowIssueExceptionPopoverOptions['t'],
  onViewMore: () => void,
  hidePopover: () => void
) => {
  const text = getIssueExceptionText(source);
  const datetimePrefix = getIssueLogDatetimePrefix(source.log_content);
  return (
    <div class='issues-log-popover-wrapper'>
      <div class='issues-log-popover-header'>
        {datetimePrefix && <span class='issues-log-popover-header-text'>{datetimePrefix}</span>}
      </div>
      <div class='issues-log-popover-content'>
        <pre class='issues-string-popover-pre'>{text}</pre>
      </div>
      <div class='issues-log-popover-footer'>
        <Button
          theme='primary'
          text
          onClick={() => {
            hidePopover();
            onViewMore();
          }}
        >
          {t('查看更多')}
        </Button>
      </div>
    </div>
  );
};

/** 合并明细侧栏里把浮层挂到面板上，避免被内容区 overflow 裁掉 */
export const getMergeDetailPopoverOptions = (el: HTMLElement): Partial<TippyOptions> => {
  const slider = el.closest('.bk-modal-wrapper');
  return {
    appendTo: () => (slider instanceof HTMLElement ? slider : el.ownerDocument.body),
    zIndex: 10001,
  };
};

/**
 * 表格 issues-name-exception-text 的 hover 浮层。
 * 有关联日志时展示 JSON 或原文，否则展示被省略的全文。
 */
export const showIssueExceptionPopover = (
  event: MouseEvent,
  popover: IUsePopoverTools,
  options: ShowIssueExceptionPopoverOptions
) => {
  const el = (event.currentTarget || event.target) as HTMLElement;
  if (!el) return;
  const { content, isEllipsisActive } = isEllipsisActiveLine(el);
  if (!isEllipsisActive) return;

  let popoverContent: TippyContent = content;
  let theme = 'dart';
  if (options.source.log_content) {
    try {
      popoverContent = createJsonLogPopoverContent(
        options.source,
        options.t,
        options.onViewMore,
        popover.hidePopover
      ) as unknown as TippyContent;
    } catch {
      popoverContent = createStringLogPopoverContent(
        options.source,
        options.t,
        options.onViewMore,
        popover.hidePopover
      ) as unknown as TippyContent;
    }
    theme = 'light padding-0';
  }

  popover.showPopover(event, popoverContent, {
    ...options.popoverOptions,
    theme: `${theme} issues-json-popover max-width-50vw text-wrap`,
  });
};
