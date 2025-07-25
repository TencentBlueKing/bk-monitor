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
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CancelToken } from 'monitor-api/cancel';
import { getIntelligentDetectAccessStatus, getIntelligentModel } from 'monitor-api/modules/strategies';

import IntelligentModelsStore, { IntelligentModelsType } from '../../../../../../store/modules/intelligent-models';
import { type IDetectionTypeRuleData, type MetricDetail, DetectionRuleTypeEnum } from '../../../typings';
import Form from '../form/form';
import {
  type IFormDataItem,
  type ISelectOptionItem,
  EFormItemValueType,
  FormItem,
  handleCreateModelOptionsDetail,
} from '../form/utils';

import type { ITipsData } from '../intelligent-detect/intelligent-detect';
import type { IModelData } from '../time-series-forecast/time-series-forecast';

import './abnormal-cluster.scss';

/** 内置参数的field */
const LEVEL_FIELD = 'level'; /** 告警级别key */
const MODEL_FIELD = 'plan_id'; /** 模型key */
const GROUP_FIELD = 'group'; /** 分群key */

interface AbnormalClusterEvents {
  onDataChange: IDetectionTypeRuleData<IOutlierDetecValue>;
  onModelChange: IModelData;
}

interface AbnormalClusterProps {
  data?: IDetectionTypeRuleData<IOutlierDetecValue>;
  interval: number;
  isEdit?: boolean;
  metricData: MetricDetail[];
  readonly?: boolean;
}

interface IOutlierDetecValue {
  [GROUP_FIELD]: string[];
  [MODEL_FIELD]: number | string;
  args?: {
    [key: string]: any;
  };
}

@Component({})
export default class AbnormalCluster extends tsc<AbnormalClusterProps, AbnormalClusterEvents> {
  /** 算法数据 */
  @Prop({ type: Object }) data: IDetectionTypeRuleData<IOutlierDetecValue>;
  /** 只读 */
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 是否为编辑模式 */
  @Prop({ type: Boolean, default: false }) isEdit: boolean;
  /** 指标数据 */
  @Prop({ type: Array, required: true }) metricData: MetricDetail[];
  /** 指标的汇聚周期 单位: 秒 */
  @Prop({ type: Number }) interval: number;
  /** 策略id */
  @InjectReactive('strategyId') strategyId: number;
  /** 当前编辑策略存在的智能算法 */
  @InjectReactive('editStrategyIntelligentDetectList') editStrategyIntelligentDetectList: string[];
  /** 表单实例 */
  @Ref() formRef: Form;

  localData: IDetectionTypeRuleData<IOutlierDetecValue> = {
    type: DetectionRuleTypeEnum.AbnormalCluster,
    level: 1,
    config: {
      args: {},
      group: [],
      plan_id: '',
    },
  };

  get rules() {
    return this.formItem.reduce((pre, cur) => {
      pre[cur.field] = [];
      if (cur.required) pre[cur.field].push({ required: true, message: this.$t('必填项'), trigger: 'change' });
      return pre;
    }, {});
  }

  loading = false;
  modelList = [];

  /** 提示数据 */
  tipsData: ITipsData = {
    status: 'info',
    message: '',
  };

  isChangeModel = false;

  /** 内置选项 */
  get staticFormItemData(): IFormDataItem[] {
    return [
      {
        label: window.i18n.tc('告警级别'),
        field: LEVEL_FIELD,
        value: this.localData.level,
        default: 1,
        type: 'ai-level',
        behavior: 'simplicity',
        required: true,
        clearable: false,
      },
      {
        label: window.i18n.tc('模型名称'),
        field: MODEL_FIELD,
        value: '',
        default: '',
        type: 'model-select',
        behavior: 'simplicity',
        options: [],
        required: true,
        clearable: false,
        placeholder: this.$tc('选择'),
      },
      {
        label: window.i18n.tc('分组字段'),
        field: GROUP_FIELD,
        value: this.localData.config?.group || [],
        default: '',
        type: 'tag-input',
        behavior: 'simplicity',
        options: this.groupOptions,
        required: false,
        clearable: false,
        valueType: EFormItemValueType.array,
        placeholder: this.readonly ? '--' : this.$tc('选择'),
      },
    ];
  }

  /** 模型、预测时长、阈值 */
  staticFormItem: FormItem[] = [];
  /** 模型参数表单数据 */
  argsFormItem: FormItem[] = [];

  /** 用于取消模型详情接口 */
  modelDetialCancelFn = () => {};

  /**
   * 分组字段的可选值为指标已选中的维度值
   */
  get groupOptions(): ISelectOptionItem[] {
    const metric = this.metricData[0];
    const dimensionsList = metric.dimensions;
    const checkedId = metric.agg_dimension;

    return dimensionsList.filter(
      item => item.is_dimension && checkedId.includes(item.id as string)
    ) as ISelectOptionItem[];
  }

  /**
   * 表单实际渲染数据
   */
  get formItem() {
    return [...this.staticFormItem, ...this.argsFormItem];
  }

  /** 当前选中的模型数据 */
  get currentModelData() {
    return this.modelList.find(item => item.id === this.staticFormItem[1]?.value);
  }

  created() {
    this.initData();
    this.staticFormItem = this.staticFormItemData.map(item => new FormItem(item));
    this.handleBindOnChange();
    this.getModelList();
  }

