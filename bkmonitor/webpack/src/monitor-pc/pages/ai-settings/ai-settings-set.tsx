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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { fetchAiSetting, saveAiSetting } from 'monitor-api/modules/aiops';

import ErrorMsg from '../../components/error-msg/error-msg';
// import { listIntelligentModels } from 'monitor-api/modules/strategies';
import IntelligentModelsStore, { IntelligentModelsType } from '../../store/modules/intelligent-models';
import AnomalyDetection from './components/anomaly-detection';
import ExpanCard from './components/expan-card';
// import IpSelector from './components/ip-selector';

import type { HostValueItem, SchemeItem } from './types';
import type { TranslateResult } from 'vue-i18n';

import './ai-settings-set.scss';

enum AISettingType {
  IntelligentDetect = 'IntelligentDetect',
  MultivariateAnomalyDetection = 'MultivariateAnomalyDetection',
}
interface HostData {
  default_plan_id: number;
  default_sensitivity: number;
  exclude_target: HostValueItem[][];
  intelligent_detect: Record<string, any>; // 可能需要根据实际需要调整类型
  is_enabled: boolean;
}

interface SettingsData {
  errorsMsg?: Record<string, string | TranslateResult>;
  title: string | TranslateResult;
  type: AISettingType;
  data:
    | any
    | {
        data: HostData;
        errorsMsg?: Record<string, string | TranslateResult>;
        title: string | TranslateResult;
        type: string;
      }[]
    | { default_plan_id: number };
}

@Component
export default class AiSettingsSet extends tsc<object> {
  loading = false;
  btnLoading = false;
  /* ai设置原始数据 */
  aiSetting = {
    kpi_anomaly_detection: {
      default_plan_id: 0,
    },
    multivariate_anomaly_detection: {
      host: {
        default_plan_id: 0,
        default_sensitivity: 1,
        is_enabled: true,
        exclude_target: [],
        intelligent_detect: {},
      },
    },
  };
  /* 前端表单数据 */
  settingsData: SettingsData[] = [
    {
      type: AISettingType.IntelligentDetect,
      title: window.i18n.t('单指标异常检测'),
      data: {
        default_plan_id: '',
      },
      errorsMsg: {
        default_plan_id: '',
      },
    },
    {
      type: AISettingType.MultivariateAnomalyDetection,
      title: window.i18n.t('场景智能异常检测'),
      data: [
        {
          type: 'host',
          title: window.i18n.t('主机'),
          data: {
            default_plan_id: '',
            default_sensitivity: 1,
            is_enabled: true,
            exclude_target: [],
            intelligent_detect: {},
          },
          errorsMsg: {
            default_plan_id: '',
          },
        },
      ],
    },
  ];
  // 单指标
  schemeList: SchemeItem[] = [];
  // 多指标场景
  multipleSchemeList: SchemeItem[] = [];

  async created() {
    this.loading = true;
    await this.getSchemeList();
    await this.getAiSetting();
    this.loading = false;
  }

  /**
   * 获取默认方案列表
   */
  async getSchemeList() {
    // 获取单指标
    this.schemeList = await IntelligentModelsStore.getListIntelligentModels({
      algorithm: IntelligentModelsType.IntelligentDetect,
    }).catch(() => []);
    // 获取多场景
    this.multipleSchemeList = await IntelligentModelsStore.getListIntelligentModels({
      algorithm: IntelligentModelsType.MultivariateAnomalyDetection,
    }).catch(() => []);
  }

  /** *
   *  获取ai设置
   */
  async getAiSetting() {
    const aiSetting = await fetchAiSetting().catch(() => null);
    if (aiSetting) {
      this.aiSetting = aiSetting;
      const {
        // eslint-disable-next-line @typescript-eslint/naming-convention
        kpi_anomaly_detection: { default_plan_id },
        multivariate_anomaly_detection: { host },
      } = this.aiSetting;
      this.settingsData[0].data.default_plan_id = default_plan_id || '';
      this.settingsData[1].data[0].data = {
        ...host,
        default_plan_id: host.default_plan_id || '',
        is_enabled: true, // 默认 true
      };
    }
  }

