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

/**
 * 新建采集的自定义 Hook
 */
import { computed, ref } from 'vue';

import $http from '@/api';
// import useStore from '@/hooks/use-store';
export type CardItem = {
  key: number | string;
  title: string;
  renderFn: () => any;
};

export const useOperation = () => {
  // const store = useStore();
  // const spaceUid = computed(() => store.getters.spaceUid);
  // const bkBizId = computed(() => store.getters.bkBizId);
  const tableLoading = ref(false);
  const cardRender = (cardConfig: CardItem[]) => (
    <div class='classify-main-box'>
      {cardConfig.map(item => (
        <div
          key={item.key}
          class='info-card'
        >
          <div class='card-title'>{item.title}</div>
          {item.renderFn()}
        </div>
      ))}
    </div>
  );
  /**
   * 选择采集项获取字段列表
   * @param params
   * @param isList 是否返回list
   * @returns
   */
  const handleMultipleSelected = async (params, isList = false, callback) => {
    try {
      tableLoading.value = true;
      const res = await $http.request('/resultTables/info', params);
      const data = callback?.(res) || res.data?.fields || [];
      return isList ? res : data;
    } catch (e) {
      console.warn(e);
    } finally {
      tableLoading.value = false;
    }
  };

  return {
    tableLoading,
    // 具体的方法
    cardRender,
    handleMultipleSelected,
  };
};
