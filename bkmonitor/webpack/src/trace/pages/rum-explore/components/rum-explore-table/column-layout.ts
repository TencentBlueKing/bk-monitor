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
import type { IRumCompositeItem, IRumField } from '../../typings';

/** 某条记录中最终可见的复合列行。 */
export interface CompositeRow {
  /** 位于正文后的可见标签。 */
  badges: CompositeValue[];
  /** 在接口配置中的行序号，用于区分主行和次行。 */
  index: number;
  /** 按配置顺序排列的可见正文成员。 */
  items: CompositeValue[];
  /** 两个可见正文成员之间的连接符。 */
  separator: string;
}

/** 已定位到当前原始行的复合成员。 */
export interface CompositeValue {
  /** 成员自己的元信息，供展示及交互使用。 */
  field: IRumField;
  /** 由成员位置生成的键，同一字段重复出现时依然唯一。 */
  key: string;
  /** 原始行中该字段的值。 */
  value: unknown;
}

/** 已解析元信息和展示条件的成员定义。 */
interface CompositeMember {
  /** 条件字段和允许值集合，所有条件字段均须命中。 */
  conditions: Array<[string, Set<string>]>;
  /** 接口字段索引中的成员元信息。 */
  field: IRumField;
  /** 该成员在配置中的位置标识。 */
  key: string;
}

/** 与记录无关的复合列行布局。 */
interface CompositeSection {
  /** 按配置顺序解析的标签成员。 */
  badges: CompositeMember[];
  /** 在原始 sections 配置中的位置。 */
  index: number;
  /** 按配置顺序解析的正文成员。 */
  items: CompositeMember[];
  /** 正文成员之间的连接符。 */
  separator: string;
}

type Row = Readonly<Record<string, unknown>>;

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
            key: `${index}:${placement}:${itemIndex}`,
            conditions: Object.entries(item.show_if ?? {}).map(([name, candidates]) => [
              name,
              new Set(Array.isArray(candidates) ? candidates.map(String) : []),
            ]),
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
export const resolveCompositeRows = (sections: CompositeSection[], row: Row): CompositeRow[] => {
  /** 在原始行上取值并检查成员的 show_if 条件。 */
  const resolveValues = (members: CompositeMember[]) => {
    return members.flatMap(({ field, key, conditions }) => {
      const value = row[field.name];
      if (!hasFieldValue(value)) return [];
      const visible = conditions.every(([name, candidates]) => {
        const raw = row[name];
        const values = Array.isArray(raw) ? raw : [raw];
        return values.some(item => item !== null && item !== undefined && candidates.has(String(item)));
      });
      return visible ? [{ field, key, value }] : [];
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
