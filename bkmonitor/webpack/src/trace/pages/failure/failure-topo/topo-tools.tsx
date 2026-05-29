/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent, onMounted, ref, shallowRef, watch } from 'vue';

import { incidentTopologyMenu } from 'monitor-api/modules/incident';
import { random } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { useIncidentInject } from '../utils';
import AggregationSelect from './aggregation-select';
import Timeline from './timeline';

import type { TopoRawData } from './types';

import './topo-tools.scss';

const fullscreenHelper = (function () {
  // 全屏请求的兼容性封装
  function requestFullscreen(element) {
    if (element.requestFullscreen) {
      element.requestFullscreen();
    } else if (element.webkitRequestFullscreen) {
      element.webkitRequestFullscreen();
    } else if (element.mozRequestFullScreen) {
      element.mozRequestFullScreen();
    } else if (element.msRequestFullscreen) {
      element.msRequestFullscreen();
    } else {
      console.error('Fullscreen API is not supported in this browser');
    }
  }

  // 全屏退出的兼容性封装
  function exitFullscreen() {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else {
      console.error('Fullscreen API is not supported in this browser');
    }
  }

  // 监听全屏事件的处理
  function onFullscreenChange(handler) {
    document.addEventListener('fullscreenchange', handler, false);
    document.addEventListener('webkitfullscreenchange', handler, false);
    document.addEventListener('mozfullscreenchange', handler, false);
    document.addEventListener('MSFullscreenChange', handler, false);
  }

  return {
    requestFullscreen,
    exitFullscreen,
    onFullscreenChange,
  };
})();

