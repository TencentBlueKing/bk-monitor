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

import { getBizRouteHref } from 'monitor-common/utils';

import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

/**
 * AI 诊断里余下的跳转一律新开页，不与左侧告警详情联动。
 * 指标趋势 / 告警列表 / 日志聚类 / 事件列表改为在会话里回显，见 chat/chat-result-card.tsx。
 * 面板内的明细改为 hover「添加至聊天」，见 use-hover-to-chat.ts。
 */

/**
 * 跳转策略配置详情页（查看态）。
 * 路由 `/strategy-config/detail/:id`，与告警表策略名跳转一致。
 */
export function openStrategyDetail(strategyId: number | string) {
  if (strategyId === undefined || strategyId === null || strategyId === '') return;
  const store = useAlarmCenterDetailStore();
  const bizId = store.alarmDetail?.bk_biz_id || store.bizId || window.cc_biz_id;
  window.open(getBizRouteHref(`/strategy-config/detail/${strategyId}`, bizId), '_blank');
}
