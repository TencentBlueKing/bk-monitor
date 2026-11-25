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
import { onScopeDispose, shallowRef } from 'vue';

import { Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { checkHostPluginVersion } from '../services/collection';
import { collectionTarget, summarizeInvalidHosts } from '../utils/collection';

import type { CollectionHost, InvalidHostGroup } from '../types/collection';

/** 等这么久才给跳过入口：避免它被顺手点掉，也保证用户点到时是真的「不想等了」 */
const SKIP_REVEAL_DELAY = 1000;

/** 校验结论：accept 保留这批主机，reselect 需要重新选择，stale 表示结果已过期不再适用 */
type CheckDecision = 'accept' | 'reselect' | 'stale';

/**
 * @description 目标主机的采集器版本校验：只提示不拦截，接口异常也不阻断选择流程
 * 校验过程接管主机字段并隐藏其他入口，不通过时才弹窗让用户决策
 * @param bizId 业务 ID
 * @param signal 表单销毁时中止请求
 */
export const useHostPluginCheck = (bizId: number, signal: AbortSignal) => {
  const { t } = useI18n();
  /** 校验不通过时的告警弹窗，仅在需要用户决策时展示 */
  const dialogShow = shallowRef(false);
  /** 校验不通过的主机分组，非空表示进入告警态 */
  const groups = shallowRef<InvalidHostGroup[]>([]);
  /** 是否有在途校验：决定主机字段是否被加载态接管、提交是否可用 */
  const verifying = shallowRef(false);
  /** 是否提供跳过入口：等待较久才出现，避免正常校验也被引导跳过 */
  const skipable = shallowRef(false);
  // 连续确认时只采纳最后一次结果，避免旧请求的结果覆盖新一轮选择
  let latestToken = 0;
  // 结果态等待用户选择时的 resolve 回调，由 settle 调用以结束挂起
  let resolveDecision: ((decision: CheckDecision) => void) | undefined;
  // 在途校验请求的控制器，供跳过校验中止
  let checkController: AbortController | undefined;
  // 跳过入口的定时器，校验结束时清理
  let skipTimer: ReturnType<typeof setTimeout> | undefined;

  /**
   * @description 清理跳过入口的定时器
   * @returns 无
   */
  const clearSkipTimer = () => {
    if (skipTimer) clearTimeout(skipTimer);
    skipTimer = undefined;
  };

  /**
   * @description 关闭弹窗并给出校验结论
   * @param decision 本轮校验的结论
   * @returns 传入的结论，便于在判定分支里直接返回
   */
  const finish = (decision: CheckDecision) => {
    dialogShow.value = false;
    return decision;
  };

  /**
   * @description 结束等待用户选择，并关闭弹窗
   * @param decision 用户的决定，accept 保留主机，reselect 重新选择
   * @returns 无
   */
  const settle = (decision: CheckDecision) => {
    const resolve = resolveDecision;
    resolveDecision = undefined;
    dialogShow.value = false;
    resolve?.(decision);
  };

  /**
   * @description 作废上一轮挂起的用户决策：旧结论不再适用，弹窗交由最新一轮校验管理
   * @returns 无
   */
  const abandon = () => {
    const resolve = resolveDecision;
    resolveDecision = undefined;
    resolve?.('stale');
  };

  /**
   * @description 校验已选主机的采集器版本，主机为空时直接放行
   * @param hosts 本次确认的主机列表
   * @returns 校验结论：accept 保留这批主机，reselect 需要重新选择，stale 表示结果已过期
   */
  const verify = async (hosts: CollectionHost[]): Promise<CheckDecision> => {
    const token = ++latestToken;
    // 新一轮开始：先作废上一轮挂起的用户决策，再中止上一轮在途请求，避免旧结论写回表单
    // 空主机同样要作废上一轮，否则旧轮返回的告警会落在这批已清空的选择上
    abandon();
    checkController?.abort();
    clearSkipTimer();
    groups.value = [];
    dialogShow.value = false;
    skipable.value = false;
    // 主机为空时无需校验，直接放行；接管状态要立刻还原，不能停在加载态
    if (!hosts.length) {
      verifying.value = false;
      return 'accept';
    }
    verifying.value = true;
    // 校验请求单独持有控制器，跳过校验只中止本次校验，不影响表单内的其他请求
    const current = new AbortController();
    const abortCheck = () => current.abort();
    signal.addEventListener('abort', abortCheck);
    checkController = current;
    // 等得够久才给跳过入口，正常校验期间不提供，避免被顺手点掉
    skipTimer = setTimeout(() => {
      if (token === latestToken) skipable.value = true;
    }, SKIP_REVEAL_DELAY);
    try {
      const result = await checkHostPluginVersion(bizId, collectionTarget(hosts), current.signal);
      // 主机已经再次变更，当前结果不再适用；弹窗归最新一次校验管理，这里不关闭
      if (token !== latestToken) return 'stale';
      // 用户跳过校验或表单已销毁：不展示告警，直接放行已选主机
      if (current.signal.aborted || signal.aborted) return finish('accept');
      const invalidGroups = summarizeInvalidHosts(result);
      // 校验通过或返回结构异常（无失效主机明细）时直接放行
      if (result.result || !invalidGroups.length) return finish('accept');
      groups.value = invalidGroups;
      dialogShow.value = true;
      return new Promise<CheckDecision>(resolve => {
        resolveDecision = resolve;
      });
    } catch {
      // 旧请求失败不影响最新一次校验，静默丢弃
      if (token !== latestToken) return 'stale';
      // 用户跳过校验或表单已销毁：不提示错误，直接放行已选主机
      if (current.signal.aborted) return finish('accept');
      Message({ theme: 'error', message: t('版本校验失败，请稍后重试') });
      return finish('accept');
    } finally {
      signal.removeEventListener('abort', abortCheck);
      if (checkController === current) checkController = undefined;
      // 只清理最新一轮：旧轮结束得更晚时不能清掉新一轮的定时器与标记
      if (token === latestToken) {
        clearSkipTimer();
        verifying.value = false;
        skipable.value = false;
      }
    }
  };

  /**
   * @description 跳过校验：中止本次校验并直接采用已选主机，校验只提示不拦截
   * @returns 无
   */
  const skip = () => {
    checkController?.abort();
  };

  // 表单销毁时清理定时器并结束等待，避免调用方一直挂起
  onScopeDispose(() => {
    clearSkipTimer();
    settle('accept');
  });

  return {
    dialogShow,
    groups,
    verifying,
    skipable,
    verify,
    skip,
    handleContinue: () => settle('accept'),
    handleReselect: () => settle('reselect'),
  };
};
