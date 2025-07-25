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
import { type PropType, defineComponent, onMounted, ref, shallowRef } from 'vue';

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
  },
  emits: ['update:AggregationConfig', 'changeRefleshTime', 'timelineChange', 'play'],
  setup(props, { emit }) {
    const treeData = shallowRef([]);
    const checkedIds = ref([]);
    const autoAggregate = ref(true);
    const aggregateCluster = ref(true);
    let autoAggregateIdText = '';
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
    /** 缓存默认聚合id */
    const setAutoAggregated = data => {
      Object.keys(data.default_aggregated_config).forEach(key => {
        const treeNode = treeData.value.find(item => item.key === key);
        if (treeNode) {
          const select = data.default_aggregated_config[key];
          if (select.includes(treeNode.key)) {
            checkedIds.value.push(treeNode.children.map(({ id }) => id).concat(treeNode.id));
          } else {
            const data = treeNode.children.some(s => select.includes(s.key));
            if (data) {
              checkedIds.value.push(treeNode.id);
            }
            treeNode.children.map(({ key, id }) => {
              select.includes(key) && checkedIds.value.push(id);
            });
          }
        }
      });
      autoAggregateIdText = checkedIds.value.join('|');
    };
    /** 获取聚合数据 */
    incidentTopologyMenu({
      id: incidentId.value,
    }).then(data => {
      // checkedIds.value = data
      treeData.value = data.menu.map(item => {
        const parentId = random(10);
        return {
          ...item,
          id: parentId,
          name: item.entity_type,
          key: item.entity_type,
          children: item.aggregate_bys?.map(child => {
            const name = child.aggregate_key
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
      setAutoAggregated(data);
    });
    /** 设置默认聚合规则选中 */
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
      if (v) {
        checkedIds.value = autoAggregateIdText.split('|');
      } else {
        checkedIds.value = [];
      }
      autoAggregate.value = v;
      setTreeDataChecked();
      updateAggregationConfig();
    };
    /** 更新选中 */
    const handleUpdateCheckedIds = (v: string[]) => {
      checkedIds.value = v;
      autoAggregate.value = v.join('|') === autoAggregateIdText;
      setTreeDataChecked();
      updateAggregationConfig();
    };
    /** 更新调用关系聚合 */
    const handleUpdateAggregateCluster = (v: boolean) => {
      aggregateCluster.value = v;
      updateAggregationConfig();
    };
    /** 播放 */
    const handlePlay = value => {
      emit('play', value);
    };
    const getAggregationConfigValue = () => {
      if (autoAggregate.value || !checkedIds.value.length) {
        return {
          aggregate_cluster: aggregateCluster.value,
          auto_aggregate: autoAggregate.value,
        };
      }
      return {
        aggregate_cluster: aggregateCluster.value,
        auto_aggregate: false,
        aggregate_config: aggregateConfig.value,
      };
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
    return {
      isFullscreen,
      autoAggregateIdText,
      treeData,
      timeLine,
      checkedIds,
      autoAggregate,
      handleFullscreen,
      handleChangeTimeLine,
      handleUpdateAutoAggregate,
      handleUpdateCheckedIds,
      handleUpdateAggregateCluster,
      handleChangeRefleshTime,
      handleTimelineChange,
      handlePlay,
      t,
    };
  },
  render() {
    return (
      <div class='topo-tools'>
        <AggregationSelect
          class='topo-tools-agg'
          autoAggregate={this.autoAggregate}
          checkedIds={this.checkedIds}
          treeData={this.treeData}
          onUpdate:aggregateCluster={this.handleUpdateAggregateCluster}
          onUpdate:autoAggregate={this.handleUpdateAutoAggregate}
          onUpdate:checkedIds={this.handleUpdateCheckedIds}
        />
        <Timeline
          ref='timeLine'
          timelinePlayPosition={this.timelinePlayPosition}
          topoRawDataList={this.topoRawDataList}
          onChangeRefleshTime={this.handleChangeRefleshTime}
          onPlay={this.handlePlay}
          onTimelineChange={this.handleTimelineChange}
        />
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
