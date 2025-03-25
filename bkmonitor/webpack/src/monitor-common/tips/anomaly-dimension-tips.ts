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
/**
 *
 * @param metric 指标信息
 * @param isCorrelationMetrics 是否是关联指标
 * @returns
 */
export const createAnomalyDimensionTips = (metric: Record<string, any>, isCorrelationMetrics: boolean) => {
  if (isCorrelationMetrics)
    return `<div>${window.i18n.tc('分类名')}: ${metric.metric_name_alias}</div>
                <div>${window.i18n.tc('指标数')}: ${metric.totalPanels?.length}</div>
              `;
  let dimensionsHtml = '';
  for (const [key, val] of Object.entries(metric?.dimensions || {})) {
    dimensionsHtml += `<div class='tips-item'>
              <span class='tips-item-label'>${key}:</span>
              <span class='tips-item-value'>${val}</span>
            </div>`;
  }
  return `<div class='anomaly-dimension-tips'>
            <div class='dimension-tips-header'>
              ${window.i18n.tc('异常维度值')}:
              <span class='anomaly-score'>
                ${window.i18n.tc('异常分值')}
                <span class='score-num'>${metric.anomaly_score}</span>
              </span>
            </div>
            <div class='dimension-tips-content'>
                ${dimensionsHtml}
            </div>
          </div>
`;
};
