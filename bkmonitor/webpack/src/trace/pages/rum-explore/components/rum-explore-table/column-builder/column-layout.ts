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
import type { CompositeMember, CompositeRow, CompositeSection, IRumCompositeItem, IRumField } from '../../../typings';

/** 判断字段能否展示，保留布尔 false 和数值 0。 */
export const hasFieldValue = (value: unknown): boolean => {
  if (Array.isArray(value)) return value.some(hasFieldValue);
  return value !== null && value !== undefined && value !== '';
};

/**
 * 在展示列键和接口字段键之间转换排序，保留排序方向与优先级。
 * @param sort 单条或多条排序规则，空值用于清除排序
 * @param keys 本次转换的字段键映射
 * @returns 与输入同形式的排序规则
 */
export const mapSortKeys = (sort: string | string[] = '', keys: ReadonlyMap<string, string>) => {
  /** 只替换字段名，降序标记随原规则保留。 */
  const mapRule = (rule: string) => {
    const descending = rule.startsWith('-');
    const field = descending ? rule.slice(1) : rule;
    return `${descending ? '-' : ''}${keys.get(field) ?? field}`;
  };

  if (!Array.isArray(sort)) return mapRule(sort);
  const seen = new Set<string>();
  return sort
    .filter(Boolean)
    .map(mapRule)
    .filter(rule => {
      const field = rule.replace(/^-/, '');
      if (seen.has(field)) return false;
      seen.add(field);
      return true;
    });
};

/**
 * 将字段配置解析为可复用的列布局、分析候选和排序字段。
 * @param field 展示列对应的字段
 * @param fields 完整字段索引，包含不可独立成列的成员
 */
export const resolveColumnLayout = (field: IRumField | undefined, fields: ReadonlyMap<string, IRumField>) => {
  const composite = field?.composite;
  if (!composite) {
    const analysisField = field?.is_dimensions ? field : undefined;
    return { sortField: field, analysisField, analysisFields: analysisField ? [analysisField] : [] };
  }

  const analysisFieldsByName = new Map<string, IRumField>();
  const sections = (Array.isArray(composite.sections) ? composite.sections : []).map((section, index) => {
    /** 解析成员引用和展示条件，并收集有分析能力的字段。 */
    const resolveMembers = (items: IRumCompositeItem[] | undefined, placement: 'badge' | 'item'): CompositeMember[] => {
      if (!Array.isArray(items)) return [];
      return items.flatMap((item, itemIndex) => {
        const memberField = fields.get(item?.field_name);
        if (!memberField) return [];
        if (memberField.is_dimensions) analysisFieldsByName.set(memberField.name, memberField);
        return [
          {
            field: memberField,
            isPrimary: memberField.name === composite.primary,
            key: `${index}:${placement}:${itemIndex}`,
            showIf: Object.entries(item.show_if ?? {}).map(([name, candidates]) => [
              name,
              new Set(Array.isArray(candidates) ? candidates.map(String) : []),
            ]),
            type: item.type,
          },
        ];
      });
    };

    return {
      index,
      items: resolveMembers(section?.items, 'item'),
      badges: resolveMembers(section?.badges, 'badge'),
      separator: typeof section?.separator === 'string' ? section.separator : '',
    };
  });

  const sortField = fields.get(composite.primary);
  const analysisFields = [...analysisFieldsByName.values()];
  const analysisField = analysisFieldsByName.get(composite.primary) ?? analysisFields[0];
  return { sections, sortField, analysisFields, analysisField };
};

/**
 * 按当前记录求值并过滤不可见成员，保留有内容的复合行。
 * @param sections 已解析的行布局
 * @param row 列表接口返回的扁平记录
 * @returns 可以交给复合单元格展示的行
 */
export const resolveCompositeRows = (
  sections: CompositeSection[],
  row: Readonly<Record<string, unknown>>
): CompositeRow[] => {
  /** 在原始行上取值并检查成员的 show_if 条件。 */
  const resolveValues = (members: CompositeMember[]) => {
    return members.flatMap(({ field, isPrimary, key, showIf, type }) => {
      const value = row[field.name];
      const isPlaceholder = !hasFieldValue(value);
      if (isPlaceholder && !isPrimary) return [];
      const visible = showIf.every(([name, candidates]) => {
        const raw = row[name];
        const values = Array.isArray(raw) ? raw : [raw];
        return values.some(item => item !== null && item !== undefined && candidates.has(String(item)));
      });
      return visible ? [{ field, isPlaceholder, key, type, value }] : [];
    });
  };

  return sections.flatMap(({ index, items, badges, separator }) => {
    const visibleItems = resolveValues(items);
    const visibleBadges = resolveValues(badges);
    return visibleItems.length || visibleBadges.length
      ? [{ index, items: visibleItems, badges: visibleBadges, separator }]
      : [];
  });
};
