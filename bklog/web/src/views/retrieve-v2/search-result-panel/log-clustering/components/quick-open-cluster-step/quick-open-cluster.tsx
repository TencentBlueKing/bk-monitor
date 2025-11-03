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

import { Component, Prop, Emit, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import $http from '../../../../../../api';
import clusterImg from '../../../../../../images/cluster-img/cluster.png';
import FilterRule from './filter-rule';

import type { From } from 'bk-magic-vue';

import './quick-open-cluster.scss';

interface IProps {
  totalFields: any[];
}

const { $i18n } = window.mainComponent;

@Component
export default class QuickOpenCluster extends tsc<IProps> {
  @Prop({ type: Array, required: true }) totalFields: any[];
  @Prop({ type: Object, required: true }) retrieveParams: object;
  @Ref('quickClusterFrom') quickClusterFromRef: From;
  @Ref('filterRule') filterRuleRef;

  isShowDialog = false;
  formData = {
    clustering_fields: '',
    filter_rules: [],
  };
  cloneFormData = null;
  confirmLading = false;
  formRules = {
    clustering_fields: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
  };
  popoverInstance = null;

  get clusterField() {
    return this.totalFields
      .filter(item => item.is_analyzed)
      .map(el => {
        const { field_name: id, field_alias: alias } = el;
        return { id, name: alias ? `${id}(${alias})` : id };
      });
  }

  get indexId() {
    return window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId;
  }

  get bkBizId() {
    return this.$store.state.bkBizId;
  }

  get datePickerValue() {
    const { start_time = 'now-15m', end_time = 'now' } = this.$store.state.indexItem;
    return [start_time, end_time];
  }

  @Emit('cluster-created')
  handleCreateCluster() {
    return true;
  }

  @Watch('formData.clustering_fields')
  handleClusteringFields(fieldName) {
    if (this.formData.filter_rules.length) {
      for (const rule of this.formData.filter_rules) {
        const targetField = this.totalFields.find(f => f.field_name === fieldName);
        Object.assign(rule, { ...targetField, fields_name: targetField.field_name });
      }
    }
  }

  handleAccessCluster() {
    this.isShowDialog = true;
  }
  async handleConfirmSubmit() {
    const isRulePass = await this.filterRuleRef.handleCheckRuleValidate();
    if (!isRulePass) {
      return;
    }
    this.quickClusterFromRef.validate().then(async () => {
      this.confirmLading = true;
      try {
        const data = {
          bk_biz_id: this.bkBizId,
          clustering_fields: this.formData.clustering_fields,
          filter_rules: this.formData.filter_rules
            .filter(item => item.value.length)
            .map(item => ({
              fields_name: item.fields_name,
              logic_operator: item.logic_operator,
              op: item.op,
              value: item.value[0],
            })),
        };
        const res = await $http.request('retrieve/createClusteringConfig', {
          params: {
            index_set_id: this.indexId,
          },
          data,
        });
        if (res.code === 0) {
          // 若是从未弹窗过的话，打开更多聚类的弹窗
          const clusterPopoverState = localStorage.getItem('CLUSTER_MORE_POPOVER');
          if (!clusterPopoverState) {
            const dom = document.querySelector('#more-operator');
            dom?.addEventListener('popoverShowEvent', this.operatorTargetEvent);
            dom?.dispatchEvent(new Event('popoverShowEvent'));
            localStorage.setItem('CLUSTER_MORE_POPOVER', 'true');
          }
          this.isShowDialog = false;
          this.handleCreateCluster();
        }
      } catch (error) {
        console.warn(error);
      } finally {
        this.confirmLading = false;
      }
    });
  }
  /** 聚类提示弹窗事件 */
  operatorTargetEvent(event: Event) {
    this.popoverDestroy();
    this.popoverInstance = this.$bkPopover(event.target, {
      content: `<div style='width: 230px; padding: 4px 8px; line-height: 18px;'>
          <div style='display: flex; justify-content: space-between'>
            <i
              class='bk-icon icon-info'
              style='color: #979BA5; font-size: 14px; margin: 2px 4px 0 0;'>
            </i>
            <div style='font-size: 12px; color: #63656E;'>
              <p>${$i18n.t('可在更多操作中管理日志聚类，包含以下能力：')}</p>
              <p>1. ${$i18n.t('启用或停用日志聚类')}</p>
              <p>2. ${$i18n.t('正则管理')}</p>
            </div>
          </div>
          <div style='display: flex; justify-content: flex-end; margin-top: 8px;'>
            <div
              id='i-know'
              style='color: #FFF;
              background: #3A84FF;
              padding: 4px 8px;
              border-radius: 2px;
              font-size: 12px;
              cursor: pointer;'>
              ${$i18n.t('知道了')}
            </div>
          </div>
        </div>`,
      arrow: true,
      trigger: 'manual',
      theme: 'light',
      placement: 'bottom-end',
      hideOnClick: false,
      interactive: true,
      allowHTML: true,
      distance: -10,
    });
    this.popoverInstance.show(500);
    const iKnowDom = document.querySelector('#i-know');
    iKnowDom.addEventListener('click', () => {
      this.popoverDestroy();
      const dom = document.querySelector('#more-operator');
      dom.removeEventListener('customEvent', this.operatorTargetEvent);
    });
  }
  popoverDestroy() {
    this.popoverInstance?.hide();
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }
  handleOpenDialog(v: boolean) {
    if (v) {
      this.cloneFormData = structuredClone(this.formData);
      if (this.clusterField[0]?.id) {
        this.formData.clustering_fields = this.clusterField[0]?.id || '';
        const targetField = this.totalFields.find(f => f.field_name === this.clusterField[0]?.id);
        this.formData.filter_rules.push({
          ...targetField,
          op: 'LIKE',
          value: ['%ERROR%'],
          fields_name: targetField.field_name,
        });
      }
    } else {
      this.formData = this.cloneFormData;
    }
  }
  render() {
    const accessDialogSlot = () => (
      <bk-dialog
        width='640'
        ext-cls='cluster-set-dialog'
        v-model={this.isShowDialog}
        confirm-fn={this.handleConfirmSubmit}
        header-position='left'
        loading={this.confirmLading}
        mask-close={false}
        render-directive='if'
        theme='primary'
        title={$i18n.t('日志聚类接入')}
        on-value-change={this.handleOpenDialog}
      >
        <bk-alert type='info'>
          <div slot='title'>
            {$i18n.t('大量的日志会导致聚类结果过多，建议使用过滤规则将重要日志进行聚类；如：仅聚类 warn 日志')}
          </div>
        </bk-alert>
        <bk-form
          ref='quickClusterFrom'
          form-type='vertical'
          {...{
            props: {
              model: this.formData,
              rules: this.formRules,
            },
          }}
        >
          <bk-form-item
            label={$i18n.t('聚类字段')}
            property='clustering_fields'
            required
          >
            <div class='setting-item'>
              <bk-select
                style='width: 482px'
                v-model={this.formData.clustering_fields}
                clearable={false}
              >
                {this.clusterField.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
              <span
                v-bk-tooltips={{
                  content: $i18n.t('只能基于一个字段进行聚类，并且字段是为text的分词类型，默认为log字段'),
                  placements: ['right'],
                }}
              >
                <span class='bk-icon icon-info' />
              </span>
            </div>
          </bk-form-item>
          <bk-form-item
            label={$i18n.t('过滤规则')}
            property='filter_rules'
          >
            <FilterRule
              ref='filterRule'
              v-model={this.formData.filter_rules}
              date-picker-value={this.datePickerValue}
              retrieve-params={this.retrieveParams}
              total-fields={this.totalFields}
            />
          </bk-form-item>
          {/* <bk-form-item
            label={$i18n.t('告警屏蔽时间')}
            property='threshold'
            required
          >
            <bk-input
              class='shield-time'
              type='number'
            >
              <div
                slot='append'
                class='group-text'
              >
                {$i18n.t('天')}
              </div>
            </bk-input>
            <div class='alert-tips'>
              <i class='bk-icon icon-info'></i>
              <span>{$i18n.t('此为系统默认告警屏蔽时间，以防止聚类初期的告警风暴')}</span>
            </div>
          </bk-form-item> */}
        </bk-form>
      </bk-dialog>
    );
    return (
      <div class='quick-open-cluster-container'>
        {accessDialogSlot()}
        <div class='left-box'>
          <h2>{$i18n.t('快速开启日志聚类')}</h2>
          <p>
            {$i18n.t('日志聚类可以通过智能分析算法，将相似度高的日志进行快速的汇聚分析，提取日志 Pattern 并进行展示')}
          </p>
          <h3>{$i18n.t('日志聚类的优势')}</h3>
          <p>1. {$i18n.t('有利于发现日志中的规律和共性问题，方便从海量日志中排查问题，定位故障')}</p>
          <p>
            2. {$i18n.t('可从海量日志中，提取共性部分同时保留独立信息以便于减少存储成本，最多可减少 10% 的存储成本')}
          </p>
          <p>3. {$i18n.t('当版本变更时，可快速定位变更后新增问题')}</p>
          <bk-button
            style='margin-top: 32px;'
            theme='primary'
            onClick={this.handleAccessCluster}
          >
            {$i18n.t('接入日志聚类')}
          </bk-button>
        </div>
        <div class='right-box'>
          {/** biome-ignore lint/performance/noImgElement: reason */}
          {/** biome-ignore lint/nursery/useImageSize: reason */}
          <img
            alt='日志聚类'
            src={clusterImg}
          />
        </div>
      </div>
    );
  }
}
