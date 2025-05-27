<script setup>
  import { computed } from 'vue';
  import { RetrieveUrlResolver } from '@/store/url-resolver';

  import TimeRange from '@/components/time-range/time-range';
  import { handleTransformToTimestamp } from '@/components/time-range/utils';
  import useStore from '@/hooks/use-store';
  import { updateTimezone } from '@/language/dayjs';
  import { useRoute, useRouter } from 'vue-router/composables';

  import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';

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
    RetrieveHelper.fire(RetrieveEvent.SEARCH_TIME_CHANGE, val);
  };

  const handleFormatChange = value => {
    store.commit('updateIndexItemParams', { format: value });
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
  </span>
</template>
