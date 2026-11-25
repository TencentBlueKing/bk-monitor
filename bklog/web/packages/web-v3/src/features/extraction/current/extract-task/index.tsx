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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { defineComponent, ref, computed, watch, onMounted } from 'vue';

import useRoute from '@/shared/composables/use-route';
import useRouter from '@/shared/composables/use-router';
import { renderDrawerInlineFormSkeleton } from '@/shared/ui/loading/drawer-skeleton';


import './index.scss';

export default defineComponent({
  name: 'Extract',
  setup() {
    const store = useApplicationStore();
    const router = useRouter();
    const route = useRoute();

    const isLoading = ref(false);

    const bkBizId = computed(() => store.bkBizId);

    watch(bkBizId, (_, __, onCleanup) => {
      isLoading.value = true;
      const timer = setTimeout(() => {
        isLoading.value = false;
      }, 400);
      onCleanup(() => clearTimeout(timer));
    });

    onMounted(() => {
      const newBkBizId = store.bkBizId;
      const spaceUid = store.spaceUid;

      router.replace({
        query: {
          bizId: newBkBizId,
          spaceUid,
          ...route.query,
        },
      });
    });

    const isFormPage = computed(() => ['extract-create', 'extract-clone'].includes(String(route.name)));

    return () => (
      <div
        class={[
          'log-extract-container',
          {
            'log-extract-create-page': isFormPage.value,
            'log-extract-list-page': route.name === 'extract-home',
          },
        ]}
        v-loading={{
          loading: isLoading.value && isFormPage.value,
          indicator: renderDrawerInlineFormSkeleton,
        }}
      >
        <router-view />
      </div>
    );
  },
});