  initData() {
    if (this.data) {
      this.localData = this.data;
    } else {
      this.emitLocalData();
    }
  }

  @Watch('groupOptions')
  groupOptionsChange(val: ISelectOptionItem[]) {
    const groupField = this.staticFormItem[1];
    if (groupField) {
      const oldVal = groupField.value;
      groupField.options = val;
      const map = val.map(item => item.id);
      groupField.value = groupField.value.filter(item => map.includes(item));
      if (JSON.stringify(oldVal) !== JSON.stringify(groupField.value)) {
        this.handleFormValueChange();
      }
    }
  }

  /** 绑定组件回调方法 */
  handleBindOnChange() {
    /** 模型 */
    const modelItem = this.staticFormItem.find(item => item.field === MODEL_FIELD);
    modelItem.onChange = this.modelSelected;
  }

  /**
   * 获取模型列表
   */
  async getModelList() {
    this.loading = true;
    const resData = await IntelligentModelsStore.getListIntelligentModels({
      algorithm: IntelligentModelsType.AbnormalCluster,
    }).catch(() => (this.loading = false));
    let modelItem: FormItem = null;
    this.staticFormItem.forEach(item => {
      if (item.field === MODEL_FIELD) modelItem = item;
    });
    // 根据服务端返回的 is_default 字段 是否 默认选中 特定的模型。
    let defaultSelectModelId = null;
    if (resData.length) {
      this.modelList = resData;
      modelItem.options = resData.map(item => {
        if (item.is_default) defaultSelectModelId = item.id;
        return {
          id: item.id,
          name: item.name,
          default: !!item.is_default,
          loading: false,
          detail: handleCreateModelOptionsDetail(item, this.interval),
        };
      });
    }
    // 这里给模型选择器添加默认选中。第一个是编辑模式，后面 2、3 项是新建页面下使用（优先选中 is_default 为 true 的项，否则就选中第一项）
    modelItem.value = this.localData.config[MODEL_FIELD] || defaultSelectModelId || modelItem.options[0]?.id;
    this.getModelItemData(modelItem.value);
    this.loading = false;
  }

  /**
   * 获取模型参数
   */
  async getModelItemData(modelId: string, relId?: string, needLoading = true) {
    if (!modelId) return;
    const { latest_release_id } = this.currentModelData || {};
    const params = {
      id: modelId,
      latest_release_id: relId || latest_release_id,
    };
    needLoading && (this.loading = true);
    const detailData = await getIntelligentModel(params, {
      cancelToken: new CancelToken(c => (this.modelDetialCancelFn = c)),
    }).finally(() => needLoading && (this.loading = false));

    const valueDisplay = this.localData.config?.args || {};
    this.argsFormItem = FormItem.createFormItemData(detailData, valueDisplay);
    this.handleFormValueChange();
    this.handleModelChange({
      name: detailData.name,
      instruction: detailData.instruction,
      document: detailData.document,
    });
  }

  /**
   * 切换模型
   * @param item 模型数据
   */
  modelSelected() {
    this.isChangeModel = true;
  }

  /**
   * 模型信息发生变化
   * @returns 模型信息
   */
  @Emit('modelChange')
  handleModelChange(data: IModelData) {
    return data;
  }

  @Watch('strategyId', { immediate: true })
  strategyIdChange(val: number) {
    if (!!val && `${val}` !== '0') this.getStatusMessage();
  }

  /** 获取头部提示信息 */
  async getStatusMessage() {
    // 新增策略无需调用检查接口
    if (!this.editStrategyIntelligentDetectList?.includes('AbnormalCluster')) return;
    const resData = await getIntelligentDetectAccessStatus({ strategy_id: this.strategyId });
    const statusMap = {
      waiting: 'info',
      running: 'success',
      failed: 'error',
    };
    this.tipsData.status = statusMap[resData.status];
    this.tipsData.message =
      resData.status_detail?.replace?.(/(([1-9]\d*\.?\d*)|(0\.\d*))/g, '<span class="hl">$1</span>') || '';
  }

  handleFormValueChange() {
    const fn = src =>
      src.reduce((total, item: FormItem) => {
        total[item.field] = FormItem.handleValueType(item);
        return total;
      }, {});
    const staticParams = fn(this.staticFormItem);
    const argsParams = fn(this.argsFormItem);
    const { level, ...params } = staticParams;
    this.localData.level = level;
    this.localData.config = {
      ...params,
      args: argsParams,
    };
    this.emitLocalData();
  }

  @Emit('dataChange')
  emitLocalData() {
    return this.localData;
  }

  validate() {
    return new Promise((res, rej) => {
      this.formRef
        .validate()
        .then(validator => res(validator))
        .catch(validator => rej(validator));
    });
  }

  clearError() {
    this.formRef.clearError();
  }

  render() {
    return (
      <div
        class='abnormal-cluster-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.tipsData.message && !this.isChangeModel && (
          <bk-alert
            class='alert-message'
            type={this.tipsData.status}
          >
            <div
              class='alert-message-number'
              slot='title'
              domPropsInnerHTML={this.tipsData.message}
            />
          </bk-alert>
        )}
        <Form
          ref='formRef'
          class='time-serise-forecast-wrap'
          formItemList={this.formItem}
          label-width={126}
          readonly={this.readonly}
          rules={this.rules}
          onChange={this.handleFormValueChange}
        />
      </div>
    );
  }
}
