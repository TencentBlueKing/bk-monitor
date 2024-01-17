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

import { defineComponent, inject, onMounted, PropType, reactive, Ref, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Switcher } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';

import { listApplicationServices, queryLabels, queryServicesDetail } from '../../../../monitor-api/modules/apm_profile';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import {
  ApplicationList,
  ConditionType,
  IConditionItem,
  RetrievalFormData,
  SearchType,
  ToolsFormData
} from '../typings';

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
    const toolsFormData = inject<Ref<ToolsFormData>>('toolsFormData');

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
    /** 应用/服务可选列表 */
    const applicationList = ref<ApplicationList>({
      normal: [],
      no_data: []
    });
    /** 当前选中的应用/服务 */
    const selectApplicationData = ref();
    const localFormData = reactive<RetrievalFormData>({
      type: SearchType.Profiling,
      server: {
        app_name: '',
        service_name: ''
      },
      isComparison: false,
      where: [],
      comparisonWhere: []
    });
    watch(
      () => props.formData,
      newVal => {
        newVal && Object.assign(localFormData, newVal);
      },
      {
        immediate: true
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

    /**
     * 选择应用/服务
     * @param val 选项值
     */
    function handleApplicationChange(val: string[]) {
      const [appName, serviceName] = val;
      localFormData.server.app_name = appName;
      localFormData.server.service_name = serviceName;
      getLabelList();
      handleEmitChange();
    }

    /** 查看详情 */
    async function handleDetailClick() {
      if (!localFormData.server.app_name || !localFormData.server.service_name) return;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      selectApplicationData.value = await queryServicesDetail({
        start_time: start * 1000 * 1000,
        end_time: end * 1000 * 1000,
        app_name: localFormData.server.app_name,
        service_name: localFormData.server.service_name
      }).catch(() => ({}));
      emit('showDetail', selectApplicationData.value);
    }

    /**
     * 对比模式开关
     * @param val 开关状态
     */
    function handleComparisonChange(val: boolean) {
      localFormData.isComparison = val;
      handleEmitChange();
    }

    const labelList = ref<string[]>([]);
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
    function handleConditionChange(val: IConditionItem, index: number, type: ConditionType) {
      if (type === ConditionType.Where) {
        localFormData.where[index] = val;
      } else {
        localFormData.comparisonWhere[index] = val;
      }
      handleEmitChange();
    }

    onMounted(() => {
      getApplicationList();
      getLabelList();
    });

    /** 获取应用/服务列表 */
    async function getApplicationList() {
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      applicationList.value = await listApplicationServices({
        start_time: start * 1000 * 1000,
        end_time: end * 1000 * 1000
      }).catch(() => ({
        normal: [
          {
            bk_biz_id: 100605,
            application_id: 2,
            app_name: 'profiling_bar',
            app_alias: 'demo应用',
            description: 'xxx',
            services: [
              {
                id: 2,
                name: 'service2',
                has_data: false
              },
              {
                id: 3,
                name: 'service3',
                has_data: true
              }
            ]
          }
        ],
        no_data: [
          {
            bk_biz_id: 100605,
            application_id: 2,
            app_name: 'profiling_bar2',
            app_alias: 'demo应用2',
            description: 'xxx',
            services: [
              {
                id: 2,
                name: 'service3',
                has_data: false
              }
            ]
          }
        ]
      }));
    }

    /** 获取过滤项列表 */
    async function getLabelList() {
      if (!localFormData.server.app_name || !localFormData.server.service_name) return;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      const labels = await queryLabels({
        app_name: localFormData.server.app_name,
        service_name: localFormData.server.service_name,
        start: start * 1000 * 1000,
        end: end * 1000 * 1000
      }).catch(() => ({ label_keys: [] }));
      labelList.value = labels.label_keys;
    }

    function handleEmitChange() {
      emit('change', localFormData);
    }

    return {
      t,
      applicationList,
      localFormData,
      retrievalType,
      labelList,
      handleTypeChange,
      handleApplicationChange,
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
                  <ApplicationCascade
                    list={this.applicationList}
                    value={[this.localFormData.server.app_name, this.localFormData.server.service_name]}
                    onChange={this.handleApplicationChange}
                  ></ApplicationCascade>
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
                  labelList={this.labelList}
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
                    labelList={this.labelList}
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
