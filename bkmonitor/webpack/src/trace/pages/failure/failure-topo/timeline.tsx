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
import { type PropType, type Ref, computed, defineComponent, inject, ref, watch } from 'vue';

import { DatePicker, Dropdown, Slider } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import type { IncidentDetailData, TopoRawData } from './types';

import './timeline.scss';
import 'bkui-vue/lib/time-picker/time-picker.css';

const refreshList = [
  // 刷新间隔列表
  {
    name: 'off',
    label: '关闭（off）',
    id: -1,
  },
  {
    name: '1m',
    id: 60 * 1000,
  },
  {
    name: '5m',
    id: 5 * 60 * 1000,
  },
  {
    name: '15m',
    id: 15 * 60 * 1000,
  },
  {
    name: '30m',
    id: 30 * 60 * 1000,
  },
  {
    name: '1h',
    id: 60 * 60 * 1000,
  },
  {
    name: '2h',
    id: 60 * 2 * 60 * 1000,
  },
  {
    name: '1d',
    id: 60 * 24 * 60 * 1000,
  },
];

export default defineComponent({
  props: {
    timelinePlayPosition: {
      type: Number,
      default: 0,
    },
    topoRawDataList: {
      type: Array as PropType<TopoRawData[]>,
      default: () => [],
    },
  },
  emits: ['changeRefleshTime', 'play', 'update:modelValue', 'timelineChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
    /** 时间切片数据 */
    const timeList = computed(() => {
      return props.topoRawDataList.map(item => item.create_time);
    });
    const timelinePosition = ref(0); // 时间轴位置
    const time = ref(new Date());
    const refreshTime = ref('1m'); // 自动刷新时间
    const isShow = ref(false);
    const isPlay = ref(false);
    /** 拖动轴变化 */
    const handleTimelineChange = (value, setTime = true) => {
      emit('timelineChange', value);
      setTime && (time.value = new Date(props.topoRawDataList?.[timelinePosition.value]?.create_time * 1000));
    };
    /** 选择时间变化后，对比时间，更新拖动轴 */
    const handlePickSuccess = () => {
      /** 获取到离当前时间最近的一帧 */
      const selectTimestamp = new Date(time.value).getTime() / 1000;
      const timeDifferences = timeList.value.map(timestamp => Math.abs(timestamp - selectTimestamp));
      const nearestTimestamp = timeList.value[timeDifferences.indexOf(Math.min(...timeDifferences))];
      const index = timeList.value.findIndex(item => item === nearestTimestamp);
      if (index !== -1) {
        handleTimelineChange(index, false);
      }
    };
    /** 切换自动更新时间 */
    const handleRefreshChange = ({ id, name }) => {
      refreshTime.value = name;
      isShow.value = !isShow.value;
      emit('changeRefleshTime', id);
    };

    /** 开启播放 */
    const handlePlay = () => {
      isPlay.value = !isPlay.value;
      /** 当前停留在最后一帧，点击播放是应该从头开始 */
      const isStart = timelinePosition.value === props.topoRawDataList.length - 1;
      const params = { value: isPlay.value, isStart, ...(isStart ? { timeline: 0 } : {}) };
      emit('play', params);
      /** 兼容只有一条diff情况，导致数据状态不更新 */
      setTimeout(() => {
        if (props.topoRawDataList.length - 1 === 0 && timelinePosition.value === 0) {
          isPlay.value = false;
        }
      });
    };

    const changeTimeLine = value => {
      timelinePosition.value = value;
      changePlayStatus(value);
    };
    const handleStop = () => {};

    const handleDisabledDate = (e: Date | number | string) => {
      const time = dayjs(e);
      const startTime = dayjs(incidentDetail.value.create_time * 1000).startOf('day');
      const endTime = dayjs(incidentDetail.value.end_time ? incidentDetail.value.end_time * 1000 : dayjs()).endOf(
        'day'
      );
      if (time.isBefore(startTime) || time.isAfter(endTime)) {
        return true;
      }
      return false;
    };
    const changePlayStatus = value => {
      /** 非播放状态下，该值变化可能是时间选择器变化导致的，这种情况保持原值 */
      if (isPlay.value) {
        time.value = new Date(props.topoRawDataList?.[value]?.create_time * 1000);
      }
      if (value + 1 === props.topoRawDataList.length) {
        isPlay.value = false;
      }
      timelinePosition.value = value;
    };
    /** 监听外部传入的切片位置更新拖动轴 */
    watch(
      () => props.timelinePlayPosition,
      value => changePlayStatus(value),
      {
        deep: true,
      }
    );
    watch(
      () => props.topoRawDataList,
      () => {
        if (!props.topoRawDataList?.[timelinePosition.value]?.create_time) {
          return;
        }
        time.value = new Date(props.topoRawDataList?.[timelinePosition.value]?.create_time * 1000);
      },
      { immediate: true }
    );

    return {
      time,
      isShow,
      isPlay,
      timelinePosition,
      refleshTime: refreshTime,
      handlePlay,
      handleStop,
      changeTimeLine,
      handleRefreshChange,
      handleDisabledDate,
      handleTimelineChange,
      handlePickSuccess,
      t,
    };
  },
  render() {
    const len = this.topoRawDataList.length || 100;
    const max = len > -1 ? len - 1 : 1;
    return (
      <div class='failure-topo-timeline'>
        <span class='label'>{this.t('时间轴')}</span>
        <span
          class={['icon-monitor', this.isPlay ? 'icon-weibiaoti519' : 'icon-mc-arrow-right']}
          onClick={this.handlePlay}
        />
        {max === 0 ? (
          <Slider
            class='slider'
            maxValue={1}
            minValue={0}
            modelValue={1}
          />
        ) : (
          <Slider
            class='slider'
            v-model={this.timelinePosition}
            maxValue={max}
            minValue={0}
            // onUpdate:modelValue={this.handleTimelineChange}
            onChange={this.handleTimelineChange}
          />
        )}

        <DatePicker
          class='date-picker'
          v-model={this.time}
          appendToBody={true}
          clearable={false}
          disabled={this.isPlay}
          disabledDate={this.handleDisabledDate}
          type='datetime'
          onPick-success={this.handlePickSuccess}
        />

        <Dropdown
          v-slots={{
            default: () => (
              <div
                class={['trigger-name refresh-name', this.isPlay && 'disabled-refresh']}
                v-bk-tooltips={{
                  placement: 'bottom',
                  content: this.t('自动刷新设置'),
                }}
                onClick={() => (this.isShow = !this.isShow && !this.isPlay)}
              >
                <i class='icon-monitor mr5 icon-zidongshuaxin' />
                <span class='trigger-text text-active'>{this.refleshTime}</span>
              </div>
            ),
            content: () => {
              return (
                <Dropdown.DropdownMenu>
                  {refreshList.map(item => (
                    <Dropdown.DropdownItem
                      key={item.name}
                      extCls={item.name === this.refleshTime ? 'text-active' : ''}
                      onClick={this.handleRefreshChange.bind(this, item)}
                    >
                      {item.label ?? item.name}
                    </Dropdown.DropdownItem>
                  ))}
                </Dropdown.DropdownMenu>
              );
            },
          }}
          popoverOptions={{
            extCls: 'timeline-dropdown-popover',
          }}
          isShow={this.isShow}
          trigger='manual'
        />
      </div>
    );
  },
});
