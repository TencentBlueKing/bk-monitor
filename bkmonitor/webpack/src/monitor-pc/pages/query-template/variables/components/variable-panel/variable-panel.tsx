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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { VariableTypeEnum, VariableTypeMap } from '../../../constants';
import ConditionDetail from '../condition/condition-detail';
import ConditionVariable from '../condition/condition-variable';
import ConstantDetail from '../constant/constant-detail';
import ConstantVariable from '../constant/constant-variable';
import DimensionValueDetail from '../dimension-value/dimension-value-detail';
import DimensionValueVariable from '../dimension-value/dimension-value-variable';
import DimensionDetail from '../dimension/dimension-detail';
import DimensionVariable from '../dimension/dimension-variable';
import FunctionDetail from '../function/function-detail';
import FunctionVariable from '../function/function-variable';
import MethodDetail from '../method/method-detail';
import MethodVariable from '../method/method-variable';

import type {
  ConditionVariableModel,
  ConstantVariableModel,
  DimensionValueVariableModel,
  DimensionVariableModel,
  FunctionVariableModel,
  MethodVariableModel,
  VariableModelType,
} from '../../index';

import './variable-panel.scss';

interface VariablePanelEvents {
  onDataChange: (data: VariableModelType) => void;
}

interface VariablePanelProps {
  data: VariableModelType;
  scene?: 'create' | 'detail' | 'edit';
}

@Component
export default class VariablePanel extends tsc<VariablePanelProps, VariablePanelEvents> {
  @Prop() data: VariableModelType;
  @Prop({ default: 'create', type: String }) scene: VariablePanelProps['scene'];

  get title() {
    return VariableTypeMap[this.data.type];
  }

  get editVariableLabelTooltips() {
    return [
      { label: this.$tc('变量名'), value: this.data.name },
      { label: this.$tc('变量别名'), value: this.data.alias },
      { label: this.$tc('变量描述'), value: this.data.desc },
    ];
  }

  handleDataChange(value: VariableModelType) {
    this.$emit('dataChange', value);
  }

  /** 变量详情 */
  renderVariableDetail() {
    switch (this.data.type) {
      case VariableTypeEnum.METHOD:
        return <MethodDetail data={this.data as MethodVariableModel} />;
      case VariableTypeEnum.DIMENSION:
        return <DimensionDetail data={this.data as DimensionVariableModel} />;
      case VariableTypeEnum.DIMENSION_VALUE:
        return <DimensionValueDetail data={this.data as DimensionValueVariableModel} />;
      case VariableTypeEnum.FUNCTION:
        return <FunctionDetail data={this.data as FunctionVariableModel} />;
      case VariableTypeEnum.CONDITION:
        return <ConditionDetail data={this.data as ConditionVariableModel} />;
      default:
        return <ConstantDetail data={this.data as ConstantVariableModel} />;
    }
  }

  /** 新增变量表单 */
  renderVariableForm() {
    switch (this.data.type) {
      case VariableTypeEnum.METHOD:
        return (
          <MethodVariable
            data={this.data as MethodVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.DIMENSION:
        return (
          <DimensionVariable
            data={this.data as DimensionVariableModel}
            onDataChange={this.handleDataChange}
          />
        );
      case VariableTypeEnum.DIMENSION_VALUE:
        return <DimensionValueVariable data={this.data as DimensionValueVariableModel} />;
      case VariableTypeEnum.FUNCTION:
        return <FunctionVariable data={this.data as FunctionVariableModel} />;
      case VariableTypeEnum.CONDITION:
        return <ConditionVariable data={this.data as ConditionVariableModel} />;
      default:
        return <ConstantVariable data={this.data as ConstantVariableModel} />;
    }
  }

  renderEditVariableValue() {
    switch (this.data.type) {
      case VariableTypeEnum.METHOD:
        return <bk-select />;
      case VariableTypeEnum.DIMENSION:
        return <bk-select />;
      case VariableTypeEnum.DIMENSION_VALUE:
        return <bk-select />;
      case VariableTypeEnum.FUNCTION:
        return <bk-select />;
      case VariableTypeEnum.CONDITION:
        return;
      default:
        return <bk-input />;
    }
  }

  render() {
    if (this.scene === 'edit')
      return (
        <bk-popover
          width={188}
          placement='top'
        >
          <div class='variable-value'>
            <div class='variable-value-label'>
              <span>{this.data.alias || this.data.name}</span>
            </div>
            <div class='variable-value-input'>{this.renderEditVariableValue()}</div>
          </div>
          <ul slot='content'>
            {this.editVariableLabelTooltips.map(item => (
              <li key={item.label}>
                <span class='label'>{item.label}：</span>
                <span class='value'>{item.value}</span>
              </li>
            ))}
          </ul>
        </bk-popover>
      );

    return (
      <div class={['variable-panel', this.scene]}>
        <div class='variable-type-title'>{this.title}</div>
        <div class='variable-form'>
          {this.scene === 'detail' ? this.renderVariableDetail() : this.renderVariableForm()}
        </div>
      </div>
    );
  }
}
