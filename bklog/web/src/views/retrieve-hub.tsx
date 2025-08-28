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
import { defineComponent } from 'vue';

import { useRoute } from 'vue-router/composables';
const RetrieveV3 = () => import(/* webpackChunkName: 'logRetrieve-v3' */ '@/views/retrieve-v3/index');
const RetrieveV1 = () => import(/* webpackChunkName: 'logRetrieve-v1' */ '@/views/retrieve/index.vue');

export default defineComponent({
  name: 'RetrieveHub',
  components: {
    'retrieve-v1': RetrieveV1,
    'retrieve-v3': RetrieveV3,
  },
  setup() {
    const route = useRoute();
    const version = localStorage.getItem('retrieve_version') ?? 'v3';

    return () => {
      if (route.name === 'retrieve') {
        if (version === 'v1') {
          return <retrieve-v1></retrieve-v1>;
        }
      }

      return <retrieve-v3></retrieve-v3>;
    };
  },
});
