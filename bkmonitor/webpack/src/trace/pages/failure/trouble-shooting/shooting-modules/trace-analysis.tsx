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
import { TRACE_FIELD_CONFIG } from '../../utils';
import { replaceEntityInText } from '../entity-replace';
import { createInteractionExecutor, createPopoverRenderers, generateUrl } from './common';

import type { ITraceAnalysis } from '../../types';
import type { IShootingModuleContext, TranslateFn } from './module-context';

/**
 * Trace分析模块
 * @returns {JSX.Element} 配置内容元素
 */
export const renderTraceAnalysisSlot = (options: IShootingModuleContext, $t: TranslateFn) => {
  // 统一消费后端 interaction，并补充仅用于展示的侧滑标题
  const executeInteraction = createInteractionExecutor(options);
  const executeTraceInteraction = (
    interaction?: ITraceAnalysis['interaction'],
    title?: string,
    availabilityRef?: ITraceAnalysis['availability_ref']
  ) => {
    const traceInteraction = interaction ? { ...interaction, drawer_type: 'trace' as const } : interaction;
    executeInteraction(traceInteraction, title, availabilityRef);
  };

  // 通用的溢出 Popover 渲染器（多行溢出检测：scrollHeight > clientHeight）
  const { renderCommonPopover, contentPopoverBlock } = createPopoverRenderers(options, $t);

  // Trace分析标题
  const traceTitle = (item: ITraceAnalysis, itemIndex: number) => {
    // 仅后端明确提供外链且地址有效的 Trace 记录允许点击。
    const canOpenTrace = item.interaction?.action === 'link' && !!item.interaction.url;
    return (
      <span class='log-title'>
        {`${$t('分析结果')} ${itemIndex + 1}`}
        <i18n-t
          class='log-title-count'
          keypath='（共 {0} 条异常信息）'
          tag='span'
        >
          <span
            style='font-weight: 700;margin: 0 2px;'
            class={canOpenTrace ? 'cursor-link' : ''}
            onClick={(e: MouseEvent) => {
              if (!canOpenTrace) return;
              e.stopPropagation();
              executeTraceInteraction(item.interaction, undefined, item.availability_ref);
            }}
          >
            {' '}
            {item.log_count}{' '}
          </span>
        </i18n-t>
      </span>
    );
  };

  // Trace分析子Collapse内容
  const traceChildContent = (item: ITraceAnalysis, itemIndex: number) => {
    // 字段点击跳转处理函数
    const handleFieldClick = (key: string, value: Record<string, any>) => {
      const url = generateUrl(key, value, item, options);
      if (!url) return;

      // 字段地址由前端生成，但仍通过 Trace interaction 执行后端可用性校验。
      executeTraceInteraction(
        {
          ...item.interaction,
          action: 'link',
          drawer_type: 'trace',
          url,
          version: 'v1',
        },
        undefined,
        item.availability_ref
      );
    };
    return (
      <span class='table-content'>
        {Object.entries(TRACE_FIELD_CONFIG).map(([key, value], fieldIndex) => {
          const content = String(item[key] ?? '');
          const traceFieldIndex = itemIndex * 100 + fieldIndex;
          return (
            <span
              key={key}
              class='table-content-item'
            >
              <span class='item-label'>{value.label}</span>
              {key === 'demo_log' ? (
                renderCommonPopover(content, traceFieldIndex, 'trace_field', {
                  contentCls: 'overflow-popover-content__trace-field',
                  renderDefault: onMouseenter => (
                    <span
                      class='item-value'
                      onMouseenter={onMouseenter}
                    >
                      {item[key]}
                    </span>
                  ),
                })
              ) : (
                <span
                  class={['item-value', { 'item-value-link': !!value.url }]}
                  onClick={value.url ? () => handleFieldClick(key, value) : undefined}
                >
                  {item[key]}
                </span>
              )}
            </span>
          );
        })}
      </span>
    );
  };
  // Trace分析内容
  const traceContent = (item: ITraceAnalysis, index: number) => {
    return (
      <div class='log-content-warpper'>
        {/* Pattern展示 */}
        {contentPopoverBlock('Pattern：', item.pattern, index, 'trace_pattern', 'text')}

        <div class='log-content'>
          <div class='log-content-title'>
            <span>{$t('示例 span：')}</span>
          </div>
          {/* Trace详情表格 */}
          {traceChildContent(item, index)}
        </div>
      </div>
    );
  };
  const renderTraceSlot = () => {
    const len = options.contentList.trace_analysis?.length || 0;
    return (
      <>
        {/* Trace分析总结区域 */}
        <div class='card-summary'>
          <div class='card-summary-title'>{$t('Trace 分析总结：')}</div>
          <MarkdownViewer
            class='markdown-viewer-has-link'
            value={replaceEntityInText(options.summaryList.trace_analysis, options.extractedInfoList?.trace_analysis)}
          />
        </div>
        {/* Trace分析详情折叠面板 */}
        {len > 0 && (
          <Collapse
            class='trace-collapse log-collapse inner-collapse'
            v-model={options.activeIndex.trace}
            v-slots={{
              default: (item, index) => traceTitle(item, index),
              content: (item, index) => traceContent(item, index),
            }}
            header-icon='right-shape'
            list={options.contentList?.trace_analysis || []}
          />
        )}
      </>
    );
  };

  return renderTraceSlot();
};
