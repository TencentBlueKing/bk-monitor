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
import FilterVarGroup from './filter-var-group';
import FilterVarSelectSimple from './filter-var-select-simple';
import GroupsSelector from './groups-selector';
import LayoutSelect from './layout-select';
import { CP_METHOD_LIST, DEFAULT_METHOD, METHOD_LIST, PANEL_INTERVAL_LIST } from './utils';

import type { IViewOptions, PanelModel } from '../../../plugins/typings';

import './dashboard-panel.scss';

const cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
const ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];

export default defineComponent({
  name: 'DashboardPanel',
  props: {
    sceneId: { type: String, default: '' },
    sceneViewParams: { type: Object, default: () => ({}) },
    // 是否为单图模式
    isSingleChart: { default: false, type: Boolean },
    sceneData: { type: Object as PropType<PanelModel>, required: true },
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
    const timeRange = ref([startTimeMinusOneHour, endTimeMinusOneHour]);
    const compareType = ref(CompareId.none);
    const currentTarget = ref(null);
    const curTargetTitle = ref('');
    const compareTargets = ref([]);
    const timeOffset = shallowRef([]);

    const filtersVal = shallowRef({});
    const targetList = shallowRef([]);
    const groups = shallowRef([]);
    const viewOptions = shallowRef<IViewOptions>({
      interval: 'auto',
      method: DEFAULT_METHOD,
      group_by: [],
      compare_targets: [],
      current_target: null,
    });
    const panelsColumn = ref(1);

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
          // handleGetTargetsData();
          handleGetGroupsData();
        }
      },
      { immediate: true }
    );

    // async function handleGetTargetsData() {
    //   const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
    //   const variablesService = new VariablesService({
    //     start_time: startTime,
    //     end_time: endTime,
    //   });
    //   const promiseList =
    //     selectorPanel.value?.targets?.map(item =>
    //       currentInstance?.appContext.config.globalProperties?.$api[item.apiModule]
    //         [item.apiFunc]({
    //           ...variablesService.transformVariables(item.data),
    //           start_time: startTime,
    //           end_time: endTime,
    //         })
    //         .then(data => {
    //           const list = Object.prototype.toString.call(data) === '[object Object]' ? data.data : data;
    //           return list;
    //         })
    //         .catch(err => {
    //           console.error(err);
    //           return [];
    //         })
    //     ) || [];
    //   const res = await Promise.all(promiseList).catch(err => {
    //     console.error(err);
    //     return [];
    //   });
    //   const hostListData = res.reduce((total, cur) => total.concat(cur), []);
    //   targetList.value = hostListData;
    // }

    async function handleGetGroupsData() {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      const variablesService = new VariablesService({
        start_time: startTime,
        end_time: endTime,
      });
      const target = groupPanel.value?.targets?.[0];
      if (!target) {
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
        });
    }

    function handleIntervalChange(val) {
      viewOptions.value = {
        ...viewOptions.value,
        interval: val,
      };
    }
    function handleMethodChange(val) {
      viewOptions.value = {
        ...viewOptions.value,
        method: val,
      };
    }

    function handleChangeLayout(val) {
      panelsColumn.value = val;
    }

    function handleGroupChange(val) {
      viewOptions.value = {
        ...viewOptions.value,
        group_by: val,
      };
    }

    function handleFiltersChange(val) {
      filtersVal.value = {
        ...filtersVal.value,
        ...val,
      };
      const currentTargetTemp = {};
      for (const key in val) {
        if (cloudIdMap.includes(key) || ipMap.includes(key)) {
          currentTarget[key] = val[key];
        }
      }
      currentTarget.value = Object.keys(currentTargetTemp).length ? currentTargetTemp : null;
      viewOptions.value = {
        ...viewOptions.value,
        variables: val,
        current_target: currentTarget.value || undefined,
      };
    }

    function handleCompareTypeChange(val) {
      compareType.value = val;
      compareTargets.value = [];
      timeOffset.value = [];
      viewOptions.value = {
        ...viewOptions.value,
        compare_targets: [],
      };
    }
    function handleCompareTimeChange(val) {
      timeOffset.value = val;
    }
    function handleCompareTargetChange(val) {
      compareTargets.value = val;
      viewOptions.value = {
        ...viewOptions.value,
        compare_targets: compareTargets.value,
      };
    }

    function handleTargetListChange(val) {
      targetList.value = val;
    }
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
            <FilterVarGroup
              panels={this.variablesPanel}
              onChange={this.handleFiltersChange}
              onCurTargetTitleChange={this.handleCurTargetTitleChange}
              onTargetListChange={this.handleTargetListChange}
            />
            {this.sceneId === 'container' && (
              <GroupsSelector
                list={this.groups}
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
