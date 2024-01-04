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

import { defineComponent, PropType, reactive, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Switcher } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';

import { ConditionType, SearchType } from '../typings';
import { RetrievalFormData } from '../typings/profiling-retrieval';

import ApplicationCascade from './application-cascade';
import ConditionItem from './condition-item';

import './retrieval-search.scss';

export default defineComponent({
  name: 'RetrievalSearch',
  props: {
    formData: {
      type: Object as PropType<RetrievalFormData>,
      default: () => null
    }
  },
  emits: ['change', 'showDetail'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const retrievalType = [
      {
        label: t('持续 Profiling'),
        value: SearchType.Profiling
      },
      {
        label: t('上传 Profiling'),
        value: SearchType.Upload
      }
    ];
    const localFormData = reactive<RetrievalFormData>({
      type: SearchType.Profiling,
      server: null,
      isComparison: false,
      where: [],
      comparisonWhere: []
    });
    watch(
      () => props.formData,
      newVal => {
        newVal && Object.assign(localFormData, newVal);
      }
    );

    /**
     * 检索类型切换
     * @param type 检索类型
     */
    function handleTypeChange(type: SearchType) {
      if (localFormData.type === type) return;
      localFormData.type = type;
      handleEmitChange();
    }

    function handleDetailClick() {
      // if (!localFormData.server) return;
      emit('showDetail');
    }

    /**
     * 对比模式开关
     * @param val 开关状态
     */
    function handleComparisonChange(val: boolean) {
      localFormData.isComparison = val;
      handleEmitChange();
    }

    /**
     * 添加条件
     * @param type 条件类型
     */
    function addCondition(type: ConditionType) {
      if (type === ConditionType.Where) {
        localFormData.where.push({
          key: '',
          method: 'eq',
          value: ''
        });
      } else {
        localFormData.comparisonWhere.push({
          key: '',
          method: 'eq',
          value: ''
        });
      }
    }

    /**
     * 条件修改
     * @param val 修改后的值
     * @param index 条件索引
     * @param type 条件类型
     */
    function handleConditionChange(val, index, type: ConditionType) {
      if (type === ConditionType.Where) {
        localFormData.where[index] = val;
      } else {
        localFormData.comparisonWhere[index] = val;
      }
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
      handleDetailClick,
      handleComparisonChange,
      addCondition,
      handleConditionChange
    };
  },
  render() {
    return (
      <div class='retrieval-search-component'>
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
            {this.localFormData.type === SearchType.Profiling && (
              <div class='service form-item'>
                <div class='label'>{this.t('应用/服务')}</div>
                <div class='content'>
                  <ApplicationCascade></ApplicationCascade>
                  <div
                    class='detail-btn'
                    onClick={this.handleDetailClick}
                  >
                    <i class='icon-monitor icon-mc-detail'></i>
                  </div>
                </div>
              </div>
            )}
            <div class='comparison form-item'>
              <div class='label'>{this.t('对比模式')}</div>
              <div class='content'>
                <Switcher
                  modelValue={this.localFormData.isComparison}
                  theme='primary'
                  size='small'
                  onChange={this.handleComparisonChange}
                />
              </div>
            </div>
            <div class='search-panel'>
              <div class='search-title'>{this.t('查询项')}</div>
              {this.localFormData.where.map((item, index) => (
                <ConditionItem
                  class='condition-item'
                  data={item}
                  onChange={val => this.handleConditionChange(val, index, ConditionType.Where)}
                />
              ))}
              <Button
                class='add-condition'
                onClick={() => this.addCondition(ConditionType.Where)}
              >
                <Plus class='f22' />
                {this.t('添加条件')}
              </Button>
            </div>
            {this.localFormData.isComparison && (
              <div class='search-panel'>
                <div class='search-title'>{this.t('对比项')}</div>
                {this.localFormData.comparisonWhere.map((item, index) => (
                  <ConditionItem
                    class='condition-item'
                    data={item}
                    onChange={val => this.handleConditionChange(val, index, ConditionType.Comparison)}
                  />
                ))}
                <Button
                  class='add-condition'
                  onClick={() => this.addCondition(ConditionType.Comparison)}
                >
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
