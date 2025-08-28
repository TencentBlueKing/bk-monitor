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

import { computed, defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import { useOperation } from '../../hook/useOperation';
import InfoTips from '../common-comp/info-tips';

import './step2-custom-report.scss';

export default defineComponent({
  name: 'StepCustomReport',

  emits: ['next', 'prev'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { cardRender } = useOperation();
    const formData = ref({ name: '' });
    /** 基本信息 */
    const renderBaseInfo = () => (
      <bk-form
        class='base-info-form'
        label-width={100}
        // model={formData.value}
      >
        <bk-form-item
          label={t('采集名')}
          property='name'
          required={true}
        >
          <bk-input
            class='w-45'
            maxlength={50}
            value={formData.value.name}
            clearable
            onInput={val => (formData.value.name = val)}
          />
        </bk-form-item>
        <bk-form-item
          label={t('数据分类')}
          property='name'
          required={true}
        >
          <div class='bk-button-group'>
            <bk-button class='is-selected'>{t('容器日志上报')}</bk-button>
            <bk-button>{t('otlp 日志上报')}</bk-button>
          </div>
          <InfoTips
            class='block'
            tips={t(
              '自定义上报数据，可以通过采集器，或者指定协议例如otlp等方式进行上报，自定义上报有一定的使用要求，具体可以查看使用说明',
            )}
          />
        </bk-form-item>
        <bk-form-item
          label={t('数据名')}
          required={true}
        >
          <bk-input
            class='w-45'
            maxlength={50}
            minlength={5}
            placeholder={t('用于索引和数据源，仅支持数字、字母、下划线，5～50 字符')}
            value={formData.value.name}
            clearable
            onInput={val => (formData.value.name = val)}
          />
        </bk-form-item>
        <bk-form-item label={t('所属索引集')}>
          <bk-select class='w-45' />
        </bk-form-item>
        <bk-form-item label={t('备注说明')}>
          <bk-input
            class='w-45'
            maxlength={100}
            type='textarea'
            value={formData.value.name}
            clearable
            onInput={val => (formData.value.name = val)}
          />
        </bk-form-item>
      </bk-form>
    );

    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
    ];
    return () => (
      <div class='operation-step2-custom-report'>
        {cardRender(cardConfig)}
        <div class='classify-btns'>
          <bk-button
            class='mr-8'
            on-click={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </bk-button>
          <bk-button
            class='mr-8 width-88'
            theme='primary'
            on-click={() => {
              emit('next');
            }}
          >
            {t('下一步')}
          </bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
