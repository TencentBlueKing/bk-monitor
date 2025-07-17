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
import { DetectionRuleTypeEnum, type IDetectionTypeRuleData } from '../../../typings';
import Form from '../form/form';
import { FormItem, type IFormDataItem } from '../form/utils';

import type { IModelData } from '../time-series-forecast/time-series-forecast';

import './intelligent-detect.scss';

const MODEL_FIELD = 'plan_id'; // 模型类型id字段
const LEVEL_FIELD = 'level'; /** 告警级别key */

// 图表显示类型: none-无, boundary-上下界, score-异常分值, forecasting-预测
export type ChartType = 'boundary' | 'forecasting' | 'none' | 'score';
interface IAiOpsValue {
  [MODEL_FIELD]: string;
  visual_type: ChartType;
  args: { [key in string]: number | string };
}

interface IntelligentDetectProps {
  data?: IDetectionTypeRuleData<IAiOpsValue>;
  readonly?: boolean;
  isEdit?: boolean;
  interval: number;
  resultTableId: string;
}

interface IntelligentDetectEvents {
  onDataChange: IDetectionTypeRuleData<IAiOpsValue>;
  onChartTypeChange: ChartType;
  onModelChange: IModelData;
}

export interface ITipsData {
  status: 'error' | 'info' | 'success';
  message: string;
}
@Component({})
export default class IntelligentDetect extends tsc<IntelligentDetectProps, IntelligentDetectEvents> {
  @Prop({ type: Object }) data: IDetectionTypeRuleData<IAiOpsValue>;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 是否为编辑模式 */
  @Prop({ type: Boolean, default: false }) isEdit: boolean;
  /** 指标的汇聚周期 单位: 秒 */
  @Prop({ type: Number }) interval: number;
  /** 结果表id */
  @Prop({ type: String }) resultTableId: string;
  /** 策略id */
  @InjectReactive('strategyId') strategyId: number;
  /** 当前编辑策略存在的智能算法 */
  @InjectReactive('editStrategyIntelligentDetectList') editStrategyIntelligentDetectList: string[];
  /** 表单实例 */
  @Ref() formRef: Form;

  localData: IDetectionTypeRuleData<IAiOpsValue> = {
    type: DetectionRuleTypeEnum.IntelligentDetect,
    level: 1,
    config: {
      [MODEL_FIELD]: '',
      visual_type: 'none',
      args: {},
    },
  };

  /** 模型数据 */
  modelList = [];

  loading = false;

  /** 编辑时是否更换了模型 */
  isChangeModel = false;

  /** 默认选项 */
  get staticFormItemData(): IFormDataItem[] {
    return [
      {
        label: window.i18n.tc('告警级别'),
        field: LEVEL_FIELD,
        value: this.localData.level,
        type: 'ai-level',
        required: true,
      },
      {
        label: window.i18n.tc('模型名称'),
        value: '',
        field: MODEL_FIELD,
        type: 'model-select',
        required: false,
        options: [],
        disabled: false,
      },
    ];
  }
  /** 告警级别、模型 */
  staticFormItem: FormItem[] = [];

  /** 模型参数表单数据 */
  argsFormItem: FormItem[] = [];

  /** 提示数据 */
  tipsData: ITipsData = {
    status: 'info',
    message: '',
  };

  /** 模型详情取消请求方法 */
  modelDetailCancelFn = () => {};

  /** 当前选中模型的id */
  get currentModelId() {
    return this.staticFormItem.find(item => item.field === MODEL_FIELD).value as string;
  }
  /** 当前选中的模型数据 */
  get currentModelData() {
    return this.modelList.find(item => item.id === this.currentModelId);
  }
  /** 表单组件展示数据 */
  get formItemList() {
    return [...this.staticFormItem, ...this.argsFormItem].filter(item => !item.isAdvanced);
  }

  get rules() {
    return this.formItemList.reduce((pre, cur) => {
      pre[cur.field] = [];
      if (cur.required) pre[cur.field].push({ required: true, message: this.$t('必填项'), trigger: 'change' });
      return pre;
    }, {});
  }

  mounted() {
    this.getModelList();
    this.initData();
    this.staticFormItem = this.staticFormItemData.map(item => new FormItem(item));
    this.handleBindOnChange();
  }

  initData() {
    if (this.data) {
      this.localData = this.data;
    } else {
      this.emitLocalData();
    }
  }

