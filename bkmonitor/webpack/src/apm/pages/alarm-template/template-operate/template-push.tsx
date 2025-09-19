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

import { applyStrategyTemplate, checkStrategyTemplate, retrieveStrategyTemplate } from 'monitor-api/modules/model';
import { random } from 'monitor-common/utils';

import RelationServiceTable from './relation-service-table';

import type { TemplateDetail } from '../components/template-form/typing';
import type { IRelationService } from './typings';

import './template-push.scss';

interface IProps {
  params?: Record<string, any>;
  show?: boolean;
  showAgain?: boolean;
  onShowChange?: (v: boolean) => void;
}

@Component
export default class TemplatePush extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) params: Record<string, any>;
  /* 再次下发已关联的服务，相当于“同步”操作  模板保存成功后续下发步骤样式 */
  @Prop({ type: Boolean, default: false }) showAgain: boolean;

  relationService: IRelationService[] = [];

  strategyDetailMap = new Map<number, TemplateDetail>();

  selectKeys = [];
  submitLoading = false;

  @Watch('show')
  handleWatchShowChange(v: boolean) {
    if (v) {
      this.getCheckStrategyTemplate();
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
        extra: [],
        global: {},
      };
      applyStrategyTemplate(params)
        .then(() => {
          this.$bkMessage({
            message: this.$t('下发成功'),
            theme: 'success',
          });
          this.handleShowChange(false);
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
    checkStrategyTemplate({
      strategy_template_ids: this.params?.strategy_template_ids,
      // service_names: this.params?.service_names,
      app_name: this.params?.app_name,
    }).then(data => {
      this.relationService = (data?.list || []).map(item => ({
        ...item,
        key: random(8),
      }));
    });
  }

  async getStrategyDetails(ids: (number | string)[]) {
    const fn = id => {
      return new Promise((resolve, reject) => {
        retrieveStrategyTemplate(id, {
          strategy_template_id: id,
          app_name: this.params?.app_name,
        })
          .then(data => {
            this.strategyDetailMap.set(id, data);
            resolve(data);
          })
          .catch(reject);
      });
    };
    const promiseList = [];
    for (const id of ids) {
      if (!this.strategyDetailMap.has(id)) {
        promiseList.push(fn(id));
      }
    }
    await Promise.all(promiseList);
    return Promise.resolve(this.strategyDetailMap);
  }

  handleChangeCheckKeys(selectKeys: string[]) {
    this.selectKeys = Array.from(new Set(selectKeys));
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
            getStrategyDetails={this.getStrategyDetails}
            relationService={this.relationService}
            showAgain={this.showAgain}
            onChangeCheckKeys={this.handleChangeCheckKeys}
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
          <bk-button>{this.$t('取消')}</bk-button>
        </div>
      </bk-sideslider>
    );
  }
}
