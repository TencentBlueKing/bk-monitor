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
import { Alert as TAlert } from 'tdesign-vue-next';

import { Button as TButton } from 'tdesign-vue-next';

import { defineComponent, ref } from 'vue';

import { copyMessage } from '@/shared/lib/util';
import useLocale from '@/shared/composables/use-locale';


export default defineComponent({
  name: 'DownloadUrl',
  props: {
    taskId: {
      type: Number,
      default: undefined,
    },
  },
  setup(props) {
    const store = useApplicationStore();
    const { t } = useLocale();

    const loading = ref(false); // 加载状态
    const buttonRef = ref<any>(null); // 按钮引用

    // 处理点击事件
    const handleClick = () => {
      try {
        let urlPrefix = window.AJAX_URL_PREFIX;
        if (!urlPrefix.endsWith('/')) {
          urlPrefix += '/';
        }
        const { bkBizId } = store;

        const downloadUrl = `${urlPrefix}log_extract/tasks/download/?task_id=${props.taskId}&bk_biz_id=${bkBizId}`;
        copyMessage(new URL(downloadUrl, window.location.origin).href, t('已复制到剪切板'));
      } catch (e) {
        console.warn(e);
      }
    };

    return () => (
      <div class='list-box-container'>
        <div class='list-title'>
          <span class='bk-icon icon-download' />
          <h2 class='text'>{t('下载链接')}</h2>
          <TButton
            ref={buttonRef}
            style='margin-left: 20px'
            loading={loading.value}
            theme='primary'
            onClick={handleClick}
          >
            {t('点击获取')}
          </TButton>
        </div>
        <TAlert
          style='margin-top: 10px'
          message={t('链接可重复获取，每个链接只能下载一次。')}
          theme={'info'} data-v2-display='alert'
        />
      </div>
    );
  },
});