  /** 绑定组件回调方法 */
  handleBindOnChange() {
    /** 模型 */
    const modelItem = this.staticFormItem.find(item => item.field === MODEL_FIELD);
    modelItem.onChange = this.modelSelected;
  }

  modelSelected(item: FormItem) {
    this.isChangeModel = true;
    this.getModelItemData(item.value);
  }

  /** 获取模型的列表数据 */
  async getModelList() {
    this.loading = true;
    const resData = await IntelligentModelsStore.getListIntelligentModels({
      algorithm: IntelligentModelsType.IntelligentDetect,
    }).catch(() => (this.loading = false));
    const modelItem: FormItem = this.staticFormItem.find(item => item.field === MODEL_FIELD);
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
          detail: this.handleCreateModelOptionsDetail(item),
        };
      });
    }
    // 这里给模型选择器添加默认选中。第一个是编辑模式，后面 2、3 项是新建页面下使用（优先选中 is_default 为 true 的项，否则就选中第一项）
    modelItem.value = this.localData.config[MODEL_FIELD] || defaultSelectModelId || modelItem.options[0]?.id;
    this.getModelItemData(modelItem.value);
  }

  /** 获取模型描述信息 */
  handleCreateModelOptionsDetail(item: any) {
    return {
      name: item.name,
      releaseId: item.latest_release_id,
      description: {
        dataLength: {
          value: item.ts_depend,
          isMatch: true,
        },
        frequency: {
          value: item.ts_freq,
          isMatch: item.ts_freq === 0 ? true : this.interval === item.ts_freq.value,
        },
        message: {
          value: item.description,
          isMatch: true,
        },
      },
      instruction: item.instruction || '',
      document: item.document || '',
    };
  }

  /** 获取单个模型的数据 */
  async getModelItemData(id: string, relId?: number, needLoading = true) {
    if (!id) return;
    const { latest_release_id, visual_type } = this.currentModelData || {};
    const params = {
      id,
      latest_release_id: relId || latest_release_id,
    };
    needLoading && (this.loading = true);
    const detailData = await getIntelligentModel(params, {
      cancelToken: new CancelToken(c => (this.modelDetailCancelFn = c)),
    }).finally(() => needLoading && (this.loading = false));
    const valueDisplay = this.localData.config?.args || {};
    this.argsFormItem = FormItem.createFormItemData(detailData, valueDisplay);
    this.handleValueChange();
    this.handleModelChange({
      name: detailData.name,
      instruction: detailData.instruction,
      document: detailData.document,
    });
    this.handleChartTypeChange(visual_type);
  }
  /** 切换模型操作 */
  @Emit('modelChange')
  async handleModelChange(data: IModelData) {
    return data;
  }

  /** 切换数据模型预览图的类型变化 */
  @Emit('chartTypeChange')
  handleChartTypeChange(type: ChartType) {
    return type || this.currentModelData.visual_type;
  }

  handleValueChange() {
    this.localData.level = this.staticFormItem.find(item => item.field === LEVEL_FIELD).value as number;
    this.localData.config = {
      [MODEL_FIELD]: this.currentModelId,
      visual_type: this.currentModelData?.visual_type,
      args: this.argsFormItem.reduce((args, item) => {
        args[item.field] = item.value;
        return args;
      }, {}),
    };
    this.emitLocalData();
  }

  @Emit('dataChange')
  emitLocalData() {
    return this.localData;
  }

  @Watch('strategyId', { immediate: true })
  strategyIdChange(val: number) {
    if (!!val && `${val}` !== '0') this.getStatusMessage();
  }

  /** 获取头部提示信息 */
  async getStatusMessage() {
    // 新增策略无需调用检查接口
    if (!this.editStrategyIntelligentDetectList?.includes('IntelligentDetect')) return;
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

  /** 校验方法 */
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
        style={{
          'margin-left': this.readonly ? '-28px' : '0px',
        }}
        class='intelligent-detect-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.tipsData.message && !this.isChangeModel && (
          <bk-alert
            class='alert-message'
            type={this.tipsData.status}
          >
            <div
              class='ai-ops-tips'
              slot='title'
              domPropsInnerHTML={this.tipsData.message}
            />
          </bk-alert>
        )}
        <Form
          ref='formRef'
          class='time-serise-forecast-wrap'
          formItemList={this.formItemList}
          label-width={126}
          readonly={this.readonly}
          rules={this.rules}
          onChange={this.handleValueChange}
        />
      </div>
    );
  }
}
