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

import { Button, Input } from 'bkui-vue';
import { EnlargeLine } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import FieldTypeIcon from '../../../../trace-explore/components/field-type-icon';

import type { IRumOriginBlockVM, IRumOriginRowVM } from '../../typings';

import './origin-data-panel.scss';
import 'vue-json-pretty/lib/styles.css';

/** 原始值的运行时类型映射到检索侧的字段类型，直接复用 FieldTypeIcon 的图标与配色 */
const VALUE_TYPE_TO_FIELD_TYPE: Record<IRumOriginRowVM['valueType'], string> = {
  number: 'long',
  string: 'keyword',
  boolean: 'boolean',
  object: 'object',
};

/** 值是否为 JSON 文本，是则该行支持「格式化」切换展示 */
function isJsonValue(value: string): boolean {
  try {
    return typeof JSON.parse(value) === 'object';
  } catch {
    return false;
  }
}

/**
 * 原始数据面板：Span / Attributes / Resource / Links / Events 五个折叠块。
 * Links 按 trace_id 分组，Events 按事件名分组，Events 支持按键或值搜索过滤。
 */
export default defineComponent({
  name: 'RumOriginDataPanel',
  props: {
    blocks: {
      type: Array as PropType<IRumOriginBlockVM[]>,
      default: () => [],
    },
    /** 块内搜索关键字，仅 searchable 为 true 的块（当前只有 Events）会用到 */
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
    /** 收起的二级分组（Links 按 trace_id、Events 按事件名），默认全部展开 */
    const collapsedGroups = shallowRef<Set<string>>(new Set());
    /** 已切换为「格式化」展示的 JSON 行，未记录的行默认以原文展示 */
    const jsonRows = shallowRef<Set<string>>(new Set());

    /** 展开/收起整个折叠块，整条块头均可点击（cursor: pointer 见 scss） */
    function toggleBlock(key: string) {
      const next = new Set(expandedKeys.value);
      next.has(key) ? next.delete(key) : next.add(key);
      expandedKeys.value = next;
    }

    /** 展开/收起块内的二级分组（Links / Events） */
    function toggleGroup(key: string) {
      const next = new Set(collapsedGroups.value);
      next.has(key) ? next.delete(key) : next.add(key);
      collapsedGroups.value = next;
    }

    /** 切换单行 JSON 值的「格式化 / 原文」展示 */
    function toggleFormat(rowId: string) {
      const next = new Set(jsonRows.value);
      next.has(rowId) ? next.delete(rowId) : next.add(rowId);
      jsonRows.value = next;
    }

    /**
     * 渲染一行键值
     * @param index 行在所属块/分组内的序号，用于斑马纹，并参与行内状态 id 的构成
     * @param idPrefix 行内状态（格式化开关）的命名空间：普通块用 block.key、分组内用 groupKey，
     *                 避免不同块中同名 key 的行互相串状态
     */
    function renderRow(row: IRumOriginRowVM, index: number, idPrefix: string) {
      const rowId = `${idPrefix}_${row.key}_${index}`;
      const isJson = isJsonValue(row.value);
      const showJson = jsonRows.value.has(rowId);
      return (
        <div
          key={rowId}
          class={{ 'origin-row': true, 'is-odd': index % 2 === 0 }}
        >
          <div class='row-key'>
            {/* 行高 24px、类型图标 14px，下沉 5px 使图标与右侧值文本首行视觉居中 */}
            <FieldTypeIcon
              style='margin-top: 5px;'
              type={VALUE_TYPE_TO_FIELD_TYPE[row.valueType]}
            />
            <span
              class='key-text'
              v-overflow-tips
              title={row.key}
            >
              {row.key}
            </span>
            <div class='row-operator'>
              <EnlargeLine
                class='icon-add-query'
                v-bk-tooltips={{ content: t('添加为检索条件') }}
                onClick={() => emit('conditionAdd', row.key, row.value)}
              />
              <i
                class='icon-monitor icon-mc-copy'
                v-bk-tooltips={{ content: t('复制') }}
                onClick={() => emit('copy', row.value)}
              />
            </div>
          </div>
          <div class='row-value'>{isJson && showJson ? <VueJsonPretty data={JSON.parse(row.value)} /> : row.value}</div>
          {isJson ? (
            <Button
              class='format-button'
              outline={showJson}
              size='small'
              theme='primary'
              onClick={() => toggleFormat(rowId)}
            >
              <i class='icon-monitor icon-code' />
              {t('格式化')}
            </Button>
          ) : null}
        </div>
      );
    }

    /** 渲染一个折叠块：块头（标题 / 摘要 / 搜索框）+ 展开后的键值行或二级分组 */
    function renderBlock(block: IRumOriginBlockVM) {
      const expanded = expandedKeys.value.has(block.key);
      return (
        <div
          key={block.key}
          class={{ 'origin-block': true, 'is-expanded': expanded }}
        >
          <div
            class={['block-head', { 'has-block-search': block.searchable }]}
            onClick={() => toggleBlock(block.key)}
          >
            <span class='block-title'>
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
            {expanded && block.searchable ? (
              // 块头整行可点击收起，这里包一层拦截冒泡，避免在搜索框内点击/清空时误收起整个块
              <span
                class='block-search'
                onClick={e => {
                  e.stopPropagation();
                }}
              >
                <Input
                  modelValue={props.eventKeyword}
                  placeholder={t('搜索')}
                  type='search'
                  clearable
                  onUpdate:modelValue={(value: string) => emit('update:eventKeyword', value)}
                />
              </span>
            ) : null}
          </div>
          {expanded ? (
            <div class='block-body'>
              {block.rows?.map((row, index) => renderRow(row, index, block.key))}
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
                      <i class={`group-arrow icon-monitor ${collapsed ? 'icon-arrow-right' : 'icon-arrow-down'}`} />
                      {group.name}
                    </div>
                    {collapsed ? null : group.rows.map((row, index) => renderRow(row, index, groupKey))}
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
