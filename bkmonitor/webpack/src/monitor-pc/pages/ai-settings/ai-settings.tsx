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
import { getBusinessTargetDetail } from 'monitor-api/modules/commons';
import { transformDataKey } from 'monitor-common/utils/utils';

import IntelligentModelsStore, { IntelligentModelsType } from '../../store/modules/intelligent-models';
// import HistoryDialog from '../../components/history-dialog/history-dialog';
import StrategyTargetTable from '../strategy-config/strategy-config-detail/strategy-config-detail-table.vue';
import { handleSetTargetDesc } from './components/common';

import type { AnomalyDetectionBase, SchemeItem } from './types';

import './ai-settings.scss';

interface DetectionItem {
  data: AnomalyDetectionBase;
  name?: string;
  type?: string;
  excludeTargetDetail?: {
    objType: string;
    targetTable: any[];
    targetType: string;
  };
  excludeTargetText?: {
    message: string;
    messageCount: number;
    subMessage: string;
    subMessageCount: number;
  };
}

type DetectionType = 'sceneIntelligent' | 'singleMetric';

@Component
export default class AiSettingsPage extends tsc<object> {
  loading = false;
  /** 单指标异常检测列表 */
  schemeList: SchemeItem[] = [];
  /** 场景异常智能检测列表 */
  multipleSchemeList: SchemeItem[] = [];

  textMap = {
    host: '主机',
  };

  /** 单指标异常检测 */
  singleMetric: DetectionItem = {
    data: {
      default_plan_id: 0,
    },
  };

  /** 场景异常智能检测 */
  sceneIntelligent: DetectionItem[] = [];

  excludeTargetDialog = {
    show: false,
    tableData: [],
    objType: '',
    targetType: '',
  };

  mounted() {
    this.loading = true;
    Promise.all([this.getSchemeList(), this.getAiSetting()]).finally(() => {
      this.loading = false;
    });
  }

  /**
   * 获取默认方案列表用于展示详细信息
   */
  async getSchemeList() {
    // 获取单指标
    this.schemeList = await IntelligentModelsStore.getListIntelligentModels({
      algorithm: IntelligentModelsType.IntelligentDetect,
    });
    // 获取多场景
    this.multipleSchemeList = await IntelligentModelsStore.getListIntelligentModels({
      algorithm: IntelligentModelsType.MultivariateAnomalyDetection,
    });
  }

  /** *
   *  获取ai设置
   */
  async getAiSetting() {
    const aiSetting = await fetchAiSetting();
    if (!aiSetting) return;
    this.singleMetric.data = aiSetting.kpi_anomaly_detection;
    this.sceneIntelligent = Object.keys(aiSetting.multivariate_anomaly_detection).map(key => {
      const detection = aiSetting.multivariate_anomaly_detection[key];
      return {
        name: this.$tc(this.textMap[key]),
        type: key,
        data: detection,
        excludeTargetText: null,
      };
    });
    this.getTargetDetail();
  }

  /* 获取关闭检测对象的详情信息 */
  getTargetDetail() {
    for (const detection of this.sceneIntelligent) {
      if (detection.data.exclude_target?.[0]?.[0]?.value?.length) {
        getBusinessTargetDetail({
          target: detection.data.exclude_target,
        })
          .then(data => {
            if (data) {
              detection.excludeTargetDetail = {
                targetTable: transformDataKey(data.target_detail),
                targetType: data.node_type,
                objType: data.instance_type,
              };
              detection.excludeTargetText = handleSetTargetDesc(
                data.target_detail,
                data.node_type,
                data.instance_type,
                data.node_count,
                data.instance_count
              );
              return;
            }
          })
          .catch(() => null);
      }
    }
  }

  /** 关闭通知对象弹窗 */
  handleShowTargetDetail(item: DetectionItem) {
    this.excludeTargetDialog.show = true;
    this.excludeTargetDialog.tableData = item.excludeTargetDetail?.targetTable || [];
    this.excludeTargetDialog.objType = item.excludeTargetDetail?.objType || '';
    this.excludeTargetDialog.targetType = item.excludeTargetDetail?.targetType || '';
  }

  handleJump() {
    this.$router.push({
      name: 'ai-settings-set',
    });
  }

