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
import type { IRumActionRelated, IRumErrorRelated, IRumLongTaskRelated } from '../../typings';

/**
 * 详情页关联数据的 mock，取值参照《RUM 检索接口协议》第 3 章的响应示例与设计稿。
 * 版本关联（current / first / note）协议中暂无对应接口，先按设计稿占位。
 */

export function getMockActionRelated(): IRumActionRelated {
  return { resourceCount: 3, errorCount: 0, longTaskCount: 1 };
}

export function getMockErrorRelated(endTime: number): IRumErrorRelated {
  /** 24 个 1h 桶，末尾几桶抬升以呈现设计稿里的突增形态 */
  const bucketStart = (endTime - 24 * 3600) * 1000;
  const values = [8, 12, 8, 14, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 20, 26, 36, 42, 46, 50, 64];
  return {
    userCount: 4,
    userGrowthRate: 300,
    sessionCount: 6,
    occurrenceCount: 1234,
    trend: values.map((value, index) => ({ time: Math.floor(bucketStart / 1000) + index * 3600, value })),
    version: {
      current: 'v1.2.1',
      first: 'v1.20',
      note: window.i18n.t('上次发布版本后开始大量出现') as string,
    },
  };
}

export function getMockLongTaskRelated(): IRumLongTaskRelated {
  return { actionName: '', actionType: '' };
}
