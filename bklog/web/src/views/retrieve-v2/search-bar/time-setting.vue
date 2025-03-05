<script setup>
  import { computed } from 'vue';
  import { RetrieveUrlResolver } from '@/store/url-resolver';

  import TimeRange from '@/components/time-range/time-range';
  import { handleTransformToTimestamp } from '@/components/time-range/utils';
  import useStore from '@/hooks/use-store';
  import { updateTimezone } from '@/language/dayjs';
  import { useRoute, useRouter } from 'vue-router/composables';
  const store = useStore();
  const route = useRoute();
  const router = useRouter();
  /** 时间选择器绑定的值 */
  const timeRangValue = computed(() => {
    return store.state.indexItem.datePickerValue;
  });

  const formatValue = computed(() => store.getters.retrieveParams.format);

  const setRouteParams = () => {
    const query = { ...route.query };
    const { start_time, end_time, interval, begin, size, format } = store.getters.retrieveParams;
    const timezone = store.state.indexItem.timezone;

    const resolver = new RetrieveUrlResolver({
      start_time,
      end_time,
      interval,
      timezone,
      begin,
      size,
      format,
      datePickerValue: store.state.indexItem.datePickerValue,
    });
    Object.assign(query, resolver.resolveParamsToUrl());

    router.replace({
      query,
    });
  };

  const timezone = computed(() => {
    const { timezone = '' } = store.state.indexItem;
    return timezone;
  });

  const handleTimezoneChange = timezone => {
    store.commit('updateIndexItemParams', { timezone });
    updateTimezone(timezone);
    store.dispatch('requestIndexSetQuery');
    setRouteParams();
  };

  // 日期变化
  const handleTimeRangeChange = async val => {
    store.commit('updateIsSetDefaultTableColumn', false);
    const result = handleTransformToTimestamp(val, formatValue.value);
    store.commit('updateIndexItemParams', { start_time: result[0], end_time: result[1], datePickerValue: val });
    await store.dispatch('requestIndexSetFieldInfo');
    store.dispatch('requestIndexSetQuery');
    setRouteParams();
  };

  const handleFormatChange = value => {
    store.commit('updateIndexItemParams', { format: value });
  };

  /** 刷新 */
  const handleRefresh = () => {
    store.dispatch('requestIndexSetQuery');
  };
</script>
<template>
  <span class="query-params-wrap">
    <TimeRange
      :timezone="timezone"
      :value="timeRangValue"
      @change="handleTimeRangeChange"
      @timezone-change="handleTimezoneChange"
      @format-change="handleFormatChange"
    ></TimeRange>
    <!-- 自动刷新 -->
    <!-- <bk-popover
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
    </bk-popover> -->
    <!-- 手动刷新 -->
    <!-- <span
      class="search-refresh"
      v-bk-tooltips="{ content: $t('刷新') }"
      @click="handleRefresh"
    >
      <i class="bklog-icon bklog-log-refresh"></i>
    </span> -->
  </span>
</template>