  renderForm(item: DetectionItem, type: DetectionType) {
    const schemeList = type === 'singleMetric' ? this.schemeList : this.multipleSchemeList;

    const formatValue = val => {
      if (this.loading) {
        return <div class='skeleton-element' />;
      }
      return val || '--';
    };

    /** 目前单指标异常检测只有这一个信息项 */
    if (type === 'singleMetric') {
      return (
        <div class='detail-form'>
          <div class='form-item'>
            <div class='label'>{this.$t('默认方案')}:</div>
            <div class='value'>
              {formatValue(schemeList.find(scheme => scheme.id === item.data.default_plan_id)?.name)}
            </div>
          </div>
        </div>
      );
    }

    return (
      <div class='detail-form'>
        {/* <div class='form-item'>
          <div class='label'>{this.$t('是否启用')}:</div>
          <div class='value'>{formatValue(this.$t(item.data.is_enabled ? '是' : '否'))}</div>
        </div>
        <div class='form-item'>
          <div class='label'>{this.$t('关闭通知的对象')}:</div>
          <div class='value'>
            {formatValue(
              item.excludeTargetText ? (
                <span
                  class='target-overview'
                  onClick={() => {
                    this.handleShowTargetDetail(item);
                  }}
                >
                  {item.excludeTargetText?.messageCount > 0 ? (
                    <i18n path={item.excludeTargetText.message}>
                      <span class='host-count'> {item.excludeTargetText.messageCount} </span>
                    </i18n>
                  ) : (
                    '--'
                  )}
                  {item.excludeTargetText?.subMessageCount > 0 ? (
                    <span>
                      (
                      <i18n path={item.excludeTargetText.subMessage}>
                        <span class='host-count'> {item.excludeTargetText.subMessageCount} </span>
                      </i18n>
                      )
                    </span>
                  ) : null}
                </span>
              ) : (
                '--'
              )
            )}
          </div>
        </div> */}
        <div class='form-item'>
          <div class='label'>{this.$t('默认方案')}:</div>
          <div class='value'>
            {formatValue(schemeList.find(scheme => scheme.id === item.data.default_plan_id)?.name)}
          </div>
        </div>
        {/* <div class='form-item'>
          <div class='label'>{this.$t('默认敏感度')}:</div>
          <div class='value'>{formatValue(item.data.default_sensitivity ?? '--')}</div>
        </div> */}
      </div>
    );
  }

  render() {
    return (
      <div class='ai-settings-page'>
        {/* <bk-alert
          title='错误的提示文字'
          type='error'
          closable
        ></bk-alert> */}

        <div class='ai-settings-page-content'>
          <div class='single-metric-detection'>
            <div class='header'>
              <div class='title'>{this.$t('单指标异常检测')}</div>
              <div class='btns'>
                <bk-button
                  class='edit-btn'
                  theme='primary'
                  outline
                  onClick={this.handleJump}
                >
                  {this.$t('编辑')}
                </bk-button>
                {/* <HistoryDialog /> */}
              </div>
            </div>
            {this.renderForm(this.singleMetric, 'singleMetric')}
          </div>

          <div class='scene-detection'>
            <div class='title'>{this.$t('场景智能异常检测')}</div>
            {this.loading ? (
              <div class='skeleton-element empty-scene-detection' />
            ) : (
              this.sceneIntelligent.map(item => (
                <div
                  key={item.name}
                  class='detection-item'
                >
                  <div class='name'>{item.name}</div>
                  {this.renderForm(item, 'sceneIntelligent')}
                </div>
              ))
            )}
          </div>
        </div>

        <bk-dialog
          width='1100'
          ext-cls='target-table-wrap'
          v-model={this.excludeTargetDialog.show}
          header-position='left'
          need-footer={false}
          show-footer={false}
          title={this.$t('关闭目标')}
          on-change={v => {
            this.excludeTargetDialog.show = v;
          }}
        >
          <StrategyTargetTable
            objType={this.excludeTargetDialog.objType}
            tableData={this.excludeTargetDialog.tableData}
            targetType={this.excludeTargetDialog.targetType}
          />
        </bk-dialog>
      </div>
    );
  }
}
