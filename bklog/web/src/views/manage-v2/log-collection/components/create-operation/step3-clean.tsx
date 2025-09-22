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

import { useOperation } from '../../hook/useOperation';
import CollectIssuedSlider from '../business-comp/step3/collect-issued-slider';
import FieldList from '../business-comp/step3/field-list';
import ReportLogSlider from '../business-comp/step3/report-log-slider';
import InfoTips from '../common-comp/info-tips';
import { jsonStr, tableFieldData } from './detail';
import { log } from './log';
// // 使用 webpack 的 require.context 预加载该目录下的所有 png 资源
// const iconsContext = (require as any).context('@/images/log-collection', false, /\.png$/);

import './step3-clean.scss';

export default defineComponent({
  name: 'StepClean',

  emits: ['next', 'prev'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { cardRender } = useOperation();
    const showCollectIssuedSlider = ref(false);
    const showReportLogSlider = ref(false);
    const jsonText = ref(jsonStr);
    const cleaningModeList = [
      {
        label: t('JSON'),
        value: 'bk_log_json',
      },
      {
        label: t('分隔符'),
        value: 'bk_log_delimiter',
      },
      {
        label: t('正则表达式'),
        value: 'bk_log_regexp',
      },
      // {
      //   label: t('高级清洗'),
      //   value: 'advanced',
      // },
    ];
    const cleaningMode = ref('bk_log_json');
    /** 根据清洗模式，渲染不同的内容 */
    const renderCleaningMode = () => {
      if (cleaningMode.value === 'bk_log_json') {
        return <bk-button class='clean-btn'>{t('清洗')}</bk-button>;
      }
      if (cleaningMode.value === 'bk_log_delimiter') {
        return (
          <div class='separator-box select-group'>
            <div class='select-item'>
              <span class='select-title'>{t('分隔符')}</span>
              <bk-select class='select-box' />
            </div>
            <bk-button class='clean-btn'>{t('调试')}</bk-button>
          </div>
        );
      }
      if (cleaningMode.value === 'bk_log_regexp') {
        return (
          <div class='regex-box-main'>
            <div class='title'>
              {t('正则表达式')}
              <i
                class='bk-icon icon-info-circle tips-icon'
                v-bk-tooltips={{
                  placement: 'right',
                  content: `${t('正则表达式(golang语法)需要匹配日志全文，如以下DEMO将从日志内容提取请求时间与内容')}<br />${t(' - 日志内容：[2006-01-02 15:04:05] content')}<br /> ${t(' - 表达式：')} \[(?P<request_time>[^]]+)\] (?P<content>.+)`,
                }}
              />
            </div>
            <bk-input
              placeholder={'(?P<request_ip>[d.]+)[^[]+[(?P<request_time>[^]]+)]'}
              type='textarea'
            />
            <bk-button class='clean-btn'>{t('调试')}</bk-button>
          </div>
        );
      }
    };
    /** 应用模版下拉框 */
    const renderTemplateSelect = () => (
      <bk-select
        class='template-select'
        ext-popover-cls={'template-select-popover'}
        searchable
        // on-selected={handleAddSortFields}
      >
        <span
          class='form-link'
          slot='trigger'
        >
          <i class='bklog-icon bklog-app-store link-icon' />
          {t('应用模板')}
        </span>
        {[
          { id: 1, name: '模板名称' },
          { id: 2, name: '模板名称' },
        ].map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            name={item.name}
          >
            <div class='template-option'>
              <span class='option-name'>{item.name}</span> <span class='option-btn'>{t('应用')}</span>
            </div>
          </bk-option>
        ))}
      </bk-select>
    );

    /** 选择清洗模式 */
    const handleChangeCleaningMode = mode => {
      cleaningMode.value = mode.value;
    };
    /** 清洗设置 */
    const renderSetting = () => (
      <div class='clean-setting'>
        <bk-alert
          class='clean-alert'
          title={t('通过字段清洗，可以格式化日志内容方便检索、告警和分析。')}
          type='info'
        />
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
                <bk-select class='select-box' />
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
              <span
                class='form-link'
                on-click={() => {
                  showReportLogSlider.value = true;
                }}
              >
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
              {/* 应用模版 */}
              {renderTemplateSelect()}
              <span class='form-link'>
                <i class='bklog-icon bklog-help link-icon' />
                {t('说明文档')}
              </span>
            </div>
            <div class='bk-button-group'>
              {cleaningModeList.map(mode => (
                <bk-button
                  key={mode.value}
                  class={{ 'is-selected': mode.value === cleaningMode.value }}
                  on-click={() => handleChangeCleaningMode(mode)}
                >
                  {mode.label}
                </bk-button>
              ))}
            </div>
            {renderCleaningMode()}
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('字段列表')}</span>
          <div class='form-box'>
            <FieldList
              data={tableFieldData.fields}
              selectEtlConfig={cleaningMode.value}
            />
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
                <bk-select class='select-box' />
              </div>
              <div class='select-item'>
                <span class='select-title'>{t('时间格式')}</span>
                <bk-select class='select-box' />
              </div>
              <div class='select-item'>
                <span class='select-title'>{t('时区选择')}</span>
                <bk-select class='select-box' />
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
          <div class='form-box mt-5'>
            <bk-switcher size='large' />
            <InfoTips
              class='ml-12'
              tips={t('定义元数据并补充至日志中，可通过元数据进行过滤筛选')}
            />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('路径样例')}</span>
          <div class='form-box mt-5'>
            <div class='url-demo-box'>
              <bk-input class='input-box' />
              <i class='bklog-icon bklog-refresh-icon icons' />
            </div>
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title'>{t('采集路径分割正则')}</span>
          <div class='form-box mt-5'>
            <div class='url-demo-box'>
              <bk-input class='input-box' />
              <bk-button class='debug-btn'>{t('调试')}</bk-button>
            </div>
            <div class='debug-box'>
              <bk-input
                class='first-input'
                disabled
              />
              <span class='symbol'>:</span>
              <bk-input disabled />
            </div>
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
        <div
          class='status-box loading'
          on-Click={() => {
            showCollectIssuedSlider.value = true;
          }}
        >
          <span class='status-icon-box' />
          <i class='bklog-icon bklog-caijixiafazhong status-icon' />
          {/* <i class='bklog-icon bklog-circle-correct-filled status-icon' /> */}
          {/* <i class='bklog-icon bklog-shanchu status-icon' /> */}
          <span class='status-txt'>{t('采集下发中...')}</span>
        </div>
        {cardRender(cardConfig)}
        <CollectIssuedSlider
          data={log}
          isShow={showCollectIssuedSlider.value}
          on-change={value => {
            showCollectIssuedSlider.value = value;
          }}
        />
        <ReportLogSlider
          isShow={showReportLogSlider.value}
          jsonText={jsonText.value}
          on-change={value => {
            showReportLogSlider.value = value;
          }}
        />
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
          <bk-button class='template-btn'>{t('另存为模板')}</bk-button>
          <bk-button class='mr-8'>{t('重置')}</bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
