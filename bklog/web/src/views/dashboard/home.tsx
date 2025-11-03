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

import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { useRoute, useRouter } from 'vue-router/composables';

export default defineComponent({
  setup() {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const getQueryString = () => {
      return Object.keys(route.query ?? {}).reduce((str, key) => {
        return str.length > 0 ? `${str}&${key}=${route.query[key]}` : `${key}=${route.query[key]}`;
      }, '');
    };

    const handleBtnClick = (isNewTarget = true) => {
      if (isNewTarget) {
        const target = `${window.MONITOR_URL}/?bizId=${store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID]}#/grafana?${getQueryString()}`;
        window.open(target, '_blank');
        return;
      }

      router.push({
        name: 'default-dashboard',
        query: {
          spaceUid: store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
          ...(route.query ?? {}),
        },
      });
    };

    return () => (
      <div style='display: flex; justify-content: center; align-items: center; height: 100%;font-size: 18px;'>
        <div>
          已迁移监控平台仪表盘
          <span style='padding: 0 8px;'></span>
          <bk-button
            theme='primary'
            on-click={handleBtnClick}
          >
            点击跳转新版
          </bk-button>
          <span style='padding: 0 8px;'></span>
          <bk-button
            outline={true}
            on-click={() => handleBtnClick(false)}
          >
            查看旧版
          </bk-button>
        </div>
      </div>
    );
  },
});
