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
import { type Ref, shallowRef, watch } from 'vue';

import { getCascadeValueSplit } from 'trace/components/retrieval-filter/utils';

import { HOST_FILTER_FIELDS_ENUM } from '../constants/constants';

export const useHostListFilter = (options: { filterOptionsMap: Ref<null | object> }) => {
  const { filterOptionsMap } = options;
  /** 集群模块字段 id -> name 映射表，用于将级联值路径（每一级 id）还原为可读名称 */
  const clusterModuleOptionsMap = shallowRef(new Map());
  /** 过滤选项刷新计数器，递增时触发 RetrievalFilter 组件强制重渲染（解决级联数据更新后 UI 不刷新问题） */
  const refreshKey = shallowRef(0);

  /** 递归遍历集群模块选项树，构建 id -> name 映射 */
  const setClusterModuleOptionsMap = option => {
    if (option.id && option.name) {
      clusterModuleOptionsMap.value.set(option.id, option.name);
    }
    if (option?.children?.length) {
      for (const item of option.children) {
        setClusterModuleOptionsMap(item);
      }
    }
  };
  // filterOptionsMap 变化时，提取 cluster_module 字段的选项树，构建 id -> name 映射
  watch(
    () => filterOptionsMap.value,
    () => {
      if (filterOptionsMap.value) {
        for (const key in filterOptionsMap.value) {
          if (key === HOST_FILTER_FIELDS_ENUM.clusterModule) {
            for (const item of filterOptionsMap.value[key]) {
              setClusterModuleOptionsMap(item);
            }
            refreshKey.value += 1;
            break;
          }
        }
      }
    },
    {
      immediate: true,
    }
  );

  /**
   * 主机列表已选条件 tag 的 value 展示格式化：
   * - 百分比类字段（CPU/内存/磁盘/IO 等）追加 `%`
   * - 集群模块字段：将级联值（按 / 拆分的 id 路径）还原为可读名称，以 / 拼接
   * @param isTips 是否为悬浮提示（tips）场景，集群模块在 tips 中直接展示原始值
   */
  const tagValueDisplayFormatter = (val, { value, key, isTips }) => {
    if (
      [
        HOST_FILTER_FIELDS_ENUM.cpuLoad,
        HOST_FILTER_FIELDS_ENUM.cpuUsage,
        HOST_FILTER_FIELDS_ENUM.diskInUse,
        HOST_FILTER_FIELDS_ENUM.ioUtil,
        HOST_FILTER_FIELDS_ENUM.memUsage,
        HOST_FILTER_FIELDS_ENUM.pscMemUsage,
      ].includes(key)
    ) {
      return `${val}%`;
    }
    if ([HOST_FILTER_FIELDS_ENUM.clusterModule].includes(key)) {
      // tips 悬浮提示场景直接展示原始值；tag 展示则还原为可读名称路径
      if (isTips) {
        return val;
      }
      const valArr = getCascadeValueSplit(value.id);
      const valStr = valArr.map(item => clusterModuleOptionsMap.value.get(item) || item).join('/');
      return valStr;
    }
    return val;
  };
  return {
    refreshKey,
    tagValueDisplayFormatter,
  };
};
