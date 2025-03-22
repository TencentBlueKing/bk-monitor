<script setup>
  import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { RetrieveUrlResolver } from '@/store/url-resolver';
  import { useRoute, useRouter } from 'vue-router/composables';
  import PopInstanceUtil from '../../../global/pop-instance-util';

  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import BookmarkPop from './bookmark-pop';
  // #else
  // #code const BookmarkPop = () => null;
  // #endif

  import { ConditionOperator } from '@/store/condition-operator';
  import { bkMessage } from 'bk-magic-vue';

  import $http from '../../../api';
  import { deepClone, copyMessage } from '../../../common/util';
  import useResizeObserve from '../../../hooks/use-resize-observe';
  import CommonFilterSelect from './common-filter-select.vue';
  import { withoutValueConditionList } from './const.common';
  import SqlQuery from './sql-query';
  import UiInput from './ui-input';

  const props = defineProps({
    activeFavorite: {
      default: null,
      type: Object,
    },
    showFavorites: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['refresh', 'height-change']);
  const store = useStore();
  const { $t } = useLocale();
  const queryTypeList = ref([$t('UI 模式'), $t('语句模式')]);
  const refRootElement = ref(null);
  const refKeywordInspectElement = ref(null);

  const queryParams = ['ui', 'sql'];
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

  const inspectResponse = ref({
    is_legal: true,
    is_resolved: true,
    keyword: '',
    message: '',
  });

  const activeIndex = ref(getDefaultActiveIndex());

  const uiQueryValue = ref([]);
  const sqlQueryValue = ref('');

  const refPopContent = ref(null);
  const refPopTraget = ref(null);

  const popToolInstance = new PopInstanceUtil({
    refContent: refPopContent,
    tippyOptions: {
      placement: 'bottom-end',
      zIndex: 200,
      appendTo: document.body,
      interactive: true,
      theme: 'log-light transparent',
      arrow: false,
      offset: [60, 0],
    },
  });

  const inspectPopInstance = new PopInstanceUtil({
    refContent: refKeywordInspectElement,
    tippyOptions: {
      placement: 'bottom-end',
      offset: [0, 10],
    },
  });

  const isFilterSecFocused = computed(() => store.state.retrieve.catchFieldCustomConfig.fixedFilterAddition);

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

  const isCopyBtnActive = computed(() => {
    if (activeIndex.value === 0) {
      return addition.value.length > 0;
    }

    return sqlQueryValue.value.length > 0;
  });

  const isIndexFieldLoading = computed(() => store.state.indexFieldInfo.is_loading);
  const totalFields = computed(() => store.state.indexFieldInfo.fields ?? []);

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

  const beforeQueryBtnClick = () => {
    return $http
      .request('favorite/checkKeywords', {
        data: {
          keyword: sqlQueryValue.value,
          fields: totalFields.value.map(item => ({
            field_name: item.field_name,
            is_analyzed: item.is_analyzed,
            field_type: item.field_type,
          })),
        },
      })
      .then(resp => {
        if (resp.result) {
          Object.assign(inspectResponse.value, resp.data);
          return resp.data;
        }

        return Promise.reject(resp);
      });
  };

  const getBtnQueryResult = () => {
    store.commit('updateIndexItemParams', {
      addition: uiQueryValue.value.filter(val => !val.is_focus_input),
      keyword: sqlQueryValue.value ?? '',
      ip_chooser: uiQueryValue.value.find(item => item.field === '_ip-select_')?.value?.[0] ?? {},
    });

    if (route.query.tab !== 'graphAnalysis') {
      store.dispatch('requestIndexSetQuery');
    }

    setRouteParams();
  };

  const handleBtnQueryClick = () => {
    if (!isInputLoading.value) {
      if (searchMode.value === 'sql') {
        beforeQueryBtnClick().then(resp => {
          if (resp.is_legal && resp.is_resolved) {
            getBtnQueryResult();
          }
        });

        return;
      }

      getBtnQueryResult();
    }
  };

  const handleSqlRetrieve = value => {
    beforeQueryBtnClick().then(resp => {
      if (resp.is_legal) {
        store.commit('updateIndexItemParams', {
          keyword: value,
        });

        store.dispatch('requestIndexSetQuery');
        setRouteParams();
      }
    });
  };

  const handleSqlQueryChange = value => {
    store.commit('updateIndexItemParams', {
      keyword: value,
    });

    setRouteParams();
  };

  const handleClearBtnClick = () => {
    sqlQueryValue.value = '';
    uiQueryValue.value.splice(0);
    store.commit('updateIndexItemParams', {
      ip_chooser: {},
    });
    popToolInstance?.hide(300);
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
    popToolInstance?.uninstallInstance();
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
    if (props.activeFavorite?.index_set_id !== store.state.indexId) {
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
    const { name, group_id, display_fields, visible_type, is_enable_display_fields, index_set_type } =
      props.activeFavorite;
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
    } else {
      Object.assign(data, {
        index_set_id: store.state.indexId,
        index_set_type: 'single',
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
      popToolInstance?.hide(300);

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

  const getTargetElement = () => {
    if (activeIndex.value === 0) {
      return refRootElement.value?.querySelector('.search-item-focus.hidden-pointer');
    }

    const editorLine = refRootElement.value?.querySelector('.search-sql-editor .cm-editor .cm-scroller .cm-line');
    return editorLine?.lastElementChild ?? editorLine;
  };

  const setPopProps = () => {
    if (activeIndex.value === 0) {
      popToolInstance?.setProps({
        offset: [60, 0],
      });
      return;
    }

    popToolInstance?.setProps({
      offset: [60, 20],
    });
  };

  let isPopupShow = false;
  const handlePopupChange = ({ isShow }) => {
    isPopupShow = isShow;
  };

  const handleMouseenterInputSection = () => {
    if (isPopupShow) {
      return;
    }

    const target = getTargetElement();
    setPopProps();

    if (target) {
      popToolInstance.cancelHide();
      popToolInstance.show(target);
    }
  };

  const handleMouseleaveInputSection = () => {
    popToolInstance?.hide(300);
  };

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
          window.mainComponent.messageSuccess($t('“常驻筛选”面板被折叠，过滤条件已填充到上方搜索框。'));
          uiQueryValue.value.push(
            ...formatAddition(common_filter_addition.filter(additionFilter)).map(item => ({
              ...item,
              isCommonFixed: true,
            })),
          );
          localStorage.removeItem('commonFilterAddition');
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

  const handleMouseenterPopContent = () => {
    popToolInstance.cancelHide();
  };

  const handleMouseleavePopContent = () => {
    popToolInstance.hide(300);
  };

  const handleMouseleaveInspect = e => {
    inspectPopInstance.hide(300);
  };

  /**
   * @description 鼠标移入错误校验区域时，弹出错误信息
   * @param e
   */
  const handleMouseenterInspect = (e, isRoot = true) => {
    inspectPopInstance.cancelHide();
    if (isRoot) {
      inspectPopInstance.show(e.target);
    }
  };

  /**
   * @description 点击错误校验区域时，替换关键字
   */
  const handleInspectKeywordReplace = () => {
    sqlQueryValue.value = inspectResponse.value.keyword;
    inspectResponse.value.keyword = '';
    inspectResponse.value.is_legal = true;
    inspectResponse.is_resolved = false;
    inspectPopInstance.hide(300);
  };

  onBeforeUnmount(() => {
    popToolInstance.onBeforeUnmount();
    popToolInstance.uninstallInstance();
  });
</script>
<template>
  <div
    ref="refRootElement"
    :class="['search-bar-wrapper']"
  >
    <div
      :class="[
        'search-bar-container',
        { 'set-border': isFilterSecFocused, 'inspect-error': !inspectResponse.is_legal },
      ]"
    >
      <div
        class="search-options"
        @click="handleQueryTypeChange"
      >
        <span class="mode-text">{{ queryText }}</span>
        <span class="bklog-icon bklog-qiehuan-2" />
      </div>
      <div
        class="search-input"
        :class="{ disabled: isInputLoading }"
        @mouseenter="handleMouseenterInputSection"
        @mouseleave="handleMouseleaveInputSection"
      >
        <UiInput
          v-if="activeIndex === 0"
          v-model="uiQueryValue"
          @change="handleQueryChange"
          @popup-change="handlePopupChange"
        ></UiInput>
        <SqlQuery
          v-if="activeIndex === 1"
          v-model="sqlQueryValue"
          @retrieve="handleSqlRetrieve"
          @popup-change="handlePopupChange"
          @change="handleSqlQueryChange"
        ></SqlQuery>
        <div
          ref="refPopTraget"
          class="hidden-focus-pointer"
        ></div>
        <div class="search-tool items">
          <div
            v-show="!inspectResponse.is_legal"
            style="color: #ea3636"
            class="bklog-icon bklog-circle-alert-filled bklog-keyword-validate"
            @mouseenter="handleMouseenterInspect"
            @mouseleave="handleMouseleaveInspect"
          >
            <div v-show="false">
              <div
                class="bklog-keyword-inspect"
                ref="refKeywordInspectElement"
                @mouseenter="e => handleMouseenterInspect(e, false)"
                @mouseleave="handleMouseleaveInspect"
              >
                <div class="inspect-row">
                  <div class="inspect-title">{{ $t('语法错误') }}：</div>
                  <div class="inspect-message">{{ inspectResponse.message }}</div>
                </div>
                <div
                  class="inspect-row"
                  v-show="inspectResponse.is_resolved"
                >
                  <div class="inspect-title">{{ $t('你可能想输入:') }}</div>
                  <div class="inspect-message">
                    <span>{{ inspectResponse.keyword }}</span>
                    <span
                      class="inspect-keyword-replace"
                      @click="handleInspectKeywordReplace"
                      >{{ $t('替换') }}</span
                    >
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div
            v-bk-tooltips="$t('常用查询设置')"
            :class="['bklog-icon bklog-setting', { disabled: isInputLoading, 'is-focused': isFilterSecFocused }]"
            @click="handleFilterSecClick"
          />
          <BookmarkPop
            :active-favorite="!props.activeFavorite"
            :addition="uiQueryValue"
            :class="{ disabled: isInputLoading }"
            :match-s-q-l-str="matchSQLStr"
            :search-mode="queryParams[activeIndex]"
            :sql="sqlQueryValue"
            @refresh="handleRefresh"
            @save-current-active-favorite="saveCurrentActiveFavorite"
          />
        </div>
        <div
          class="search-tool search-btn"
          @click.stop="handleBtnQueryClick"
        >
          <bk-button
            :loading="isInputLoading"
            icon="search"
            size="small"
            theme="primary"
          />
        </div>
      </div>
      <div style="display: none">
        <div
          ref="refPopContent"
          class="bklog-search-input-poptool"
          @mouseenter="handleMouseenterPopContent"
          @mouseleave="handleMouseleavePopContent"
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
      </div>
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
