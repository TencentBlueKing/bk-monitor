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
import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EmptyStatus, {
  type EmptyStatusOperationType,
  type EmptyStatusType,
} from '../../../../components/empty-status/empty-status';
import DimensionFieldTree from '../../../trace-explore/components/dimension-field-tree';
import StatisticsList from '../../../trace-explore/components/statistics-list';
import { convertToTree } from '../../../trace-explore/utils';
import { useFieldStatisticsPopover } from '../../composables/use-field-statistics-popover';
import {
  DEFAULT_FIELD_GROUP_ICON,
  RAW_FIELD_GROUP_ICON,
  RAW_FIELD_GROUP_NAME,
  RUM_FIELD_GROUP_ICON_MAP,
} from '../../constants';
import { statisticsApi } from '../../services/rum-search';

import type { ConditionChangeEvent, IDimensionFieldTreeItem } from '../../../trace-explore/typing';
import type { IRumCommonParams, IRumField, IRumFieldGroup } from '../../typings';

import './rum-dimension-panel.scss';

interface IRenderGroup {
  alias: string;
  icon: string;
  isRawGroup: boolean;
  name: string;
  nodes: IDimensionFieldTreeItem[];
  /** 分组是否适用于当前 span 类型，不适用时默认折叠 */
  supported: boolean;
}

