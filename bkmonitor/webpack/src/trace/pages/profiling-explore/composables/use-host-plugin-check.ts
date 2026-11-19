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

import type { CollectionHost, InvalidHostGroup, PluginVersionCheckResult } from '../types/collection';

/** 校验弹窗最短展示时长，避免校验过快时弹窗一闪而过 */
const DIALOG_MIN_DURATION = 250;

/**
 * @description 目标主机的采集器版本校验：只提示不拦截，接口异常也不阻断选择流程
 * @param bizId 业务 ID
 * @param signal 表单销毁时中止请求
 */
export function useHostPluginCheck(bizId: number, signal: AbortSignal) {
  const { t } = useI18n();
  /** 校验弹窗是否展示 */
  const dialogShow = shallowRef(false);
  /** 校验不通过的主机，为空时弹窗展示加载态 */
  const groups = shallowRef<InvalidHostGroup[]>([]);
  // 连续确认时只采纳最后一次结果，避免旧请求的结果覆盖新一轮选择
  let latestToken = 0;
  // 结果态等待用户选择时的 resolve 回调，由 settle 调用以结束挂起
  let resolveDecision: ((accepted: boolean) => void) | undefined;
  // 在途校验请求的控制器，供加载态主动停止校验
  let checkController: AbortController | undefined;

  /**
   * @description 关闭弹窗并给出校验结论
   * @param accepted 是否保留这批主机
   * @returns 传入的结论，便于在判定分支里直接返回
   */
  function finish(accepted: boolean) {
    dialogShow.value = false;
    return accepted;
  }

  /**
   * @description 结束等待用户选择，并关闭弹窗
   * @param accepted 用户是否选择继续采集
   * @returns 无
   */
  function settle(accepted: boolean) {
    const resolve = resolveDecision;
    resolveDecision = undefined;
    dialogShow.value = false;
    resolve?.(accepted);
  }

  /**
   * @description 请求校验结果，并与最短展示时长一起等待，避免校验过快时弹窗闪动
   * @param hosts 待校验主机
   * @param checkSignal 本次校验的中止信号
   * @returns 校验结果
   */
  async function requestCheck(hosts: CollectionHost[], checkSignal: AbortSignal): Promise<PluginVersionCheckResult> {
    const [result] = await Promise.all([
      checkHostPluginVersion(bizId, collectionTarget(hosts), checkSignal),
      new Promise(resolve => setTimeout(resolve, DIALOG_MIN_DURATION)),
    ]);
    return result;
  }

  // 表单销毁时关闭弹窗并结束等待，避免调用方一直挂起
  onScopeDispose(() => settle(true));

  /**
   * @description 校验已选主机的采集器版本，主机为空时直接放行
   * @param hosts 本次确认的主机列表
   * @returns 是否保留这批主机，false 表示需要重新选择
   */
  async function verify(hosts: CollectionHost[]): Promise<boolean> {
    if (!hosts.length) return true;
    const token = ++latestToken;
    groups.value = [];
    dialogShow.value = true;
    // 校验请求单独持有控制器，停止校验时只中止本次校验，不影响表单内的其他请求
    const current = new AbortController();
    const abortCheck = () => current.abort();
    signal.addEventListener('abort', abortCheck);
    checkController = current;
    try {
      const result = await requestCheck(hosts, current.signal);
      // 主机已经再次变更，当前结果不再适用；弹窗归最新一次校验管理，这里不关闭
      if (token !== latestToken) return true;
      // 表单已销毁，关闭弹窗并放行，避免调用方一直挂起
      if (signal.aborted) return finish(true);
      const invalidGroups = summarizeInvalidHosts(result);
      // 校验通过或返回结构异常（无失效主机明细）时直接放行
      if (result.result || !invalidGroups.length) return finish(true);
      groups.value = invalidGroups;
      return new Promise<boolean>(resolve => {
        resolveDecision = resolve;
      });
    } catch {
      // 旧请求失败不影响最新一次校验，静默丢弃
      if (token !== latestToken) return true;
      // 用户停止校验或表单已销毁：不提示错误，直接放行已选主机
      if (current.signal.aborted) return finish(true);
      Message({ theme: 'error', message: t('版本校验失败，请稍后重试') });
      return finish(true);
    } finally {
      signal.removeEventListener('abort', abortCheck);
      if (checkController === current) checkController = undefined;
    }
  }

  /**
   * @description 加载态停止校验：中止在途请求并直接采用已选主机，校验只提示不拦截
   * @returns 无
   */
  function cancel() {
    checkController?.abort();
  }

  return {
    dialogShow,
    groups,
    verify,
    cancel,
    handleContinue: () => settle(true),
    handleReselect: () => settle(false),
  };
}
