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

import { type PropType, defineComponent, shallowRef } from 'vue';

import { Switcher } from 'bkui-vue';
import CommonTable from 'trace/pages/alarm-center/components/alarm-table/components/common-table/common-table';
import { useI18n } from 'vue-i18n';

import TagCell from './tag-cell';

import type { TSourceAnalysisRule } from '../../typings';
import type { BaseTableColumn } from 'trace/pages/trace-explore/components/trace-explore-table/typing';

import './analysis-rule-table.scss';

export default defineComponent({
  name: 'AnalysisRuleTable',
  props: {
    /** 源码分析规则列表数据 */
    data: {
      type: Array as PropType<any[]>,
      default: () => [],
    },
  },
  setup() {
    const { t } = useI18n();

    /** 表格列配置 */
    const tableColumns = shallowRef<BaseTableColumn[]>([
      {
        /** 匹配方式列 */
        colKey: 'conditions',
        ellipsis: false,
        resizable: true,
        width: 440,
        minWidth: 440,
        sorter: false,
        cellRenderer: _row => <div>匹配方式</div>,
        title: () => <span>{t('匹配方式')}</span>,
      },
      {
        /** 优先级列 */
        colKey: 'priority',
        ellipsis: false,
        resizable: true,
        width: 105,
        minWidth: 105,
        sorter: false,
        cellRenderer: (row: TSourceAnalysisRule) => <div class='priority-tag'>{row.priority}</div>,
        title: () => <span>{t('优先级')}</span>,
      },
      {
        /** 智能体列 */
        colKey: 'agent_id',
        ellipsis: false,
        resizable: true,
        width: 224,
        minWidth: 224,
        sorter: false,
        cellRenderer: row => <TagCell tags={[row.agent_id]} />,
        title: () => <span>{t('智能体')}</span>,
      },
      {
        colKey: 'knowledge_base_ids',
        ellipsis: false,
        resizable: true,
        width: 224,
        minWidth: 224,
        sorter: false,
        cellRenderer: row => <TagCell tags={row.knowledge_base_ids} />,
        title: () => <span>{t('知识库')}</span>,
      },
      {
        /** 关联 skill 列 */
        colKey: 'skill_ids',
        ellipsis: false,
        resizable: true,
        width: 224,
        minWidth: 224,
        sorter: false,
        cellRenderer: row => <TagCell tags={row.skill_ids} />,
        title: () => <span>skill</span>,
      },
      {
        /** 启用状态列 */
        colKey: 'is_enabled',
        ellipsis: false,
        resizable: true,
        width: 73,
        minWidth: 73,
        sorter: false,
        cellRenderer: row => (
          <Switcher
            modelValue={row.is_enabled}
            size='small'
            theme='primary'
          />
        ),
        title: () => <span>状态</span>,
      },
      {
        /** 操作列 */
        colKey: 'operate',
        ellipsis: false,
        resizable: true,
        width: 72,
        minWidth: 72,
        sorter: false,
        cellRenderer: _row => (
          <span>
            <span class='icon-monitor icon-bianji' />
            <span class='icon-monitor icon-mc-delete-line' />
          </span>
        ),
        title: () => <span>xxxx</span>,
      },
    ] as any[]);

    return {
      tableColumns,
    };
  },
  render() {
    return (
      <div class='ai-config-analysis-rule-table'>
        {/* 通用表格组件展示源码分析规则 */}
        <CommonTable
          columns={this.tableColumns}
          data={this.data}
        />
      </div>
    );
  },
});
