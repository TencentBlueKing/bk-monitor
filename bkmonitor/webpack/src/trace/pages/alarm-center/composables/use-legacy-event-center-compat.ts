/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { computed, shallowRef } from 'vue';

import dayjs from 'dayjs';
import { checkAllowed } from 'monitor-api/modules/iam';
import { promqlToQueryConfig } from 'monitor-api/modules/strategies';
import { docCookies, LANGUAGE_COOKIE_KEY, random } from 'monitor-common/utils';
import { useRoute } from 'vue-router';

import { EMode } from '../../../components/retrieval-filter/typing';
import { AlertAllActionEnum, MY_ALARM_BIZ_ID, MY_AUTH_BIZ_ID } from '../typings/constants';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';

/**
 * 旧版（fta-solutions/pages/event）批量操作 URL 字段值 → 新版 AlertAllActionEnum 映射
 * 来源：fta-solutions/pages/event/event.tsx 中的 EBatchAction
 */
const LEGACY_BATCH_ACTION_MAP: Record<string, AlertAllActionEnum> = {
  alarmConfirm: AlertAllActionEnum.CONFIRM,
  quickShield: AlertAllActionEnum.SHIELD,
};

/**
 * @description 兼容旧版「事件中心」(fta-solutions/pages/event) 的 URL 入口逻辑
 * - 旧 URL 字段（actionId / collectId / alertId / metricId）注入 queryString
 * - PromQL 异步转换为 queryString
 * - 旧 batchAction 映射为新版 autoShowAlertAction
 * - 通过 collectId/alertId + specEvent 标记自动展开第一条详情
 * - 业务权限提示（无权限业务存在时显示申请权限横条）
 *
 * 必须在 alarm-center.tsx 的 getUrlParams() 解析完之后调用，
 * 才能在已有 queryString 基础上做 AND 拼接。
 */
