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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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
import { Collapse } from 'bkui-vue';

import MarkdownViewer from '../../../../components/markdown-editor/viewer';
import { replaceEntityInText } from '../entity-replace';
import { createInteractionExecutor, createPopoverRenderers } from './common';

import type { ILogAnalysis } from '../../types';
import type { IShootingModuleContext, TranslateFn } from './module-context';

/**
 * 日志分析模块
 * @returns {JSX.Element} 配置内容元素
 */
export const renderLogsAnalysisSlot = (options: IShootingModuleContext, $t: TranslateFn) => {
  // 统一消费后端 interaction，并补充仅用于展示的侧滑标题
  const executeInteraction = createInteractionExecutor(options);

  // 通用的溢出 Popover 渲染器（多行溢出检测：scrollHeight > clientHeight）
  const { contentPopoverBlock } = createPopoverRenderers(options, $t);

  // 日志分析标题：仅 action=drawer 时可点击打开日志侧滑；error/none 无跳转样式
  const logTitle = (item: ILogAnalysis, itemIndex: number) => {
    const canOpenLogDrawer = item.interaction?.action === 'drawer';
    return (
      <span class='log-title'>
        {`${$t('聚类结果')} ${itemIndex + 1}`}
        <i18n-t
          class='log-title-count'
          keypath='（共 {0} 条日志）'
          tag='span'
        >
          <span
            style='font-weight: 700;margin: 0 2px;'
            class={canOpenLogDrawer ? 'cursor-link' : ''}
            onClick={(e: MouseEvent) => {
              if (!canOpenLogDrawer) return;
              e.stopPropagation();
              executeInteraction(item.interaction, $t('日志详情'));
            }}
          >
            {item.log_count}
          </span>
        </i18n-t>
      </span>
    );
  };
  // 日志分析内容
  const logContent = (item: ILogAnalysis, index: number) => {
    return (
      <div class='log-content-warpper'>
        {/* Pattern展示 */}
        {contentPopoverBlock('Pattern：', item.pattern, index, 'log_pattern', 'text')}
        {/* 示例日志展示（JSON格式） */}
        {contentPopoverBlock($t('示例日志：'), item.demo_log, index, 'demo_log', 'json')}
      </div>
    );
  };
  /**
   * 从 logs_analysis.contents 中取出聚类记录列表。
   * 跳过 log_dimension_from_variables 等非数组字段。
   */
  const getLogAnalysisRecords = (): ILogAnalysis[] => {
    const contents = options.contentList?.logs_analysis;
    if (!contents) return [];
    for (const value of Object.values(contents)) {
      if (Array.isArray(value)) {
        return value as ILogAnalysis[];
      }
    }
    return [];
  };
  const renderLogsSlot = () => {
    const logRecords = getLogAnalysisRecords();
    return (
      <>
        {/* 日志分析总结区域 */}
        <div class='card-summary'>
          <div class='card-summary-title'>{$t('日志分析总结：')}</div>
          <MarkdownViewer
            class='markdown-viewer-has-link'
            value={replaceEntityInText(options.summaryList.logs_analysis, options.extractedInfoList?.logs_analysis)}
          />
        </div>
        {/* 日志分析详情折叠面板 */}
        {logRecords.length > 0 && (
          <Collapse
            class='log-collapse inner-collapse'
            v-model={options.activeIndex.log}
            v-slots={{
              default: (item, index) => logTitle(item, index),
              content: (item, index) => logContent(item, index),
            }}
            header-icon='right-shape'
            list={logRecords}
          />
        )}
      </>
    );
  };

  return renderLogsSlot();
};
