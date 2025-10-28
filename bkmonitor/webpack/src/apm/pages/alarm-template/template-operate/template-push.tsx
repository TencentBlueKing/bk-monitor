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

import { applyStrategyTemplate } from 'monitor-api/modules/model';
import { random } from 'monitor-common/utils';

import { getCheckStrategyTemplate, getCompareStrategyTemplate } from '../service/detail';
import RelationServiceTable from './relation-service-table';

import type { IRelationService, TCompareData } from './typings';

import './template-push.scss';

interface IProps {
  metricFunctions?: any[];
  params?: Record<string, any>;
  show?: boolean;
  onShowChange?: (v: boolean) => void;
  onShowDetails?: (v: Record<string, any>) => void;
  onSuccess?: () => void;
}

@Component
export default class TemplatePush extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) params: Record<string, any>;
  @Prop({ default: () => [] }) metricFunctions: any[];

  loading = false;
  relationService: IRelationService[] = [];

  compareDataMap = new Map<string, TCompareData>();

  selectKeys = [];
  submitLoading = false;

  @Watch('show')
  handleWatchShowChange(v: boolean) {
    this.loading = false;
    this.submitLoading = false;
    if (v) {
      this.getCheckStrategyTemplate();
    } else {
      this.relationService = [];
      this.compareDataMap.clear();
      this.selectKeys = [];
    }
  }

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }

  handleSubmit() {
    if (this.selectKeys.length) {
      this.submitLoading = true;
      const services = [];
      const sets = new Set(this.selectKeys);
      for (const item of this.relationService) {
        if (sets.has(item.key)) {
          services.push(item.service_name);
        }
      }
      const params = {
        app_name: this.params?.app_name,
        service_names: Array.from(new Set(services)),
        strategy_template_ids: this.params?.strategy_template_ids,
      };
      applyStrategyTemplate(params)
        .then(() => {
          this.$bkMessage({
            message: this.$t('下发成功'),
            theme: 'success',
          });
          this.handleShowChange(false);
          this.$emit('success');
        })
        .catch(() => {
          this.$bkMessage({
            message: this.$t('下发失败'),
            theme: 'error',
          });
        })
        .finally(() => {
          this.submitLoading = false;
        });
    }
  }

  getCheckStrategyTemplate() {
    this.loading = true;
    getCheckStrategyTemplate({
      strategy_template_ids: this.params?.strategy_template_ids,
      app_name: this.params?.app_name,
    })
      .then(data => {
        this.relationService = (data?.list || []).map(item => ({
          ...item,
          key: random(8),
        }));
      })
      .finally(() => {
        this.loading = false;
      });
  }

  async getCompareStrategyTemplate(params: { service_name: string; strategy_template_id: number }) {
    const key = `${params.service_name}_____${params.strategy_template_id}`;
    if (this.compareDataMap.has(key)) {
      return this.compareDataMap.get(key);
    }
    const data = await getCompareStrategyTemplate({
      app_name: this.params?.app_name,
      ...params,
    }).catch(() => null);
    if (data) {
      this.compareDataMap.set(key, data);
    }
    return data;
  }

  handleChangeCheckKeys(selectKeys: string[]) {
    this.selectKeys = Array.from(new Set(selectKeys));
  }

  handleGoStrategy(id) {
    if (id) {
      window.open(location.href.replace(location.hash, `#/strategy-config/detail/${id}`));
    }
  }

  handleShowDetails(id: number) {
    this.$emit('showDetails', {
      id,
      app_name: this.params?.app_name,
    });
  }

  render() {
    return (
      <bk-sideslider
        width={1000}
        ext-cls={'template-push-side-component'}
        before-close={() => {
          this.handleShowChange(false);
        }}
        isShow={this.show}
        quick-close
      >
        <div
          class='template-push-header'
          slot='header'
        >
          <span class='header-left'>
            <span class='header-title'>{this.$t('下发')}</span>
            <span class='split-line' />
            <span class='header-desc'>{this.params?.name || '--'}</span>
          </span>
        </div>
        <div
          class='template-push-content'
          slot='content'
        >
          <RelationServiceTable
            getCompareData={this.getCompareStrategyTemplate}
            loading={this.loading}
            metricFunctions={this.metricFunctions}
            relationService={this.relationService}
            onChangeCheckKeys={this.handleChangeCheckKeys}
            onGoStrategy={this.handleGoStrategy}
            onShowDetails={this.handleShowDetails}
          />
        </div>
        <div
          class='template-push-footer'
          slot='footer'
        >
          <bk-button
            class='mr-8'
            disabled={!this.selectKeys.length}
            loading={this.submitLoading}
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.$t('一键生成')}
          </bk-button>
          <bk-button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </div>
      </bk-sideslider>
    );
  }
}
