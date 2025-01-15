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
import { computed, defineComponent, getCurrentInstance, inject, type PropType, type Ref, ref } from 'vue';
import { watch } from 'vue';
import { shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import dayjs from 'dayjs';
import { random } from 'monitor-common/utils';

import CommonDetail from '../../../components/common-detail/common-detail';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import FlexDashboardPanel from '../../../plugins/components/flex-dashboard-panel';
import { useTimeOffsetProvider, useViewOptionsProvider } from '../../../plugins/hooks';
import { VariablesService } from '../../../utils/index';
import CompareSelect, { CompareId } from './compare-select';
// import FilterVarGroup from './filter-var-group';
import FilterVarSelectSimple from './filter-var-select-simple';
import FilterVarTagInput from './filter-var-tag-input';
import GroupsSelector from './groups-selector';
import LayoutSelect from './layout-select';
import { CP_METHOD_LIST, DEFAULT_METHOD, METHOD_LIST, PANEL_INTERVAL_LIST } from './utils';

import type { BookMarkModel, IViewOptions } from '../../../plugins/typings';

import './dashboard-panel.scss';

const cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
const ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];

export default defineComponent({
  name: 'DashboardPanel',
  props: {
    sceneId: { type: String, default: '' },
    // 是否为单图模式
    isSingleChart: { default: false, type: Boolean },
    sceneData: { type: Object as PropType<BookMarkModel>, required: true },
    groupTitle: { type: String, default: 'Groups' },
  },

  setup(props) {
    const { t } = useI18n();
    const currentInstance = getCurrentInstance();
    const startTime = inject<Ref>('startTime') || ref('');
    const endTime = inject<Ref>('endTime') || ref('');
    const startTimeMinusOneHour = dayjs
      .tz(startTime.value || undefined)
      .subtract(1, 'hour')
      .format('YYYY-MM-DD HH:mm:ss');
    const endTimeMinusOneHour = dayjs
      .tz(endTime.value || undefined)
      .add(1, 'hour')
      .format('YYYY-MM-DD HH:mm:ss');
    // 时间范围
    const timeRange = ref([startTimeMinusOneHour, endTimeMinusOneHour]);
    // 对比类型
    const compareType = ref(CompareId.none);
    // 当前目标
    const currentTarget = ref(null);
    // 当前目标name
    const curTargetTitle = ref('');
    // 目标对比的对比列表
    const compareTargets = ref([]);
    // 时间对比
    const timeOffset = shallowRef([]);
    // 当前选择的变量（当前仅有主机列表与容器列表）
    const filtersVal = shallowRef({});
    // 目标对比的可选项
    const targetList = shallowRef([]);
    // group_by 可选项
    const groups = shallowRef([]);
    const viewOptions = shallowRef<IViewOptions>({
      interval: 'auto',
      method: DEFAULT_METHOD,
      group_by: [],
      compare_targets: [],
      current_target: null,
      filters: {},
      variables: {},
    });
    // 当前选择的图表分列
    const panelsColumn = ref(1);
    const groupsLoading = ref(false);

    useViewOptionsProvider(viewOptions);
    useTimeOffsetProvider(timeOffset);

    const selectorPanel = computed(() => {
      return props.sceneData?.selectorPanel;
    });
    const variablesPanel = computed(() => {
      return props.sceneData?.variables;
    });
    const groupPanel = computed(() => {
      return props.sceneData?.groupPanel;
    });
    const compareListEnable = computed(() => {
      if (props.sceneId === 'host') {
        return [CompareId.none, CompareId.time, CompareId.target];
      }
      if (props.sceneId === 'container') {
        return [CompareId.none, CompareId.time];
      }
      return [];
    });

    watch(
      () => props.sceneData,
      sceneData => {
        if (sceneData) {
          handleGetGroupsData();
        }
      },
      { immediate: true }
    );

    /**
     * @description 获取group by 选项数据
     * @returns
     */
    async function handleGetGroupsData() {
      groupsLoading.value = true;
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      const variablesService = new VariablesService({
        start_time: startTime,
        end_time: endTime,
      });
      const target = groupPanel.value?.targets?.[0];
      if (!target) {
        groupsLoading.value = false;
        return;
      }
      currentInstance?.appContext.config.globalProperties?.$api[target.apiModule]
        [target.apiFunc]({
          ...variablesService.transformVariables(target.data),
          start_time: startTime,
          end_time: endTime,
        })
        .then(data => {
          groups.value = data;
        })
        .catch(err => {
          console.error(err);
          return [];
        })
        .finally(() => {
          groupsLoading.value = false;
        });
    }

    /**
     * @description 汇聚周期数据
     * @param val
     */
    function handleIntervalChange(val) {
      viewOptions.value = {
        ...viewOptions.value,
        interval: val,
      };
    }
    /**
     * @description 汇聚方法
     * @param val
     */
    function handleMethodChange(val) {
      viewOptions.value = {
        ...viewOptions.value,
        method: val,
      };
    }
    /**
     * @description 图表分列
     * @param val
     */
    function handleChangeLayout(val) {
      panelsColumn.value = val;
    }
    /**
     * @description group_by数据
     * @param val
     */
    function handleGroupChange(val) {
      viewOptions.value = {
        ...viewOptions.value,
        group_by: val,
      };
    }
    /**
     * @description filters （当前为主机列表与容器列表选择）
     * @param val
     */
    function handleFiltersChange(val) {
      filtersVal.value = {
        ...filtersVal.value,
        ...val,
      };
      const currentTargetTemp = {};
      for (const key in val) {
        if (cloudIdMap.includes(key) || ipMap.includes(key)) {
          currentTargetTemp[key] = val[key];
        }
      }
      currentTarget.value = Object.keys(currentTargetTemp).length ? currentTargetTemp : null;
      viewOptions.value = {
        ...viewOptions.value,
        variables: val,
        current_target: currentTarget.value || undefined,
      };
    }
    /**
     * @description 对比类型
     * @param val
     */
    function handleCompareTypeChange(val) {
      compareType.value = val;
      compareTargets.value = [];
      timeOffset.value = [];
      viewOptions.value = {
        ...viewOptions.value,
        compare_targets: [],
      };
    }
    /**
     * @description 时间对比
     * @param val
     */
    function handleCompareTimeChange(val) {
      console.log(val);
      timeOffset.value = val;
    }
    /**
     * @description 目标对比
     * @param val
     */
    function handleCompareTargetChange(val) {
      const compareTargetsTemp = [];
      for (const target of val) {
        const targetTemp = {};
        for (const key in target) {
          if (cloudIdMap.includes(key) || ipMap.includes(key)) {
            targetTemp[key] = target[key];
          }
        }
        compareTargetsTemp.push(targetTemp);
      }
      compareTargets.value = compareTargetsTemp;
      viewOptions.value = {
        ...viewOptions.value,
        compare_targets: compareTargets.value,
      };
    }
    /**
     * @description 目标列表数据（当前为主机列表与容器列表中接口获取）
     * @param val
     */
    function handleTargetListChange(val) {
      targetList.value = val;
    }
    /**
     * @description 当前目标，用于目标对比
     * @param val
     */
    function handleCurTargetTitleChange(val) {
      curTargetTitle.value = val;
    }

    return {
      selectorPanel,
      targetList,
      viewOptions,
      panelsColumn,
      variablesPanel,
      groups,
      compareListEnable,
      curTargetTitle,
      groupsLoading,
      t,
      handleIntervalChange,
      handleMethodChange,
      handleChangeLayout,
      handleGroupChange,
      handleFiltersChange,
      handleCompareTypeChange,
      handleCompareTimeChange,
      handleCompareTargetChange,
      handleTargetListChange,
      handleCurTargetTitleChange,
    };
  },

  render() {
    return (
      <div class='span-details__dashboard-panel'>
        <div class='dashboard-panel__charts'>
          <div class='groups-header'>
            {!!this.variablesPanel.length && (
              <FilterVarTagInput
                panel={this.variablesPanel[0]}
                onChange={this.handleFiltersChange}
                onCurTargetTitleChange={this.handleCurTargetTitleChange}
                onTargetListChange={this.handleTargetListChange}
              />
            )}
            {/* <FilterVarGroup
              panels={this.variablesPanel}
              onChange={this.handleFiltersChange}
              onCurTargetTitleChange={this.handleCurTargetTitleChange}
              onTargetListChange={this.handleTargetListChange}
            /> */}
            {this.sceneId === 'container' && (
              <GroupsSelector
                list={this.groups}
                loading={this.groupsLoading}
                name={this.groupTitle}
                value={this.viewOptions.group_by}
                onChange={this.handleGroupChange}
              />
            )}
          </div>
          <div class='dashboard-tools'>
            <FilterVarSelectSimple
              class='mr-24'
              label={this.t('汇聚周期') as string}
              options={PANEL_INTERVAL_LIST}
              value={this.viewOptions.interval}
              onChange={this.handleIntervalChange}
            />
            <FilterVarSelectSimple
              class='mr-24'
              label={this.t('汇聚方法') as string}
              options={METHOD_LIST.concat(...CP_METHOD_LIST)}
              value={this.viewOptions.method}
              onChange={this.handleMethodChange}
            />
            <CompareSelect
              compareListEnable={this.compareListEnable}
              curTarget={this.curTargetTitle}
              panel={this.variablesPanel}
              targetOptions={this.targetList}
              onTargetChange={this.handleCompareTargetChange}
              onTimeChange={this.handleCompareTimeChange}
              onTypeChange={this.handleCompareTypeChange}
            />
            <LayoutSelect
              class='ml-auto'
              layoutActive={this.panelsColumn}
              onLayoutChange={this.handleChangeLayout}
            />
          </div>
          <div class='dashboard-panel__content'>
            <FlexDashboardPanel
              id={random(10)}
              column={this.panelsColumn}
              dashboardId={random(10)}
              isSingleChart={this.isSingleChart}
              needOverviewBtn={!!this.sceneData?.list?.length}
              panels={this.sceneData?.overview_panels}
            />
          </div>
        </div>

        {this.sceneData?.overviewDetailPanel && <CommonDetail panel={this.sceneData?.overviewDetailPanel} />}
      </div>
    );
  },
});
