<script setup>
  import { ref, computed, watch, nextTick } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { RetrieveUrlResolver } from '@/store/url-resolver';
  import { useRoute, useRouter } from 'vue-router/composables';

  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import BookmarkPop from './bookmark-pop';
  // #else
  // #code const BookmarkPop = () => null;
  // #endif

  import { ConditionOperator } from '@/store/condition-operator';
  import { bkMessage } from 'bk-magic-vue';

  import $http from '../../../api';
  import { deepClone, copyMessage } from '../../../common/util';
  import SqlQuery from './sql-query';
  import UiInput from './ui-input';

  const props = defineProps({
    activeFavorite: {
      default: null,
      type: Object,
    },
  });

  const emit = defineEmits(['refresh', 'height-change']);
  const store = useStore();
  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI查询'), $t('语句查询')]);
  const queryParams = ['ui', 'sql'];
  const btnQuery = $t('查询');
  const route = useRoute();
  const router = useRouter();

  const getDefaultActiveIndex = () => {
    if (route.query.search_mode) {
      return queryParams.findIndex(m => m === route.query.search_mode);
    }

    if (route.query.keyword?.length) {
      return 1;
    }

    return Number(localStorage.getItem('bkLogQueryType') ?? 0);
  };

  const activeIndex = ref(getDefaultActiveIndex());

  const uiQueryValue = ref([]);
  const sqlQueryValue = ref('');

  const indexItem = computed(() => store.state.indexItem);

  const keyword = computed(() => indexItem.value.keyword);
  const addition = computed(() => indexItem.value.addition);
  const searchMode = computed(() => indexItem.value.search_mode);
  const clearSearchValueNum = computed(() => store.state.clearSearchValueNum);
  const queryText = computed(() => queryTypeList.value[activeIndex.value]);

  const isChartMode = computed(() => route.query.tab === 'graphAnalysis');

  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const isInputLoading = computed(() => {
    return indexFieldInfo.value.is_loading;
  });

  const isIndexFieldLoading = computed(() => store.state.indexFieldInfo.is_loading);

  const isMonitorTraceLog = computed(() => !!window?.__IS_MONITOR_TRACE__);

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
  const formatAddition = addition => {
    return addition.map(v => {
      const value = {
        ...v,
        field_type: (indexFieldInfo.value.fields ?? []).find(f => f.field_name === v.field)?.field_type,
      };

      const instance = new ConditionOperator(value);
      return { ...value, ...instance.getShowCondition() };
    });
  };
  watch(
    addition,
    () => {
      uiQueryValue.value.splice(0);
      uiQueryValue.value.push(...formatAddition(addition.value));
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

      router.replace({
        params: { ...route.params },
        query: {
          ...(route.query ?? {}),
          search_mode: queryParams[activeIndex.value],
        },
      });
    },
    { immediate: true },
  );

  const setRouteParams = () => {
    const query = { ...route.query };

    const resolver = new RetrieveUrlResolver({
      keyword: keyword.value,
      addition: store.getters.retrieveParams.addition,
    });

    Object.assign(query, resolver.resolveParamsToUrl());

    router.replace({
      query,
    });
  };

  const handleBtnQueryClick = () => {
    if (!isInputLoading.value) {
      store.commit('updateIndexItemParams', {
        addition: uiQueryValue.value.filter(val => !val.is_focus_input),
        keyword: sqlQueryValue.value ?? '',
        ip_chooser: uiQueryValue.value.find(item => item.field === '_ip-select_')?.value?.[0] ?? {},
      });

      store.dispatch('requestIndexSetQuery');
      setRouteParams();
    }
  };

  const handleSqlRetrieve = value => {
    store.commit('updateIndexItemParams', {
      keyword: value,
    });

    store.dispatch('requestIndexSetQuery');
    setRouteParams();
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
    // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
    emit('refresh', isRefresh);
    // #endif
  };

  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const handleQueryTypeChange = () => {
    activeIndex.value = activeIndex.value === 0 ? 1 : 0;
    localStorage.setItem('bkLogQueryType', activeIndex.value);
  };
  const sourceSQLStr = ref('');
  const sourceUISQLAddition = ref([]);
  const initSourceSQLStr = (params, search_mode) => {
    if (search_mode === 'ui') {
      sourceUISQLAddition.value = formatAddition(deepClone(params.addition));
    } else {
      sourceSQLStr.value = params.keyword;
    }
  };
  watch(
    () => props.activeFavorite?.id,
    () => {
      if (!props.activeFavorite) return;
      initSourceSQLStr(props.activeFavorite.params, props.activeFavorite.search_mode);
    },
    { immediate: true },
  );

  const matchSQLStr = computed(() => {
    if (activeIndex.value === 0) {
      if (sourceUISQLAddition.value.length !== uiQueryValue.value.length) {
        return false;
      }
      const differerntUISQL = sourceUISQLAddition.value.find((item, index) => {
        return (
          item.field + item.operator + item.value !==
          uiQueryValue.value[index].field + uiQueryValue.value[index].operator + uiQueryValue.value[index].value
        );
      });
      return !differerntUISQL;
    } else {
      return sqlQueryValue.value === sourceSQLStr.value;
    }
  });

  const saveCurrentActiveFavorite = async () => {
    const {
      name,
      group_id,
      display_fields,
      visible_type,
      is_enable_display_fields,
      index_set_name,
      index_set_names,
      index_set_type,
      index_set_ids,
      index_set_id,
    } = props.activeFavorite;
    const searchMode = activeIndex.value === 0 ? 'ui' : 'sql';
    const reqFormatAddition = uiQueryValue.value.map(item => new ConditionOperator(item).getRequestParam());
    const searchParams =
      searchMode === 'sql'
        ? { keyword: sqlQueryValue.value, addition: [] }
        : {
            addition: reqFormatAddition.filter(v => v.field !== '_ip-select_'),
            keyword: '*',
          };

    const data = {
      name,
      group_id,
      display_fields,
      visible_type,
      is_enable_display_fields,
      search_mode: searchMode,
      ip_chooser: reqFormatAddition.find(item => item.field === '_ip-select_')?.value?.[0] ?? {},
      index_set_id,
      index_set_ids,
      index_set_name,
      index_set_type,
      index_set_names,
      ...searchParams,
    };
    try {
      const res = await $http.request('favorite/updateFavorite', {
        params: { id: props.activeFavorite?.id },
        data,
      });
      if (res.result) {
        window.mainComponent.messageSuccess($t('保存成功'));
        initSourceSQLStr(res.data.params, res.data.search_mode);
        handleRefresh(true);
      }
    } catch (error) {}
  };

  const handleCopyQueryValue = async () => {
    const { search_mode, keyword, addition } = store.getters.retrieveParams;
    if (search_mode === 'ui') {
      $http
        .request('retrieve/generateQueryString', {
          data: {
            addition,
          },
        })
        .then(res => {
          if (res.result) {
            copyMessage(res.data?.querystring || '', $t('复制成功'));
          } else {
            bkMessage({
              theme: 'error',
              message: $t('复制失败'),
            });
          }
        })
        .catch(err => {
          console.log(err);
        });
    } else {
      copyMessage(JSON.stringify(keyword), $t('复制成功'));
    }
  };
