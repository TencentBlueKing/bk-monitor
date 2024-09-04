<script setup>
  import axios from 'axios';

  import { ref, computed } from 'vue';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import QueryHistory from './query-history';
  import TimeSetting from './time-setting';
  import UiInput from './ui-input';

  const store = useStore();
  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI语句'), $t('SQL语句')]);
  const btnQuery = $t('查询');
  const activeIndex = ref(0);


  const emit = defineEmits(['change', 'should-retrieve']);
  /** props相关 */
  const props = defineProps({});

  const queryType = computed(() => queryTypeList.value[activeIndex.value]);
  const searchItemList = ref([]);

  const handleQueryTypeChange = index => {
    activeIndex.value = index;
  };

  const handleBtnQueryClick = () => {
    store.commit('updateIndexItemParams', {
      addition: searchItemList.value.filter(val => !val.disabled && !val.is_focus_input),
    });

    store.dispatch('requestIndexSetQuery');
  };

  const handleIndexSetSelected = payload => {
    store.dispatch('requestIndexSetItemChanged', payload);
  }
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

      <SelectIndexSet style="width: 200px; margin: 0 12px" @selected="handleIndexSetSelected"></SelectIndexSet>
      <QueryHistory></QueryHistory>
      <TimeSetting></TimeSetting>
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
</style>
