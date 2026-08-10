/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { docCookies, LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { useDocumentLink } from '@/hooks/documentLink';

import './index.scss';

export default defineComponent({
  name: 'AbnormalTips',
  props: {
    tipsText: {
      type: String,
      default: '',
    },
    linkText: {
      type: String,
      default: '',
    },
    linkUrl: {
      type: String,
      default: '',
    },
    docLink: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { handleGotoLink } = useDocumentLink();
    const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';

    const handleOpenLink = (url: string) => {
      if (!url) return;
      window.open(url, '_blank');
    };

    return () => (
      <div class='abnormal-tips-wrap'>
        <div class={['abnormal-tips-wrap__content', { 'is-en': isEn }]}>
          <span class='abnormal-tips-wrap__text'>{props.tipsText}</span>
          <div>
            {props.linkUrl && props.linkText ? (
              <span
                class='abnormal-tips-wrap__link'
                onClick={() => handleOpenLink(props.linkUrl)}
              >
                {props.linkText}
                <span class='icon-monitor icon-mc-link' />
              </span>
            ) : null}
            {props.docLink ? (
              <span
                class='abnormal-tips-wrap__link'
                onClick={() => handleGotoLink(props.docLink)}
              >
                {t('查看文档')}
                <span class='icon-monitor icon-mc-link' />
              </span>
            ) : null}
          </div>
        </div>
      </div>
    );
  },
});