export function useLegacyEventCenterCompat() {
  const route = useRoute();
  const alarmStore = useAlarmCenterStore();

  /** 是否需要自动展开第一条数据的详情 */
  const shouldAutoOpenFirstDetail = shallowRef(false);
  /** 是否显示业务权限提示横条 */
  const showPermissionTips = shallowRef(false);

  /** 旧版 batchAction（一次性映射为新版枚举） */
  const legacyBatchAction = computed<AlertAllActionEnum | undefined>(() => {
    const action = route.query?.batchAction as string | undefined;
    return action ? LEGACY_BATCH_ACTION_MAP[action] : undefined;
  });

  /**
   * @description 同步注入旧版「跳转入口字段」到 queryString，并按需修改 timeRange
   * 注意：内部直接修改 alarmStore.queryString / timeRange / filterMode
   */
  function applyLegacyQueryStringInjection() {
    const query = route.query || {};
    const actionId = query.actionId as string | undefined;
    const collectId = query.collectId as string | undefined;
    const legacyAlertId = query.alertId as string | undefined;
    const metricIds = parseMetricIdQuery(query.metricId);

    let qs = alarmStore.queryString || '';
    const append = (clause: string) => {
      qs = qs ? `${qs} AND ${clause}` : clause;
    };

    if (actionId && String(actionId).length > 10) {
      append(`action_id : ${actionId}`);
      const ts = +String(actionId).slice(0, 10) * 1000;
      alarmStore.timeRange = [
        dayjs.tz(ts).add(-30, 'd').format('YYYY-MM-DD HH:mm:ssZZ'),
        dayjs.tz(ts).format('YYYY-MM-DD HH:mm:ssZZ'),
      ];
    }

    if (collectId) {
      append(`action_id : ${collectId}`);
      alarmStore.timeRange = ['now-30d', 'now'];
    }

    /**
     * 兼容新版首页搜索：?alertId=xxx 时拼成 `id : xxx` 检索条件
     * 但需避免与新版「展开详情」语义冲突——仅当 URL 没有显式带 alarmId 时才做注入
     */
    if (legacyAlertId && !query.alarmId) {
      append(`id : ${legacyAlertId}`);
    }

    if (metricIds.length) {
      const metricClause = `metric : (${metricIds.map(v => `"${v}"`).join(' OR ')})`;
      append(metricClause);
    }

    const hasLegacyInjection = !!(
      (actionId && String(actionId).length > 10) ||
      collectId ||
      (legacyAlertId && !query.alarmId) ||
      metricIds.length
    );

    if (qs !== alarmStore.queryString) {
      alarmStore.queryString = qs;
    }
    /** 旧入口注入的都是 queryString 形式，强制切到 queryString 模式 */
    if (hasLegacyInjection) {
      alarmStore.filterMode = EMode.queryString;
    }
  }

  /** PromQL 异步转换为 queryString */
  async function applyPromqlIfNeeded() {
    const rawPromql = route.query?.promql as string | undefined;
    if (!rawPromql) return;
    const promql = parsePromqlQuery(rawPromql);
    const data = await promqlToQueryConfig({ promql }).catch(() => null);
    const configs = data?.query_configs as Array<{ metric_id?: string }> | undefined;
    if (!configs?.length) return;

    const seen = new Set<string>();
    const parts: string[] = [];
    for (const c of configs) {
      if (c.metric_id && !seen.has(c.metric_id)) {
        parts.push(`${isEn ? 'metric' : '指标ID'}: "${c.metric_id}"`);
        seen.add(c.metric_id);
      }
    }
    if (parts.length) {
      alarmStore.queryString = parts.join(' OR ');
      alarmStore.filterMode = EMode.queryString;
    }
  }

  /**
   * @description 设置「自动展开第一条数据详情」标志位
   * 旧版语义：URL 带 collectId/alertId 且 location.search 中含 specEvent 字符串
   */
  function setupAutoOpenFirstDetailFlag() {
    const hasLegacyDetailEntry = !!(route.query?.collectId || route.query?.alertId);
    const hasSpecEventFlag = location?.search?.includes('specEvent') ?? false;
    shouldAutoOpenFirstDetail.value = hasLegacyDetailEntry && hasSpecEventFlag;
  }

  /** 计算业务权限提示展示状态 */
  function computeShowPermissionTips() {
    const ids = alarmStore.bizIds || [];
    if (!ids.length) {
      showPermissionTips.value = false;
      return;
    }
    showPermissionTips.value = ids
      .filter(id => ![MY_AUTH_BIZ_ID, MY_ALARM_BIZ_ID].includes(+id))
      .some(id => !window.space_list?.some(item => +item.id === +id));
  }

  function dismissPermissionTips() {
    showPermissionTips.value = false;
  }

  /** 申请无权限业务的访问权限 */
  async function handleApplyPermission() {
    const ids = (alarmStore.bizIds || [])
      .filter(id => ![MY_AUTH_BIZ_ID, MY_ALARM_BIZ_ID].includes(+id))
      .filter(id => !window.space_list?.some(item => +item.id === +id));
    if (!ids.length) return;
    const applyObj = await checkAllowed({
      action_ids: [
        'view_business_v2',
        'manage_event_v2',
        'manage_downtime_v2',
        'view_event_v2',
        'view_host_v2',
        'view_rule_v2',
      ],
      resources: ids.map(id => ({ id, type: 'space' })),
    }).catch(() => null);
    if (applyObj?.apply_url) {
      window.open(applyObj.apply_url, random(10));
    }
  }

  return {
    legacyBatchAction,
    shouldAutoOpenFirstDetail,
    showPermissionTips,
    applyLegacyQueryStringInjection,
    applyPromqlIfNeeded,
    setupAutoOpenFirstDetailFlag,
    computeShowPermissionTips,
    dismissPermissionTips,
    handleApplyPermission,
  };
}

/** 解析 URL 中的 metricId 字段（兼容字符串、JSON 数组字符串、数组三种形式） */
function parseMetricIdQuery(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(v => String(v));
  if (typeof value !== 'string') return [String(value)];
  try {
    const parsed = JSON.parse(decodeURIComponent(value));
    if (Array.isArray(parsed)) return parsed.map(v => String(v));
    return [String(parsed)];
  } catch {
    return [value];
  }
}

/** 兼容历史链接中被 JSON.stringify 包裹过的 PromQL 参数 */
function parsePromqlQuery(value: string): string {
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === 'string' ? parsed : value;
  } catch {
    return value;
  }
}
