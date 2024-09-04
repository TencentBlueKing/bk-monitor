<script setup>
  import { ref, computed, onMounted, onUnmounted } from 'vue';

  import useStore from '@/hooks/use-store';
  import TimeRange from '@/components/time-range/time-range';
  import { debounce } from 'throttle-debounce';
  import { updateTimezone } from '@/language/dayjs';
  import { Time_Range_List } from './const-values';

  const store = useStore();

  /** 时间选择器绑定的值 */
  const timeRangValue = computed(() => {
    const { start_time = 'now-15m', end_time = 'now' } = store.state.indexItem;
    return [start_time, end_time];
  });

  const timezone = computed(() => {
    const { timezone = '' } = store.state.indexItem;
    return timezone;
  });

  /** 轮训定时器 */
  const refreshTimer = ref(null);
  const refreshTimeout = ref(0);
  const autoRefreshPopper = ref(null);

  /** 自动刷新规则 */
  const refreshActive = ref(false);
  const refreshTimeList = [...Time_Range_List];

  // 自动刷新
  const handleDropdownShow = () => {
    refreshActive.value = true;
  };
  const handleDropdownHide = () => {
    refreshActive.value = false;
  };
  const handleTimezoneChange = timezone => {
    store.commit('updateIndexItemParams', { timezone });
    updateTimezone(timezone);
    store.dispatch('requestIndexSetQuery');
  };

  // 日期变化
  const handleTimeRangeChange = val => {
    if (val.every(item => typeof item === 'string')) {
      localStorage.setItem('SEARCH_DEFAULT_TIME', JSON.stringify(val));
    }
    store.commit('updateIndexItemParams', { start_time: val[0], end_time: val[1] });
    setRefreshTime(0);
    store.dispatch('requestIndexSetQuery');
  };

  // 清除定时器，供父组件调用
  const pauseRefresh = () => {
    clearTimeout(refreshTimer.value);
  };

  // 如果没有参数就是检索后恢复自动刷新
  const setRefreshTime = (timeout = refreshTimeout.value) => {
    clearTimeout(refreshTimer.value);
    refreshTimeout.value = timeout;
    if (timeout) {
      refreshTimer.value = setTimeout(() => {
        emit('should-retrieve');
      }, timeout);
    }
  };

  /** 页面不可见时停止轮训 */
  const handleVisibilityChange = () => {
    // 窗口隐藏时取消轮询，恢复时恢复轮询（原来是自动刷新就恢复自动刷新，原来不刷新就不会刷新）
    document.hidden ? clearTimeout(refreshTimer.value) : setRefreshTime();
  };

  const refreshTimeText = computed(() => {
    if (!refreshTimeout.value) return 'off';
    return refreshTimeList.find(item => item.id === refreshTimeout.value).name;
  });
  /** 是否自动刷新 */
  const isAutoRefresh = computed(() => refreshTimeout.value !== 0);

  /** 刷新 */
  const handleRefresh = (isClear = false) => {
    /** 点击直接刷新时应该清楚定时器，避免可能出现定时器也到达时间刷新2次的问题 */
    if (isClear) {
      clearTimeout(refreshTimer.value);
      setRefreshTime();
    }
    emit('should-retrieve');
  };

  const handleRefreshDebounce = debounce(300, handleRefresh);

  const handleSelectRefreshTimeout = timeout => {
    setRefreshTime(timeout);
    autoRefreshPopper.value.instance.hide();
  };

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  });
  /** 清除 */
  onUnmounted(() => {
    pauseRefresh();
    document.removeAllListeners('visibilitychange', handleVisibilityChange);
  });
</script>
<template>
  <span class="query-params-wrap">
    <TimeRange
      :timezone="timezone"
      :value="timeRangValue"
      @change="handleTimeRangeChange"
      @timezone-change="handleTimezoneChange"
    ></TimeRange>
    <!-- 自动刷新 -->
    <bk-popover
      ref="autoRefreshPopper"
      :distance="15"
      :offset="0"
      :on-hide="handleDropdownHide"
      :on-show="handleDropdownShow"
      animation="slide-toggle"
      placement="bottom-start"
      theme="light bk-select-dropdown"
      trigger="click"
    >
      <slot name="trigger">
        <div class="auto-refresh-trigger">
          <span
            :class="['bklog-icon', isAutoRefresh ? 'bklog-auto-refresh' : 'bklog-no-refresh']"
            data-test-id="retrieve_span_periodicRefresh"
            @click.stop="handleRefreshDebounce"
          ></span>
          <span :class="isAutoRefresh && 'active-text'">{{ refreshTimeText }}</span>
          <span
            class="bk-icon icon-angle-down"
            :class="refreshActive && 'active'"
          ></span>
        </div>
      </slot>
      <template #content>
        <div class="bk-select-dropdown-content auto-refresh-content">
          <div class="bk-options-wrapper">
            <ul class="bk-options bk-options-single">
              <li
                v-for="item in refreshTimeList"
                :class="['bk-option', refreshTimeout === item.id && 'is-selected']"
                :key="item.id"
                @click="handleSelectRefreshTimeout(item.id)"
              >
                <div class="bk-option-content">{{ item.name }}</div>
              </li>
            </ul>
          </div>
        </div>
      </template>
    </bk-popover>
    <!-- 手动刷新 -->
    <span
      class="search-refresh"
      v-bk-tooltips="{ content: $t('刷新') }"
    >
      <i
        class="bklog-icon bklog-log-refresh"
        @click="handleRefresh(true)"
      ></i>
    </span>
  </span>
</template>
