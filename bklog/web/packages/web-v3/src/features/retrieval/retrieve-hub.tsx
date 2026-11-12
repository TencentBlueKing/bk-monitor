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
import { defineAsyncComponent, defineComponent } from 'vue';

import { useRoute } from 'vue-router';

import UnAuthorized from '@/features/authorization/denied/index';
import RetrieveV3 from '@/features/retrieval/workspace/index';
const RetrieveV1 = defineAsyncComponent(
  () => import(/* webpackChunkName: 'logRetrieve-v1' */ '@/features/retrieval/classic/container'),
);

export default defineComponent({
  name: 'RetrieveHub',
  components: {
    'retrieve-v1': RetrieveV1,
    'retrieve-v3': RetrieveV3,
  },
  setup() {
    const route = useRoute();
    const store = useApplicationStore();
    const version = localStorage.getItem('retrieve_version') ?? 'v3';

    return () => {
      // 恢复空间前不挂载检索页，避免初始化请求及 URL 适配丢失原始索引信息。
      if (store.spaceResolveFailed) {
        return <UnAuthorized type='space' />;
      }

      if (route.name === 'retrieve') {
        if (version === 'v1') {
          return <retrieve-v1></retrieve-v1>;
        }
      }

      return <retrieve-v3></retrieve-v3>;
    };
  },
});
