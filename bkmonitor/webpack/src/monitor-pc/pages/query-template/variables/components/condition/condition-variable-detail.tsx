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

import VariableCommonFormDetail from '../common-form/variable-common-form-detail';
import { STRING_CONDITION_METHOD_LIST } from '@/constant/constant';

import type { ConditionVariableModel } from '../../index';
interface ConditionDetailProps {
  variable: ConditionVariableModel;
}

@Component
export default class ConditionVariableDetail extends tsc<ConditionDetailProps> {
  @Prop({ type: Object, required: true }) variable!: ConditionVariableModel;

  get transformDefaultValue() {
    return this.variable.defaultValue.map(item => {
      const name = this.variable.dimensionList.find(dim => dim.id === item.key)?.name || item.key;
      const operation = STRING_CONDITION_METHOD_LIST.find(method => method.id === item.method);
      return {
        name,
        operation,
        value: item.value,
      };
    });
  }

  render() {
    return (
      <div class='condition-detail'>
        <VariableCommonFormDetail data={this.variable.data}>
          <div class='form-item'>
            <div class='form-item-label'>{this.$t('关联指标')}：</div>
            <div class='form-item-value'>{this.variable.metric?.metric_id || '--'}</div>
          </div>
          <div class='form-item'>
            <div class='form-item-label'>{this.$t('可选维度')}：</div>
            <div class='form-item-value'>
              {this.variable.isAllDimensionOptions ? (
                <span>- ALL -</span>
              ) : (
                <div class='tag-list'>
                  {this.variable.dimensionOptionsMap.map(item => (
                    <div
                      key={item.id}
                      class='tag-item'
                    >
                      {item.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div class='form-item'>
            <div class='form-item-label'>{this.$t('默认值')}：</div>
            <div class='form-item-value'>
              {this.transformDefaultValue.length
                ? this.transformDefaultValue.map(item => (
                    <div
                      key={item.name}
                      class='condition-tag'
                    >
                      <div class='key-wrap'>
                        <span class='key-name'>{item.name}</span>
                        <span class={['key-method', item.operation?.id]}>{item.operation.name}</span>
                      </div>
                      <div class='value-wrap'>
                        {item.value.map((item, index) => [
                          index > 0 && (
                            <span
                              key={`${index}_condition`}
                              class='value-condition'
                            >
                              OR
                            </span>
                          ),
                          <span
                            key={`${index}_key`}
                            class='value-name'
                          >
                            {item || '""'}
                          </span>,
                        ])}
                      </div>
                    </div>
                  ))
                : '--'}
            </div>
          </div>
        </VariableCommonFormDetail>
      </div>
    );
  }
}
