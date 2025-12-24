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
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';

export default defineComponent({
  name: 'UnAuthorized',
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();
    /**
     * 打开接入指引
     */
    const handleOpenGuide = () => {
      const docPath = 'markdown/ZH/LogSearch/4.7/UserGuide/QuickStart/guideline_log.md';
      const url = (window as any).BK_DOC_URL.replace(/\/$/, '');
      url && window.open(`${url}/${docPath}`);
    };

    /**
     * 移除业务参数重试
     * @returns
     */
    const handleRetry = () => {
      store.commit('updateStorage', {
        [BK_LOG_STORAGE.BK_SPACE_UID]: undefined,
        [BK_LOG_STORAGE.BK_BIZ_ID]: undefined,
      });

      const resolver = router.resolve({
        name: 'retrieve',
        params: {
          indexId: undefined,
        },
        query: {
          ...route.query,
          spaceUid: undefined,
          bizId: undefined,
          bkBizId: undefined,
          type: undefined,
          page_from: undefined,
        },
      });

      window.open(resolver.href, '_self');
    };

    const exceptionMap = {
      space: () => [
        <span>
          当前无可用业务信息，请联系管理员申请（空间UID：{route.query.spaceUid}，业务ID：{route.query.bizId}）
        </span>,
        <span>或者移除业务参数重试</span>,
        <span
          style={{ color: '#3a84ff', cursor: 'pointer' }}
          onClick={handleRetry}
        >
          重试
        </span>,
      ],
      indexset: () => [
        <span>业务下无采集项，请按照指引完成接入，或联系管理员申请</span>,
        <span
          onClick={handleOpenGuide}
          style={{ color: '#3a84ff', cursor: 'pointer' }}
        >
          接入指引
        </span>,
      ],
      api: () => 'API无权限，请联系管理员申请',
    };

    console.log('un-authorized route.query', route.query);

    const getExceptionText = () => {
      const type = route.query.type as keyof typeof exceptionMap;
      return exceptionMap[type as keyof typeof exceptionMap]?.() ?? '无权限，请联系管理员';
    };

    const exceptionStyle = `height: calc(100vh - 100px); 
      display: flex; 
      flex-direction: column; 
      justify-content: center; 
      align-items: center;`;

    const exceptionTextStyle = `display: flex; 
      flex-direction: column; 
      align-items: center;
      gap: 10px; 
      font-size: 14px; 
      font-weight: 500;`;

    return () => (
      <div>
        <bk-exception
          style={exceptionStyle}
          type='403'
          scene='part'
        >
          <div style={exceptionTextStyle}>{getExceptionText()}</div>
        </bk-exception>
      </div>
    );
  },
});
