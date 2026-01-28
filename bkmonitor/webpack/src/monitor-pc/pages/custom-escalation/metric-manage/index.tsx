/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import {
  customTimeSeriesDetail,
  type getCustomTsFields,
  modifyCustomTimeSeries,
  type ICustomTimeSeriesDetail,
} from '../service';

import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import IndicatorDimension from './components/indicator-dimension';

import BasicInfo from './components/basic-info';
import HelpInfo from './components/help-info';

import './index.scss';

/**
 * 自定义时序字段类型定义
 */
export type ICustomTsFields = ServiceReturnType<typeof getCustomTsFields>;

/**
 * 自定义指标管理详情页组件
 * 用于展示和管理自定义时序指标的详细信息，包括基本信息、指标列表、维度列表等
 */
@Component
export default class CustomEscalationDetailNew extends tsc<any, any> {
  loading = false; // 加载状态
  copyIsPlatform = false; // 是否为平台指标、事件
  helpPanelStorageKey = '__custom_escalation_help_panel__';
  // 是否显示右侧帮助栏（默认显示，除非明确设置为 'false'）
  isShowHelpPanel = (localStorage.getItem(this.helpPanelStorageKey) ?? 'true') === 'true';

  // 详情数据
  detailData = {
    time_series_group_id: 0,
    bk_data_id: 0,
    access_token: '',
    name: '',
    scenario: '',
    scenario_display: [],
    data_label: '',
    is_platform: false,
    protocol: '',
    last_time: '',
    auto_discover: false,
  } as ICustomTimeSeriesDetail;

  /**
   * 组件创建时的初始化
   */
  async created(): Promise<void> {
    await this.getDetailData();
  }

  /**
   * 获取详情数据
   * @param needLoading 是否显示加载状态
   */
  async getDetailData(needLoading = true): Promise<void> {
    this.loading = needLoading;
    try {
      const detailData = await customTimeSeriesDetail({
        with_metrics: false, // 不获取指标数据，用 get ts fields 获取
        time_series_group_id: Number(this.$route.params.id),
      });

      this.detailData = detailData || this.detailData;
      this.copyIsPlatform = this.detailData.is_platform ?? false;
    } catch (error) {
      console.error('获取详情数据失败:', error);
    } finally {
      this.loading = false;
    }
  }

  /**
   * 编辑字段通用方法
   * @param props 字段属性
   * @param showMsg 是否显示成功消息
   */
  async handleEditFiled(props: Record<string, any>, showMsg = true) {
    this.loading = true;
    try {
      const params = {
        time_series_group_id: this.detailData.time_series_group_id,
        ...props,
      };
      const data = await modifyCustomTimeSeries(params);
      if (data && showMsg) {
        this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      }
    } finally {
      this.loading = false;
    }
  }

  /**
   * 处理路由跳转
   * 跳转到自定义指标查看页面
   */
  handleJump(): void {
    this.$router.push({
      name: 'custom-escalation-view',
      params: { id: String(this.detailData.time_series_group_id) },
      query: { name: this.detailData.name },
    });
  }

  /**
   * 处理显示帮助面板
   */
  handleShowHelpPanel(): void {
    this.isShowHelpPanel = !this.isShowHelpPanel;
    localStorage.setItem(this.helpPanelStorageKey, this.isShowHelpPanel.toString());
  }

  /**
   * 渲染组件
   * 包含导航栏、提示条、基本信息、指标维度列表和帮助面板
   */
  render() {
    return (
      <div
        class='custom-detail-page-component'
        v-bkloading={{ isLoading: this.loading }}
      >
        {/* 导航栏 */}
        <CommonNavBar
          class='common-nav-bar-single'
          needBack={true}
          routeList={this.$store.getters.navRouteList}
        >
          <div
            class='custom'
            slot='custom'
          >
            <span class='dec'>{this.$t('自定义指标管理')}</span>
            <span class='title'>{this.detailData.data_label || '-'}</span>
          </div>
          <div slot='append'>
            <span
              class={[this.isShowHelpPanel ? 'active' : '', 'icon-monitor icon-audit']}
              onClick={this.handleShowHelpPanel}
            />
          </div>
        </CommonNavBar>
        {/* 提示条 */}
        <bk-alert class='hint-alert'>
          <i18n
            slot='title'
            path='数据上报好了，去 {0}'
          >
            <span
              style='color: #3a84ff; cursor: pointer'
              onClick={this.handleJump}
            >
              {this.$t('查看数据')}
            </span>
          </i18n>
        </bk-alert>
        <div class='custom-detail-page'>
          <div class='custom-detail'>
            {/* 基本信息 */}
            <BasicInfo
              detailData={this.detailData}
              copyIsPlatform={this.copyIsPlatform}
              onEditFiled={this.handleEditFiled}
            />
            {/* 指标/维度列表 */}
            <div class='custom-detail-page-table'>
              <IndicatorDimension
                isAPMPage={false}
                metricId={this.detailData.time_series_group_id}
                metricName={this.detailData.name}
              />
            </div>
          </div>
          {/* 右侧帮助面板 */}
          <HelpInfo
            detailData={this.detailData}
            isShow={this.isShowHelpPanel}
          />
        </div>
      </div>
    );
  }
}
