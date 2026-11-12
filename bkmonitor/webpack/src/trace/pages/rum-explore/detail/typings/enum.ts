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
import type {
  RumCardToneEnum,
  RumDetailTabEnum,
  RumSectionTypeEnum,
  RumTimelineFilterCategoryEnum,
  RumTimelineSortEnum,
  RumViewLoadingTypeEnum,
} from '../constants';

/** 统计卡片主值的语义配色取值 */
export type RumCardToneType = (typeof RumCardToneEnum)[keyof typeof RumCardToneEnum];

/** 详情抽屉的 Tab 取值 */
export type RumDetailTabType = (typeof RumDetailTabEnum)[keyof typeof RumDetailTabEnum];

/** 详情区块的展示类型取值，与 record_detail 接口的 sections[].type 对齐 */
export type RumSectionType = (typeof RumSectionTypeEnum)[keyof typeof RumSectionTypeEnum];

/** 链路上下文列表的快捷筛选类别取值，口径见 timeline 接口协议 2.12.3 */
export type RumTimelineFilterCategoryType =
  (typeof RumTimelineFilterCategoryEnum)[keyof typeof RumTimelineFilterCategoryEnum];

/** 时间轴 View 卡片的排序方向取值 */
export type RumTimelineSortType = (typeof RumTimelineSortEnum)[keyof typeof RumTimelineSortEnum];

/** View 的路由类型取值，取自 view.loading_type */
export type RumViewLoadingType = (typeof RumViewLoadingTypeEnum)[keyof typeof RumViewLoadingTypeEnum];
