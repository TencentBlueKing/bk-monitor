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

import { CancelToken } from '../../../../../../../monitor-api/index';
import {
  getIntelligentDetectAccessStatus,
  getIntelligentModel,
  listIntelligentModels
} from '../../../../../../../monitor-api/modules/strategies';
import { THRESHOLD_METHOD_LIST } from '../../../../../../constant/constant';
import { DetectionRuleTypeEnum, IDetectionTypeRuleData } from '../../../typings';
import { BoundType } from '../form/alarm-threshold-select';
import Form from '../form/form';
import { FormItem, IFormDataItem } from '../form/utils';
import { ITipsData } from '../intelligent-detect/intelligent-detect';
import { IItem, IThresholdSelectValue } from '../threshold/threshold-select';

import './time-series-forecast.scss';

/** 内置参数的field */
const MODEL_FIELD = 'plan_id'; /** 模型 */
const DURATION_FIELD = 'duration'; /** 预测时长 */
const THRESHOLDS_FIELD = 'thresholds'; /** 阈值 */
const LEVEL_FIELD = 'level'; /** 告警级别key */

interface ITimeSeriesForecastValue {
  [MODEL_FIELD]: string;
  [DURATION_FIELD]: number | string;
  [THRESHOLDS_FIELD]: any;
  bound_type: BoundType;
  args: Record<string, IThresholdSelectValue>;
  visual_type?: string;
}

interface TimeSeriesForecastingProps {
  data?: IDetectionTypeRuleData<ITimeSeriesForecastValue>;
  readonly?: boolean;
  isEdit?: boolean;
  unit: string;
  interval: number;
  methodList?: IItem[];
}

interface TimeSeriesForecastingEvents {
  onDataChange: IDetectionTypeRuleData<ITimeSeriesForecastValue>;
  onModelChange: IModelData;
}

export interface IModelData {
  name: string; // 算法名称
  instruction: string; // 方案描述
  document?: string; // 使用说明
}

@Component({})
export default class TimeSeriesForecasting extends tsc<TimeSeriesForecastingProps, TimeSeriesForecastingEvents> {
  @Prop({ type: Object }) data: IDetectionTypeRuleData<ITimeSeriesForecastValue>;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 是否为编辑模式 */
  @Prop({ type: Boolean, default: false }) isEdit: boolean;
  /** 单位 */
  @Prop({ type: String, default: '' }) unit: string;
  /** 方法列表 */
  @Prop({ type: Array, default: () => [...THRESHOLD_METHOD_LIST] }) methodList: IItem[];
  /** 指标的汇聚周期 单位: 秒 */
  @Prop({ type: Number }) interval: number;
  /** 策略id */
  @InjectReactive('strategyId') strategyId: number;
  /** 当前编辑策略存在的智能算法 */
  @InjectReactive('editStrategyIntelligentDetectList') editStrategyIntelligentDetectList: string[];
  @Ref() formRef: Form;

  localData: IDetectionTypeRuleData<ITimeSeriesForecastValue> = {
    type: DetectionRuleTypeEnum.TimeSeriesForecasting,
    level: 1,
    config: {
      args: {},
      duration: '',
      plan_id: '',
      thresholds: [[{ method: 'gte', threshold: 0 }]],
      visual_type: 'forecasting',
      bound_type: 'middle'
    }
  };

  get rules() {
    return this.formItem.reduce((pre, cur) => {
      pre[cur.field] = [];
      if (cur.required) pre[cur.field].push({ required: true, message: this.$t('必填项'), trigger: 'change' });
      return pre;
    }, {});
  }

