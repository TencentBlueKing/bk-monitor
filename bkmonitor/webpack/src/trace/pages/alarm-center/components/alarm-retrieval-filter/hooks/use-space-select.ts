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

export function useSpaceSelect() {
  const allowedBizList = shallowRef([]);
  const isMultiple = shallowRef(false);

  /**
   * @description: 通过业务id 获取无权限申请url
   * @param {string} bizIds 业务id
   * @return {*}
   */
  async function handleCheckAllowedByIds(values?: (number | string)[]) {
    let allowedBizIdList = [];
    if (!values?.length) {
      allowedBizIdList = allowedBizList.value.filter(item => item.noAuth).map(item => item.id);
    }
    if (!allowedBizIdList?.length) return;
    const applyObj = await checkAllowed({
      action_ids: [
        'view_business_v2',
        'manage_event_v2',
        'manage_downtime_v2',
        'view_event_v2',
        'view_host_v2',
        'view_rule_v2',
      ],
      resources: allowedBizIdList.map(id => ({ id, type: 'space' })),
    });
    if (applyObj?.apply_url) {
      window.open(applyObj?.apply_url, random(10));
    }
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
