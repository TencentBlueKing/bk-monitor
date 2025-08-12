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

import { VariableTypeMap } from '../../../constants';
import AggMethodDetail from '../agg-method/agg-method-detail';
import AggMethodVariable from '../agg-method/agg-method-variable';
import ConditionDetail from '../condition/condition-detail';
import ConditionVariable from '../condition/condition-variable';
import DimensionValueDetail from '../dimension-value/dimension-value-detail';
import DimensionValueVariable from '../dimension-value/dimension-value-variable';
import DimensionDetail from '../dimension/dimension-detail';
import DimensionVariable from '../dimension/dimension-variable';
import FunctionDetail from '../function/function-detail';
import FunctionVariable from '../function/function-variable';
import GeneralDetail from '../general/general-detail';
import GeneralVariable from '../general/general-variable';

import type { VariableModel } from '../../../typings';

import './variable-panel.scss';

interface VariablePanelProps {
  data: VariableModel;
  metric: any;
  scene?: 'create' | 'detail' | 'edit';
}

@Component
export default class VariablePanel extends tsc<VariablePanelProps> {
  @Prop() data: VariableModel;
  @Prop() metric: any;
  @Prop({ default: 'create', type: String }) scene: VariablePanelProps['scene'];

  get title() {
    return VariableTypeMap[this.data.type];
  }

  renderVariableDetail() {
    switch (this.data.type) {
      case 'agg_method':
        return <AggMethodDetail data={this.data} />;
      case 'dimension':
        return <DimensionDetail data={this.data} />;
      case 'dimension_value':
        return <DimensionValueDetail data={this.data} />;
      case 'function':
        return <FunctionDetail data={this.data} />;
      case 'condition':
        return <ConditionDetail data={this.data} />;
      default:
        return <GeneralDetail data={this.data} />;
    }
  }

  renderVariableForm() {
    switch (this.data.type) {
      case 'agg_method':
        return <AggMethodVariable data={this.data} />;
      case 'dimension':
        return <DimensionVariable data={this.data} />;
      case 'dimension_value':
        return <DimensionValueVariable data={this.data} />;
      case 'function':
        return <FunctionVariable data={this.data} />;
      case 'condition':
        return <ConditionVariable data={this.data} />;
      default:
        return <GeneralVariable data={this.data} />;
    }
  }

  render() {
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
