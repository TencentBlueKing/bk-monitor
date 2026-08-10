/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { type ShallowRef, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { getHostOrTopoNodeDetail } from 'monitor-api/modules/scene_view';

import { isHostNode } from '../utils/topo-tree';

import type { IDetailItem } from '../../../components/common-detail/typing';
import type { IHostTopoTreeNode } from '../types';

/**
 * @description 监听拓扑选中节点变化（带防抖），调用接口获取主机详情数据
 */
export const useHostDetail = (selectedNode: ShallowRef<IHostTopoTreeNode | null>) => {
  /** 详情数据 */
  const detailData = shallowRef<IDetailItem[]>([]);
  /** 加载状态 */
  const loading = shallowRef(false);

  /** 获取详情数据 */
  const fetchDetail = async (node: IHostTopoTreeNode) => {
    loading.value = true;
    try {
      const data = await getHostOrTopoNodeDetail(
        isHostNode(node)
          ? {
              bk_biz_id: node.bk_biz_id,
              bk_host_id: node.bk_host_id,
            }
          : {
              bk_biz_id: node.bk_biz_id,
              bk_inst_id: node.bk_inst_id,
              bk_obj_id: node.bk_obj_id,
            }
      ).catch(() => []);
      // 处理 list 类型数据
      detailData.value =
        data.map?.((item: IDetailItem) => {
          if (item.type === 'list') {
            item.isExpand = false;
            item.isOverflow = false;
          }
          return item;
        }) || [];
    } catch {
      detailData.value = [];
    } finally {
      loading.value = false;
    }
  };

  /** 防抖后的 fetch（300ms） */
  const debouncedFetch = useDebounceFn(fetchDetail, 300);

  /** 监听选中节点变化 */
  watch(
    () => selectedNode.value,
    node => {
      if (!node) {
        detailData.value = [];
        return;
      }
      debouncedFetch(node);
    },
    { immediate: true }
  );

  /** 是否为主机节点 */
  const isHostSelected = () => !!selectedNode.value && isHostNode(selectedNode.value);

  return {
    detailData,
    loading,
    isHostSelected,
  };
};
