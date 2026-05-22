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

export const mockData = {
  main_issue_id: '1741234567abcd1234',
  active_members: [
    {
      member_issue_id: '1741299999eeee1111',
      member_name: '支付链路延迟飙升',
      anomaly_message: 'cpu 使用率过高',
      merge_reasons: ['影响范围不同'],
      merge_operator: 'admin',
      merge_time: 1741334000,
      status: 'active',
    },
  ],
  split_history: [
    {
      member_issue_id: '1741300000ffff2222',
      member_name: 'DB 连接池耗尽',
      anomaly_message: 'cpu 使用率过高',
      merge_reasons: ['合并原因不同', '责任 Owner 不同'],
      merge_operator: 'admin',
      merge_time: 1741334100,
      status: 'split',
      split_reasons: ['责任 Owner 不同'],
      split_operator: 'dev1',
      split_time: 1741400000,
      split_kind: 'manual',
    },
  ],
};
