<script setup>

import { useApplicationStore } from '@/app/state/domains/application-store';
import { computed } from 'vue';
  import { RetrieveUrlResolver } from '@/app/state/url-resolver';

  import TimeRange from '@/shared/ui/time-range/time-range';
  import { handleTransformToTimestamp, MAX_SEARCH_TIME_RANGE } from '@/shared/ui/time-range/utils';

  import { updateTimezone } from '@/platform/i18n/dayjs';
  import { useRoute, useRouter } from "vue-router";

  import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';

  const store = useApplicationStore();
  const route = useRoute();
  const router = useRouter();
  /** 时间选择器绑定的值 */
  const timeRangValue = computed(() => {
    return store.indexItem.datePickerValue;
  });

  const formatValue = computed(() => store.retrieveParams.format);

  const setRouteParams = () => {
    const query = { ...route.query };
    const { start_time, end_time, interval, begin, size, format } = store.retrieveParams;
    const timezone = store.indexItem.timezone;

    const resolver = new RetrieveUrlResolver({
      start_time,
      end_time,
      interval,
      timezone,
      begin,
      size,
      format,
      datePickerValue: store.indexItem.datePickerValue,
    });
    Object.assign(query, resolver.resolveParamsToUrl());
    router.replace({
      query,
    });
  };

  const timezone = computed(() => {
    const { timezone = '' } = store.indexItem;
    return timezone;
  });

  const handleTimezoneChange = async timezone => {
    store.updateIndexItemParams({ timezone });
    updateTimezone(timezone);
    setRouteParams();
    // 场景化检索模式下条件为空时跳过检索请求
    if (!(store.isSceneMode && store.isSceneFilterEmpty)) {
      // 检索条件有变更时先加载字段信息
      if (store.indexItem.isSceneFilterChanged) {
        await store.requestIndexSetFieldInfo();
      }
      store.requestIndexSetQuery();
      RetrieveHelper.fire(RetrieveEvent.SEARCH_TIME_ZONE_CHANGE, timezone);
    }
  };

  // 日期变化
  const handleTimeRangeChange = async val => {
    store.updateIsSetDefaultTableColumn(false);
    const result = handleTransformToTimestamp(val, formatValue.value);
    store.updateIndexItemParams({ start_time: result[0], end_time: result[1], datePickerValue: val });
    setRouteParams();
    // 场景化检索模式下条件为空时跳过检索请求
    if (!(store.isSceneMode && store.isSceneFilterEmpty)) {
      await store.requestIndexSetFieldInfo();
      store.requestIndexSetQuery();
    }
    RetrieveHelper.fire(RetrieveEvent.SEARCH_TIME_CHANGE, val);
  };

  const handleFormatChange = value => {
    store.updateIndexItemParams({ format: value });
  };
</script>
<template>
  <span class="query-params-wrap">
    <TimeRange
      :max-duration="MAX_SEARCH_TIME_RANGE"
      :timezone="timezone"
      :value="timeRangValue"
      @change="handleTimeRangeChange"
      @timezone-change="handleTimezoneChange"
      @format-change="handleFormatChange"
    />
  </span>
</template>
