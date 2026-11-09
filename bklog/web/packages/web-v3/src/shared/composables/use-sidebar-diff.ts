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

import {
  computed,
  onScopeDispose,
  ref,
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type WatchStopHandle,
} from 'vue';
import { deepEqual } from '@/shared/lib/util';
import { toWorkerMessage } from '@/shared/lib/worker-message';
import useLocale from '@/shared/composables/use-locale';
import { bkInfoBox as InfoBox } from '@/platform/compat/tdesign/info-box';

/** The getter also follows replacement of an Options API form after loading.
 * Start observing on initialization: V2 ignores all changes before this point. */
export function useSidebarDiff<Form extends object>(formData: MaybeRefOrGetter<Form>) {
  const { t } = useLocale();
  const initCloneData = shallowRef<Form | null>(null);
  const isChange = ref(false);
  const isDataInit = ref(false);
  const watchFormData = computed(() => ({ ...toValue(formData) }));
  let stopWatch: WatchStopHandle | undefined;
  onScopeDispose(() => stopWatch?.());

  function initSidebarFormData() {
    initCloneData.value = Object.fromEntries(
      Object.entries(watchFormData.value).map(([key, value]) => [key, structuredClone(toWorkerMessage(value))]),
    ) as Form;
    isDataInit.value = true;
    if (!stopWatch)
      stopWatch = watch(
        watchFormData,
        current => {
          if (!isChange.value && isDataInit.value && !deepEqual(current, initCloneData.value)) isChange.value = true;
        },
        { deep: true },
      );
  }

  function isSidebarClosed(): Promise<boolean> {
    return new Promise(resolve => {
      const confirm = () => {
        resolve(true);
        isChange.value = false;
        isDataInit.value = false;
      };
      if (isChange.value) {
        InfoBox({
          extCls: 'sideslider-close-cls',
          title: t('确认离开当前页？'),
          subTitle: t('离开将会导致未保存信息丢失'),
          okText: t('离开'),
          confirmFn: confirm,
          cancelFn: () => resolve(false),
        });
      } else confirm();
    });
  }

  async function handleCloseSidebar(): Promise<boolean> {
    return await isSidebarClosed();
  }
  return { initCloneData, isChange, isDataInit, isSidebarClosed, initSidebarFormData, handleCloseSidebar };
}
