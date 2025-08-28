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

import './step2-bk-data-collection.scss';

export default defineComponent({
  name: 'StepBkDataCollection',

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
            maxlength={50}
            value={formData.value.name}
            clearable
            onInput={val => (formData.value.name = val)}
          />
        </bk-form-item>
        <bk-form-item label={t('所属索引集')}>
          <bk-select />
        </bk-form-item>
      </bk-form>
    );
    /** 数据源 */
    const renderDataSource = () => (
      <div class='data-source-box'>
        <div class='label-form-box'>
          <span class='label-title'>{t('数据源')}</span>
          <div class='form-box'>
            <div></div>
            <div class='data-source-table'></div>
          </div>
        </div>
      </div>
    );
    /** 字段设置 */
    const renderFieldSetting = () => (
      <div class='field-setting-box'>
        <bk-alert
          class='field-setting-alert'
          title={t('未匹配到对应字段，请手动指定字段后提交。')}
          type='warning'
        ></bk-alert>
        <div class='label-form-box'>
          <span class='label-title'>{t('目标字段')}</span>
          <div class='form-box'>
            <bk-select class='select-sort' />
            <InfoTips
              class='block'
              tips={t('用于标识日志文件来源及唯一性')}
            />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('排序字段')}</span>
          <div class='form-box'>
            <InfoTips
              class='block'
              tips={t('用于控制日志排序的字段')}
            />
          </div>
        </div>
      </div>
    );
    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
      {
        title: t('数据源'),
        key: 'dataSource',
        renderFn: renderDataSource,
      },
      {
        title: t('字段设置'),
        key: 'fieldSetting',
        renderFn: renderFieldSetting,
      },
    ];
    return () => (
      <div class='operation-step2-bk-data-collection'>
        {cardRender(cardConfig)}
        <div class='classify-btns-fixed'>
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
          >
            {t('提交')}
          </bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
