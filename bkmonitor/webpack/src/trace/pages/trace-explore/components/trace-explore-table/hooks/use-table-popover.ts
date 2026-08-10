/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import type { MaybeRef } from 'vue';

import { type UseTablePopoverOptions, useTablePopover } from '../../../../../hooks/use-table-popover';
import { isEllipsisActiveSingleLine } from '../../../../../utils/dom-helper';
import { ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME } from '../constants';

import type { PrimaryTable } from '@blueking/tdesign-ui';

type DelegationRoot = MaybeRef<HTMLElement> | MaybeRef<InstanceType<typeof PrimaryTable>>;

/**
 * @description trace-explore 表格列描述弹出 popover 处理（页面专属，依赖 dataset.colDescription 约定）
 */
export const useTableHeaderDescription = (
  delegationRoot: DelegationRoot,
  options?: Omit<UseTablePopoverOptions, 'getContentOptions'>
) =>
  useTablePopover(delegationRoot, {
    trigger: { selector: options?.trigger?.selector || `.${ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME}` },
    getContentOptions: triggerDom => {
      const content = triggerDom.dataset.colDescription;
      if (!content) return;
      const { isEllipsisActive } = isEllipsisActiveSingleLine(triggerDom.parentElement);
      return { content, popoverTarget: isEllipsisActive ? triggerDom.parentElement : triggerDom };
    },
    popoverOptions: {
      theme: 'light max-width-50vw text-wrap',
      placement: 'right',
      ...(options?.popoverOptions || {}),
    },
  });
