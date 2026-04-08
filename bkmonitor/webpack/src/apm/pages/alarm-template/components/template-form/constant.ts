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

import { AlgorithmEnum, YearRoundAndRingRatioAlgorithmEnum } from './typing';

/** 告警级别 */
export const LEVEL_LIST = [
  { id: 1, name: window.i18n.t('致命'), disabled: false, icon: 'icon-danger' },
  { id: 2, name: window.i18n.t('预警'), disabled: false, icon: 'icon-mind-fill' },
  { id: 3, name: window.i18n.t('提醒'), disabled: false, icon: 'icon-tips' },
];

/** 同级别告警连接关系 */
export const ALGORITHM_RELATIONSHIP = [
  { id: 'and', name: window.i18n.t('且') },
  { id: 'or', name: window.i18n.t('或') },
];

export const ALGORITHM_RELATIONSHIP_MAP = {
  [ALGORITHM_RELATIONSHIP[0].id]: ALGORITHM_RELATIONSHIP[0].name,
  [ALGORITHM_RELATIONSHIP[1].id]: ALGORITHM_RELATIONSHIP[1].name,
};

/** 检测算法 */
export const ALGORITHM_TYPE = [
  { id: AlgorithmEnum.Threshold, name: window.i18n.t('静态阈值') },
  { id: AlgorithmEnum.YearRoundAndRingRatio, name: window.i18n.t('同环比') },
];

/** 检测算法枚举 */
export const ALGORITHM_TYPE_MAP = {
  [AlgorithmEnum.Threshold]: window.i18n.t('静态阈值'),
  [AlgorithmEnum.YearRoundAndRingRatio]: window.i18n.t('同环比'),
};

/** 同环比检测算法 */
export const YEAR_ROUND_AND_RING_RATION_ALGORITHM = [
  { id: YearRoundAndRingRatioAlgorithmEnum.FiveMinuteRingRatio, name: window.i18n.t('前5分钟') },
  { id: YearRoundAndRingRatioAlgorithmEnum.YesterdayComparison, name: window.i18n.t('昨天同期') },
  { id: YearRoundAndRingRatioAlgorithmEnum.LastWeekComparison, name: window.i18n.t('上周同期') },
  { id: YearRoundAndRingRatioAlgorithmEnum.WeeklyAverageComparison, name: window.i18n.t('前七天同期均值') },
];

/** 同环比检测算法枚举 */
export const YEAR_ROUND_AND_RING_RATION_ALGORITHM_MAP = {
  [YearRoundAndRingRatioAlgorithmEnum.FiveMinuteRingRatio]: window.i18n.t('前5分钟'),
  [YearRoundAndRingRatioAlgorithmEnum.YesterdayComparison]: window.i18n.t('昨天同期'),
  [YearRoundAndRingRatioAlgorithmEnum.LastWeekComparison]: window.i18n.t('上周同期'),
  [YearRoundAndRingRatioAlgorithmEnum.WeeklyAverageComparison]: window.i18n.t('前七天同期均值'),
};