export default defineComponent({
  name: 'TopoTools',
  props: {
    topoRawDataList: {
      type: Array as PropType<TopoRawData[]>,
      default: () => [],
    },
    timelinePlayPosition: {
      type: Number,
      default: 0,
    },
    showResource: {
      type: Boolean,
      default: false,
    },
    showService: {
      type: Boolean,
      default: false,
    },
  },
  emits: [
    'update:AggregationConfig',
    'changeRefleshTime',
    'timelineChange',
    'play',
    'showService',
    'update:showResource',
    'update:showService',
  ],
  setup(props, { emit }) {
    const treeData = shallowRef([]);
    const checkedIds = ref([]);
    const isAutoAggregate = ref(true);
    // 从属关系聚合（控制 UI 树形选择器展示，不直接传接口）
    const aggregateCluster = ref(false);
    // 部署版本聚合（对应接口字段 aggregate_version）
    const aggregateVersion = ref(false);
    // 调用关系聚合（对应接口字段 aggregate_cluster）
    const aggregateCall = ref(true);
    /** 菜单接口返回的动态聚合开关列表 */
    const aggregateSwitches = shallowRef<{ [k: string]: any; default: boolean; key: string; name: string }[]>([]);
    /** 动态开关的当前状态 map，key 为 switch.key */
    const switchStates = ref<Record<string, boolean>>({});
    let aggregateIdText = '';
    const isFullscreen = ref(false);
    const { t } = useI18n();
    const aggregateConfig = ref({});
    const timeLine = ref(null);
    const incidentId = useIncidentInject();
    const handleChangeRefleshTime = (value: number) => {
      emit('changeRefleshTime', value);
    };
    const handleTimelineChange = (value: number) => {
      emit('timelineChange', value);
    };
    const handleChangeTimeLine = value => {
      timeLine.value.changeTimeLine(value);
    };
    /** 缓存默认选中 ID */
    const setCheckedId = data => {
      checkedIds.value = [];
      Object.keys(data.default_aggregated_config).forEach(key => {
        const treeNode = treeData.value.find(item => item.key === key);
        if (treeNode) {
          const select = data.default_aggregated_config[key];
          if (select.includes(treeNode.key)) {
            // 选中所有子节点和父节点
            checkedIds.value.push(...treeNode.children.map(({ id }) => id), treeNode.id);
          } else {
            const hasSelectedChild = treeNode.children.some(s => select.includes(s.key));
            if (hasSelectedChild) {
              checkedIds.value.push(treeNode.id);
            }
            // 选中匹配的子节点
            treeNode.children.forEach(({ key, id }) => {
              if (select.includes(key)) {
                checkedIds.value.push(id);
              }
            });
          }
        }
      });
      // 缓存默认选中的 ID 字符串，用于判断是否为自动聚合状态
      aggregateIdText = checkedIds.value.join('|');
    };
    /** 获取聚合数据 */
    incidentTopologyMenu(
      {
        id: incidentId.value,
      },
      { needMessage: false }
    ).then(data => {
      treeData.value = data.menu.map(item => {
        const parentId = random(10);
        return {
          ...item,
          id: parentId,
          name: item.entity_type,
          key: item.entity_type,
          children: item.aggregate_bys?.map(child => {
            const name = !child.is_anomaly
              ? `${t('按 {0} 聚合', [child.aggregate_key])}`
              : `${`${t('聚合异常')}${item.entity_type}`}`;
            return {
              ...child,
              parentId,
              id: random(10),
              name,
              key: child.aggregate_key,
            };
          }),
        };
      });
      // 解析动态聚合开关列表 (如 aggregate_version)
      if (data.aggregate_switches?.length) {
        aggregateSwitches.value = data.aggregate_switches;
        const states: Record<string, boolean> = {};
        for (const sw of data.aggregate_switches) {
          states[sw.key] = sw.default ?? false;
          // 将后端返回的 default 值同步到对应的 ref 变量
          if (sw.key === 'aggregate_version') {
            aggregateVersion.value = sw.default ?? false;
          }
        }
        switchStates.value = states;
      }
      // 缓存默认聚合选中的 ID，用于手动聚合模式
      setCheckedId(data);
    });
    /** 设置 Tree 数据的选中状态（仅在手动聚合模式下使用） */
    const setTreeDataChecked = () => {
      const config = {};
      treeData.value = treeData.value.map(item => {
        return {
          ...item,
          checked: checkedIds.value.includes(item.id),
          children: item.children?.map(child => {
            const checked = checkedIds.value.includes(child.id);
            if (checked) {
              if (!config[item.entity_type]) {
                config[item.entity_type] = {
                  aggregate_keys: [],
                  aggregate_anomaly: false,
                };
              }
              if (child.is_anomaly) {
                config[item.entity_type].aggregate_anomaly = true;
              } else {
                config[item.entity_type].aggregate_keys.push(child.aggregate_key);
              }
            }
            return {
              ...child,
              checked,
            };
          }),
        };
      });
      aggregateConfig.value = config;
    };
    /** 更新聚合规则 */
    const handleUpdateAutoAggregate = (v: boolean) => {
      isAutoAggregate.value = v;

      if (!v) {
        // 切换到手动聚合：初始化选中状态和 Tree 数据
        if (checkedIds.value.length === 0 && aggregateIdText) {
          checkedIds.value = aggregateIdText.split('|');
        }
        // 更新 treeData 的 checked 属性，供 Tree 组件使用
        setTreeDataChecked();
      }

      updateAggregationConfig();
    };
    /** 更新选中（手动聚合模式下的 Tree 勾选变化） */
    const handleUpdateCheckedIds = (v: string[]) => {
      checkedIds.value = v;
      // 更新 treeData 的 checked 属性和聚合配置
      setTreeDataChecked();
      updateAggregationConfig();
    };
    /** 重置到默认选中状态 */
    const handleResetCheckedIds = () => {
      if (aggregateIdText) {
        checkedIds.value = aggregateIdText.split('|');
        setTreeDataChecked();
        updateAggregationConfig();
      }
    };
    /** 更新从属关系聚合 */
    const handleUpdateAggregateCluster = (v: boolean) => {
      aggregateCluster.value = v;
      updateAggregationConfig();
    };
    /** 更新部署版本聚合 */
    const handleUpdateAggregateVersion = (v: boolean) => {
      aggregateVersion.value = v;
      switchStates.value = { ...switchStates.value, aggregate_version: v };
      updateAggregationConfig();
    };
    /** 更新调用关系聚合 */
    const handleUpdateAggregateCall = (v: boolean) => {
      aggregateCall.value = v;
      updateAggregationConfig();
    };
    /** 播放 */
    const handlePlay = value => {
      emit('play', value);
    };
    const getAggregationConfigValue = () => {
      const config: Record<string, any> = {
        aggregate_call: aggregateCall.value,
        aggregate_version: aggregateVersion.value,
        auto_aggregate: isAutoAggregate.value,
      };
      /** 手动聚合 + 从属关系聚合开启 + 有勾选节点时，才带 aggregate_config */
      if (!isAutoAggregate.value && aggregateCluster.value && checkedIds.value.length) {
        config.aggregate_config = aggregateConfig.value;
      }
      return config;
    };
    const updateAggregationConfig = () => {
      emit('update:AggregationConfig', getAggregationConfigValue());
    };
    /** 全屏相关 */
    const exitFullscreen = () => {
      if (!document.fullscreenElement) {
        isFullscreen.value = false;
      }
    };
    const handleFullscreen = () => {
      if (isFullscreen.value) {
        fullscreenHelper.exitFullscreen();
        isFullscreen.value = false;
      } else {
        fullscreenHelper.requestFullscreen(document.querySelector('.failure-topo'));
        isFullscreen.value = true;
      }
    };
    onMounted(() => {
      fullscreenHelper.onFullscreenChange(exitFullscreen);
    });

    const isResourceHover = ref(false);
    const isServiceHover = ref(false);
    const isResourceSelected = ref(props.showResource);
    const isServiceSelected = ref(props.showService);

    watch(
      () => props.showResource,
      newVal => {
        isResourceSelected.value = newVal;
      }
    );

    watch(
      () => props.showService,
      newVal => {
        isServiceSelected.value = newVal;
      }
    );

    const handleToggle = (type: 'resource' | 'service') => {
      if (type === 'resource') {
        isResourceSelected.value = !isResourceSelected.value;
        emit('update:showResource', isResourceSelected.value);
      } else {
        isServiceSelected.value = !isServiceSelected.value;
        emit('update:showService', isServiceSelected.value);

        if (isServiceSelected.value) {
          emit('showService');
        }
      }
    };

    return {
      isFullscreen,
      aggregateIdText,
      treeData,
      timeLine,
      checkedIds,
      isAutoAggregate,
      aggregateSwitches,
      isResourceHover,
      isResourceSelected,
      isServiceHover,
      isServiceSelected,
      handleFullscreen,
      handleChangeTimeLine,
      handleUpdateAutoAggregate,
      handleUpdateCheckedIds,
      handleResetCheckedIds,
      handleUpdateAggregateCluster,
      handleUpdateAggregateVersion,
      handleUpdateAggregateCall,
      handleChangeRefleshTime,
      handleTimelineChange,
      handlePlay,
      t,
      handleToggle,
    };
  },
  render() {
    return (
      <div class='topo-tools'>
        <AggregationSelect
          class='topo-tools-agg'
          aggregateSwitches={this.aggregateSwitches}
          checkedIds={this.checkedIds}
          isAutoAggregate={this.isAutoAggregate}
          treeData={this.treeData}
          onReset:checkedIds={this.handleResetCheckedIds}
          onUpdate:aggregateCall={this.handleUpdateAggregateCall}
          onUpdate:aggregateCluster={this.handleUpdateAggregateCluster}
          onUpdate:aggregateVersion={this.handleUpdateAggregateVersion}
          onUpdate:checkedIds={this.handleUpdateCheckedIds}
          onUpdate:isAutoAggregate={this.handleUpdateAutoAggregate}
        />
        <Timeline
          ref='timeLine'
          timelinePlayPosition={this.timelinePlayPosition}
          topoRawDataList={this.topoRawDataList}
          onChangeRefleshTime={this.handleChangeRefleshTime}
          onPlay={this.handlePlay}
          onTimelineChange={this.handleTimelineChange}
        />
        <div class='topo-sidebar-toggle-wrap'>
          <div class='topo-sidebar-toggle'>
            <span
              class={['resource-wrap', { selected: this.isResourceSelected }]}
              v-bk-tooltips={{ content: this.isResourceSelected ? this.t('收起资源拓扑') : this.t('展开资源拓扑') }}
              onClick={() => this.handleToggle('resource')}
              onMouseenter={() => {
                this.isResourceHover = true;
              }}
              onMouseleave={() => {
                this.isResourceHover = false;
              }}
            >
              <i class='icon-monitor icon-ziyuan' />
            </span>
            <span
              class={['service-wrap', { selected: this.isServiceSelected }]}
              v-bk-tooltips={{
                content: this.isServiceSelected ? this.t('收起节点/边概览') : this.t('展开节点/边概览'),
              }}
              onClick={() => this.handleToggle('service')}
              onMouseenter={() => {
                this.isServiceHover = true;
              }}
              onMouseleave={() => {
                this.isServiceHover = false;
              }}
            >
              <i class='icon-monitor icon-mc-overview' />
            </span>
          </div>
        </div>
        <div
          class='topo-tools-list'
          v-bk-tooltips={{ content: this.t('全屏'), disabled: this.isFullscreen }}
          onClick={this.handleFullscreen}
        >
          <span class='fullscreen'>
            <i class={['icon-monitor', !this.isFullscreen ? 'icon-mc-full-screen' : 'icon-shouqi1']} />
          </span>
        </div>
      </div>
    );
  },
});
