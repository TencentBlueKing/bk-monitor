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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { fetchAiSetting, saveAiSetting } from 'monitor-api/modules/aiops';
import { getBusinessTargetDetail } from 'monitor-api/modules/commons';
import { listIntelligentModels } from 'monitor-api/modules/strategies';
import { transformDataKey } from 'monitor-common/utils/utils';

import StrategyTargetTable from '../strategy-config/strategy-config-detail/strategy-config-detail-table.vue';

import AnomalyDetection from './components/anomaly-detection';
import { handleSetTargetDesc } from './components/common';
import Notification from './components/notification';
import SingleIndicator from './components/single-indicator';
import { AiSetting, SchemeItem } from './types';

import './ai-settings.scss';

@Component
export default class AiSettings extends tsc<{}> {
  @Ref('single-indicator') readonly singleIndicatorEl: SingleIndicator;
  @Ref('single-host') readonly singleIndicatorHostEl: SingleIndicator;

  loading = false;
  btnLoading = false;
  isEdit = false;
  // 单指标
  schemeList: SchemeItem[] = [];
  // 多指标场景
  multipleSchemeList: SchemeItem[] = [];

  // ai设置数据
  aiSetting: AiSetting = {
    kpi_anomaly_detection: {
      default_plan_id: 0
    },
    multivariate_anomaly_detection: {
      host: {
        default_plan_id: 0,
        default_sensitivity: 0,
        is_enabled: true,
        exclude_target: [],
        intelligent_detect: {}
      }
    }
  };

  excludeTargetDetail = {
    targets: [],
    targetTable: [],
    targetType: '',
    objType: '',
    desc: '',
    nodeCount: 0,
    instanceCount: 0,
    info: null,
    show: false
  };

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
    this.isEdit = false;
    this.loading = false;
  }

  created() {
    this.getSchemeList();
    this.getAiSetting();
  }

  /**
   * 校验表单
   */
  async handleValidate() {
    return Promise.all([this.singleIndicatorEl?.validate(), this.singleIndicatorHostEl?.validate()])
      .then(() => true)
      .catch(() => false);
  }

  /**
   *  保存操作
   */
  async handleSubmit() {
    const result = await this.handleValidate();
    if (result) {
      this.btnLoading = true;
      this.loading = true;
      const excludeTarget = this.aiSetting.multivariate_anomaly_detection.host.exclude_target;
      const excludeTargetValue = excludeTarget?.[0]?.[0]?.value || [];
      const params = {
        ...this.aiSetting,
        multivariate_anomaly_detection: {
          ...this.aiSetting.multivariate_anomaly_detection,
          host: {
            ...this.aiSetting.multivariate_anomaly_detection.host,
            exclude_target: excludeTargetValue.length ? excludeTarget : []
          }
        },
        kpi_anomaly_detection: {
          ...this.aiSetting.kpi_anomaly_detection,
          is_enabled: undefined, // 单指标异常检测需去除是否启用
          default_sensitivity: undefined
        }
      };
      await saveAiSetting(params).catch(() => (this.loading = false));
      this.btnLoading = false;
      this.loading = false;
      this.isEdit = false;
      this.$bkMessage({
        theme: 'success',
        message: this.$t('保存成功！')
      });
    }
  }

  /** *
   *   重置操作
   */

  async handleReSet() {
    this.loading = true;
    this.aiSetting = await fetchAiSetting({ bk_biz_id: 0 }).catch(() => (this.loading = false));
    this.loading = false;
  }

  handleCancel() {
    this.getAiSetting();
  }

  /* 查看状态时需要显示目标概览 */
  async getTargetDetail() {
    if (this.aiSetting.multivariate_anomaly_detection.host.exclude_target?.[0]?.[0]?.value?.length) {
      const data = await getBusinessTargetDetail({
        target: this.aiSetting.multivariate_anomaly_detection.host.exclude_target
      }).catch(() => null);
      if (data) {
        this.excludeTargetDetail = {
          ...this.excludeTargetDetail,
          targets: data.target_detail,
          targetTable: transformDataKey(data.target_detail),
          targetType: data.node_type,
          objType: data.instance_type,
          nodeCount: data.node_count,
          instanceCount: data.instance_count
        };
        this.excludeTargetDetail.desc = '';
        const info = handleSetTargetDesc(
          this.excludeTargetDetail.targets,
          this.excludeTargetDetail.targetType as any,
          this.excludeTargetDetail.objType,
          this.excludeTargetDetail.nodeCount,
          this.excludeTargetDetail.instanceCount
        );
        this.excludeTargetDetail.info = info;
      }
    } else {
      this.excludeTargetDetail.info = {
        message: '',
        messageCount: 0,
        subMessage: '',
        subMessageCount: 0
      };
    }
  }
  handleExcludeTargetChange() {
    this.getTargetDetail();
  }
  handleShowTargetDetail() {
    this.excludeTargetDetail.show = true;
  }

  render() {
    return (
      <div
        class='ai-settings'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div style={{ margin: '24px' }}>
          <AnomalyDetection
            title={this.$t('单指标异常检测')}
            showExpand={true}
          >
            <SingleIndicator
              ref='single-indicator'
              isEdit={this.isEdit}
              data={this.aiSetting.kpi_anomaly_detection}
              schemeList={this.schemeList}
              isSingle={true}
            />
          </AnomalyDetection>
          <AnomalyDetection
            title={this.$t('场景智能异常检测')}
            showExpand={true}
          >
            <AnomalyDetection
              title={this.$t('主机')}
              showExpand={true}
              theme='dark'
            >
              <SingleIndicator
                ref='single-host'
                isEdit={this.isEdit}
                data={this.aiSetting.multivariate_anomaly_detection.host}
                schemeList={this.multipleSchemeList}
              >
                <Notification
                  slot='notification'
                  isEdit={this.isEdit}
                  hostInfo={this.excludeTargetDetail.info}
                  v-model={this.aiSetting.multivariate_anomaly_detection.host.exclude_target}
                  onShowTargetDetail={this.handleShowTargetDetail}
                  onChange={this.handleExcludeTargetChange as any}
                />
              </SingleIndicator>
            </AnomalyDetection>
          </AnomalyDetection>
        </div>
        {/* 底部操作按钮 */}
        <div class='footer'>
          {this.isEdit ? (
            <span>
              <bk-button
                class='mr10'
                theme='primary'
                loading={this.btnLoading}
                on-click={this.handleSubmit}
              >
                {this.$t('保存')}
              </bk-button>
              <bk-button
                theme='default'
                onClick={this.handleReSet}
                class='mr10'
              >
                {this.$t('重置')}
              </bk-button>
              <bk-button
                theme='default'
                onClick={this.handleCancel}
              >
                {this.$t('取消')}
              </bk-button>
            </span>
          ) : (
            <bk-button
              onClick={() => (this.isEdit = true)}
              theme='primary'
            >
              {this.$t('button-编辑')}
            </bk-button>
          )}
        </div>
        {!!this.excludeTargetDetail.targetTable ? (
          <bk-dialog
            v-model={this.excludeTargetDetail.show}
            on-change={v => (this.excludeTargetDetail.show = v)}
            show-footer={false}
            header-position='left'
            need-footer={false}
            width='1100'
            title={this.$t('关闭目标')}
            ext-cls='target-table-wrap'
          >
            <StrategyTargetTable
              tableData={this.excludeTargetDetail.targetTable}
              targetType={this.excludeTargetDetail.targetType}
              objType={this.excludeTargetDetail.objType}
            ></StrategyTargetTable>
          </bk-dialog>
        ) : undefined}
      </div>
    );
  }
}
