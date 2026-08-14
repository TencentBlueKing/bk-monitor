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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { InfoBox, Switcher } from 'bkui-vue';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import CommonTable from 'trace/pages/alarm-center/components/alarm-table/components/common-table/common-table';
import { useI18n } from 'vue-i18n';

import { updateSourceAnalysisRuleApi } from '../../services/ai-config';
import TagCell from './tag-cell';

import type { TSourceAnalysisRule } from '../../typings';
import type { FilterValue } from '@blueking/tdesign-ui/typings/packages/table';
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
    /** 列表加载中 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 前端搜索关键词，仅匹配匹配方式 condition 的 value、智能体、知识库、skill */
    searchValue: {
      type: String,
      default: '',
    },
  },
  emits: {
    /** 清空搜索值 */
    clearSearch: () => true,
    /** 规则局部更新（如启停、调整优先级）后回写列表 */
    updateRule: (_rule: TSourceAnalysisRule) => true,
    /** 编辑规则 */
    editRule: (_rule: TSourceAnalysisRule) => true,
    /** 删除规则 */
    deleteRule: (_rule: TSourceAnalysisRule) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /**
     * @description 清空搜索值
     */
    const handleClearSearch = () => {
      emit('clearSearch');
    };

    /** 表头筛选值（当前生效的列筛选） */
    const columnFilter = shallowRef<FilterValue | undefined>(undefined);
    /** 排序值，如 'priority' / '-priority' */
    const sortValue = shallowRef('');

    /** 经搜索、列筛选、排序后的规则列表 */
    const filteredData = computed<TSourceAnalysisRule[]>(() => {
      let rows = [...props.data];

      // 1. 前端搜索：仅匹配匹配方式 condition 的 value、智能体、知识库、skill
      const keyword = props.searchValue?.trim().toLowerCase();
      if (keyword) {
        rows = rows.filter((row: TSourceAnalysisRule) => {
          const conditionValueMatch = row.conditions.some(condition =>
            (condition.value ?? []).some(val => val.toLowerCase().includes(keyword))
          );
          const agentMatch = row.agent_id?.toLowerCase().includes(keyword);
          const knowledgeMatch = (row.knowledge_base_ids ?? []).some(id => id.toLowerCase().includes(keyword));
          const skillMatch = (row.skill_ids ?? []).some(id => id.toLowerCase().includes(keyword));
          return conditionValueMatch || agentMatch || knowledgeMatch || skillMatch;
        });
      }

      // 2. 列筛选：当前仅"启用状态"列支持筛选，根据选中的状态值过滤
      const statusFilter = columnFilter.value?.is_enabled;
      if (Array.isArray(statusFilter) && statusFilter.length > 0) {
        rows = rows.filter((row: TSourceAnalysisRule) => statusFilter.includes(row.is_enabled));
      }

      // 3. 排序：按优先级字段升序/降序
      if (sortValue.value) {
        const descending = sortValue.value.startsWith('-');
        const colKey = descending ? sortValue.value.slice(1) : sortValue.value;
        if (colKey === 'priority') {
          rows.sort((a: TSourceAnalysisRule, b: TSourceAnalysisRule) =>
            descending ? b.priority - a.priority : a.priority - b.priority
          );
        }
      }

      return rows;
    });

    /** 过滤后是否为空：为空且非加载中时展示 EmptyStatus 空状态 */
    const isEmpty = computed(() => !props.loading && filteredData.value.length === 0);

    /** 空状态类型：搜索无结果时为 search-empty，否则为 empty */
    const emptyType = computed(() => (props.searchValue ? 'search-empty' : 'empty'));

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
        sorter: true,
        cellRenderer: (row: TSourceAnalysisRule) => <div class='priority-tag'>{row.priority}</div>,
        title: () => (
          <span class='priority-col-title'>
            <span>{t('优先级')}</span>
            {/* 优先级说明提示图标：hover 展示数值区间说明 */}
            <span
              class='icon-monitor icon-hint'
              v-bk-tooltips={{
                placement: 'top',
                content: t('数值越高，优先级越高，最大值为10000'),
              }}
            />
          </span>
        ),
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
        filter: {
          list: [
            {
              label: t('启用'),
              value: true,
              checked: false,
            },
            {
              label: t('停用'),
              value: false,
              checked: false,
            },
          ],
          type: 'multiple',
          showConfirmAndReset: true,
          resetValue: [],
        },
        cellRenderer: row => (
          <Switcher
            beforeChange={() => handleEnableChange(row)}
            modelValue={row.is_enabled}
            size='small'
            theme='primary'
          />
        ),
        title: t('状态'),
      },
      {
        /** 操作列 */
        colKey: 'operate',
        ellipsis: false,
        resizable: true,
        width: 72,
        minWidth: 72,
        sorter: false,
        cellRenderer: (row: TSourceAnalysisRule) => (
          <span class='operate-col-wrap'>
            {/* 编辑规则按钮 */}
            <span
              class='icon-monitor icon-bianji'
              onClick={() => {
                emit('editRule', row);
              }}
            />
            {/* 删除规则按钮：默认策略置灰不可删除 */}
            <span
              class={['icon-monitor icon-mc-delete-line', { 'is-disabled': row.is_default }]}
              v-bk-tooltips={{
                placement: 'top',
                content: t('默认策略不可删除'),
                disabled: !row.is_default,
              }}
              onClick={() => {
                if (!row.is_default) {
                  emit('deleteRule', row);
                }
              }}
            />
          </span>
        ),
        title: () => '',
      },
    ] as any[]);

    /**
     * @description 表头列筛选变化：记录筛选值并驱动表格数据过滤
     * @param {FilterValue} value 列筛选值，key 为 colKey，value 为选中的筛选项数组
     */
    const handleColumnFilter = (value: FilterValue) => {
      columnFilter.value = value;
    };

    /**
     * @description 表格排序变化：记录排序值并驱动表格数据排序
     * @param {string} sort 排序值，如 'priority' 升序、'-priority' 降序
     */
    const handleSortChange = (sort: string) => {
      sortValue.value = sort;
    };

    /** 启停规则切换：二次确认后调用更新接口，成功则 resolve(true) 使开关生效 */
    function handleEnableChange(row: TSourceAnalysisRule) {
      return new Promise(resolve => {
        InfoBox({
          title: row.is_enabled ? t('确定停用此规则') : t('确定启用此规则'),
          onConfirm: () => {
            const isEnabled = !row.is_enabled;
            console.log(row.id);
            updateSourceAnalysisRuleApi(row.id, { is_enabled: isEnabled })
              .then(data => {
                resolve(!!data?.is_enabled);
                emit('updateRule', {
                  ...row,
                  is_enabled: isEnabled,
                });
              })
              .catch(() => {
                resolve(false);
              });
          },
          onCancel: () => {
            resolve(false);
          },
        });
      });
    }

    return {
      filteredData,
      isEmpty,
      emptyType,
      handleClearSearch,
      tableColumns,
      columnFilter,
      sortValue,
      handleColumnFilter,
      handleSortChange,
    };
  },
  render() {
    return (
      <div class='ai-config-analysis-rule-table'>
        {/* 过滤结果为空且非加载中时，展示自定义空状态 */}
        <CommonTable
          empty={
            (this.isEmpty
              ? () => (
                  <EmptyStatus
                    scene='part'
                    type={this.emptyType}
                    onOperation={this.handleClearSearch}
                  />
                )
              : undefined) as any
          }
          activeRowType={null}
          columns={this.tableColumns}
          data={this.filteredData}
          filterValue={this.columnFilter}
          loading={this.loading}
          sort={this.sortValue}
          onFilterChange={this.handleColumnFilter}
          onSortChange={this.handleSortChange as any}
        />
      </div>
    );
  },
});
