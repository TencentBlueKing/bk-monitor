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
import { RUM_VIEW_LOADING_TYPE_ICONS } from '../../../constants';

import type { BadgePresentation } from '../../../typings';

/** 同一字段在复合标签位置使用的样式类和选图规则。 */
export const BADGE_PRESENTATIONS: ReadonlyMap<string, BadgePresentation> = new Map<string, BadgePresentation>([
  ['attributes.action.frustration.type', { className: 'rum-badge-long-task' }],
  ['attributes.action.type', { className: 'rum-badge-action rum-badge-mono' }],
  ['attributes.http.request.method', { className: 'rum-badge-mono' }],
  ['attributes.http.response.status_code', { className: 'rum-badge-mono' }],
  ['attributes.long_task.entry_type', { className: 'rum-badge-long-task' }],
  ['attributes.resource.type', { className: 'rum-badge-resource rum-badge-mono' }],
  [
    'attributes.view.loading_type',
    {
      className: 'rum-badge-view',
      resolveIcon: value => {
        const loadingType = String(value) as keyof typeof RUM_VIEW_LOADING_TYPE_ICONS;
        return Object.hasOwn(RUM_VIEW_LOADING_TYPE_ICONS, loadingType)
          ? { icon: RUM_VIEW_LOADING_TYPE_ICONS[loadingType] }
          : undefined;
      },
    },
  ],
  ['events.attributes.exception.type', { className: 'rum-badge-error rum-badge-mono' }],
  ['virtual.viewport', { resolveIcon: () => ({ icon: 'icon-chuangkou', className: 'is-viewport' }) }],
]);
