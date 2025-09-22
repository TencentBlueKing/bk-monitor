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

import useLocale from '@/hooks/use-locale';

import HostDetail from '../../common-comp/host-detail';

import './collect-issued-slider.scss';
/**
 * @description: 采集才发侧边栏
 */
export default defineComponent({
  name: 'CollectIssuedSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    isStopCollection: {
      type: Boolean,
      default: false,
    },
    data: {
      type: Object,
      default: () => ({}),
    },
  },

  emits: ['change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const collectionName = ref();

    const renderHeader = () => (
      <div>
        {props.isStopCollection ? (
          <div class='collect-link'>
            {t('编辑采集项')}
            <span style='padding: 3px 9px; background-color: #f0f1f5'>
              <span class='bk-icon bklog-icon bklog-position' />
              {collectionName.value}
            </span>
          </div>
        ) : (
          <span>{t('采集下发')}</span>
        )}
      </div>
    );

    const renderContent = () => (
      <div class='collect-issued-slider-content'>
        <div class='collect-issued-slider-alert'>
          <i class='bklog-icon bklog-alert alert-icon' />
          {t('采集下发存在失败，请点击 重试，如再次失败请 联系助手。')}
        </div>
        <HostDetail log={props.data} />
      </div>
    );

    return () => (
      <bk-sideslider
        width={960}
        ext-cls='collect-issued-slider-main'
        before-close={() => {
          emit('change', false);
        }}
        scopedSlots={{
          header: renderHeader,
          content: renderContent,
        }}
        is-show={props.isShow}
        quick-close
        transfer
        // @animation-end="closeSlider"
        // @shown="showSlider"
      />
    );
  },
});
