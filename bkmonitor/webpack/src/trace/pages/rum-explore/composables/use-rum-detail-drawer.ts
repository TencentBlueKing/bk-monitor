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
import { type MaybeRef, computed, shallowRef } from 'vue';

import { get } from '@vueuse/core';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import {
  RUM_DETAIL_SPAN_TYPES,
  RUM_RECORD_ID_FIELD_MAP,
  RumModeEnum,
  SESSION_ID_FIELD,
  SPAN_TYPE_FIELD,
} from '../constants';

import type { TimeRangeType } from '../../../components/time-range/utils';
import type { IRumDetailContext } from '../detail/typings';
import type { IRumSpanRecord, RumModeType } from '../typings';
import type { LocationQuery } from 'vue-router';

interface RumDetailDrawerOptions {
  /** 当前检索的 RUM 应用名。 */
  appName: MaybeRef<string>;
  /** 进入页面时的路由参数，供初始化完成后恢复详情。 */
  initialQuery: LocationQuery;
  /** 表格当前的检索视角。 */
  mode: MaybeRef<RumModeType>;
  /** 当前已加载的表格记录，供高亮回退和记录导航使用。 */
  rows: MaybeRef<IRumSpanRecord[]>;
  /** 记录缺少时间戳时使用的检索时间范围。 */
  timeRange: MaybeRef<TimeRangeType>;
  /** 页内打开或切换记录后通知页面协调来源行高亮和 Events 抽屉。 */
  onOpen: (rowKey: string) => void;
  /** 通过页面现有的查询同步逻辑更新详情 URL。 */
  setUrlParams: (params: Record<string, string>) => void;
}

interface RumDetailDrawerState {
  /** 传给详情组件的取数上下文。 */
  context: IRumDetailContext;
  /** 打开详情时的来源行标识，旧链接可能缺失。 */
  detailRowKey?: string;
  /** 是否按当前结果列表切换上一条和下一条。 */
  showRecordNavigation: boolean;
}

type RumDetailUrlContext = {
  /** URL 保存的来源行标识。 */
  detailRowKey?: string;
  /** 旧关联 Session 链接保存的来源行标识，解码时兼容。 */
  sessionSourceRowKey?: string;
  /** URL 保存的记录导航开关。 */
  showRecordNavigation?: boolean;
} & IRumDetailContext;

/**
 * @description 管理 RUM 行详情的打开、关闭、记录导航与 URL 恢复。
 * @param {RumDetailDrawerOptions} options 查询上下文、结果列表及页面联动回调
 * @returns 详情组件状态、来源行和侧弹操作
 */
