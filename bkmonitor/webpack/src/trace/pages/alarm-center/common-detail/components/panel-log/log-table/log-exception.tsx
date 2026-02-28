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

import { useI18n } from 'vue-i18n';

import './log-exception.scss';

export default defineComponent({
  name: 'LogException',

  setup() {
    const { t } = useI18n();

    const searchEmpty = () => {
      return (
        <div class='log-table-new-empty-data'>
          <h1>{t('检索无数据')}</h1>
          <div class='sub-title'>{t('您可按照以下顺序调整检索方式')}</div>
          <div class='empty-validate-steps'>
            <div class='validate-step1'>
              <h3>1. {t('优化查询语句')}</h3>
              <div class='step1-content'>
                <span class='step1-content-label'>{t('查询范围')}：</span>
                <span class='step1-content-value'>
                  log: bklog*
                  <br />
                  {t('包含')} bklog
                  <br />= bklog {t('使用通配符')} (*)
                </span>
              </div>
              <div class='step1-content'>
                <span class='step1-content-label'>{t('精准匹配')}：</span>
                <span class='step1-content-value'>log: "bklog"</span>
              </div>
            </div>
            <div class='validate-step2'>
              <h3>2. {t('检查是否为分词问题')}</h3>
              <div>
                {t('当您的鼠标移动至对应日志内容上时，该日志单词将展示为蓝色。')}
                <br />
                <br />
                {t('若目标内容为整段蓝色，或中间存在字符粘连的情况。')}
                <br />
                {t('可能是因为分词导致的问题')}；
                {/* <br />
                <span
                  class='segment-span-tag'
                  onClick={openConfiguration}
                >
                  {t('点击设置自定义分词')}
                </span> */}
                <br />
                <br />
                {t('将字符粘连的字符设置至自定义分词中，等待 3～5 分钟，新上报的日志即可生效设置。')}
              </div>
            </div>
            <div class='validate-step3'>
              <h3>3.{t('一键反馈')}</h3>
              <div>
                {t('若您仍无法确认问题原因，请点击下方反馈按钮与我们联系，平台将第一时间响应处理。')}
                <br />
                {/* <span class='segment-span-tag'>问题反馈</span> */}
                <a
                  class='segment-span-tag'
                  href={'wxwork://message/?username=BK助手'}
                >
                  {t('问题反馈')}
                </a>
              </div>
            </div>
          </div>
        </div>
      );
    };

    return { t, searchEmpty };
  },
  render() {
    return this.searchEmpty();
  },
});
