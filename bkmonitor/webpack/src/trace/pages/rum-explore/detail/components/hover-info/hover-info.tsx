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
import type { PropType } from 'vue';

import { useI18n } from 'vue-i18n';

import type { IRumHoverInfo } from '../../typings/detail';

import './hover-info.scss';

/** hover 展示卡片：标题 + 官方定义链接 + 专业解释 + 用户感受 + 参考来源（不含计算方式） */
export default defineComponent({
  name: 'RumHoverInfo',
  props: {
    data: {
      type: Object as PropType<IRumHoverInfo | null>,
      default: null,
    },
  },
  setup(props) {
    const { t } = useI18n();

    return () => {
      const { data } = props;
      if (!data) return null;
      return (
        <div class='rum-hover-info'>
          <div class='hover-header'>
            <span class='hover-title'>{data.title}</span>
            {data.source?.url ? (
              <a
                class='hover-source-link'
                href={data.source.url}
                rel='noopener noreferrer'
                target='_blank'
              >
                {t('查看官方定义')}
                <i class='icon-monitor icon-fenxiang link-icon' />
              </a>
            ) : null}
          </div>
          <div class='hover-body'>
            <div class='hover-section'>
              <div class='section-label'>
                <i class='icon-monitor icon-chuli section-icon' />
                {t('专业解释')}
              </div>
              <div class='section-content'>{data.description}</div>
            </div>
            {data.user_experience ? (
              <div class='hover-section'>
                <div class='section-label is-experience'>
                  <i class='icon-monitor icon-user2 section-icon' />
                  {t('用户感受')}
                </div>
                <div class='section-content'>{data.user_experience}</div>
              </div>
            ) : null}
          </div>
          {data.source?.label ? <div class='hover-footer'>{`${t('来源')}：${data.source.label}`}</div> : null}
        </div>
      );
    };
  },
});