export function useRumDetailDrawer(options: RumDetailDrawerOptions) {
  // 查询初始化会重写 URL，恢复时使用进入页面时保存的参数。
  const { detailContext: initialDetailContext, detailShow: initialDetailShow } = options.initialQuery;
  /** 当前已打开的详情，空值统一表示关闭。 */
  const detail = shallowRef<null | RumDetailDrawerState>(null);
  /** 详情组件取数所需的业务上下文。 */
  const context = computed(() => detail.value?.context ?? null);
  /** 侧弹显隐由当前详情状态派生。 */
  const isShow = computed(() => detail.value !== null);
  /** 会话入口和会话 Span 都使用 Session 层级。 */
  const mode = computed<RumModeType>(() =>
    context.value?.span_type === RumModeEnum.SESSION ? RumModeEnum.SESSION : get(options.mode)
  );
  /** 当前详情的记录导航能力，与来源行标识独立。 */
  const showRecordNavigation = computed(() => detail.value?.showRecordNavigation ?? true);
  /** 恢复来源行高亮，旧普通详情链接按记录 ID 反查。 */
  const detailRowKey = computed(() => {
    const current = detail.value;
    if (!current) return '';
    if (current.detailRowKey !== undefined) return current.detailRowKey;
    if (!current.context.record_id) return '';
    const tableMode = get(options.mode);
    const row = get(options.rows).find(item => getDetailRecordId(item, tableMode) === current.context.record_id);
    return getTableRowKey(row, tableMode);
  });

  /**
   * @description 按现有 URL 格式序列化详情，并分别保存来源行和记录导航开关。
   * @returns {void}
   */
  function syncDetailQuery() {
    const current = detail.value;
    const urlContext = current && {
      ...current.context,
      detailRowKey: current.detailRowKey,
      showRecordNavigation: current.showRecordNavigation,
    };
    options.setUrlParams({
      detailShow: String(isShow.value),
      detailContext: encodeURIComponent(JSON.stringify(urlContext)),
    });
  }

  /**
   * @description 原地打开行详情。关联 Session 使用目标会话 ID 取数并关闭列表记录导航。
   * @param {IRumSpanRecord} row 当前检索结果中的来源行
   * @param {string} [relatedSessionId] 从关联 Session 入口传入的会话 ID
   * @returns {void}
   */
  function handleOpenDetail(row: IRumSpanRecord, relatedSessionId?: string) {
    const tableMode = get(options.mode);
    const isRelatedSession = relatedSessionId !== undefined;
    const isSession = isRelatedSession || tableMode === RumModeEnum.SESSION;
    const rowKey = getTableRowKey(row, tableMode);
    const [queryStart, queryEnd] = handleTransformToTimestamp(get(options.timeRange));
    const startSeconds = microToUnixSeconds(row?.start_time);
    // View 和 Session 记录可能缺少结束时间，优先回落到同一行的开始时间。
    const endSeconds = microToUnixSeconds(row?.end_time) ?? startSeconds;
    detail.value = {
      context: {
        app_name: get(options.appName),
        record_id: relatedSessionId ?? getDetailRecordId(row, tableMode),
        span_type: isSession
          ? RumModeEnum.SESSION
          : tableMode === RumModeEnum.VIEW
            ? RumModeEnum.VIEW
            : String(row?.[SPAN_TYPE_FIELD] ?? ''),
        start_time: startSeconds ?? queryStart,
        end_time: endSeconds ?? queryEnd,
      },
      detailRowKey: rowKey,
      showRecordNavigation: !isRelatedSession,
    };
    options.onOpen(rowKey);
    syncDetailQuery();
  }

  /**
   * @description 侧弹关闭时清理详情状态并同步 URL。
   * @param {boolean} show 侧弹组件回传的显隐状态
   * @returns {void}
   */
  function handleShowChange(show: boolean) {
    if (show || !detail.value) return;
    detail.value = null;
    syncDetailQuery();
  }

  /**
   * @description 按当前检索结果循环查找相邻的可展示详情记录。
   * @param {-1 | 1} step -1 向前查找，1 向后查找
   * @returns {void}
   */
  function handleStepDetail(step: -1 | 1) {
    const current = detail.value;
    const rows = get(options.rows);
    if (!current?.showRecordNavigation || !rows.length) return;

    const tableMode = get(options.mode);
    const currentIndex = Math.max(
      0,
      rows.findIndex(row => getDetailRecordId(row, tableMode) === current.context.record_id)
    );
    const canOpenEveryRow = tableMode === RumModeEnum.VIEW || tableMode === RumModeEnum.SESSION;
    for (let offset = 1; offset < rows.length; offset++) {
      const index = (currentIndex + step * offset + rows.length) % rows.length;
      const row = rows[index];
      if (canOpenEveryRow || RUM_DETAIL_SPAN_TYPES.has(row[SPAN_TYPE_FIELD] ?? '')) {
        handleOpenDetail(row);
        return;
      }
    }
  }

  /**
   * @description 切换到上一条可展示的记录。
   * @returns {void}
   */
  const handlePreviousDetail = () => handleStepDetail(-1);

  /**
   * @description 切换到下一条可展示的记录。
   * @returns {void}
   */
  const handleNextDetail = () => handleStepDetail(1);

  /**
   * @description 恢复进入页面时的详情，兼容旧普通链接和旧关联 Session 链接。
   * @returns {void}
   */
  function restoreDetail() {
    if (initialDetailShow !== 'true' || typeof initialDetailContext !== 'string') return;
    try {
      const {
        detailRowKey: savedRowKey,
        sessionSourceRowKey,
        showRecordNavigation: savedNavigation,
        ...savedContext
      } = JSON.parse(decodeURIComponent(initialDetailContext)) as RumDetailUrlContext;
      if (typeof savedContext.app_name !== 'string' || typeof savedContext.record_id !== 'string') return;
      const legacyRowKey = typeof sessionSourceRowKey === 'string' ? sessionSourceRowKey : undefined;
      detail.value = {
        context: savedContext,
        detailRowKey: typeof savedRowKey === 'string' ? savedRowKey : legacyRowKey,
        showRecordNavigation: typeof savedNavigation === 'boolean' ? savedNavigation : legacyRowKey === undefined,
      };
    } catch {
      // 无法解码的详情参数跳过恢复，检索页照常打开。
    }
  }

  return {
    context,
    detailRowKey,
    isShow,
    mode,
    showRecordNavigation,
    handleNextDetail,
    handleOpenDetail,
    handlePreviousDetail,
    handleShowChange,
    restoreDetail,
  };
}

/**
 * @description 读取行自身的详情记录 ID，会话 Span 使用会话详情与时间轴共用的会话 ID。
 * @param {IRumSpanRecord} row 表格记录
 * @param {RumModeType} mode 当前检索视角
 * @returns {string} 详情接口使用的记录 ID
 */
function getDetailRecordId(row: IRumSpanRecord, mode: RumModeType) {
  const isSessionSpan = mode === RumModeEnum.SPAN && row?.[SPAN_TYPE_FIELD] === RumModeEnum.SESSION;
  return isSessionSpan ? String(row?.[SESSION_ID_FIELD] ?? '') : getTableRowKey(row, mode);
}

/**
 * @description 读取当前检索视角下的表格行标识。
 * @param {IRumSpanRecord | undefined} row 来源行
 * @param {RumModeType} mode 当前检索视角
 * @returns {string} 行标识，缺失时返回空串
 */
function getTableRowKey(row: IRumSpanRecord | undefined, mode: RumModeType) {
  return String(row?.[RUM_RECORD_ID_FIELD_MAP[mode]] ?? '');
}

/**
 * @description 将行内微秒级时间戳转换成秒。
 * @param {unknown} value 行内原始时间戳
 * @returns {number | null} 秒级时间戳，缺失或无效时返回 null
 */
function microToUnixSeconds(value: unknown): null | number {
  const num = Number(value);
  return Number.isFinite(num) && num > 0 ? Math.floor(num / 1000000) : null;
}