  loading = false;
  /** 内置选项 */
  staticFormItemData: IFormDataItem[] = [
    {
      label: window.i18n.tc('告警级别'),
      field: LEVEL_FIELD,
      value: this.localData.level,
      default: 1,
      type: 'ai-level',
      behavior: 'simplicity',
      required: true,
      clearable: false
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
      clearable: false
    },
    {
      label: window.i18n.tc('预测时长'),
      field: DURATION_FIELD,
      value: 7 * 24 * 60 * 60,
      default: 7 * 24 * 60 * 60,
      type: 'input-unit',
      behavior: 'simplicity',
      min: 1,
      max: 7,
      width: 50,
      required: true,
      unitId: 24 * 60 * 60,
      unitOption: [
        {
          id: 24 * 60 * 60,
          name: window.i18n.tc('天')
        }
      ]
    },
    {
      label: window.i18n.tc('告警阈值'),
      field: THRESHOLDS_FIELD,
      value: [],
      default: [],
      boundType: 'middle',
      type: 'alarm-thresholds',
      unit: '',
      methodList: [],
      required: true
    }
  ];
  /** 模型、预测时长、阈值 */
  staticFormItem: FormItem[] = [];
  /** 模型参数表单数据 */
  argsFormItem: FormItem[] = [];

  /** 模型数据 */
  modelList = [];

  /** 提示数据 */
  tipsData: ITipsData = {
    status: 'info',
    message: ''
  };
  isChangeModel = false;

  /** 用于取消模型详情接口 */
  modelDetialCancelFn = () => {};

  /**
   * 表单实际渲染数据
   */
  get formItem() {
    const formItemList = [...this.staticFormItem];
    formItemList.splice(2, 0, ...this.argsFormItem);
    return formItemList;
  }
  /** 当前选中的模型数据 */
  get currentModelData() {
    return this.modelList.find(item => item.id === this.staticFormItem[1]?.value);
  }

  created() {
    this.getModelList();
    this.staticFormItem = this.staticFormItemData.map(item => new FormItem(item));
    this.unitChange(this.unit);
    this.handleBindOnChange();
    this.methodListChange(this.methodList);
    this.initData();
  }

  initData() {
    if (this.data) {
      this.localData = this.data;
    } else {
      this.emitLocalData();
    }
  }

  @Watch('unit')
  unitChange(val) {
    const target = this.getThresholdsItem();
    target.unit = val;
  }

  @Watch('methodList', { deep: true })
  methodListChange(val) {
    const target = this.getThresholdsItem();
    target.methodList = val;
  }

  @Watch('strategyId', { immediate: true })
  strategyIdChange(val: number) {
    if (!!val && `${val}` !== '0') this.getStatusMessage();
  }
  /**
   * 获取阈值表单数据
   */
  getThresholdsItem(): FormItem {
    return this.staticFormItem.find(item => item.field === THRESHOLDS_FIELD);
  }

  /** 绑定组件回调方法 */
  handleBindOnChange() {
    /** 模型 */
    const modelItem = this.staticFormItem.find(item => item.field === MODEL_FIELD);
    modelItem.onChange = this.modelSelected;
  }

  /**
   * 切换模型
   * @param item 模型数据
   */
  modelSelected(item: FormItem) {
    this.isChangeModel = true;
    this.getModelItemData(item.value);
  }

  /** 获取头部提示信息 */
  async getStatusMessage() {
    // 新增策略无需调用检查接口
    if (!this.editStrategyIntelligentDetectList?.includes('TimeSeriesForecasting')) return;
    const resData = await getIntelligentDetectAccessStatus({ strategy_id: this.strategyId });
    const statusMap = {
      waiting: 'info',
      running: 'success',
      failed: 'error'
    };
    this.tipsData.status = statusMap[resData.status];
    this.tipsData.message =
      resData.status_detail?.replace?.(/(([1-9]\d*\.?\d*)|(0\.\d*))/g, '<span class="hl">$1</span>') || '';
  }

