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
import { Button as TButton } from 'tdesign-vue-next';
import { defineComponent } from 'vue';


import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
import { useRoute, useRouter } from 'vue-router';

export default defineComponent({
  setup() {
    const store = useApplicationStore();
    const route = useRoute();
    const router = useRouter();

    const getQueryString = () => {
      return Object.keys(route.query ?? {}).reduce((str, key) => {
        return str.length > 0 ? `${str}&${key}=${route.query[key]}` : `${key}=${route.query[key]}`;
      }, '');
    };

    const handleBtnClick = (isNewTarget = true) => {
      if (isNewTarget) {
        const target = `${window.MONITOR_URL}/?bizId=${store.storage[BK_LOG_STORAGE.BK_BIZ_ID]}#/grafana?${getQueryString()}`;
        window.open(target, '_blank', 'noopener,noreferrer');
        return;
      }

      router.push({
        name: 'default-dashboard',
        query: {
          spaceUid: store.storage[BK_LOG_STORAGE.BK_SPACE_UID],
          ...(route.query ?? {}),
        },
      });
    };

    return () => (
      <div style='display: flex; justify-content: center; align-items: center; height: 100%;font-size: 18px;'>
        <div>
          已迁移监控平台仪表盘
          <span style='padding: 0 8px;'></span>
          <TButton
            theme='primary'
            onClick={() => handleBtnClick()}
          >
            点击跳转新版
          </TButton>
          <span style='padding: 0 8px;'></span>
          <TButton

            onClick={() => handleBtnClick(false)} variant={(true) ? 'outline' : 'base'}
          >
            查看旧版
          </TButton>
        </div>
      </div>
    );
  },
});
