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

import './step3-clean.scss';

export default defineComponent({
  name: 'StepClean',

  emits: ['next', 'prev'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { cardRender } = useOperation();
    /** 清洗设置 */
    const renderSetting = () => (
      <div class='clean-setting'>
        <bk-alert
          class='clean-alert'
          title={t('通过字段清洗，可以格式化日志内容方便检索、告警和分析。')}
          type='info'
        ></bk-alert>
        <div class='label-form-box'>
          <span class='label-title'>{t('原始日志')}</span>
          <div class='form-box'>
            <bk-radio-group>
              <bk-radio class='mr-24'>{t('保留')}</bk-radio>
              <bk-radio>{t('丢弃')}</bk-radio>
            </bk-radio-group>
            <div class='select-group'>
              <div class='select-item'>
                <span class='select-title'>{t('分词符')}</span>
                <bk-select class='select-box'></bk-select>
              </div>
              <div class='select-item'>
                <bk-checkbox class='mr-5' />
                {t('大小写敏感')}
              </div>
            </div>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('日志样例')}</span>
          <div class='form-box'>
            <div class='example-box'>
              <span class='form-link'>
                <i class='bklog-icon bklog-audit link-icon' />
                {t('上报日志')}
              </span>
              <span class='form-link'>
                <i class='bklog-icon bklog-refresh2 link-icon' />
                {t('刷新')}
              </span>
              <InfoTips
                class='ml-12'
                tips={t('作为清洗调试的原始数据')}
              />
            </div>
            <bk-input type='textarea' />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('清洗模式')}</span>
          <div class='form-box'>
            <div class='example-box'>
              <span class='form-link'>
                <i class='bklog-icon bklog-app-store link-icon' />
                {t('应用模板')}
              </span>
              <span class='form-link'>
                <i class='bklog-icon bklog-help link-icon' />
                {t('说明文档')}
              </span>
            </div>
            <div class='bk-button-group'>
              <bk-button class='is-selected'>{t('JSON')}</bk-button>
              <bk-button>{t('分隔符')}</bk-button>
              <bk-button>{t('正则表达式')}</bk-button>
              {/* <bk-button>{t('高级清洗')}</bk-button> */}
            </div>
            <bk-button class='clean-btn'>{t('清洗')}</bk-button>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('字段列表')}</span>
          <div class='form-box'>
            <div class='tab-box'>
              <div class='tab-list'>
                <span class='tab-item is-selected'>{t('可见字段 (8)')}</span>
                <span class='tab-item'>{t('被隐藏字段 (0)')}</span>
              </div>
              <span class='checkbox-box'>
                <bk-checkbox class='mr-5' />
                {t('显示内置字段')}
              </span>
            </div>
            <div class='fields-table'>111</div>
            <div class='example-box'>
              <span class='form-link'>
                <i class='bk-icon icon-plus link-icon add-btn' />
                {t('新增字段')}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
    /** 高级设置 */
    const renderAdvanced = () => (
      <div class='advanced-setting'>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('指定日志时间')}</span>
          <div class='form-box'>
            <bk-radio-group>
              <bk-radio class='mr-24'>{t('日志上报时间')}</bk-radio>
              <bk-radio>{t('指定字段为日志时间')}</bk-radio>
            </bk-radio-group>
            <div class='select-group'>
              <div class='select-item'>
                <span class='select-title'>{t('字段')}</span>
                <bk-select class='select-box'></bk-select>
              </div>
              <div class='select-item'>
                <span class='select-title'>{t('时间格式')}</span>
                <bk-select class='select-box'></bk-select>
              </div>
              <div class='select-item'>
                <span class='select-title'>{t('时间格式')}</span>
                <bk-select class='select-box'></bk-select>
              </div>
            </div>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('失败日志')}</span>
          <bk-radio-group class='form-box'>
            <bk-radio class='mr-24'>{t('保留')}</bk-radio>
            <bk-radio>{t('丢弃')}</bk-radio>
          </bk-radio-group>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('路径元数据')}</span>
          <div class='form-box'>
            <bk-switcher size='large'></bk-switcher>
            <InfoTips
              class='ml-12'
              tips={t('定义元数据并补充至日志中，可通过元数据进行过滤筛选')}
            />
          </div>
        </div>
      </div>
    );
    const cardConfig = [
      {
        title: t('清洗设置'),
        key: 'cleanSetting',
        renderFn: renderSetting,
      },
      {
        title: t('高级设置'),
        key: 'advancedSetting',
        renderFn: renderAdvanced,
      },
    ];
    return () => (
      <div class='operation-step3-clean'>
        <div class='status-box success'>
          <span class='status-icon-box'>
            <i class='bklog-icon bklog-circle-correct-filled status-icon' />
            {/* <i class='bklog-icon bklog-shanchu status-icon' /> */}
          </span>
          <span class='status-txt'>{t('采集下发中...')}</span>
        </div>
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
            on-click={() => {
              emit('next');
            }}
          >
            {t('下一步')}
          </bk-button>
          <bk-button class='template-btn'>{t('另存为模板')}</bk-button>
          <bk-button class='mr-8'>{t('重置')}</bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
