<script setup>
  import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { useRoute, useRouter } from 'vue-router/composables';
  import { RetrieveUrlResolver } from '@/store/url-resolver';
  // import PopInstanceUtil from './pop-instance-util';

  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import BookmarkPop from './bookmark-pop';
  // #else
  // #code const BookmarkPop = () => null;
  // #endif

  import { ConditionOperator } from '@/store/condition-operator';

  import $http from '../../../api';
  import { deepClone, copyMessage } from '../../../common/util';
  import SqlQuery from './sql-query';
  import UiInput from './ui-input';
  import { bkMessage } from 'bk-magic-vue';
  import CommonFilterSelect from './common-filter-select.vue';
  import useResizeObserve from '../../../hooks/use-resize-observe';
  import { withoutValueConditionList } from './const.common';

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
  const refRootElement = ref(null);
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

    // addition 是一个json字符串，解析出来之后至少为 [{'field': ''}], 所以这里判定长度至少 包含 '[{}]'
    if (route.query.addition?.length > 4) {
      return 0;
    }

    return Number(localStorage.getItem('bkLogQueryType') ?? 0);
  };

  const activeIndex = ref(getDefaultActiveIndex());

  const uiQueryValue = ref([]);
  const sqlQueryValue = ref('');

  // const refPopContent = ref(null);
  // const refPopTraget = ref(null);

  // const popToolInstance = new PopInstanceUtil({
  //   refContent: refPopContent,
  //   tippyOptions: {
  //     placement: 'top-end',
  //     zIndex: 200,
  //     appendTo: document.body,
  //     interactive: true,
  //     theme: 'log-light transparent',
  //     arrow: false,
  //   },
  // });

  const isFilterSecFocused = computed(() => store.state.retrieve.catchFieldCustomConfig.fixedFilterAddition);

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

  const isCopyBtnActive = computed(() => {
    if (activeIndex.value === 0) {
      return addition.value.length > 0;
    }

    return sqlQueryValue.value.length > 0;
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
    if(props.activeFavorite?.index_set_id !== store.state.indexId ){
      return false;
    }
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
  const indexSetItem = computed(() => store.state.indexItem);

  const saveCurrentActiveFavorite = async () => {
    if (matchSQLStr.value) {
      return;
    }
    const {
      name,
      group_id,
      display_fields,
      visible_type,
      is_enable_display_fields,
      index_set_names,
      index_set_type,
      index_set_ids,
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
      index_set_type,
      ...searchParams,
    };
    if (indexSetItem.value.isUnionIndex) {
      Object.assign(data, {
        index_set_ids: indexSetItem.value.ids,
        index_set_type: 'union',
      });
    }else{
      Object.assign(data, {
        index_set_id: store.state.indexId,
        index_set_type: 'single'
      });
    }
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
    if (!isCopyBtnActive.value) {
      return;
    }

    if (activeIndex.value === 0) {
      if (addition.value.length > 0) {
        $http
          .request('retrieve/generateQueryString', {
            data: {
              addition: addition.value,
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
      }
    } else {
      const target = sqlQueryValue.value.replace(/^\s+|\s+$/, '');
      if (target.length) {
        copyMessage(target, $t('复制成功'));
      }
    }
  };

  // const handleMouseenterInputSection = () => {
  //   popToolInstance.show(refPopTraget.value);
  // };

  // const handleMouseleaveInputSection = () => {
  // };

  useResizeObserve(refRootElement, () => {
    if (refRootElement.value) {
      handleHeightChange(refRootElement.value.offsetHeight);
    }
  });

  const additionFilter = addition => {
    return withoutValueConditionList.includes(addition.operator) || addition.value?.length > 0;
  };

  const handleFilterSecClick = () => {
    if (isFilterSecFocused.value) {
      if (activeIndex.value === 0) {
        const { common_filter_addition } = store.getters;
        if (common_filter_addition.length) {
          window.mainComponent.messageSuccess($t('常驻筛选”面板被折叠，过滤条件已填充到上方搜索框。'));
          uiQueryValue.value.push(
            ...formatAddition(common_filter_addition.filter(additionFilter)).map(item => ({
              ...item,
              isCommonFixed: true,
            })),
          );

          store.commit('updateIndexItemParams', {
            addition: uiQueryValue.value.filter(val => !val.is_focus_input),
            keyword: sqlQueryValue.value ?? '',
            ip_chooser: uiQueryValue.value.find(item => item.field === '_ip-select_')?.value?.[0] ?? {},
          });

          setRouteParams();
        }
      }
    }

    if (activeIndex.value === 1) {
      store.dispatch('userFieldConfigChange', {
        fixedFilterAddition: !isFilterSecFocused.value,
      });

      return;
    }

    store.dispatch('userFieldConfigChange', {
      fixedFilterAddition: !isFilterSecFocused.value,
      filterAddition: [],
    });
  };

  onBeforeUnmount(() => {
    // popToolInstance.onBeforeUnmount();
    // popToolInstance.uninstallInstance();
  });
</script>
<template>
  <div
    ref="refRootElement"
    :class="['search-bar-wrapper', { readonly: isChartMode }]"
  >
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
        ></UiInput>
        <SqlQuery
          v-if="activeIndex === 1"
          v-model="sqlQueryValue"
          @retrieve="handleSqlRetrieve"
        ></SqlQuery>
        <div
          class="hidden-focus-pointer"
          ref="refPopTraget"
        ></div>
        <div class="search-tool items">
          <div
            v-bk-tooltips="$t('复制当前查询')"
            :class="['bklog-icon bklog-data-copy', , { disabled: isInputLoading || !isCopyBtnActive }]"
            @click.stop="handleCopyQueryValue"
          ></div>
          <div
            v-bk-tooltips="$t('清理当前查询')"
            :class="['bklog-icon bklog-brush', { disabled: isInputLoading || !isCopyBtnActive }]"
            @click.stop="handleClearBtnClick"
          ></div>

          <BookmarkPop
            :activeFavorite="!props.activeFavorite"
            :addition="uiQueryValue"
            :class="{ disabled: isInputLoading }"
            :search-mode="queryParams[activeIndex]"
            :sql="sqlQueryValue"
            :matchSQLStr="matchSQLStr"
            @saveCurrentActiveFavorite="saveCurrentActiveFavorite"
            @refresh="handleRefresh"
          ></BookmarkPop>

          <div
            v-bk-tooltips="$t('常用查询设置')"
            :class="['bklog-icon bklog-setting', { disabled: isInputLoading, 'is-focused': isFilterSecFocused }]"
            @click="handleFilterSecClick"
          ></div>
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
      <!-- <div style="display: none">
        <div
          ref="refPopContent"
          class="bklog-search-input-poptool"
        >
          <div
            v-bk-tooltips="$t('复制当前查询')"
            :class="['bklog-icon bklog-data-copy', , { disabled: isInputLoading }]"
            @click.stop="handleCopyQueryValue"
          ></div>
          <div
            v-bk-tooltips="$t('清理当前查询')"
            :class="['bklog-icon bklog-brush', { disabled: isInputLoading }]"
            @click.stop="handleClearBtnClick"
          ></div>
        </div>
      </div> -->
    </div>
    <template v-if="isFilterSecFocused">
      <CommonFilterSelect></CommonFilterSelect>
    </template>
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

  [data-tippy-root] .tippy-box {
    &[data-theme*='transparent'] {
      background-color: transparent;
      border: none;
    }
  }

  .bklog-search-input-poptool {
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;

    .bklog-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      margin-right: 4px;
      color: #4d4f56;
      cursor: pointer;
      background: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      box-shadow: 0 1px 3px 1px #0000001f;

      &:hover {
        color: #3a84ff;
      }
    }
  }
</style>
