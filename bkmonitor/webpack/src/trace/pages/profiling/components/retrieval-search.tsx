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

import {
  type PropType,
  type Ref,
  computed,
  defineComponent,
  inject,
  onMounted,
  ref,
  shallowReadonly,
  toRef,
  unref,
  watch,
} from 'vue';

import { Button, Switcher } from 'bkui-vue';
import { Plus } from 'bkui-vue/lib/icon';
import { listApplicationServices, queryLabels } from 'monitor-api/modules/apm_profile';
import { useI18n } from 'vue-i18n';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import {
  type ApplicationList,
  type IConditionItem,
  type RetrievalFormData,
  type SearchState,
  type ToolsFormData,
  ConditionType,
  SearchType,
} from '../typings';
import ApplicationCascade from './application-cascade';
import ConditionItem from './condition-item';

import './retrieval-search.scss';

export default defineComponent({
  name: 'RetrievalSearch',
  props: {
    formData: {
      type: Object as PropType<RetrievalFormData>,
      default: () => null,
    },
  },
  emits: ['change', 'typeChange', 'appServiceChange', 'showDetail'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const toolsFormData = inject<Ref<ToolsFormData>>('toolsFormData');

    const retrievalType = [
      {
        label: t('持续 Profiling'),
        value: SearchType.Profiling,
      },
      {
        label: t('上传 Profiling'),
        value: SearchType.Upload,
      },
    ];
    /** 应用/服务可选列表 */
    const applicationList = ref<ApplicationList>({
      normal: [],
      no_data: [],
    });
    const applicationListLoading = ref(false);
    const localFormData = shallowReadonly(unref(toRef(props, 'formData')));

    watch(
      () => toolsFormData.value.timeRange,
      () => {
        getApplicationList();
        getLabelList();
      }
    );

    /**
     * 检索类型切换
     * @param type 检索类型
     */
    function handleTypeChange(type: SearchType) {
      if (localFormData.type === type) return;
      emit('typeChange', type);
      getLabelList();
    }

    /**
     * 选择应用/服务
     * @param val 选项值
     */
    function handleApplicationChange(val: string[]) {
      if (!val.length) return;
      const [appName, serviceName] = val;
      if (localFormData.server.app_name === appName && localFormData.server.service_name === serviceName) return;
      emit('appServiceChange', appName, serviceName);
      getLabelList();
    }

    /** 查看详情 */
    async function handleDetailClick() {
      if (!localFormData.server.app_name || !localFormData.server.service_name) return;
      emit('showDetail');
    }

    /**
     * 对比模式开关
     * @param val 开关状态
     */
    function handleComparisonChange(val: boolean) {
      const updateItem: Partial<SearchState['formData']> = {};
      updateItem.isComparison = val;
      if (!val) {
        updateItem.dateComparisonEnable = false;
      }
      handleEmitChange(updateItem, true);
    }

    /**
     * 时间对比开关
     * @param val 开关状态
     */
    function handleDataComparisonChange(val: boolean) {
      const updateItem: Partial<SearchState['formData']> = {};
      updateItem.dateComparisonEnable = val;
      handleEmitChange(updateItem, false);
    }

    const labelList = ref<string[]>([]);
    /**
     * 添加条件
     * @param type 条件类型
     */
    function addCondition(type: ConditionType) {
      const conditionKey: 'comparisonWhere' | 'where' = type === ConditionType.Where ? 'where' : 'comparisonWhere';
      const updateItem: Partial<SearchState['formData']> = {
        [conditionKey]: [
          ...(localFormData?.[conditionKey] || []),
          {
            key: '',
            method: 'eq',
            value: '',
          },
        ],
      };

      handleEmitChange(updateItem, false);
    }

    /**
     * 删除条件
     * @param index 索引
     * @param type 条件类型
     */
    function deleteCondition(index: number, type: ConditionType) {
      const conditionKey: 'comparisonWhere' | 'where' = type === ConditionType.Where ? 'where' : 'comparisonWhere';
      const conditionItem: IConditionItem[] = [...(localFormData?.[conditionKey] || [])];
      const deleteItem = conditionItem.splice(index, 1);
      handleEmitChange(
        {
          [conditionKey]: [...(conditionItem || [])],
        },
        deleteItem[0].value !== ''
      );
    }

    /**
     * 条件修改
     * @param val 修改后的值
     * @param index 条件索引
     * @param type 条件类型
     */
    function handleConditionChange(val: IConditionItem, index: number, type: ConditionType) {
      const conditionKey: 'comparisonWhere' | 'where' = type === ConditionType.Where ? 'where' : 'comparisonWhere';
      const oldVal: IConditionItem = localFormData[conditionKey][index];
      localFormData[conditionKey][index] = val;
      // 如果旧数据有值或者新数据有值，需要根据新条件查询
      handleEmitChange(
        {
          [conditionKey]: [...localFormData[conditionKey]],
        },
        Boolean(oldVal.value || val.value)
      );
    }

    onMounted(() => {
      getApplicationList();
      getLabelList();
    });

    /** 获取应用/服务列表 */
    async function getApplicationList() {
      applicationListLoading.value = true;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      applicationList.value = await listApplicationServices({
        start_time: start,
        end_time: end,
      }).catch(() => ({
        normal: [],
        no_data: [],
      }));
      applicationListLoading.value = false;
    }

    /** 查询项公共参数 */
    const labelCommonParams = computed(() => {
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      const params =
        localFormData.type === SearchType.Profiling
          ? { ...localFormData.server, global_query: false }
          : { global_query: true };
      return {
        ...params,
        start: start * 1000 * 1000,
        end: end * 1000 * 1000,
      };
    });

    /** 获取过滤项列表 */
    async function getLabelList() {
      labelList.value = [];
      const updateItem: Partial<SearchState['formData']> = {
        where: [],
        comparisonWhere: [],
      };

      if (localFormData.type === SearchType.Profiling && !localFormData.server.app_name) {
        handleEmitChange(updateItem, true);
        return;
      }
      const labels = await queryLabels(
        {
          ...labelCommonParams.value,
        },
        { needMessage: false }
      ).catch(() => ({ label_keys: [] }));
      // 获取label列表后，移除不在列表中的选项
      updateItem.where = localFormData.where.filter(item => labels.label_keys.includes(item.key));
      updateItem.comparisonWhere = localFormData.comparisonWhere.filter(item => labels.label_keys.includes(item.key));
      handleEmitChange(updateItem, true);
      labelList.value = labels.label_keys;
    }

    /**
     * @param hasQuery 是否查询
     */
    function handleEmitChange(updateItem: Partial<SearchState['formData']>, hasQuery: boolean) {
      emit('change', updateItem, hasQuery);
    }

    return {
      t,
      applicationList,
      applicationListLoading,
      localFormData,
      retrievalType,
      labelList,
      labelCommonParams,
      handleTypeChange,
      handleApplicationChange,
      handleDetailClick,
      handleComparisonChange,
      handleDataComparisonChange,
      addCondition,
      deleteCondition,
      handleConditionChange,
    };
  },
  render() {
    return (
      <div class='retrieval-search-component'>
        <div class='title'>{this.t('route-Profiling 检索')}</div>
        <div class='search-form-wrap'>
          <Button.ButtonGroup class='type-button-group'>
            {this.retrievalType.map(item => (
              <Button
                key={item.value}
                class='button-item'
                selected={item.value === this.localFormData.type}
                onClick={() => this.handleTypeChange(item.value)}
              >
                {item.label}
              </Button>
            ))}
          </Button.ButtonGroup>

          <div class='form-wrap'>
            {this.localFormData.type === SearchType.Profiling && [
              <div
                key='service'
                class='service form-item'
              >
                <div class='label'>{this.t('应用/服务')}</div>
                <div class='content'>
                  <ApplicationCascade
                    list={this.applicationList}
                    loading={this.applicationListLoading}
                    value={[this.localFormData.server.app_name, this.localFormData.server.service_name]}
                    onChange={this.handleApplicationChange}
                  />
                  <div
                    class='detail-btn'
                    onClick={this.handleDetailClick}
                  >
                    <i class='icon-monitor icon-mc-detail' />
                  </div>
                </div>
              </div>,
              <div
                key='comparison'
                class='comparison form-item'
              >
                <div class='comparison-item'>
                  <div class='label'>{this.t('对比模式')}</div>
                  <div class='content'>
                    <Switcher
                      modelValue={this.localFormData.isComparison}
                      size='small'
                      theme='primary'
                      onChange={this.handleComparisonChange}
                    />
                  </div>
                </div>
                {this.localFormData.isComparison && (
                  <div class='comparison-item'>
                    <div class='label'>{this.t('时间对比')}</div>
                    <div class='content'>
                      <Switcher
                        modelValue={this.localFormData.dateComparisonEnable}
                        size='small'
                        theme='primary'
                        onChange={this.handleDataComparisonChange}
                      />
                    </div>
                  </div>
                )}
              </div>,
            ]}

            <div class='search-panel'>
              <div class='search-title'>{this.t('查询项')}</div>
              {this.localFormData.where.map((item, index) => (
                <ConditionItem
                  key={item.key}
                  class='condition-item'
                  data={item}
                  labelList={this.labelList}
                  valueListParams={this.labelCommonParams}
                  onChange={val => this.handleConditionChange(val, index, ConditionType.Where)}
                  onDelete={() => this.deleteCondition(index, ConditionType.Where)}
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
                    key={item.key}
                    class='condition-item'
                    data={item}
                    labelList={this.labelList}
                    valueListParams={this.labelCommonParams}
                    onChange={val => this.handleConditionChange(val, index, ConditionType.Comparison)}
                    onDelete={() => this.deleteCondition(index, ConditionType.Comparison)}
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
  },
});
