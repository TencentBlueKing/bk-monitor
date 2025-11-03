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

import { defineComponent, ref, computed, watch, onMounted } from 'vue';

import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';

import './index.scss';

export default defineComponent({
  name: 'Extract',
  setup() {
    const store = useStore();
    const router = useRouter();
    const route = useRoute();

    const isRender = ref(true);
    const isLoading = ref(false);

    const bkBizId = computed(() => store.state.bkBizId);

    watch(bkBizId, () => {
      isLoading.value = true;
      isRender.value = false;
      setTimeout(() => {
        isRender.value = true;
        isLoading.value = false;
      }, 400);
    });

    onMounted(() => {
      const newBkBizId = store.state.bkBizId;
      const spaceUid = store.state.spaceUid;

      router.replace({
        query: {
          bizId: newBkBizId,
          spaceUid,
          ...route.query,
        },
      });
    });

    return () => (
      <div
        class='log-extract-container'
        v-bkloading={{ isLoading: isLoading.value }}
      >
        <router-view />
      </div>
    );
  },
});
