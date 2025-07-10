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

import { INCIDENT_STORAGE_KEY } from '../../../services/incident-services';
import { BaseScenario } from './base-scenario';

import type { BaseTableColumn } from '../../../../trace-explore/components/trace-explore-table/typing';

/**
 * @class IncidentScenario
 * @classdesc 故障场景表格特殊列渲染配置类
 * @extends BaseScenario
 */
export class IncidentScenario extends BaseScenario {
  /**
   * @readonly 场景标识
   */
  readonly name = INCIDENT_STORAGE_KEY;

  constructor(
    private readonly context: {
      handleShowDetail: (id: string) => void;
      handlePopoverShow: (e: MouseEvent, content: any) => void;
      handleClearTimer: () => void;
    }
  ) {
    super();
  }

  /**
   * @description 获取当前场景的特殊列配置
   */
  getColumnsConfig(): Map<string, Partial<BaseTableColumn>> {
    const commonColumnConfig = this.getCommonColumnsConfig();
    const columns = new Map(commonColumnConfig);

    return columns;
  }

  // ----------------- 故障场景私有渲染方法 -----------------

  // ----------------- 故障场景私有逻辑方法 -----------------
}
