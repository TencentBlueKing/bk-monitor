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
import { defineComponent, ref } from 'vue';

import BklogPopover from '@/components/bklog-popover';
import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  props: {
    matchMode: {
      type: Object,
      default: () => ({
        caseSensitive: false,
        regexMode: false,
        wordMatch: false,
      }),
    },
    border: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const isCaseSensitive = ref(props.matchMode.caseSensitive);
    const isRegexMode = ref(props.matchMode.regexMode);
    const isWordMatch = ref(props.matchMode.wordMatch);
    // 切换大小写敏感
    const toggleCaseSensitive = () => {
      isCaseSensitive.value = !isCaseSensitive.value;
      emit('change', {
        caseSensitive: isCaseSensitive.value,
        regexMode: isRegexMode.value,
        wordMatch: isWordMatch.value,
      });
    };

    // 切换正则模式
    const toggleRegexMode = () => {
      isRegexMode.value = !isRegexMode.value;
      emit('change', {
        caseSensitive: isCaseSensitive.value,
        regexMode: isRegexMode.value,
        wordMatch: isWordMatch.value,
      });
    };

    // 切换整词匹配
    const toggleWordMatch = () => {
      isWordMatch.value = !isWordMatch.value;
      emit('change', {
        caseSensitive: isCaseSensitive.value,
        regexMode: isRegexMode.value,
        wordMatch: isWordMatch.value,
      });
    };

    return () => (
      <div class={['bklog-g_components-match-mode', { border: props.border }]}>
        <BklogPopover
          content={t('大小写匹配')}
          options={{ theme: 'material', appendTo: document.body } as any}
          trigger='hover'
        >
          <span
            class={[
              'bklog-g_components-match-mode-icon',
              'bklog-icon',
              'bklog-daxiaoxie',
              { active: isCaseSensitive.value },
            ]}
            onClick={toggleCaseSensitive}
          />
        </BklogPopover>

        <BklogPopover
          content={t('精确匹配')}
          options={{ theme: 'material', appendTo: document.body } as any}
          trigger='hover'
        >
          <span
            class={['bklog-g_components-match-mode-icon', 'bklog-icon', 'bklog-ab', { active: isWordMatch.value }]}
            onClick={toggleWordMatch}
          />
        </BklogPopover>

        <BklogPopover
          content={t('正则匹配')}
          options={{ placement: 'top', theme: 'material', appendTo: document.body } as any}
          trigger='hover'
        >
          <span
            class={[
              'bklog-g_components-match-mode-icon',
              'bklog-icon',
              'bklog-tongpeifu',
              { active: isRegexMode.value },
            ]}
            onClick={toggleRegexMode}
          />
        </BklogPopover>
      </div>
    );
  },
});
