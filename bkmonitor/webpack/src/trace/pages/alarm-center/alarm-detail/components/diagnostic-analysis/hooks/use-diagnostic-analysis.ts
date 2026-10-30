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
import { computed, shallowRef, watch } from 'vue';

import { MessageStatus } from '@blueking/chat-x';
import { fetchAiSetting } from 'monitor-api/modules/aiops';
import { getBizRouteHref } from 'monitor-common/utils';
import { storeToRefs } from 'pinia';

import { createAlertListPreviewMessages } from '../mock/alert-list-message';
import { createEventRecordsPreviewMessages } from '../mock/event-records-message';
import { createLogRecordsPreviewMessages } from '../mock/log-records-message';
import { createMetricSeriesPreviewMessages } from '../mock/metric-series-message';
import { createDiagnosticPanelState } from '../model';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { DiagnosticStatusType } from '../components/diagnostic-status';
import type { DiagnosticPanelState } from '../model';

/** `useDiagnosticAnalysis` 的返回值类型，供消费方（如 `diagnostic-analysis.tsx`）显式引用 */
export type UseDiagnosticAnalysisReturn = ReturnType<typeof useDiagnosticAnalysis>;

/**
 * 会话服务接入前的预览面板状态：用本地 mock 消息铺满各类结果卡片
 * （指标趋势 / 告警列表 / 日志聚类 / 事件记录），用于在无后端会话时也能完整展示面板 UI。
 */
const createPreviewPanelState = (): DiagnosticPanelState => ({
  ...createDiagnosticPanelState(),
  messages: [
    ...createMetricSeriesPreviewMessages(),
    ...createAlertListPreviewMessages(),
    ...createLogRecordsPreviewMessages(),
    ...createEventRecordsPreviewMessages(),
  ],
});

/** 在新标签页打开外部链接，空地址直接忽略 */
const openExternalLink = (url?: string) => {
  if (!url) return;
  window.open(url, '_blank', 'noopener,noreferrer');
};

/**
 * 告警详情「AI 诊断」面板的逻辑控制器。
 *
 * 当前阶段尚未接入真实会话服务，因此：
 * - 面板消息为本地 mock（见 `createPreviewPanelState`）；
 * - 输入框处于禁用态（`messageStatus: Disabled`），仅支持编辑草稿。
 */
export function useDiagnosticAnalysis() {
  const { alarmId, bizId, detail } = storeToRefs(useAlarmCenterDetailStore());
  // 以「业务 ID + 告警 ID」作为面板上下文标识，用于在切换告警时重置面板
  const contextKey = computed(() => `${bizId.value}:${alarmId.value}`);
  // 面板状态：草稿内容 + 消息列表
  const panelState = shallowRef(createPreviewPanelState());
  // AI 诊断配置状态（未配置 / 已配置 / 诊断中 等），默认未配置
  const diagnosisStatus = shallowRef<DiagnosticStatusType>('unconfigured');
  // 「联系管理员」跳转的企微客服链接，来自业务 AI 设置
  const wxCsLink = shallowRef('');

  // 拉取业务级 AI 设置中的企微客服链接，缺少业务 ID 或请求失败时置空
  const loadWxCsLink = async () => {
    const bkBizId = detail.value?.bk_biz_id ?? bizId.value;
    if (!bkBizId) {
      wxCsLink.value = '';
      return;
    }
    const res = await fetchAiSetting({ bk_biz_id: bkBizId }).catch(() => ({ wx_cs_link: '' }));
    wxCsLink.value = res?.wx_cs_link ?? '';
  };

  // 前往该告警所属策略的配置页，无策略 ID 时不跳转
  const handleConfigure = () => {
    const strategyId = detail.value?.strategy_id;
    if (!strategyId) return;
    openExternalLink(getBizRouteHref(`/strategy-config/edit/${strategyId}`, detail.value?.bk_biz_id ?? bizId.value));
  };

  // 打开企微客服链接联系管理员
  const handleContactAdmin = () => {
    openExternalLink(wxCsLink.value);
  };

  // 切换告警时重置面板内容与诊断状态
  watch(contextKey, () => {
    panelState.value = createPreviewPanelState();
    diagnosisStatus.value = 'unconfigured';
  });

  // 上下文或业务 ID 变化时重新拉取企微客服链接
  watch([contextKey, () => detail.value?.bk_biz_id], loadWxCsLink, { immediate: true });

  // 仅更新草稿内容，保持消息列表不变
  const handleDraftChange = (draft: DiagnosticPanelState['draft']) => {
    panelState.value = { ...panelState.value, draft };
  };

  return {
    contextKey,
    diagnosisStatus,
    panelState,
    // 会话服务接入前，仅允许编辑草稿，不触发发送。
    messageStatus: MessageStatus.Disabled,
    handleConfigure,
    handleContactAdmin,
    handleDraftChange,
  };
}
