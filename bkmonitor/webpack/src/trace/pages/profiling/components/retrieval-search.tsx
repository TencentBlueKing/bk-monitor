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

import {
  listApplicationServices,
  queryLabels,
  queryLabelValues,
  queryServicesDetail
} from '../../../../monitor-api/modules/apm_profile';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import {
  ApplicationList,
  ConditionType,
  IConditionItem,
  RetrievalFormData,
  SearchType,
  ServicesDetail,
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
  emits: ['change', 'typeChange', 'showDetail', 'detailChange'],
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
    const selectApplicationData = ref<ServicesDetail>();
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
      props.formData,
      newVal => {
        newVal && Object.assign(localFormData, newVal);
      },
      {
        immediate: true
      }
    );
    watch(
      () => toolsFormData.value.timeRange,
      () => {
        getLabelList();
        getApplicationList();
      }
    );

    /**
     * 检索类型切换
     * @param type 检索类型
     */
    function handleTypeChange(type: SearchType) {
      if (localFormData.type === type) return;
      localFormData.type = type;
      if (type === SearchType.Upload) {
        // 文件上传暂时不做对比项
        localFormData.isComparison = false;
      }
      getLabelList();
      handleEmitChange();
      emit('typeChange', type);
    }

    /**
     * 选择应用/服务
     * @param val 选项值
     */
    function handleApplicationChange(val: string[]) {
      if (!val.length) return;
      const [appName, serviceName] = val;
      if (localFormData.server.app_name === appName && localFormData.server.service_name === serviceName) return;
      localFormData.server.app_name = appName;
      localFormData.server.service_name = serviceName;
      getLabelList();
      getDetail();
      handleEmitChange();
    }

    async function getDetail() {
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      selectApplicationData.value = await queryServicesDetail({
        start_time: start,
        end_time: end,
        app_name: localFormData.server.app_name,
        service_name: localFormData.server.service_name
      }).catch(() => ({}));
      emit('detailChange', selectApplicationData.value);
    }

    /** 查看详情 */
    async function handleDetailClick() {
      if (!localFormData.server.app_name || !localFormData.server.service_name) return;
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
    const labelValueMap = new Map();
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
     * 删除条件
     * @param index 索引
     * @param type 条件类型
     */
    function deleteCondition(index: number, type: ConditionType) {
      if (type === ConditionType.Where) {
        localFormData.where.splice(index, 1);
      } else {
        localFormData.comparisonWhere.splice(index, 1);
      }
      handleEmitChange();
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
      getLabelValues(val.key);
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
        start_time: start,
        end_time: end
      }).catch(() => ({
        normal: [],
        no_data: []
      }));
    }

    /** 获取过滤项列表 */
    async function getLabelList() {
      localFormData.where = [];
      localFormData.comparisonWhere = [];
      labelList.value = [];
      labelValueMap.clear();
      if (localFormData.type === SearchType.Profiling && !localFormData.server.app_name) return;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      const server = localFormData.type === SearchType.Profiling ? localFormData.server : {};
      const labels = await queryLabels({
        ...server,
        start: start * 1000 * 1000,
        end: end * 1000 * 1000
      }).catch(() => ({ label_keys: [] }));
      labelList.value = labels.label_keys;
    }

    /** 获取过滤项值列表 */
    async function getLabelValues(label: string) {
      /** 缓存 */
      if (labelValueMap.has(label)) return;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      const server = localFormData.type === SearchType.Profiling ? localFormData.server : {};
      const res = await queryLabelValues({
        ...server,
        start: start * 1000 * 1000,
        end: end * 1000 * 1000,
        label_key: label
      }).catch(() => ({ label_values: [] }));
      labelValueMap.set(label, res.label_values);
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
      labelValueMap,
      handleTypeChange,
      handleApplicationChange,
      handleDetailClick,
      handleComparisonChange,
      addCondition,
      deleteCondition,
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
            {this.localFormData.type === SearchType.Profiling && [
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
              </div>,
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
            ]}

            <div class='search-panel'>
              <div class='search-title'>{this.t('查询项')}</div>
              {this.localFormData.where.map((item, index) => (
                <ConditionItem
                  class='condition-item'
                  data={item}
                  labelList={this.labelList}
                  valueList={this.labelValueMap.get(item.key) || []}
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
                    class='condition-item'
                    data={item}
                    labelList={this.labelList}
                    valueList={this.labelValueMap.get(item.key) || []}
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
  }
});
