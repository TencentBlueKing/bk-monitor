<script setup>

  import { debounce } from 'throttle-debounce';

  import TimeRange from '../../../components/time-range/time-range';
  
  import { ref, computed, onMounted, onUnmounted } from 'vue';

  import useLocale from '@/hooks/use-locale';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import UiInput from './ui-input';

  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI语句'), $t('SQL语句')]);
  const btnQuery = $t('查询');
  const activeIndex = ref(0);
  /** 轮训定时器 */
  const refreshTimer = ref(null);
  const refreshTimeout = ref(0);
  const autoRefreshPopper = ref(null);

  /** 自动刷新规则 */
  const refreshActive = ref(false)
  const emit = defineEmits(['timezone-change', 'date-picker-change', 'update:date-picker-value', 'should-retrieve', 'update:datePickerValue']);
  /** props相关 */
  const props = defineProps({
    datePickerValue: {
      type: Array,
      default: () => [],
    },
    timezone: {
        type: String,
        default: '',
      },
  })
  /** 时间选择器绑定的值 */
  const timeRangValue = computed({
    get: () => props.datePickerValue,
    set: val => {
      emit('update:date-picker-value', val)
    },
  });

  const refreshTimeList = [
    {
      id: 0,
      name: `off 关闭`,
    },
    {
      id: 60000,
      name: '1m',
    },
    {
      id: 300000,
      name: '5m',
    },
    {
      id: 900000,
      name: '15m',
    },
    {
      id: 1800000,
      name: '30m',
    },
    {
      id: 3600000,
      name: '1h',
    },
    {
      id: 7200000,
      name: '2h',
    },
    {
      id: 86400000,
      name: '1d',
    },
  ]  
  const queryType = computed(() => queryTypeList.value[activeIndex.value]);

  const searchItemList = ref([
    { fieldName: 'log-a', fieldValue: 'natural Home', disabled: false },
    { fieldName: 'log-b', fieldValue: 'natural Home', disabled: false },
    { fieldName: 'log-c', fieldValue: 'natural Home natural Home', disabled: false },
    { fieldName: 'log-d', fieldValue: 'natural Home', disabled: false },
    { fieldName: 'log-e', fieldValue: 'natural Home natural Home', disabled: false },
  ]);

  const handleQueryTypeChange = index => {
    activeIndex.value = index;
  };

  const handleBtnQueryClick = () => {};

  // 自动刷新
  const handleDropdownShow = () => {
    refreshActive.value = true;
  }
  const handleDropdownHide = () => {
    refreshActive.value = false;
  }
  const handleTimezoneChange = (timezone) => {
    emit('timezone-change', timezone);
    emit('date-picker-change');
  }
  // 日期变化
  const handleTimeRangeChange = (val) => {
    if (val.every(item => typeof item === 'string')) {
      localStorage.setItem('SEARCH_DEFAULT_TIME', JSON.stringify(val));
    }
    emit('update:date-picker-value', val);
    setRefreshTime(0);
    emit('date-picker-change');
  }

  // 清除定时器，供父组件调用
  const pauseRefresh = () => {
    clearTimeout(refreshTimer.value);
  }

  // 如果没有参数就是检索后恢复自动刷新
  const setRefreshTime = (timeout = refreshTimeout.value) => {
    clearTimeout(refreshTimer.value);
    refreshTimeout.value = timeout;
    if (timeout) {
      refreshTimer.value = setTimeout(() => {
        emit('should-retrieve');
      }, timeout);
    }
  }

  /** 页面不可见时停止轮训 */
  const handleVisibilityChange = () => {
    // 窗口隐藏时取消轮询，恢复时恢复轮询（原来是自动刷新就恢复自动刷新，原来不刷新就不会刷新）
    document.hidden ? clearTimeout(refreshTimer.value) : setRefreshTime();
  }

  const refreshTimeText = computed(() => {
    if (!refreshTimeout.value) return 'off';
    return refreshTimeList.find(item => item.id === refreshTimeout.value).name;
  })
  /** 是否自动刷新 */
  const isAutoRefresh = computed(() => refreshTimeout.value !== 0);

  /** 刷新 */
  const handleRefresh = (isClear = false) => {
    /** 点击直接刷新时应该清楚定时器，避免可能出现定时器也到达时间刷新2次的问题 */
    if (isClear) {
      clearTimeout(refreshTimer.value)
      setRefreshTime()
    }
    emit('should-retrieve');
  }

  const handleRefreshDebounce = debounce(300, handleRefresh)

  const handleDisabledTagItem = item => {
    item.disabled = !item.disabled;
  };
  const handleSelectRefreshTimeout = (timeout) => {
    setRefreshTime(timeout);
    autoRefreshPopper.value.instance.hide();
  }
  const handleDeleteTagItem = (index) => {
    searchItemList.value.splice(index, 1);
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  })
  /** 清除 */
  onUnmounted(() => {
    pauseRefresh();
    document.removeAllListeners('visibilitychange', handleVisibilityChange);
  });
</script>
<template>
  <div class="search-bar-container">
    <div class="search-options">
      <div class="query-type">
        <span
          v-for="(item, index) in queryTypeList"
          :class="['item', { active: activeIndex === index }]"
          :key="index"
          @click="() => handleQueryTypeChange(index)"
          >{{ item }}</span
        >
      </div>

      <SelectIndexSet style="width: 200px; margin: 0 12px"></SelectIndexSet>
      <span class="query-history">
        <span class="bklog-icon bklog-lishijilu"></span>
        <span>{{ $t('历史查询') }}</span>
      </span>
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
                :class="['log-icon', isAutoRefresh ? 'icon-auto-refresh' : 'icon-no-refresh']"
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
        <span class="search-refresh" v-bk-tooltips="{content: $t('刷新')}">
          <i class="log-icon icon-log-refresh" @click="handleRefresh(true)"></i>
        </span>
      </span>
    </div>
    <div class="search-input">
      <UiInput v-model="searchItemList"></UiInput>
      <div class="search-tool items">
        <span class="bklog-icon bklog-brush"></span>
        <span class="bklog-icon bklog-star-line"></span>
        <span class="bklog-icon bklog-set-icon"></span>
      </div>
      <div
        class="search-tool search-btn"
        @click="handleBtnQueryClick"
      >
        {{ btnQuery }}
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>, onUnmounted, onMounted, onUnmounted
