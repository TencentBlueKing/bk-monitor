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

import type { VNode } from 'vue';

import KeyValueList from '../components/detail-sections/key-value-list';
import RatingBar from '../components/detail-sections/rating-bar';
import SummaryCards from '../components/detail-sections/summary-cards';
import WaterfallChart from '../components/detail-sections/waterfall-chart';
import { RumSectionTypeEnum } from '../typings';

import type { IRumDetailSectionVM, RumSectionType } from '../typings';

/** 区块渲染器：把归一化后的区块视图模型渲染成对应的展示形态 */
type IRumSectionRenderer = (section: IRumDetailSectionVM) => null | VNode;

/**
 * 区块展示类型 -> 渲染组件。
 * 后端新增 sections[].type 时，只需在 RumSectionTypeEnum 加枚举并在这里注册渲染器。
 */
const SECTION_RENDERERS: Partial<Record<RumSectionType, IRumSectionRenderer>> = {
  [RumSectionTypeEnum.SUMMARY_CARDS]: section => <SummaryCards rows={section.cardRows || []} />,
  [RumSectionTypeEnum.WATERFALL]: section => (
    <WaterfallChart
      data={section.waterfall || null}
      spanType={section?.spanType || null}
    />
  ),
  [RumSectionTypeEnum.RATING_BAR]: section => <RatingBar data={section.ratingBar || null} />,
  [RumSectionTypeEnum.KEY_VALUE_LIST]: section => <KeyValueList items={section.keyValues || []} />,
};

/** @description 取区块的渲染器，未注册的展示类型直接跳过渲染而不是报错 */
export function renderSection(section: IRumDetailSectionVM): null | VNode {
  return SECTION_RENDERERS[section.type]?.(section) ?? null;
}