  handleValidate() {
    if (!this.settingsData[0].data.default_plan_id) {
      this.settingsData[0].errorsMsg.default_plan_id = window.i18n.t('请选择默认方案');
    }
    if (this.settingsData[1].data[0].data.is_enabled && !this.settingsData[1].data[0].data.default_plan_id) {
      this.settingsData[1].data[0].errorsMsg.default_plan_id = window.i18n.t('请选择默认方案');
    }
    return (
      Object.keys(this.settingsData[0].errorsMsg).every(key => !this.settingsData[0].errorsMsg[key]) &&
      Object.keys(this.settingsData[1].data[0].errorsMsg).every(key => !this.settingsData[1].data[0].errorsMsg[key])
    );
  }

  /**
   * @description 保存
   */
  async handleSubmit() {
    const validate = this.handleValidate();
    if (validate) {
      this.btnLoading = true;
      const excludeTarget = this.settingsData[1].data[0].data.exclude_target;
      const excludeTargetValue = excludeTarget?.[0]?.[0]?.value || [];
      const params = {
        ...this.aiSetting,
        multivariate_anomaly_detection: {
          ...this.aiSetting.multivariate_anomaly_detection,
          host: {
            ...this.aiSetting.multivariate_anomaly_detection.host,
            ...this.settingsData[1].data[0].data,
            exclude_target: excludeTargetValue.length ? excludeTarget : [],
          },
        },
        kpi_anomaly_detection: {
          ...this.aiSetting.kpi_anomaly_detection,
          ...this.settingsData[0].data,
          is_enabled: undefined, // 单指标异常检测需去除是否启用
          default_sensitivity: undefined,
        },
      };
      const res = await saveAiSetting(params)
        .then(() => true)
        .catch(() => false);
      this.btnLoading = res;
      if (res) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('保存成功！'),
        });
        this.handleCancel();
      }
    }
  }

  handleCancel() {
    this.$router.push({
      name: 'ai-settings',
    });
  }

  /**
   * @description 表单项渲染
   * @param label
   * @param content
   * @param isRequired
   * @returns
   */
  formItemRender(label, content, isRequired = false) {
    return (
      <div class='settings-form-item'>
        {typeof label === 'string' ? <div class={['item-label', { required: isRequired }]}>{label}</div> : label}
        <div class='item-content'>{content}</div>
      </div>
    );
  }

  /**
   * @description 渲染方案选项
   * @param schemeList
   * @returns
   */
  renderSchemeOption(schemeList: SchemeItem[]) {
    return schemeList.map(item => (
      <bk-option
        id={item.id}
        key={item.id}
        style='width: 100%;'
        name={item.name}
      >
        <bk-popover
          style='width: 100%;'
          ext-cls='programme-item-popover'
          placement='right-end'
          theme='light'
        >
          <div style='width: 100%;'>{item.name}</div>
          <div slot='content'>
            <div class='content-item'>
              <span class='content-item-title'>{this.$t('依赖历史数据长度')}:</span>
              <span>{item.ts_depend}</span>
            </div>
            <div class='content-item'>
              <span class='content-item-title'>{this.$t('数据频率')}:</span>
              <span>{item.ts_freq || this.$t('无限制')}</span>
            </div>
            <div class='content-item'>
              <span class='content-item-title'>{this.$t('描述')}:</span>
              <span class='content-item-description'>{item.description}</span>
            </div>
          </div>
        </bk-popover>
      </bk-option>
    ));
  }

  contentRender(settingsItem: SettingsData) {
    if (settingsItem.type === AISettingType.IntelligentDetect) {
      /* 单指标异常检测 */
      return (
        <div class='form-items'>
          {this.formItemRender(
            <span class='item-label required mt-6'>{this.$t('默认方案')}</span>,
            <ErrorMsg
              style='width: 100%;'
              message={settingsItem.errorsMsg.default_plan_id as string}
            >
              {this.loading ? (
                <div class='skeleton-element h16 mt-6' />
              ) : (
                <bk-select
                  v-model={settingsItem.data.default_plan_id}
                  clearable={false}
                  ext-popover-cls='ai-settings-scheme-select'
                  placeholder={this.$t('选择方案')}
                  searchable
                  on-change={() => {
                    settingsItem.errorsMsg.default_plan_id = '';
                  }}
                >
                  {this.renderSchemeOption(this.schemeList)}
                </bk-select>
              )}
            </ErrorMsg>,
            true
          )}
        </div>
      );
    }
    if (settingsItem.type === AISettingType.MultivariateAnomalyDetection) {
      /* 场景智能异常检测 */
      return settingsItem.data.map(child => {
        if (child.type === 'host') {
          return (
            <ExpanCard
              key={child.type}
              class='mb-16'
              expand={true}
              title={child.title as string}
            >
              <div class='form-items'>
                {[
                  this.formItemRender(
                    <span class='item-label required mt-6'>{this.$t('默认方案')}</span>,
                    <ErrorMsg
                      style='width: 100%;'
                      message={child.errorsMsg.default_plan_id}
                    >
                      {this.loading ? (
                        <div class='skeleton-element h16 mt-6' />
                      ) : (
                        <bk-select
                          v-model={child.data.default_plan_id}
                          clearable={false}
                          ext-popover-cls='ai-settings-scheme-select'
                          searchable
                          on-change={() => {
                            child.errorsMsg.default_plan_id = '';
                          }}
                        >
                          {this.renderSchemeOption(this.multipleSchemeList)}
                        </bk-select>
                      )}
                    </ErrorMsg>,
                    true
                  ),
                  // this.formItemRender(
                  //   <span class='item-label required'>{this.$t('默认敏感度')}</span>,
                  //   this.loading ? (
                  //     <div class='skeleton-element h16' />
                  //   ) : (
                  //     <div class='mt-6'>
                  //       <bk-slider
                  //         v-model={child.data.default_sensitivity}
                  //         max-value={10}
                  //         min-value={1}
                  //       />
                  //       <div class='sensitivity-tips'>
                  //         <span>{this.$t('较少告警')}</span>
                  //         <span>{this.$t('较多告警')}</span>
                  //       </div>
                  //     </div>
                  //   ),
                  //   true
                  // ),
                ]}
                {/* {this.formItemRender(
                  this.$t('是否启用'),
                  this.loading ? (
                    <div class='skeleton-element h16' />
                  ) : (
                    <span class='enable-switch-wrap'>
                      <bk-switcher
                        v-model={child.data.is_enabled}
                        behavior='simplicity'
                        size='small'
                        theme='primary'
                      />
                      <span class='right-tip'>
                        <span class='icon-monitor icon-hint' />
                        <span class='tip-text'>
                          {this.$t('启用后将自动进行主机异常检测，也可在监控策略中配置此类告警')}
                        </span>
                      </span>
                    </span>
                  )
                )}
                {child.data.is_enabled
                  ? [
                      this.formItemRender(
                        <span class='item-label'>{this.$t('关闭通知的对象')}</span>,
                        <IpSelector
                          value={child.data.exclude_target}
                          onChange={v => (child.data.exclude_target = v)}
                        />
                      ),
                      this.formItemRender(
                        <span class='item-label required mt-6'>{this.$t('默认方案')}</span>,
                        <ErrorMsg
                          style='width: 100%;'
                          message={child.errorsMsg.default_plan_id}
                        >
                          {this.loading ? (
                            <div class='skeleton-element h16 mt-6' />
                          ) : (
                            <bk-select
                              v-model={child.data.default_plan_id}
                              clearable={false}
                              ext-popover-cls='ai-settings-scheme-select'
                              searchable
                              on-change={() => {
                                child.errorsMsg.default_plan_id = '';
                              }}
                            >
                              {this.renderSchemeOption(this.multipleSchemeList)}
                            </bk-select>
                          )}
                        </ErrorMsg>,
                        true
                      ),
                      this.formItemRender(
                        <span class='item-label required'>{this.$t('默认敏感度')}</span>,
                        this.loading ? (
                          <div class='skeleton-element h16' />
                        ) : (
                          <div class='mt-6'>
                            <bk-slider
                              v-model={child.data.default_sensitivity}
                              max-value={10}
                              min-value={1}
                            />
                            <div class='sensitivity-tips'>
                              <span>{this.$t('较少告警')}</span>
                              <span>{this.$t('较多告警')}</span>
                            </div>
                          </div>
                        ),
                        true
                      ),
                    ]
                  : undefined} */}
              </div>
            </ExpanCard>
          );
        }
        return undefined;
      });
    }
    return undefined;
  }

  render() {
    return (
      <div class='ai-settings-set'>
        <div class='ai-settings-set-content'>
          {this.settingsData.map(item => (
            <AnomalyDetection
              key={item.type}
              showExpand={true}
              title={item.title}
            >
              {this.contentRender(item)}
            </AnomalyDetection>
          ))}
        </div>
        <div class='ai-settings-set-footer'>
          <bk-button
            class='mr-8 w-88'
            loading={this.btnLoading}
            theme='primary'
            on-click={this.handleSubmit}
          >
            {this.$t('保存')}
          </bk-button>
          <bk-button
            class='w-88'
            theme='default'
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  }
}
