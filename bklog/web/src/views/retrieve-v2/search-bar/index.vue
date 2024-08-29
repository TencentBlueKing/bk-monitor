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
        <span class="log-icon icon-lishijilu"></span>
        <span>{{ $t('历史查询') }}</span>
      </span>
    </div>
    <div class="search-input">
      <UiInput></UiInput>
      <div class="search-tool items">
        <span class="log-icon icon-brush"></span>
        <span class="log-icon icon-star-line"></span>
        <span class="log-icon icon-set-icon"></span>
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
