<script setup>
import { ref, onUnmounted } from 'vue';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper.tsx';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import useStore from '@/hooks/use-store';

const isDropdownShow = ref(false);
const dropdown = ref(null);
const selectedValue = ref('off');
const store = useStore();

const datasource = ref([
  { label: '关闭(off)', value: 'off' },
  { label: '10s', value: '10s' },
  { label: '30s', value: '30s' },
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '30m', value: '30m' },
  { label: '1h', value: '1h' },
  { label: '2h', value: '2h' },
  { label: '1d', value: '1d' },
]);

/**
 * 将时间字符串转换为毫秒数
 * @param {string} timeValue
 * @returns {number} 毫秒数
 */
const getTimeInMs = (timeValue) => {
  if (timeValue === 'off') return 0;

  const unitMap = {
    s: 1000, // 秒
    m: 60 * 1000, // 分钟
    h: 60 * 60 * 1000, // 小时
    d: 24 * 60 * 60 * 1000, // 天
  };

  const unit = timeValue.slice(-1);
  const amount = parseInt(timeValue.slice(0, -1), 10);

  // 输入验证
  if (isNaN(amount) || amount <= 0) {
    return 0;
  }

  if (!unitMap[unit]) {
    return 0;
  }

  return amount * unitMap[unit];
};

const handleRefresh = () => {
  const formatValue = store.getters.retrieveParams.format;
  const val = store.state.indexItem.datePickerValue;
  const result = handleTransformToTimestamp(val, formatValue.value);

  store.commit('updateIndexItemParams', { start_time: result[0], end_time: result[1] });
  RetrieveHelper.fire(RetrieveEvent.AUTO_REFRESH);
};

let timerId = null;
const createRefreshTimerTask = () => {
  const interval = getTimeInMs(selectedValue.value);
  timerId && clearTimeout(timerId);
  if (interval === 0) {
    return;
  }
  timerId = setTimeout(() => {
    handleRefresh();
    createRefreshTimerTask();
  }, interval);
};

onUnmounted(() => {
  timerId && clearTimeout(timerId);
});

const dropdownShow = () => {
  isDropdownShow.value = true;
};

const dropdownHide = () => {
  isDropdownShow.value = false;
};

const triggerHandler = (item) => {
  selectedValue.value = item.value;
  dropdown.value.hide();
  createRefreshTimerTask();
};
</script>
<template>
  <div class="auto-refresh-sub-bar">
    <bk-dropdown-menu
      ref="dropdown"
      trigger="click"
      ext-cls="dropdown-menu"
      class="auto-refresh-dropdown"
      @show="dropdownShow"
      @hide="dropdownHide"
    >
      <div
        slot="dropdown-trigger"
        v-bk-tooltips="{ content: $t('自动刷新设置'), placement: 'bottom' }"
        class="dropdown-trigger-text"
        :class="{ 'active': isDropdownShow }"
      >
        <i class="bklog-icon bklog-auto-refresh" />
        <span>{{ datasource.find(item => item.value === selectedValue)?.value || 'off' }}</span>
      </div>
      <ul
        slot="dropdown-content"
        class="bk-dropdown-list"
      >
        <li
          v-for="item in datasource"
          :key="item.value"
        >
          <a
            href="javascript:;"
            @click="() => triggerHandler(item)"
          >{{ item.label }}</a>
        </li>
      </ul>
    </bk-dropdown-menu>
  </div>
</template>
<style lang="scss" scoped>
@import'./auto-refresh.scss';
</style>
