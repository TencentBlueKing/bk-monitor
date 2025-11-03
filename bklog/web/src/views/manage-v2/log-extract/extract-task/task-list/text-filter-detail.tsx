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

import useLocale from '@/hooks/use-locale';

import './text-filter-detail.scss';

export default defineComponent({
  name: 'TextFilterDetail',
  props: {
    data: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const { t } = useLocale();

    return () => (
      <div class='text-filter-detail'>
        {/* 标题区域 */}
        <div class='title'>
          <span class='bk-icon icon-work-manage' />
          <h2 class='text'>{t('文本过滤')}</h2>
        </div>
        {/* 关键字过滤类型 */}
        {props.data.filter_type === 'match_word' && (
          <div class='content'>
            <span>{t('关键字过滤')}：</span>
            <span class='match'>{props.data.filter_content.keyword}</span>
          </div>
        )}
        {/* 关键字范围类型 */}
        {props.data.filter_type === 'match_range' && (
          <div class='content'>
            <span>
              {t('关键字范围: 从匹配{0}开始到匹配{1}之间的所有行', [
                <span
                  key='start'
                  class='match'
                >
                  {props.data.filter_content.start}
                </span>,
                <span
                  key='end'
                  class='match'
                >
                  {props.data.filter_content.end}
                </span>,
              ])}
            </span>
          </div>
        )}
        {/* 最新行数类型 */}
        {props.data.filter_type === 'tail_line' && (
          <div class='content'>
            <span>{t('最新行数')}：</span>
            <span class='match'>{props.data.filter_content.line_num}</span>
          </div>
        )}
        {/* 按行过滤类型 */}
        {props.data.filter_type === 'line_range' && (
          <div class='content'>
            <span>
              {t('按行过滤: 从第{0}行到第{1}行', [
                <span
                  key='start-line'
                  class='match'
                >
                  {props.data.filter_content.start_line}
                </span>,
                <span
                  key='end-line'
                  class='match'
                >
                  {props.data.filter_content.end_line}
                </span>,
              ])}
            </span>
          </div>
        )}
      </div>
    );
  },
});
