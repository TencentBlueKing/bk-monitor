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

import { defineComponent, reactive, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Switcher } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';

import ApplicationCascade from './application-cascade';

import './profiling-retrieval.scss';

export default defineComponent({
  name: 'ProfilingRetrieval',
  props: {
    formData: {
      type: Object,
      default: () => null
    }
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const retrievalType = [
      {
        label: t('持续 Profiling'),
        value: 'continuous'
      },
      {
        label: t('上传 Profiling'),
        value: 'upload'
      }
    ];
    const localFormData = reactive({
      type: 'continuous',
      servers: null,
      isComparison: false,
      where: []
    });
    watch(
      () => props.formData,
      newVal => {
        if (props.formData) {
          Object.assign(localFormData, newVal);
        }
      }
    );

    function handleTypeChange(type: string) {
      if (localFormData.type === type) return;
      localFormData.type = type;
      handleEmitChange();
    }

    function handleComparisonChange(val: boolean) {
      localFormData.isComparison = val;
      handleEmitChange();
    }

    function handleEmitChange() {
      emit('change', localFormData);
    }

    return {
      t,
      localFormData,
      retrievalType,
      handleTypeChange,
      handleComparisonChange
    };
  },
  render() {
    return (
      <div class='profiling-retrieval-component'>
        <div class='title'>{this.t('Profiling 检索')}</div>
        <div class='search-form-wrap'>
          <Button.ButtonGroup class='type-button-group'>
            {this.retrievalType.map(item => (
              <Button
                class='button-item'
                selected={item.value === this.localFormData.type}
                onClick={() => this.handleTypeChange(item.value)}
              >
                {item.label}
              </Button>
            ))}
          </Button.ButtonGroup>

          <div class='form-wrap'>
            {this.localFormData.type === 'continuous' && (
              <div class='service form-item'>
                <div class='label'>{this.t('应用/服务')}</div>
                <div class='content'>
                  <ApplicationCascade></ApplicationCascade>
                </div>
              </div>
            )}
            <div class='comparison form-item'>
              <div class='label'>{this.t('对比模式')}</div>
              <div class='content'>
                <Switcher
                  modelValue={this.localFormData.isComparison}
                  theme='primary'
                  onChange={this.handleComparisonChange}
                />
              </div>
            </div>
            <div class='search-panel'>
              <div class='search-title'>{this.t('查询项')}</div>

              <Button class='add-condition'>
                <Plus class='f22' />
                {this.t('添加条件')}
              </Button>
            </div>
            {this.localFormData.isComparison && (
              <div class='search-panel'>
                <div class='search-title'>{this.t('对比项')}</div>
                <Button class='add-condition'>
                  <Plus class='f22' />
                  {this.t('添加条件')}
                </Button>
              </div>
            )}
          </div>

          <div class='retrieve-button-tools-group'>{this.$slots.query?.()}</div>
        </div>
      </div>
    );
  }
});
