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

import { Component, Prop, Emit, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { From } from 'bk-magic-vue';

import $http from '../../../../../../api';
import { formatDate, deepClone } from '../../../../../../common/util';
import { handleTransformToTimestamp } from '../../../../../../components/time-range/utils';
import clusterImg from '../../../../../../images/cluster-img/cluster.png';

import './quick-open-cluster.scss';

interface IProps {
  totalFields: Array<any>;
}

const { $i18n } = window.mainComponent;

@Component
export default class QuickOpenCluster extends tsc<IProps> {
  @Prop({ type: Array, required: true }) totalFields: Array<any>;
  @Prop({ type: Object, required: true }) retrieveParams: object;
  @Ref('quickClusterFrom') quickClusterFromRef: From;

  isShowDialog = false;
  conditionList = [
    // 过滤条件对比
    { id: '=', name: '=' },
    { id: '!=', name: '!=' },
    { id: 'LIKE', name: 'LIKE' },
    { id: 'NOT LIKE', name: 'NOT LIKE' },
  ];
  comparedList = [
    { id: 'and', name: 'AND' },
    { id: 'or', name: 'OR' },
  ];
  operateIndex = 0;
  formData = {
    clustering_fields: '',
    filter_rules: [],
    new_cls_strategy_enable: true,
    normal_strategy_enable: false,
  };
  cloneFormData = null;
  formRules = {
    clustering_fields: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
    filter_rules: [
      {
        validator: this.checkFilterRules,
        trigger: 'blur',
      },
    ],
  };
  popoverInstance = null;

  get isShowAddFilterIcon() {
    const rules = this.formData.filter_rules;
    if (
      !rules.length ||
      (rules.slice(-1)[0].fields_name !== '' && rules.length === 1) ||
      rules.slice(-1)[0].value.length > 0
    )
      return true;
    return false;
  }

  get filterSelectList() {
    return this.totalFields
      .filter(item => !/^__dist/.test(item.field_name) && item.field_type !== '__virtual__')
      .map(el => {
        const { field_name: id, field_alias: alias } = el;
        return { id, name: alias ? `${id}(${alias})` : id };
      });
  }
  get datePickerValue() {
    const { start_time = 'now-15m', end_time = 'now' } = this.$store.state.indexItem;
    return [start_time, end_time];
  }

  get clusterField() {
    return this.totalFields
      .filter(item => item.is_analyzed)
      .map(el => {
        const { field_name: id, field_alias: alias } = el;
        return { id, name: alias ? `${id}(${alias})` : id };
      });
  }

  get indexId() {
    return this.$route.params.indexId;
  }

  get bkBizId() {
    return this.$store.state.bkBizId;
  }

  @Emit('cluster-created')
  handleCreateCluster() {
    return true;
  }

  handleAccessCluster() {
    this.isShowDialog = true;
  }
  handleConfirmSubmit() {
    this.quickClusterFromRef.validate().then(async () => {
      try {
        const data = {
          bk_biz_id: this.bkBizId,
          clustering_fields: this.formData.clustering_fields,
          new_cls_strategy_enable: this.formData.new_cls_strategy_enable,
          normal_strategy_enable: this.formData.normal_strategy_enable,
          filter_rules: this.formData.filter_rules.map(item => ({
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
          if (!Boolean(clusterPopoverState)) {
            const dom = document.querySelector('#more-operator');
            dom.addEventListener('popoverShowEvent', this.operatorTargetEvent);
            dom.dispatchEvent(new Event('popoverShowEvent'));
            localStorage.setItem('CLUSTER_MORE_POPOVER', 'true');
          }
          this.isShowDialog = false;
          this.handleCreateCluster();
        }
      } catch (error) {
        console.warn(error);
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
      this.cloneFormData = deepClone(this.formData);
      this.formData.clustering_fields = this.clusterField[0]?.id || '';
    } else {
      this.formData = this.cloneFormData;
    }
  }
  handleFieldChange(fieldName: string, index: number) {
    const field = this.totalFields.find(item => item.field_name === fieldName) ?? {};
    Object.assign(this.formData.filter_rules[index], {
      ...field,
      value: [],
    });
    const requestFields = this.fieldsKeyStrList();
    this.queryValueList(requestFields);
  }
  async queryValueList(fields = []) {
    if (!fields.length) return;
    /** 时间选择器绑定的值 */
    const tempList = handleTransformToTimestamp(this.datePickerValue);
    try {
      const res = await $http.request('retrieve/getAggsTerms', {
        params: {
          index_set_id: this.$route.params.indexId,
        },
        data: {
          keyword: this.retrieveParams?.keyword ?? '*',
          fields,
          start_time: formatDate(tempList[0] * 1000),
          end_time: formatDate(tempList[1] * 1000),
        },
      });
      this.formData.filter_rules.forEach(item => {
        item.valueList =
          res.data.aggs_items[item.fields_name]?.map(item => ({
            id: item.toString(),
            name: item.toString(),
          })) ?? [];
      });
    } catch (err) {
      this.formData.filter_rules.forEach(item => (item.valueList = []));
    }
  }
  fieldsKeyStrList() {
    const fieldsStrList = this.formData.filter_rules
      .filter(item => item.field_type !== 'text' && item.es_doc_values)
      .map(item => item.fields_name);
    return Array.from(new Set(fieldsStrList));
  }
  handleValueBlur(operateItem, val: string) {
    if (!operateItem.value.length && !!val) operateItem.value.push(val);
  }
  checkFilterRules() {
    return this.formData.filter_rules.every(item => !!item.value.length && item.fields_name);
    // return !!item.value.length && item.fields_name;
  }
  handleDeleteSelect(index: number) {
    this.formData.filter_rules.splice(index, 1);
    (this.$refs[`fieldSelectRef-${index}`] as any).close();
  }
  handleAddFilterRule() {
    this.formData.filter_rules.push({
      fields_name: '', // 过滤规则字段名
      op: '=', // 过滤规则操作符号
      value: [], // 过滤规则字段值
      logic_operator: 'and',
      valueList: [],
    });
    this.$nextTick(() => {
      const index = this.formData.filter_rules.length - 1;
      (this.$refs[`fieldSelectRef-${index}`] as any).show();
    });
  }
  render() {
    const accessDialogSlot = () => (
      <bk-dialog
        width='640'
        ext-cls='cluster-set-dialog'
        v-model={this.isShowDialog}
        confirm-fn={this.handleConfirmSubmit}
        header-position='left'
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
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
              <span
                v-bk-tooltips={{
                  content: $i18n.t('只能基于一个字段进行聚类，并且字段是为text的分词类型，默认为log字段'),
                  placements: ['right'],
                }}
              >
                <span class='bk-icon icon-info'></span>
              </span>
            </div>
          </bk-form-item>
          <bk-form-item
            label={$i18n.t('过滤规则')}
            property='filter_rules'
          >
            <div class='filter-rule'>
              {this.formData.filter_rules.map((item, index) => (
                <div class='filter-rule filter-rule-item'>
                  {!!this.formData.filter_rules.length && !!index && !!item.fields_name && (
                    <bk-select
                      class='icon-box and-or mr-neg1'
                      v-model={item.logic_operator}
                      clearable={false}
                    >
                      {this.comparedList.map(option => (
                        <bk-option
                          id={option.id}
                          name={option.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  )}
                  <bk-select
                    ref={`fieldSelectRef-${index}`}
                    class={['min-100 mr-neg1 above', { 'is-not-error': !!item.fields_name }]}
                    v-model={item.fields_name}
                    clearable={false}
                    popover-min-width={150}
                    searchable
                    on-selected={fieldsName => this.handleFieldChange(fieldsName, index)}
                  >
                    {this.filterSelectList.map(option => (
                      <bk-option
                        id={option.id}
                        name={option.name}
                      ></bk-option>
                    ))}
                    <div
                      style='cursor: pointer'
                      slot='extension'
                      onClick={() => this.handleDeleteSelect(index)}
                    >
                      <i class='bk-icon icon-close-circle'></i>
                      <span style='margin-left: 4px;'>{$i18n.t('删除')}</span>
                    </div>
                  </bk-select>
                  {!!item.fields_name && (
                    <bk-select
                      class='icon-box mr-neg1 condition'
                      v-model={item.op}
                      clearable={false}
                      popover-min-width={100}
                    >
                      {this.conditionList.map(option => (
                        <bk-option
                          id={option.id}
                          name={option.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  )}
                  {!!item.fields_name && (
                    <div onClick={() => (this.operateIndex = index)}>
                      <bk-tag-input
                        class={['mr-neg1 min-100 above', { 'is-not-error': !!item.value.length }]}
                        v-model={item.value}
                        content-width={232}
                        list={item.valueList}
                        max-data={1}
                        placeholder={$i18n.t('请输入')}
                        trigger='focus'
                        allow-auto-match
                        allow-create
                        on-blur={v => this.handleValueBlur(item, v)}
                      ></bk-tag-input>
                    </div>
                  )}
                </div>
              ))}
              {this.isShowAddFilterIcon && (
                <button
                  class='icon-box'
                  onClick={this.handleAddFilterRule}
                >
                  <i class='bk-icon icon-plus-line'></i>
                </button>
              )}
            </div>
          </bk-form-item>
          <bk-form-item
            label={$i18n.t('告警配置')}
            property='threshold'
          >
            <div class='cluster-set'>
              <bk-checkbox v-model={this.formData.new_cls_strategy_enable}>
                {$i18n.t('开启新类告警')}
                <i
                  class='log-icon icon-help'
                  v-bk-tooltips={{
                    content: $i18n.t('表示近一段时间内新增日志模式。可自定义新类判定的时间区间。如：近30天内新增'),
                    placements: ['top'],
                  }}
                ></i>
              </bk-checkbox>
              <bk-checkbox v-model={this.formData.normal_strategy_enable}>
                {$i18n.t('开启数量突增告警')}
                <i
                  class='log-icon icon-help'
                  v-bk-tooltips={{
                    content: $i18n.t('表示某日志模式数量突然异常增长，可能某些模块突发风险'),
                    placements: ['top'],
                  }}
                ></i>
              </bk-checkbox>
            </div>
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
          <img src={clusterImg} />
        </div>
      </div>
    );
  }
}
