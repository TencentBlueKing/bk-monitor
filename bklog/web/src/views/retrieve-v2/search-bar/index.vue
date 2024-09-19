<script setup>
  import { ref, computed, watch } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { isEqual } from 'lodash';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import BookmarkPop from './bookmark-pop';
  import QueryHistory from './query-history';
  import SqlQuery from './sql-query';
  import TimeSetting from './time-setting';
  import UiInput from './ui-input';
  import { ConditionOperator } from '@/store/condition-operator';

  const emit = defineEmits(['refresh', 'height-change']);
  const store = useStore();
  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI查询'), $t('语句查询')]);
  const queryParams = ['ui', 'sql'];
  const btnQuery = $t('查询');
  const activeIndex = ref(0);

  const uiQueryValue = ref([]);
  const sqlQueryValue = ref('');

  const indexItem = computed(() => store.state.indexItem);
  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
  const isInputLoading = computed(() => {
    if (activeIndex.value === 0) {
      return false;
    }

    return indexFieldInfo.value.is_loading || indexSetQueryResult.value.is_loading;
  });
  const keyword = computed(() => indexItem.value.keyword);
  const addition = computed(() => indexItem.value.addition);
  const searchMode = computed(() => indexItem.value.search_mode);
  const clearSearchValueNum = computed(() => store.state.clearSearchValueNum);

  watch(
    keyword,
    () => {
      sqlQueryValue.value = keyword.value;
    },
    { immediate: true },
  );

  watch(clearSearchValueNum, () => {
    handleClearBtnClick();
  });

  watch(
    addition,
    () => {
      uiQueryValue.value.splice(0);
      uiQueryValue.value.push(...addition.value);
    },
    { immediate: true, deep: true },
  );

  watch(searchMode, () => {
    const idex = queryParams.findIndex(m => m === searchMode.value);
    if (idex >= 0) {
      activeIndex.value = idex;
    }
  });

  watch(
    activeIndex,
    () => {
      store.commit('updateIndexItemParams', {
        search_mode: queryParams[activeIndex.value],
      });
    },
    { immediate: true },
  );

  const handleQueryTypeChange = index => {
    activeIndex.value = index;
  };

  const handleBtnQueryClick = () => {
    store.commit('updateIndexItemParams', {
      addition: uiQueryValue.value.filter(val => !val.is_focus_input),
      keyword: sqlQueryValue.value ?? '',
    });

    store.dispatch('requestIndexSetQuery');
  };

  const handleIndexSetSelected = payload => {
    if (!isEqual(indexItem.value.ids, payload.ids) || indexItem.value.isUnionIndex !== payload.isUnionIndex) {
      store.commit('updateUnionIndexList', payload.isUnionIndex ? (payload.ids ?? []) : []);
      store.dispatch('requestIndexSetItemChanged', payload ?? {}).then(() => {
        store.commit('retrieve/updateChartKey');
        store.dispatch('requestIndexSetQuery');
      });
    }
  };
  const updateSearchParam = payload => {
    const { keyword, addition, ip_chooser, search_mode } = payload;
    const foramtAddition = (addition ?? []).map(item => {
      const instance = new ConditionOperator(item);
      return instance.formatApiOperatorToFront();
    })

    store.commit('updateIndexItemParams', {
      keyword,
      addition: foramtAddition,
      ip_chooser,
      begin: 0,
      search_mode,
    });

    activeIndex.value = queryParams.findIndex(m => m === search_mode);
    if (activeIndex.value === -1) {
      if (keyword?.length) {
        activeIndex.value = 1;
      }

      if (addition.length) {
        activeIndex.value = 0;
      }
    }

    setTimeout(() => {
      store.dispatch('requestIndexSetQuery');
    });
  };

  const handleSqlRetrieve = value => {
    store.commit('updateIndexItemParams', {
      keyword: value,
    });

    store.dispatch('requestIndexSetQuery');
  };

  const handleClearBtnClick = () => {
    sqlQueryValue.value = '';
    uiQueryValue.value.splice(0);
    store.commit('updateIndexItemParams', {
      ip_chooser: {},
    });
    handleBtnQueryClick();
  };

  const handleQueryChange = () => {
    handleBtnQueryClick();
  };

  const handleRefresh = isRefresh => {
    emit('refresh', isRefresh);
  };

  const handleHeightChange = height => {
    emit('height-change', height);
  };
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
        >
          {{ item }}
        </span>
      </div>

      <SelectIndexSet
        style="width: 500px; margin: 0 12px"
        @selected="handleIndexSetSelected"
      ></SelectIndexSet>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
      <TimeSetting></TimeSetting>
    </div>
    <div
      class="search-input"
      v-bkloading="{
        isLoading: isInputLoading,
        size: 'mini',
        mode: 'spin',
        opacity: 1,
        zIndex: 10,
        theme: 'primary',
        extCls: 'bklog-sql-input-loading',
      }"
    >
      <UiInput
        v-if="activeIndex === 0"
        v-model="uiQueryValue"
        @change="handleQueryChange"
        @height-change="handleHeightChange"
      ></UiInput>
      <SqlQuery
        v-if="activeIndex === 1"
        v-model="sqlQueryValue"
        @height-change="handleHeightChange"
        @retrieve="handleSqlRetrieve"
      ></SqlQuery>
      <div class="search-tool items">
        <span
          class="bklog-icon bklog-brush"
          @click.stop="handleClearBtnClick"
        ></span>
        <BookmarkPop
          :sql="sqlQueryValue"
          :addition="uiQueryValue"
          :searchMode="queryParams[activeIndex]"
          @refresh="handleRefresh"
        ></BookmarkPop>
        <span class="disabled bklog-icon bklog-set-icon"></span>
      </div>
      <div
        class="search-tool search-btn"
        @click.stop="handleBtnQueryClick"
      >
        {{ btnQuery }}
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
<style>
  .bklog-sql-input-loading {
    .bk-loading-wrapper {
      left: 30px;
    }
  }
</style>
