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

import { fetchAiSetting } from 'monitor-api/modules/aiops';
import { listIntelligentModels } from 'monitor-api/modules/strategies';

import AnomalyDetection from './components/anomaly-detection';
import { SchemeItem } from './types';

import './ai-settings-set.scss';

@Component
export default class AiSettingsSet extends tsc<object> {
  loading = false;
  /* ai设置原始数据 */
  aiSetting = null;
  /* 前端表单数据 */
  settingsData = [
    {
      type: 'IntelligentDetect',
      title: window.i18n.t('单指标异常检测'),
      data: {
        default_plan_id: 0,
      },
    },
    {
      type: 'MultivariateAnomalyDetection',
      title: window.i18n.t('场景智能异常检测'),
      data: [
        {
          tpye: 'host',
          title: window.i18n.t('主机'),
          data: {
            default_plan_id: 0,
            default_sensitivity: 0,
            is_enabled: true,
            exclude_target: [],
            intelligent_detect: {},
          },
        },
      ],
    },
  ];
  // 单指标
  schemeList: SchemeItem[] = [];
  // 多指标场景
  multipleSchemeList: SchemeItem[] = [];

  created() {
    this.getSchemeList();
  }

  /**
   * 获取默认方案列表
   */
  async getSchemeList() {
    // 获取单指标
    this.schemeList = await listIntelligentModels({ algorithm: 'IntelligentDetect' }).catch(() => {
      this.loading = false;
    });
    // 获取多场景
    this.multipleSchemeList = await listIntelligentModels({ algorithm: 'MultivariateAnomalyDetection' }).catch(() => {
      this.loading = false;
    });
  }

  /** *
   *  获取ai设置
   */
  async getAiSetting() {
    this.loading = true;
    this.aiSetting = await fetchAiSetting().catch(() => (this.loading = false));
    await this.getTargetDetail();
    this.loading = false;
  }

  /**
   * @description 获取检测对象
   */
  async getTargetDetail() {}

  handleSubmit() {}

  handleCancel() {}

  render() {
    return (
      <div
        class='ai-settings-set'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='ai-settings-set-content'>
          {this.settingsData.map(item => (
            <AnomalyDetection
              key={item.type}
              showExpand={true}
              title={item.title}
            ></AnomalyDetection>
          ))}
        </div>
        <div class='ai-settings-set-footer'>
          <bk-button
            class='mr10'
            theme='primary'
            on-click={this.handleSubmit}
          >
            {this.$t('保存')}
          </bk-button>
          <bk-button
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
