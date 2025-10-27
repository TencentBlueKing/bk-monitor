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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';

import TemplateFormDetail from '../components/template-form/template-form-detail';
import { getAlarmTemplateDetail, getAlertsStrategyTemplate } from '../service';
import AlertServiceTable from './alert-service-table';
import { type IAlertStrategiesItem, type IStrategiesItem, type TDetailsTabValue, detailsTabColumn } from './typings';

import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import './template-details.scss';

interface IProps {
  defaultTab?: TDetailsTabValue;
  metricFunctions?: any[];
  params?: Record<string, any>;
  show?: boolean;
  onShowChange?: (v: boolean) => void;
  onShowEdit?: (v: Record<string, any>) => void;
  onShowPush?: (v: Record<string, any>) => void;
}

@Component
export default class TemplateDetails extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ default: () => [] }) metricFunctions!: any[];
  @Prop({ type: Object, default: () => ({}) }) params: Record<string, any>;
  @Prop({ default: detailsTabColumn.basic }) defaultTab?: TDetailsTabValue;

  tabList = [
    {
      label: window.i18n.t('基本信息'),
      name: detailsTabColumn.basic,
    },
    {
      label: `${window.i18n.t('关联服务')} & ${window.i18n.t('告警')}`,
      name: detailsTabColumn.service,
    },
  ];
  tabActive: TDetailsTabValue = detailsTabColumn.basic;

  templateDetail = null;

  variablesList: VariableModelType[] = [];

  // 关联服务 & 告警 数据
  alertStrategies: IAlertStrategiesItem[] = [];
  // 关联服务 & 告警 表格数据
  strategies: IStrategiesItem[] = [];
  // 关联服务 & 告警 表格数据加载状态
  serviceLoading = false;
  // 基本信息加载状态
  basicLoading = false;

  @Watch('show')
  handleWatchShowChange(v: boolean) {
    if (v) {
      this.getAlertsStrategyTemplate();
      this.getAlarmTemplateDetail();
      this.tabActive = this.defaultTab;
    }
  }

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }

  handleChangeTab(name) {
    this.tabActive = name;
  }

  handleShowTemplatePush() {
    this.$emit('showPush', {
      strategy_template_ids: this.params?.ids,
      app_name: this.params?.app_name,
      name: this.params?.name,
    });
  }
  handleShowTemplateEdit() {
    this.$emit('showEdit', {
      app_name: this.params?.app_name,
      id: this.params?.ids?.[0],
    });
  }

  getAlertsStrategyTemplate() {
    this.serviceLoading = true;
    getAlertsStrategyTemplate({
      app_name: this.params?.app_name,
      ids: this.params?.ids,
      need_strategies: true,
    })
      .then(data => {
        this.alertStrategies = data?.list || [];
        this.getStrategies();
      })
      .finally(() => {
        this.serviceLoading = false;
      });
  }

  getAlarmTemplateDetail() {
    this.basicLoading = true;
    getAlarmTemplateDetail({ id: this.params?.ids?.[0], app_name: this.params?.app_name })
      .then(data => {
        this.templateDetail = data.detailData;
        this.variablesList = data?.variablesList || [];
      })
      .finally(() => {
        this.basicLoading = false;
      });
  }

  getStrategies() {
    const strategies = [];
    for (const item of this.alertStrategies) {
      if (item?.strategies?.length) {
        strategies.push(...item.strategies);
      }
    }
    this.strategies = strategies;
  }

  handleGoService(serviceName: string) {
    const { app_name: appName } = this.params;
    const { from, to } = this.$route.query;
    let urlStr = `${window.__BK_WEWEB_DATA__?.baseroute || ''}service/?filter-service_name=${serviceName}&filter-app_name=${appName}`;
    urlStr += `&from=${from || DEFAULT_TIME_RANGE[0]}&to=${to || DEFAULT_TIME_RANGE[1]}`;
    const { href } = this.$router.resolve({
      path: urlStr,
    });
    const url = location.href.replace(location.pathname, '/').replace(location.hash, '') + href;
    window.open(url);
  }

  handleGoAlarm(id: string) {
    const { from, to } = this.$route.query;
    window.open(
      location.href.replace(
        location.hash,
        `#/event-center?queryString=${`strategy_id : "${id}"`}&activeFilterId=NOT_SHIELDED_ABNORMAL&from=${from || DEFAULT_TIME_RANGE[0]}&to=${to || DEFAULT_TIME_RANGE[1]}`
      )
    );
  }

  handleGoStrategy(id) {
    if (id) {
      window.open(location.href.replace(location.hash, `#/strategy-config/detail/${id}`));
    }
  }

  handleUnApply(params: { service_names: string[]; strategy_ids: number[] }) {
    console.log(params);
    const h = this.$createElement;
    this.$bkInfo({
      type: 'warning',
      title: this.$t('确定解除关联'),
      okText: this.$t('确定'),
      width: 480,
      closeFn: () => {
        return true;
      },
      cancelFn: () => {
        return true;
      },
      confirmLoading: true,
      confirmFn: async () => {
        await new Promise(resolve => {
          setTimeout(() => {
            resolve(true);
          }, 1500);
        });
        this.$bkMessage({
          // this.$t('解除关联失败’)
          message: this.$t('解除关联成功'),
          theme: 'success',
        });
        this.getAlertsStrategyTemplate();
        return true;
      },
      subHeader: h(
        'div',
        {
          style: {
            'min-height': '46px',
            background: '#F5F7FA',
            display: 'flex',
            alignItems: 'center',
            color: '#4D4F56',
            justifyContent: 'center',
          },
        },
        this.$t('解除关联后，{0}服务下将不会配置该策略', [params.service_names.join('、')]) as string
      ),
      cancelText: this.$t('取消'),
    });
  }

  render() {
    const tabContent = () => {
      switch (this.tabActive) {
        case detailsTabColumn.basic:
          return this.basicLoading ? (
            <div class='basic-loading'>
              {new Array(6).fill(0).map((_, index) => (
                <div
                  key={index}
                  class='basic-loading-item'
                >
                  <div class='skeleton-element item-top' />
                  <div class='skeleton-element item-bottom' />
                </div>
              ))}
            </div>
          ) : (
            <TemplateFormDetail
              data={this.templateDetail}
              metricFunctions={this.metricFunctions}
              variablesList={this.variablesList}
            />
          );
        case detailsTabColumn.service:
          return (
            <div class='relation-service-alarm'>
              {this.serviceLoading ? (
                <TableSkeleton type={4} />
              ) : (
                <AlertServiceTable
                  strategies={this.strategies}
                  onGoAlarm={this.handleGoAlarm}
                  onGoService={this.handleGoService}
                  onGoStrategy={this.handleGoStrategy}
                  onGoTemplatePush={this.handleShowTemplatePush}
                  onUnApply={this.handleUnApply}
                />
              )}
            </div>
          );
        default:
          return undefined;
      }
    };

    return (
      <bk-sideslider
        width={640}
        ext-cls={'template-details-side-component'}
        before-close={() => {
          this.handleShowChange(false);
        }}
        isShow={this.show}
        quick-close
      >
        <div
          class='template-details-header'
          slot='header'
        >
          <span class='header-left'>
            <span class='header-title'>{this.$t('模板详情')}</span>
            <span class='split-line' />
            <span
              class='header-desc'
              v-bk-overflow-tips
            >
              {this.templateDetail?.name || this.params?.name || '--'}
            </span>
          </span>
          <span class='header-right'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={() => {
                this.handleShowTemplatePush();
              }}
            >
              {this.$t('下发')}
            </bk-button>
            <bk-button
              theme='primary'
              outline
              onClick={() => {
                this.handleShowTemplateEdit();
              }}
            >
              {this.$t('编辑')}
            </bk-button>
          </span>
        </div>
        <div
          class='template-details-content'
          slot='content'
        >
          <div class='tabs'>
            {this.tabList.map(item => (
              <div
                key={item.name}
                class={['tab-item', { active: this.tabActive === item.name }]}
                onClick={() => this.handleChangeTab(item.name)}
              >
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div class='tab-content'>{tabContent()}</div>
        </div>
      </bk-sideslider>
    );
  }
}
