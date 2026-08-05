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

import { shallowRef } from 'vue';

import { checkAllowed } from 'monitor-api/modules/iam';
import { random } from 'monitor-common/utils/utils';

import { useAuthorityStore } from '@/store/modules/authority';

const SPACE_APPLY_ACTION_IDS = [
  'view_business_v2',
  'manage_event_v2',
  'manage_downtime_v2',
  'view_event_v2',
  'view_host_v2',
  'view_rule_v2',
];

export function useSpaceSelect() {
  const allowedBizList = shallowRef([]);
  const isMultiple = shallowRef(false);
  const authorityStore = useAuthorityStore();

  /**
   * @description: 通过业务id 获取无权限申请url
   * @param {string} bizIds 业务id
   * @return {*}
   */
  async function handleCheckAllowedByIds(values?: (number | string)[]) {
    // 对齐旧版：有入参用入参；无入参时取列表中的无权限业务
    const allowedBizIdList = values?.length
      ? [...values]
      : allowedBizList.value.filter(item => item.noAuth).map(item => item.id);
    if (!allowedBizIdList?.length) return;
    const requestBizId = getAuthorizedRequestBizId();
    const resources = allowedBizIdList.map(id => ({ id: Number(id), type: 'space' }));
    const applyObj = await checkAllowed({
      action_ids: SPACE_APPLY_ACTION_IDS,
      resources,
      // 显式覆盖：当前 URL 业务无权限时不能用 cc_biz_id 发申请接口
      ...(requestBizId != null ? { bk_biz_id: requestBizId } : {}),
    }).catch(() => null);
    const applyUrl = applyObj?.apply_url || applyObj?.applyUrl;
    if (openApplyUrl(applyUrl)) return;
    // 兜底：打开权限申请弹窗（与 v-authority / AuthorityModal 一致）
    await authorityStore.getIntanceAuthDetail(SPACE_APPLY_ACTION_IDS, resources, requestBizId);
  }

  function handleChangeChoiceType(v: boolean) {
    isMultiple.value = v;
  }

  return {
    isMultiple,
    handleCheckAllowedByIds,
    handleChangeChoiceType,
  };
}

/** 取一个有权限的业务作为请求上下文，避免当前 cc_biz_id 无权限时 checkAllowed 403 */
function getAuthorizedRequestBizId(): number | undefined {
  const spaceList = window.space_list || [];
  const authorized = spaceList.find(item => !item.is_demo && item.bk_biz_id != null);
  if (authorized?.bk_biz_id != null) return +authorized.bk_biz_id;
  return undefined;
}

function openApplyUrl(url?: string) {
  if (!url) return false;
  window.open(url, random(10));
  return true;
}
