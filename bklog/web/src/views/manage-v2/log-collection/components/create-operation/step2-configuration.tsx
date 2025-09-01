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
import BaseInfo from '../business-comp/base-info';
import InfoTips from '../common-comp/info-tips';

import './step2-configuration.scss';

export default defineComponent({
  name: 'StepConfiguration',

  emits: ['next', 'prev'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { cardRender } = useOperation();
    /** 基本信息 */
    const renderBaseInfo = () => <BaseInfo />;
    /** 源日志信息 */
    const renderSourceLogInfo = () => (
      <div class='source-log-info'>
        <div class='label-form-box'>
          <span class='label-title'>{t('日志类型')}</span>
          <div class='form-box'>
            <div class='bk-button-group'>
              <bk-button>{t('行日志')}</bk-button>
              <bk-button class='is-selected'>{t('段日志')}</bk-button>
            </div>
            <div class='line-rule'>
              <div class='label-title text-left'>{t('行首正则')}</div>
              <div class='rule-reg'>
                <bk-input class='reg-input' />
                <span class='form-link debug'>{t('调试')}</span>
              </div>
              <div class='line-rule-box'>
                <div class='line-rule-box-item'>
                  <div class='label-title no-require text-left'>{t('最多匹配')}</div>
                  <bk-input>
                    <div
                      class='group-text'
                      slot='append'
                    >
                      {t('行')}
                    </div>
                  </bk-input>
                </div>
                <div class='line-rule-box-right'>
                  <div class='label-title no-require text-left'>{t('最大耗时')}</div>
                  <bk-input class='time-box'>
                    <div
                      class='group-text'
                      slot='append'
                    >
                      {t('秒')}
                    </div>
                  </bk-input>
                  <InfoTips tips={t('建议配置 1s, 配置过长时间可能会导致日志积压')} />
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('采集目标')}</span>
          <div class='form-box'>
            <bk-button
              class='target-btn'
              icon='plus'
            >
              {t('选择目标')}
            </bk-button>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('采集路径')}</span>
          <div class='form-box'>
            <InfoTips tips={t('日志文件的绝对路径，可使用 通配符')} />
            <div class='form-box-url'>
              <bk-input />
            </div>
            <div>
              <span class='form-link'>
                <i class='bklog-icon link-icon bklog-expand-small' />
                {t('路径黑名单')}
              </span>
              <InfoTips tips={t('可通过正则语法排除符合条件的匹配项 。如：匹配任意字符：.*')} />
            </div>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('字符集')}</span>
          <bk-select class='form-box' />
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('采集范围')}</span>
          <bk-radio-group class='form-box'>
            <bk-radio class='mr-24'>{t('仅采集下发后的日志')}</bk-radio>
            <bk-radio>{t('采集完整文件')}</bk-radio>
          </bk-radio-group>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('日志过滤')}</span>
          <div class='form-box mt-5'>
            <bk-switcher size='large' />
            <InfoTips
              class='ml-12'
              tips={t('过滤器支持采集时过滤不符合的日志内容，请保证采集器已升级到最新版本')}
            />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('设备元数据')}</span>
          <div class='form-box mt-5'>
            <bk-switcher size='large' />
            <InfoTips
              class='ml-12'
              tips={t('该设置可以将采集设备的元数据信息补充至日志中')}
            />
          </div>
        </div>
      </div>
    );
    /** 链路配置 */
    const renderLinkConfig = () => (
      <div class='link-config label-form-box'>
        <span class='label-title'>{t('上报链路')}</span>
        <bk-select class='form-box' />
      </div>
    );
    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
      {
        title: t('源日志信息'),
        key: 'sourceLogInfo',
        renderFn: renderSourceLogInfo,
      },
      {
        title: t('链路配置'),
        key: 'linkConfiguration',
        renderFn: renderLinkConfig,
      },
    ];
    return () => (
      <div class='operation-step2-configuration'>
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
            class='width-88 mr-8'
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
