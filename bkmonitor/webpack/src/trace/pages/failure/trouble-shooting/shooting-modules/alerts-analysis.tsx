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

import { createInteractionExecutor, TableContentItem } from './common';

import type { IAnomalyAnalysis } from '../../types';
import type { IShootingModuleContext, TranslateFn } from './module-context';

/**
 * 告警异常维度分析模块
 * @returns {JSX.Element} 配置内容元素
 */
export const renderAlertsAnalysisSlot = (options: IShootingModuleContext, $t: TranslateFn) => {
  // 统一消费后端 interaction，并补充仅用于展示的侧滑标题
  const executeInteraction = createInteractionExecutor(options);

  // 告警异常维度分析标题
  const dimensionalTitle = (item: IAnomalyAnalysis) => (
    <span class='dimensional-title'>
      {/* 显示维度名称或默认标题 */}
      <span>
        {item.name || `${$t('异常维度（组合）')} ${item.$index + 1}`}
        {item.interaction?.action === 'link' && !!item.interaction.url && (
          <i
            class='icon-monitor icon-fenxiang icon-jump-page cursor-link'
            onClick={e => {
              e.stopPropagation();
              executeInteraction(item.interaction);
            }}
          />
        )}
      </span>
      {/* 国际化显示的异常程度 */}
      <i18n-t
        class='red-font'
        keypath='异常程度 {0}'
        tag='span'
      >
        <span style='font-weight: 700;'> {((item?.score || 0) * 100).toFixed(2)}% </span>
      </i18n-t>
    </span>
  );
  // 告警异常维度分析内容
  const dimensionalContent = (item: IAnomalyAnalysis) => {
    return (
      <span class='table-content'>
        {Object.keys(item.dimension_values || {}).map(key => (
          <TableContentItem
            key={key}
            label={key}
            needTitle={true}
            showLabel={true}
            value={(item.dimension_values[key] || []).join('、')}
          />
        ))}

        {/* 告警信息展示区域 */}
        {item.alerts.length > 0 && (
          <div class='dimensional-footer'>
            <i18n-t
              class='dimensional-footer-item'
              keypath='共 {0} 个告警'
              tag='span'
            >
              <b
                class='cursor-link'
                onClick={() => options.goAlertList(item.alerts)}
              >
                {item.alert_count}
              </b>
            </i18n-t>
          </div>
        )}
      </span>
    );
  };
  const renderDimensionalSlot = () => {
    const len = options.contentList?.alerts_analysis?.length;
    const displayInteraction = options.displayInteractionList.alerts_analysis;
    const canViewAll = displayInteraction?.action === 'link' && !!displayInteraction.url;
    const handleViewAll = (event: MouseEvent) => {
      event.stopPropagation();
      if (canViewAll) executeInteraction(displayInteraction);
    };
    return (
      <div>
        <div class='dimensional-desc mb-8'>
          <span>{$t('故障关联的告警，统计出最异常的维度（组合）：')}</span>
          {canViewAll && (
            <span
              class={canViewAll ? 'cursor-link' : ''}
              onClick={handleViewAll}
            >
              {$t('查看全部')}
              <i class='icon-monitor icon-fenxiang icon-jump-page' />
            </span>
          )}
        </div>
        {len > 0 && (
          <Collapse
            class='dimensional-collapse inner-collapse'
            v-model={options.activeIndex.dimensional}
            v-slots={{
              default: item => dimensionalTitle(item),
              content: item => dimensionalContent(item),
            }}
            header-icon='right-shape'
            list={options.contentList?.alerts_analysis || []}
          />
        )}
      </div>
    );
  };

  return renderDimensionalSlot();
};
