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
import { defineComponent, shallowRef } from 'vue';
import type { PropType } from 'vue';

import { Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import FieldTypeIcon from '../../../../trace-explore/components/field-type-icon';

import type { IRumOriginBlockVM, IRumOriginRowVM } from '../../typings';

import './origin-data-panel.scss';

/** 原始值的运行时类型映射到检索侧的字段类型，直接复用 FieldTypeIcon 的图标与配色 */
const VALUE_TYPE_TO_FIELD_TYPE: Record<IRumOriginRowVM['valueType'], string> = {
  number: 'long',
  string: 'keyword',
  boolean: 'boolean',
  object: 'object',
};

/**
 * 原始数据面板：Span / Attributes / Resource / Events 四个折叠块。
 * Events 块内按事件名分组，并支持按键或值搜索过滤。
 */
export default defineComponent({
  name: 'RumOriginDataPanel',
  props: {
    blocks: {
      type: Array as PropType<IRumOriginBlockVM[]>,
      default: () => [],
    },
    /** Events 块的搜索关键字 */
    eventKeyword: {
      type: String,
      default: '',
    },
  },
  emits: {
    'update:eventKeyword': (_value: string) => true,
    /** 点击某一行的「添加为检索条件」 */
    conditionAdd: (_key: string, _value: string) => true,
    /** 点击某一行的复制 */
    copy: (_value: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 展开的折叠块，默认全部收起（与设计稿一致，Events 由用户按需展开） */
    const expandedKeys = shallowRef<Set<string>>(new Set());
    /** 收起的事件分组，默认全部展开 */
    const collapsedGroups = shallowRef<Set<string>>(new Set());

    function toggleBlock(key: string) {
      const next = new Set(expandedKeys.value);
      next.has(key) ? next.delete(key) : next.add(key);
      expandedKeys.value = next;
    }

    function toggleGroup(key: string) {
      const next = new Set(collapsedGroups.value);
      next.has(key) ? next.delete(key) : next.add(key);
      collapsedGroups.value = next;
    }

    function renderRow(row: IRumOriginRowVM, index: number) {
      return (
        <div
          key={`${row.key}_${index}`}
          class={{ 'origin-row': true, 'is-odd': index % 2 === 0 }}
        >
          <div class='row-key'>
            <FieldTypeIcon type={VALUE_TYPE_TO_FIELD_TYPE[row.valueType]} />
            <span
              class='key-text'
              title={row.key}
            >
              {row.key}
            </span>
          </div>
          <i
            class='row-action icon-monitor icon-a-sousuo'
            v-bk-tooltips={{ content: t('添加为检索条件') }}
            onClick={() => emit('conditionAdd', row.key, row.value)}
          />
          <i
            class='row-action icon-monitor icon-mc-copy'
            v-bk-tooltips={{ content: t('复制') }}
            onClick={() => emit('copy', row.value)}
          />
          <pre class='row-value'>{row.value}</pre>
        </div>
      );
    }

    function renderBlock(block: IRumOriginBlockVM) {
      const expanded = expandedKeys.value.has(block.key);
      return (
        <div
          key={block.key}
          class={{ 'origin-block': true, 'is-expanded': expanded }}
        >
          <div class='block-head'>
            <span
              class='block-title'
              onClick={() => toggleBlock(block.key)}
            >
              <i class={`title-arrow icon-monitor ${expanded ? 'icon-mc-arrow-down' : 'icon-mc-arrow-right'}`} />
              {block.title}
            </span>
            {expanded ? null : (
              <span
                class='block-summary'
                title={block.summary}
              >
                {block.summary}
              </span>
            )}
            {expanded && block.groups ? (
              <Input
                class='block-search'
                modelValue={props.eventKeyword}
                placeholder={t('搜索')}
                type='search'
                clearable
                onUpdate:modelValue={(value: string) => emit('update:eventKeyword', value)}
              />
            ) : null}
          </div>
          {expanded ? (
            <div class='block-body'>
              {block.rows?.map(renderRow)}
              {block.groups?.map(group => {
                const groupKey = `${block.key}_${group.name}`;
                const collapsed = collapsedGroups.value.has(groupKey);
                return (
                  <div
                    key={groupKey}
                    class='origin-group'
                  >
                    <div
                      class='group-head'
                      onClick={() => toggleGroup(groupKey)}
                    >
                      <i
                        class={`group-arrow icon-monitor ${collapsed ? 'icon-mc-arrow-right' : 'icon-mc-arrow-down'}`}
                      />
                      {group.name}
                    </div>
                    {collapsed ? null : group.rows.map(renderRow)}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      );
    }

    return () => <div class='rum-origin-data-panel'>{props.blocks.map(renderBlock)}</div>;
  },
});
