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

import { defineComponent, onMounted, ref } from 'vue';

import http from '@/api/index';
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';

import './index.scss';

export default defineComponent({
  setup() {
    const router = useRouter();
    const route = useRoute();
    const store = useStore();
    const errorMessage = ref('正在解析地址, 请稍候 ...');

    const linkId = route.params.linkId as string;

    if (!linkId) {
      router.push({ name: 'retrieve' });
      return;
    }

    const getLinkParams = () => {
      errorMessage.value = '正在解析地址, 请稍候 ...';
      http
        .request('retrieve/getShareParams', { query: { token: linkId } }, { catchIsShowMessage: false })
        .then(resp => {
          debugger;
          if (resp.result) {
            const data = resp.data.data;
            const { storage, indexItem, catchFieldCustomConfig } = data.store;
            store.commit('updateStorage', storage);
            store.commit('updateIndexItem', indexItem);
            store.commit('retrieve/updateCatchFieldCustomConfig', catchFieldCustomConfig);
            router.push({ ...data.route });
            return;
          }

          errorMessage.value = resp.message || '获取分享链接参数失败，请稍后重试！';
        })
        .catch(err => {
          errorMessage.value = err.message || err || '获取分享链接参数失败，请稍后重试！';
        });
    };

    onMounted(() => {
      getLinkParams();
    });

    return () => (
      <div class='analysis-animation-container'>
        <bk-exception
          style={{
            marginTop: '10%',
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
            top: '0',
          }}
          scene='part'
          type='search-empty'
        >
          {errorMessage.value}
        </bk-exception>
      </div>
    );
  },
});
