<script setup>
  import { ref, computed, watch, nextTick } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import BookmarkPop from './bookmark-pop';
  import SqlQuery from './sql-query';
  import UiInput from './ui-input';

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

  const keyword = computed(() => indexItem.value.keyword);
  const addition = computed(() => indexItem.value.addition);
  const searchMode = computed(() => indexItem.value.search_mode);
  const clearSearchValueNum = computed(() => store.state.clearSearchValueNum);
  const queryText = computed(() => queryTypeList.value[activeIndex.value]);

  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const isInputLoading = computed(() => {
    return indexFieldInfo.value.is_loading;
  });

  const isIndexFieldLoading = computed(() => store.state.indexFieldInfo.is_loading);

  watch(
    () => isIndexFieldLoading.value,
    () => {
      nextTick(() => {
        uiQueryValue.value.forEach(
          v => (v.field_type = (indexFieldInfo.value.fields ?? []).find(f => f.field_name === v.field)?.field_type),
        );
      });
    },
  );

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
      uiQueryValue.value.push(
        ...addition.value.map(v => ({
          ...v,
          field_type: (indexFieldInfo.value.fields ?? []).find(f => f.field_name === v.field)?.field_type,
        })),
      );
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

  const handleBtnQueryClick = () => {
    if (!isInputLoading.value) {
      store.commit('updateIndexItemParams', {
        addition: uiQueryValue.value.filter(val => !val.is_focus_input),
        keyword: sqlQueryValue.value ?? '',
        ip_chooser: uiQueryValue.value.find(item => item.field === '_ip-select_')?.value?.[0] ?? {},
      });

      store.dispatch('requestIndexSetQuery');
    }
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

  const handleQueryTypeChange = () => {
    activeIndex.value = activeIndex.value === 0 ? 1 : 0;
  };
</script>
<template>
  <div class="search-bar-container">
    <div
      class="search-options"
      @click="handleQueryTypeChange"
    >
      <span class="mode-text">{{ queryText }}</span>
      <span class="bklog-icon bklog-double-arrow"></span>
    </div>
    <div
      class="search-input"
      :class="{ disabled: isInputLoading }"
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
        <div
          :class="['bklog-icon bklog-brush', { disabled: isInputLoading }]"
          @click.stop="handleClearBtnClick"
        ></div>
        <BookmarkPop
          :addition="uiQueryValue"
          :class="{ disabled: isInputLoading }"
          :search-mode="queryParams[activeIndex]"
          :sql="sqlQueryValue"
          @refresh="handleRefresh"
        ></BookmarkPop>
        <!-- <span class="disabled bklog-icon bklog-set-icon"></span> -->
      </div>
      <div
        class="search-tool search-btn"
        @click.stop="handleBtnQueryClick"
      >
        <bk-button
          style="width: 100%; height: 100%"
          :loading="isInputLoading"
          size="large"
          theme="primary"
          >{{ btnQuery }}</bk-button
        >
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
