import { useI18n } from 'vue-i18n';

import { Exception } from 'bkui-vue';

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
import type { Ref } from 'vue';

export default function useRenderEmpty(keyword?: Ref<any[] | string>, clearKeyword?: () => void) {
  const { t } = useI18n();

  function renderEmpty() {
    return keyword?.value?.length ? (
      <div class='flex-row justify-content-center full-width'>
        <div class=' text-center'>
          <div>
            <Exception
              scene='part'
              title={t('common.搜索结果为空')}
              type='search-empty'
            />
          </div>
          <div class='text-gray font-small mt-small'>
            <span>{t('common.可以尝试 调整关键词 或 ')}</span>
            <span
              class='text-link'
              onClick={clearKeyword}
            >
              {t('common.清空筛选条件')}
            </span>
          </div>
        </div>
      </div>
    ) : (
      <Exception
        scene='part'
        title={t('common.暂无数据')}
        type='empty'
      />
    );
  }

  return {
    renderEmpty,
  };
}
