<script setup>
  import { ref } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import QueryHistory from './query-history';
  import SqlQuery from './sql-query';
  import TimeSetting from './time-setting';
  import UiInput from './ui-input';

  const store = useStore();
  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI语句'), $t('SQL语句')]);
  const btnQuery = $t('查询');
  const activeIndex = ref(0);

  const searchItemList = ref([]);
  const sqlQueryValue = ref([]);

  const handleQueryTypeChange = index => {
    activeIndex.value = index;
  };

  const handleBtnQueryClick = () => {
    store.commit('updateIndexItemParams', {
      addition: searchItemList.value.filter(val => !val.disabled && !val.is_focus_input),
      keyword: sqlQueryValue[0] ?? '*'
    });

    store.dispatch('requestIndexSetQuery');
  };

  const handleIndexSetSelected = payload => {
    store.dispatch('requestIndexSetItemChanged', payload).then(() => {
      store.dispatch('requestIndexSetQuery');
    });
  }
  const updateSearchParam= (keyword,addition,ip_chooser) => {}
  const retrieve = () => {}

  const handleSqlRetrieve = value => {
    store.commit('updateIndexItemParams', {
      keyword: value,
    });

    store.dispatch('requestIndexSetQuery');
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
      <QueryHistory @updateSearchParam="updateSearchParam" @retrieve='retrieve'></QueryHistory>
      <TimeSetting></TimeSetting>
    </div>
    <div class="search-input">
      <UiInput
        v-if="activeIndex === 0"
        v-model="searchItemList"
      ></UiInput>
      <SqlQuery
        v-if="activeIndex === 1"
        v-model="sqlQueryValue"
        @retrieve="handleSqlRetrieve"
      ></SqlQuery>
      <div class="search-tool items">
        <span  class="disabled bklog-icon bklog-brush"></span>
        <span  class="disabled bklog-icon bklog-star-line"></span>
        <span  class="disabled bklog-icon bklog-set-icon"></span>
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
