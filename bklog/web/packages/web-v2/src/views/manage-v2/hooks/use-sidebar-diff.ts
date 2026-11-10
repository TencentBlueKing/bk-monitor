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

import { ref, computed, watch } from 'vue';

import { deepClone, deepEqual } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import { InfoBox } from 'bk-magic-vue';

export function useSidebarDiff(formData: Record<string, any>) {
  const { t } = useLocale();
  const initCloneData = ref<Record<string, any> | null>(null); // 初始化时的formData
  const isChange = ref(false);
  const isDataInit = ref(false);

  // 监听的formData对象
  const watchFormData = computed(() => ({ ...formData }));

  // 自动监听formData变更
  watch(
    watchFormData,
    newVal => {
      // 已经修改过 或 未初始化formData的值时不对比
      if (isChange.value || !isDataInit.value) {
        return;
      }
      // 对比是否进行过修改
      if (!deepEqual(newVal, initCloneData.value)) {
        isChange.value = true;
      }
    },
    { deep: true },
  );

  // 侧边栏离开,二次确认
  function isSidebarClosed(): Promise<boolean> {
    return new Promise(resolve => {
      if (isChange.value) {
        InfoBox({
          extCls: 'sideslider-close-cls',
          title: t('确认离开当前页？'),
          subTitle: t('离开将会导致未保存信息丢失'),
          okText: t('离开'),
          confirmFn() {
            resolve(true);
            isChange.value = false;
            isDataInit.value = false;
          },
          cancelFn() {
            resolve(false);
          },
        });
      } else {
        // 未编辑
        resolve(true);
        isChange.value = false;
        isDataInit.value = false;
      }
    });
  }

  // 初始化对比时的formData值
  function initSidebarFormData() {
    // 从计算属性中获取所需要对比的key列表
    initCloneData.value = Object.keys(watchFormData.value).reduce((pre: Record<string, any>, cur: string) => {
      pre[cur] = deepClone(formData[cur]);
      return pre;
    }, {});
    isDataInit.value = true;
  }

  // 是否改变过侧边弹窗的数据
  async function handleCloseSidebar(): Promise<boolean> {
    return await isSidebarClosed();
  }

  return {
    initCloneData,
    isChange,
    isDataInit,
    isSidebarClosed,
    initSidebarFormData,
    handleCloseSidebar,
  };
}