</script>
<template>
  <div :class="['search-bar-container', { readonly: isChartMode }]">
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
      <div :class="['search-tool items', { 'is-monitor-trace-log': isMonitorTraceLog }]">
        <div
          v-bk-tooltips="'复制当前查询'"
          :class="['bklog-icon bklog-data-copy', , { disabled: isInputLoading }]"
          @click.stop="handleCopyQueryValue"
        ></div>
        <div
          v-bk-tooltips="'清理当前查询'"
          :class="['bklog-icon bklog-brush', { disabled: isInputLoading }]"
          @click.stop="handleClearBtnClick"
        ></div>
        <template v-if="!isMonitorTraceLog">
          <BookmarkPop
            v-if="!props.activeFavorite"
            v-bk-tooltips="'收藏当前查询'"
            :addition="uiQueryValue"
            :class="{ disabled: isInputLoading }"
            :search-mode="queryParams[activeIndex]"
            :sql="sqlQueryValue"
            @refresh="handleRefresh"
          ></BookmarkPop>
          <template v-else>
            <div
              v-if="matchSQLStr"
              class="bklog-icon bklog-star-line disabled"
              v-bk-tooltips="'已收藏'"
              :data-boolean="matchSQLStr"
            ></div>
            <div
              v-else
              style="color: #63656e"
              class="icon bk-icon icon-save"
              v-bk-tooltips="'收藏'"
              @click="saveCurrentActiveFavorite"
            ></div>
          </template>
        </template>
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
<style scoped lang="scss">
  @import './index.scss';
</style>
<style lang="scss">
  .bklog-sql-input-loading {
    .bk-loading-wrapper {
      left: 30px;
    }
  }
</style>
