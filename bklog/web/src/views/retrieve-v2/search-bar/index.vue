<script setup>
  import { ref, computed } from 'vue';

  import useLocale from '@/hooks/use-locale';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import UiInput from './ui-input';

  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI语句'), $t('SQL语句')]);
  const btnQuery = $t('查询');
  const activeIndex = ref(0);

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
