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

import { useI18n } from 'vue-i18n';

import {
  ExploreTableColumnTypeEnum,
  type ExploreTableColumn,
} from '../../../../trace-explore/components/trace-explore-table/typing';

export function useEventColumnConfig() {
  const { t } = useI18n();
  function getTableColumnMapByAlarmType(): Record<string, ExploreTableColumn> {
    return {
      id: {
        colKey: 'id',
        title: 'ID',
        width: 160,
      },
      create_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
        colKey: 'create_time',
        title: t('创建时间'),
        width: 150,
      },
      action_name: {
        renderType: ExploreTableColumnTypeEnum.TEXT,
        colKey: 'action_name',
        title: t('套餐名称'),
        width: 180,
        sorter: true,
      },
      action_plugin_type_display: {
        renderType: ExploreTableColumnTypeEnum.TEXT,
        colKey: 'action_plugin_type_display',
        title: t('套餐类型'),
        width: 100,
        sorter: true,
      },
      operate_target_string: {
        renderType: ExploreTableColumnTypeEnum.TEXT,
        colKey: 'operate_target_string',
        title: t('执行对象'),
        width: 120,
      },
      operator: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        colKey: 'operator',
        title: t('负责人'),
        width: 220,
      },
      alert_count: {
        renderType: ExploreTableColumnTypeEnum.LINK,
        colKey: 'alert_count',
        title: t('触发告警数'),
        width: 120,
      },
      converge_count: {
        renderType: ExploreTableColumnTypeEnum.LINK,
        colKey: 'converge_count',
        title: t('防御告警数'),
        width: 120,
      },
      end_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
        colKey: 'end_time',
        title: t('结束时间'),
        width: 150,
        sorter: true,
      },
      duration: {
        renderType: ExploreTableColumnTypeEnum.DURATION,
        colKey: 'duration',
        title: t('处理时长'),
        width: 80,
        sorter: true,
      },
      status: {
        renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
        colKey: 'status',
        title: t('执行状态'),
        width: 80,
        sorter: true,
      },
      content: {
        renderType: ExploreTableColumnTypeEnum.TEXT,
        colKey: 'content',
        title: t('套餐内容'),
        width: 200,
      },
    };
  }

  return {};
}
