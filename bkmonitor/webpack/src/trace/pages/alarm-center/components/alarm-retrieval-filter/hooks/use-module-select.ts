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

import type { IModuleListItem } from '../typing/typing';

export function useModuleSelect() {
  const moduleList = shallowRef<IModuleListItem[]>([
    {
      id: 'APM',
      name: 'APM',
      children: [
        {
          id: '调用分析',
          name: '调用分析',
          cascade: [
            {
              id: '应用',
              name: '应用',
            },
            {
              id: '服务',
              name: '服务',
            },
          ],
        },
        {
          id: '日志',
          name: '日志',
          cascade: [
            {
              id: '应用',
              name: '应用',
            },
            {
              id: '服务',
              name: '服务',
            },
          ],
        },
        {
          id: '事件',
          name: '事件',
          cascade: [
            {
              id: '应用',
              name: '应用',
            },
            {
              id: '服务',
              name: '服务',
            },
          ],
        },
        {
          id: '自定义指标',
          name: '自定义指标',
          cascade: [
            {
              id: '应用',
              name: '应用',
            },
            {
              id: '服务',
              name: '服务',
            },
          ],
        },
      ],
    },
    {
      id: '拨测',
      name: '拨测',
      children: [
        {
          id: 'http',
          name: 'http',
          cascade: [
            {
              id: '拨测任务',
              name: '拨测任务',
            },
          ],
        },
        {
          id: 'http1',
          name: 'http1',
          cascade: [
            {
              id: '拨测任务',
              name: '拨测任务',
            },
          ],
        },
        {
          id: 'http2',
          name: 'http2',
          cascade: [
            {
              id: '拨测任务',
              name: '拨测任务',
            },
          ],
        },
        {
          id: 'http3',
          name: 'http3',
          cascade: [
            {
              id: '拨测任务',
              name: '拨测任务',
            },
          ],
        },
      ],
    },
    {
      id: '自定义指标',
      name: '自定义指标',
      children: [
        {
          id: '自定义指标',
          name: '自定义指标',
        },
        {
          id: '自定义指标1',
          name: '自定义指标1',
        },
      ],
    },
    {
      id: '云产品',
      name: '云产品',
      children: [
        {
          id: 'CLB',
          name: 'CLB',
        },
        {
          id: 'mysql',
          name: 'mysql',
        },
        {
          id: 'tdmq',
          name: 'tdmq',
        },
      ],
    },
    {
      id: 'APM1',
      name: 'APM1',
      children: [
        {
          id: '调用分析1',
          name: '调用分析1',
        },
        {
          id: '日志1',
          name: '日志1',
        },
        {
          id: '事件1',
          name: '事件1',
        },
        {
          id: '自定义指标1',
          name: '自定义指标1',
        },
      ],
    },
  ]);
  const searchValue = shallowRef('');
  const searchModuleList = computed(() => {
    if (!searchValue.value) {
      return moduleList.value;
    }
    return moduleList.value.filter(module => {
      const moduleNameLower = module.name.toLowerCase();
      const moduleIdLower = module.id.toLowerCase();
      const searchValueLower = searchValue.value.toLowerCase();
      const childList = module.children.filter(item => {
        const itemNameLower = item.name.toLowerCase();
        const itemIdLower = item.id.toLowerCase();
        return itemNameLower.includes(searchValueLower) || itemIdLower.includes(searchValueLower);
      });
      return (
        childList.length > 0 || moduleNameLower.includes(searchValueLower) || moduleIdLower.includes(searchValueLower)
      );
    });
  });

  return {
    moduleList,
    searchModuleList,
    searchValue,
  };
}