export default defineComponent({
  name: 'RumDimensionPanel',
  props: {
    groups: {
      type: Array as PropType<IRumFieldGroup[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    /** 统计分析的查询上下文 */
    commonParams: {
      type: Object as PropType<IRumCommonParams>,
      default: () => ({}),
    },
    /** 当前选中的 span 类型，用于决定分组默认展开还是折叠 */
    activeSpanType: {
      type: String,
      default: '',
    },
    /** 时间范围，透传给统计分析 */
    timeRange: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {
    conditionChange: (_condition: ConditionChangeEvent, _isFromDimensionFilterPanel: boolean) => true,
    close: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const searchVal = shallowRef('');
    const emptyStatus = shallowRef<EmptyStatusType>('empty');
    /** 用户手动展开收起的分组，未记录的分组按是否适用于当前类型决定 */
    const groupOverrides = shallowRef(new Map<string, boolean>());

    /** 按关键字过滤字段，命中别名、字段名或拼音都算 */
    function filterFields(fields: IRumField[], keyword: string) {
      if (!keyword) return fields;
      const lower = keyword.toLocaleLowerCase();
      return fields.filter(
        field => field.alias.includes(keyword) || field.name.includes(keyword) || field.pinyinStr?.includes(lower)
      );
    }

    const renderGroups = computed<IRenderGroup[]>(() => {
      const keyword = searchVal.value.trim();
      return props.groups
        .map(group => {
          const fields = filterFields(group.fields, keyword);
          const isRawGroup = group.name === RAW_FIELD_GROUP_NAME;
          return {
            name: group.name,
            alias: group.alias,
            isRawGroup,
            supported:
              !props.activeSpanType ||
              !group.supported_span_types?.length ||
              group.supported_span_types.includes(props.activeSpanType),
            icon: isRawGroup ? RAW_FIELD_GROUP_ICON : RUM_FIELD_GROUP_ICON_MAP[group.name] || DEFAULT_FIELD_GROUP_ICON,
            // 原始字段按 `.` 分层展示成树，业务分组保持平铺
            nodes: isRawGroup
              ? convertToTree(fields as unknown as IDimensionFieldTreeItem[])
              : (fields.map(field => ({ ...field, levelName: field.alias })) as IDimensionFieldTreeItem[]),
          };
        })
        .filter(group => group.nodes.length);
    });

    watch(
      () => props.groups,
      () => {
        groupOverrides.value = new Map();
      }
    );

    const handleSearch = useDebounceFn((keyword: string) => {
      searchVal.value = keyword;
      emptyStatus.value = keyword ? 'search-empty' : 'empty';
    }, 100);

    function isGroupExpanded(group: IRenderGroup) {
      // 搜索时把命中的分组全部摊开，避免用户还要逐个点开找
      if (searchVal.value) return true;
      return groupOverrides.value.get(group.name) ?? group.supported;
    }

    function toggleGroup(group: IRenderGroup) {
      const overrides = new Map(groupOverrides.value);
      overrides.set(group.name, !isGroupExpanded(group));
      groupOverrides.value = overrides;
    }

    const { activeFieldName, selectField, showPopover, statisticsListRef, destroyPopover, openPopover } =
      useFieldStatisticsPopover();

    function handleFieldClick(event: MouseEvent, field: IDimensionFieldTreeItem) {
      openPopover(event.currentTarget as Element, field);
    }

    function handleEmptyOperation(type: EmptyStatusOperationType) {
      if (type !== 'clear-filter') return;
      searchVal.value = '';
      handleSearch('');
    }

    return {
      t,
      searchVal,
      emptyStatus,
      renderGroups,
      activeFieldName,
      selectField,
      showPopover,
      statisticsApi,
      statisticsListRef,
      destroyPopover,
      handleSearch,
      handleFieldClick,
      handleEmptyOperation,
      isGroupExpanded,
      toggleGroup,
      handleConditionChange: (condition: { key: string; method: string; value: string }) =>
        emit('conditionChange', condition, true),
      handleClose: () => emit('close'),
    };
  },
  render() {
    if (this.loading) {
      return (
        <div class='rum-dimension-panel-skeleton'>
          <div class='skeleton-element title' />
          <div class='skeleton-element search-input' />
          {Array.from({ length: 10 }, (_, index) => (
            <div
              key={`skeleton-${index}`}
              class='skeleton-element list-item'
            />
          ))}
        </div>
      );
    }

    return (
      <div class='rum-dimension-panel'>
        <div class='panel-header'>
          <i
            class='icon-monitor icon-gongneng-shouqi'
            v-bk-tooltips={{ content: this.t('收起') }}
            onClick={this.handleClose}
          />
          <span class='panel-title'>{this.t('维度统计')}</span>
          <span class='panel-mode-tag'>Span</span>
        </div>

        <div class='panel-search'>
          <Input
            v-model={this.searchVal}
            native-attributes={{ spellcheck: false }}
            placeholder={this.t('搜索')}
            type='search'
            clearable
            show-clear-only-hover
            onClear={() => {
              this.handleSearch('');
            }}
            onEnter={this.handleSearch}
            onInput={this.handleSearch}
          />
        </div>

        {this.renderGroups.length ? (
          <div
            class='panel-groups'
            onScroll={() => {
              this.showPopover = false;
              this.destroyPopover();
            }}
          >
            {this.renderGroups.map(group => {
              const expanded = this.isGroupExpanded(group);
              return (
                <div
                  key={group.name}
                  class='dimension-group'
                >
                  <div
                    class='group-title'
                    onClick={() => this.toggleGroup(group)}
                  >
                    <i class={['icon-monitor', 'group-icon', group.icon]} />
                    <span
                      class='group-name'
                      v-overflow-tips
                    >
                      {group.alias}
                    </span>
                    {!group.isRawGroup && <span class='group-count'>{group.nodes.length}</span>}
                    <i class={['icon-monitor', 'icon-arrow-down', 'group-arrow', { collapsed: !expanded }]} />
                  </div>
                  {expanded && (
                    <DimensionFieldTree
                      activeField={this.activeFieldName}
                      expandAll={!!this.searchVal}
                      list={group.nodes}
                      onFieldClick={this.handleFieldClick}
                    />
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyStatus
            type={this.emptyStatus}
            onOperation={this.handleEmptyOperation}
          />
        )}

        <StatisticsList
          ref='statisticsListRef'
          api={this.statisticsApi}
          commonParams={this.commonParams as any}
          fieldType={this.selectField?.type}
          isShow={this.showPopover}
          optionValues={this.selectField?.option_values}
          selectField={this.selectField?.name}
          timeRange={this.timeRange as any}
          unit={this.selectField?.field_unit}
          onConditionChange={this.handleConditionChange}
          onShowMore={this.destroyPopover}
        />
      </div>
    );
  },
});
