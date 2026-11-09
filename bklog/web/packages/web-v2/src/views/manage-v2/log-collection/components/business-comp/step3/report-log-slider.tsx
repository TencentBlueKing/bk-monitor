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

import { copyText } from '@/components/monitor-echarts/utils';
import useLocale from '@/hooks/use-locale';

import './report-log-slider.scss';
import { showMessage } from '../../../utils';
/**
 * 上报日志详情
 */
export default defineComponent({
  name: 'ReportLogSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    jsonText: {
      type: Object,
      default: () => ({}),
    },
  },

  emits: ['change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    return () => (
      <bk-sideslider
        width={596}
        class='report-log-slider-main'
        before-close={() => {
          emit('change', false);
        }}
        scopedSlots={{
          header: () => (
            <div class='report-log-slider-header'>
              <span class='title'>{t('上报日志详情')}</span>
              <span
                class='copy-btn'
                on-click={() => {
                  copyText(JSON.stringify(props.jsonText));
                  showMessage(t('复制成功'));
                }}
              >
                {t('复制')}
              </span>
            </div>
          ),
          content: () => (
            <div class='p20 json-text-style'>
              <JsonFormatWrapper
                data={props.jsonText}
                deep={5}
              />
            </div>
          ),
        }}
        is-show={props.isShow}
        quick-close={true}
        transfer
      />
    );
  },
});
