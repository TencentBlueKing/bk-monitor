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
import type { IRumCompositeItem, IRumField } from './view-config';

/** 已解析元信息和展示条件的成员定义。 */
export interface CompositeMember {
  /** 接口字段索引中的成员元信息。 */
  field: IRumField;
  /** 当前成员是否为接口指定的主字段。 */
  isPrimary: boolean;
  /** 该成员在配置中的位置标识。 */
  key: string;
  /** 由接口 show_if 预处理得到的条件字段和允许值集合，所有字段均须命中。 */
  showIf: Array<[string, Set<string>]>;
  type?: IRumCompositeItem['type'];
}

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

/** 与记录无关的复合列行布局。 */
export interface CompositeSection {
  /** 按配置顺序解析的标签成员。 */
  badges: CompositeMember[];
  /** 在原始 sections 配置中的位置。 */
  index: number;
  /** 按配置顺序解析的正文成员。 */
  items: CompositeMember[];
  /** 正文成员之间的连接符。 */
  separator: string;
}

/** 已定位到当前原始行的复合成员。 */
export interface CompositeValue {
  /** 成员自己的元信息，供展示及交互使用。 */
  field: IRumField;
  /** 主字段无值时保留该成员的位置。 */
  isPlaceholder: boolean;
  /** 由成员位置生成的键，同一字段重复出现时依然唯一。 */
  key: string;
  type?: IRumCompositeItem['type'];
  /** 原始行中该字段的值。 */
  value: unknown;
}