  /**
   * 获取模型列表
   */
  async getModelList() {
    this.loading = true;
    const resData = await listIntelligentModels({ algorithm: 'TimeSeriesForecasting' }).finally(
      () => (this.loading = false)
    );
    let modelItem: FormItem = null;
    let durationItem: FormItem = null;
    let thresholdsItem: FormItem = null;
    this.staticFormItem.forEach(item => {
      if (item.field === MODEL_FIELD) modelItem = item;
      if (item.field === DURATION_FIELD) durationItem = item;
      if (item.field === THRESHOLDS_FIELD) thresholdsItem = item;
    });
    // 根据服务端返回的 is_default 字段 是否 默认选中 特定的模型。
    let defaultSelectModelId = null;
    if (!!resData.length) {
      this.modelList = resData;
      modelItem.options = resData.map(item => {
        if (!!item.is_default) defaultSelectModelId = item.id;
        return {
          id: item.id,
          name: item.name,
          default: !!item.is_default,
          loading: false,
          detail: this.handleCreateModelOptionsDetail(item)
        };
      });
    }
    // 这里给模型选择器添加默认选中。第一个是编辑模式，后面 2、3 项是新建页面下使用（优先选中 is_default 为 true 的项，否则就选中第一项）
    modelItem.value = this.localData.config[MODEL_FIELD] || defaultSelectModelId || modelItem.options[0]?.id;
    durationItem.value = this.localData.config[DURATION_FIELD] || durationItem.default;
    thresholdsItem.value = this.localData.config[THRESHOLDS_FIELD] || thresholdsItem.default;
    thresholdsItem.boundType = this.localData.config.bound_type || thresholdsItem.boundType;
    this.getModelItemData(modelItem.value);
  }

  /**
   * 获取模型参数
   */
  async getModelItemData(modelId: string, relId?: string, needLoading = true) {
    if (!modelId) return;
    const { latest_release_id } = this.currentModelData || {};
    const params = {
      id: modelId,
      latest_release_id: relId || latest_release_id
    };
    needLoading && (this.loading = true);
    const detailData = await getIntelligentModel(params, {
      cancelToken: new CancelToken(c => (this.modelDetialCancelFn = c))
    }).finally(() => needLoading && (this.loading = false));
    const valueDisplay = this.localData.config?.args || {};
    this.argsFormItem = FormItem.createFormItemData(detailData, valueDisplay);
    this.handleFormValueChange();
    this.handleModelChange({
      name: detailData.name,
      instruction: detailData.instruction,
      document: detailData.document
    });
  }

  /** 获取模型描述信息 */
  handleCreateModelOptionsDetail(item: any) {
    return {
      name: item.name,
      releaseId: item.latest_release_id,
      description: {
        dataLength: {
          value: item.ts_depend,
          isMatch: true
        },
        frequency: {
          value: item.ts_freq,
          isMatch: item.ts_freq === 0 ? true : this.interval === item.ts_freq.value
        },
        message: {
          value: item.description,
          isMatch: true
        }
      },
      instruction: item.instruction || ''
    };
  }

  /**
   * 模型信息发生变化
   * @returns 模型信息
   */
  @Emit('modelChange')
  handleModelChange(data: IModelData) {
    return data;
  }

  /**
   * 表单数据更新
   */
  handleFormValueChange() {
    const fn = src =>
      src.reduce((total, item: FormItem) => {
        total[item.field] = FormItem.handleValueType(item);
        if (item.field === 'thresholds') total.boundType = item.boundType;
        return total;
      }, {});
    const staticParams = fn(this.staticFormItem);
    const argsParams = fn(this.argsFormItem);
    const { level, ...params } = staticParams;
    this.localData.level = level;
    this.localData.config = {
      ...params,
      args: argsParams,
      visual_type: this.currentModelData?.visual_type
    };
    this.emitLocalData();
  }

  @Emit('dataChange')
  emitLocalData() {
    return this.localData;
  }

  /**
   * 校验表单
   * @returns Promise
   */
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
        v-bkloading={{ isLoading: this.loading }}
        class='time-series-forecast-wrap'
      >
        {this.tipsData.message && !this.isChangeModel && (
          <bk-alert
            type={this.tipsData.status}
            class='alert-message'
          >
            <div
              class='alert-message-number'
              slot='title'
              domPropsInnerHTML={this.tipsData.message}
            ></div>
          </bk-alert>
        )}
        <Form
          ref='formRef'
          rules={this.rules}
          readonly={this.readonly}
          formItemList={this.formItem}
          label-width={126}
          onChange={this.handleFormValueChange}
          class='time-serise-forecast-wrap'
        ></Form>
      </div>
    );
  }
}
