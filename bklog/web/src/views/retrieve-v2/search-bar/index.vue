<script setup>
import { ref, computed, watch, nextTick } from "vue";

import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import { RetrieveUrlResolver } from "@/store/url-resolver";
import { useRoute, useRouter } from "vue-router/composables";
import PopInstanceUtil from "../../../global/pop-instance-util";

// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import BookmarkPop from "./bookmark-pop";
// #else
// #code const BookmarkPop = () => null;
// #endif

import { ConditionOperator } from "@/store/condition-operator";
import { bkMessage } from "bk-magic-vue";

import $http from "../../../api";
import { copyMessage } from "../../../common/util";
import useResizeObserve from "../../../hooks/use-resize-observe";
import CommonFilterSelect from "./common-filter-select.vue";
import { withoutValueConditionList } from "./const.common";
import SqlQuery from "./sql-query";
import UiInput from "./ui-input";
import RetrieveHelper, { RetrieveEvent } from "../../retrieve-helper";
import {
  getCommonFilterAddition,
  clearStorageCommonFilterAddition,
} from "../../../store/helper";
import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from "../../../store/store.type";
import { handleTransformToTimestamp } from "@/components/time-range/utils";
import useRetrieveEvent from "@/hooks/use-retrieve-event";

const props = defineProps({
  // activeFavorite: {
  //   default: null,
  //   type: Object,
  // },
  showCopy: {
    type: Boolean,
    default: true,
  },
  showClear: {
    type: Boolean,
    default: true,
  },
  showQuerySetting: {
    type: Boolean,
    default: true,
  },
  showFavorites: {
    type: Boolean,
    default: true,
  },
  // 组件使用方式，global 为全局模式，会更新路由参数，local 为本地模式，只会向外传递搜索参数
  usageType: {
    type: String,
    default: "global",
  },
});

const emit = defineEmits(["refresh", "height-change", "search", "mode-change"]);
const store = useStore();
const { $t } = useLocale();
const queryTypeList = ref([$t("UI 模式"), $t("语句模式")]);
const refRootElement = ref(null);
const refKeywordInspectElement = ref(null);

const route = useRoute();
const router = useRouter();

const inspectResponse = ref({
  is_legal: true,
  is_resolved: true,
  keyword: "",
  message: "",
});

const uiQueryValue = ref([]);
const sqlQueryValue = ref("");
const activeFavorite = ref({});
const refPopTraget = ref(null);
const localModeActiveIndex = ref(0);

const inspectPopInstance = new PopInstanceUtil({
  refContent: refKeywordInspectElement,
  tippyOptions: {
    placement: "bottom-end",
    offset: [0, 10],
  },
});

const isGloalUsage = computed(() => props.usageType === "global");
const activeIndex = computed(() =>
  !isGloalUsage.value
    ? localModeActiveIndex.value
    : store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE] ?? 0
);
const isFilterSecFocused = computed(
  () =>
    isGloalUsage.value &&
    store.state.retrieve.catchFieldCustomConfig.fixedFilterAddition
);
const indexItem = computed(() => store.state.indexItem);
const keyword = computed(() => indexItem.value.keyword);
const addition = computed(() => indexItem.value.addition);
const searchMode = computed(() =>
  !isGloalUsage.value
    ? SEARCH_MODE_DIC[localModeActiveIndex.value]
    : SEARCH_MODE_DIC[store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? "ui"
);
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

const isIndexFieldLoading = computed(
  () => store.state.indexFieldInfo.is_loading
);

const computedIconClass = computed(() => {
  const iconClass = {
    0: "bklog-icon bklog-ui1 mode-icon",
    1: "bklog-icon bklog-yuju1 mode-icon",
  };
  return iconClass[activeIndex.value] || "";
});
const isShowSearchTools = computed(() => {
  return (
    props.showCopy ||
    props.showClear ||
    props.showQuerySetting ||
    props.showFavorites
  );
});

watch(
  () => isIndexFieldLoading.value,
  () => {
    nextTick(() => {
      uiQueryValue.value.forEach(
        (v) =>
          (v.field_type = (indexFieldInfo.value.fields ?? []).find(
            (f) => f.field_name === v.field
          )?.field_type)
      );
    });
  }
);

watch(
  keyword,
  () => {
    sqlQueryValue.value = keyword.value;
  },
  { immediate: true }
);

watch(clearSearchValueNum, () => {
  handleClearBtnClick();
});

const formatAddition = (addition) => {
  return addition.map((v) => {
    const value = {
      ...v,
      field_type: (indexFieldInfo.value.fields ?? []).find(
        (f) => f.field_name === v.field
      )?.field_type,
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
  { immediate: true, deep: true }
);

const setRouteParams = () => {
  const query = { ...route.query };

  const nextMode = SEARCH_MODE_DIC[activeIndex.value];
  const resolver = new RetrieveUrlResolver({
    keyword: keyword.value,
    addition: store.getters.retrieveParams.addition,
    search_mode: nextMode,
  });

  Object.assign(query, resolver.resolveParamsToUrl());
  router.replace({
    query,
  });
};

const requestIndexSetList = () => {
  if (route.query.tab === 'origin' || !route.query.tab) {
    store.dispatch("requestIndexSetQuery");
  }
}

const beforeQueryBtnClick = () => {
  // 功能完善后再放开
  return Promise.resolve(true);
  // return $http
  //   .request('favorite/checkKeywords', {
  //     data: {
  //       keyword: sqlQueryValue.value,
  //       fields: totalFields.value.map(item => ({
  //         field_name: item.field_name,
  //         is_analyzed: item.is_analyzed,
  //         field_type: item.field_type,
  //       })),
  //     },
  //   })
  //   .then(resp => {
  //     if (resp.result) {
  //       Object.assign(inspectResponse.value, resp.data);
  //       return resp.data;
  //     }

  //     return Promise.reject(resp);
  //   });
};

const getBtnQueryResult = () => {
  store.commit("updateIndexItemParams", {
    addition: uiQueryValue.value.filter((val) => !val.is_focus_input),
    keyword: sqlQueryValue.value ?? "",
    ip_chooser:
      uiQueryValue.value.find((item) => item.field === "_ip-select_")
        ?.value?.[0] ?? {},
  });

  requestIndexSetList();
  setRouteParams();
};

const handleBtnQueryClick = () => {
  if (isGloalUsage.value) {
    if (!isInputLoading.value) {
      const { datePickerValue, format } = store.state.indexItem;
      const result = handleTransformToTimestamp(datePickerValue, format);

      store.commit("updateIndexItemParams", {
        start_time: result[0],
        end_time: result[1],
        datePickerValue,
      });

      if (searchMode.value === "sql") {
        beforeQueryBtnClick().then(() => {
          getBtnQueryResult();
          RetrieveHelper.searchValueChange(
            searchMode.value,
            sqlQueryValue.value
          );
        });

        return;
      }

      getBtnQueryResult();
      RetrieveHelper.searchValueChange(searchMode.value, uiQueryValue.value);
    }
    return;
  }
  emit(
    "search",
    searchMode.value,
    searchMode.value === "ui" ? uiQueryValue.value : sqlQueryValue.value
  );
};

const handleSqlRetrieve = (value) => {
  if (isGloalUsage.value) {
    if (value !== "*") {
      beforeQueryBtnClick().then(() => {
        store.commit("updateIndexItemParams", {
          keyword: value,
        });

        requestIndexSetList();
        setRouteParams();
        RetrieveHelper.searchValueChange(searchMode.value, sqlQueryValue.value);
      });
      return;
    }

    requestIndexSetList();
    setRouteParams();
    RetrieveHelper.searchValueChange(searchMode.value, sqlQueryValue.value);
    return;
  }
};

const handleSqlQueryChange = (value) => {
  if (isGloalUsage.value) {
    store.commit("updateIndexItemParams", {
      keyword: value,
    });

    inspectResponse.value.is_legal = true;
    setRouteParams();
    return;
  }
};

const handleClearBtnClick = () => {
  if (!isCopyBtnActive.value || isInputLoading.value) {
    return;
  }

  sqlQueryValue.value = "";
  uiQueryValue.value.splice(0);
  store.commit("updateIndexItemParams", {
    ip_chooser: {},
  });
  handleBtnQueryClick();
};

const handleRefresh = (isRefresh) => {
  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  emit("refresh", isRefresh);
  // #endif
};

const handleHeightChange = (height) => {
  emit("height-change", height);
};

const handleQueryTypeChange = () => {
  const nextType = activeIndex.value === 0 ? 1 : 0;
  const nextMode = SEARCH_MODE_DIC[nextType];
  inspectResponse.value.is_legal = true;
  inspectResponse.is_resolved = false;
  if (isGloalUsage.value) {
    store.commit("updateStorage", { [BK_LOG_STORAGE.SEARCH_TYPE]: nextType });
    store.commit("updateIndexItemParams", {
      search_mode: nextMode,
    });
    if (
      addition.value.length > 0 ||
      (keyword.value !== "*" && keyword.value !== "")
    ) {
      handleBtnQueryClick();
    } else {
      setRouteParams();
    }
  } else {
    localModeActiveIndex.value = nextType;
  }
  emit("mode-change", nextMode);
};

const sourceSQLStr = ref("");
const sourceUISQLAddition = ref([]);
const initSourceSQLStr = (params, search_mode) => {
  if (search_mode === "ui") {
    sourceUISQLAddition.value = formatAddition(
      structuredClone(params.addition)
    );
  } else {
    sourceSQLStr.value = params?.keyword ?? "";
  }
};

const { addEvent } = useRetrieveEvent();
addEvent(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, (val) => {
  activeFavorite.value = val;
  const type =
    SEARCH_MODE_DIC.findIndex(
      (idx) => idx === activeFavorite.value.search_mode
    ) ?? 0;

  initSourceSQLStr(
    activeFavorite.value.params,
    activeFavorite.value.search_mode
  );
  store.commit("updateStorage", { searchType: type });
  setRouteParams();
});

const matchSQLStr = computed(() => {
  if (activeFavorite.value?.index_set_id !== store.state.indexId) {
    return false;
  }
  if (activeIndex.value === 0) {
    if (sourceUISQLAddition.value.length !== uiQueryValue.value.length) {
      return false;
    }
    const differerntUISQL = sourceUISQLAddition.value.find((item, index) => {
      return (
        item.field + item.operator + item.value !==
        uiQueryValue.value[index].field +
          uiQueryValue.value[index].operator +
          uiQueryValue.value[index].value
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
    index_set_type,
  } = activeFavorite.value;
  const searchMode = activeIndex.value === 0 ? "ui" : "sql";
  const reqFormatAddition = uiQueryValue.value.map((item) =>
    new ConditionOperator(item).getRequestParam()
  );
  const searchParams =
    searchMode === "sql"
      ? { keyword: sqlQueryValue.value, addition: [] }
      : {
          addition: reqFormatAddition.filter((v) => v.field !== "_ip-select_"),
          keyword: "*",
        };

  const data = {
    name,
    group_id,
    display_fields,
    visible_type,
    is_enable_display_fields,
    search_mode: searchMode,
    ip_chooser:
      reqFormatAddition.find((item) => item.field === "_ip-select_")
        ?.value?.[0] ?? {},
    index_set_type,
    ...searchParams,
  };
  if (indexSetItem.value.isUnionIndex) {
    Object.assign(data, {
      index_set_ids: indexSetItem.value.ids,
      index_set_type: "union",
    });
  } else {
    Object.assign(data, {
      index_set_id: store.state.indexId,
      index_set_type: "single",
    });
  }
  try {
    const res = await $http.request("favorite/updateFavorite", {
      params: { id: activeFavorite.value?.id },
      data,
    });
    if (res.result) {
      window.mainComponent.messageSuccess($t("保存成功"));
      initSourceSQLStr(res.data.params, res.data.search_mode);
      store.dispatch("requestFavoriteList");
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
        .request("retrieve/generateQueryString", {
          data: {
            addition: addition.value,
          },
        })
        .then((res) => {
          if (res.result) {
            copyMessage(res.data?.querystring || "", $t("复制成功"));
          } else {
            bkMessage({
              theme: "error",
              message: $t("复制失败"),
            });
          }
        })
        .catch((err) => {
          console.log(err);
        });
    }
  } else {
    const target = sqlQueryValue.value.replace(/^\s+|\s+$/, "");
    if (target.length) {
      copyMessage(target, $t("复制成功"));
    }
  }
};

useResizeObserve(refRootElement, () => {
  if (refRootElement.value) {
    handleHeightChange(refRootElement.value.offsetHeight);
  }
});

const additionFilter = (addition) => {
  return (
    withoutValueConditionList.includes(addition.operator) ||
    addition.value?.length > 0
  );
};

const handleFilterSecClick = () => {
  if (isFilterSecFocused.value) {
    if (activeIndex.value === 0) {
      const common_filter_addition = getCommonFilterAddition(store.state);
      if (common_filter_addition.length) {
        window.mainComponent.messageSuccess(
          $t("“常驻筛选”面板被折叠，过滤条件已填充到上方搜索框。")
        );
        uiQueryValue.value.push(
          ...formatAddition(common_filter_addition.filter(additionFilter)).map(
            (item) => ({
              ...item,
              isCommonFixed: true,
            })
          )
        );
        clearStorageCommonFilterAddition(store.state);
        store.commit("updateIndexItemParams", {
          addition: uiQueryValue.value.filter((val) => !val.is_focus_input),
          keyword: sqlQueryValue.value ?? "",
          ip_chooser:
            uiQueryValue.value.find((item) => item.field === "_ip-select_")
              ?.value?.[0] ?? {},
        });

        setRouteParams();
      }
    }
  }

  if (activeIndex.value === 1) {
    store.dispatch("userFieldConfigChange", {
      fixedFilterAddition: !isFilterSecFocused.value,
    });

    return;
  }

  store.dispatch("userFieldConfigChange", {
    fixedFilterAddition: !isFilterSecFocused.value,
    filterAddition: [],
  });
};

const handleMouseleaveInspect = (e) => {
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
  inspectResponse.value.keyword = "";
  inspectResponse.value.is_legal = true;
  inspectResponse.is_resolved = false;
  inspectPopInstance.hide(300);
};

defineExpose({
  setLocalMode: (val) => {
    localModeActiveIndex.value = val;
  },
  addValue: (item) => {
    if (searchMode.value === "ui") {
      const isExisted = uiQueryValue.value.find(
        (v) =>
          v.field === item.field &&
          v.operator === item.operator &&
          v.value.toString() === item.value.toString()
      );
      if (isExisted) {
        console.warn("已存在相同条件，无法添加");
        return false;
      }
      uiQueryValue.value.push(item);
      return true;
    }

    if (sqlQueryValue.value.includes(item)) {
      console.warn("已存在相同条件，无法添加");
      return false;
    }
    if (sqlQueryValue.value.length > 0) {
      sqlQueryValue.value += " AND ";
    }
    sqlQueryValue.value += item;
    return true;
  },
  getValue: () =>
    searchMode.value === "ui" ? uiQueryValue.value : sqlQueryValue.value,
});
</script>
<template>
  <div ref="refRootElement" :class="['search-bar-wrapper']">
    <div
      :class="[
        'search-bar-container',
        {
          'set-border': isFilterSecFocused,
          'inspect-error': !inspectResponse.is_legal,
        },
      ]"
    >
      <div class="search-options" @click="handleQueryTypeChange">
        <span class="mode-text">{{ queryText }}</span>
        <span v-bk-tooltips.top="queryText" :class="computedIconClass"></span>
        <span class="bklog-icon bklog-qiehuan-2" />
      </div>
      <div class="search-input" :class="{ disabled: isInputLoading }">
        <UiInput
          v-if="activeIndex === 0"
          v-model="uiQueryValue"
          @change="handleBtnQueryClick"
        ></UiInput>
        <SqlQuery
          v-if="activeIndex === 1"
          v-model="sqlQueryValue"
          @retrieve="handleSqlRetrieve"
          @change="handleSqlQueryChange"
        ></SqlQuery>
        <div ref="refPopTraget" class="hidden-focus-pointer"></div>
        <div class="search-tool items" v-if="isShowSearchTools">
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
                @mouseenter="(e) => handleMouseenterInspect(e, false)"
                @mouseleave="handleMouseleaveInspect"
              >
                <div class="inspect-row">
                  <div class="inspect-title">{{ $t("语法错误") }}：</div>
                  <div class="inspect-message">
                    {{ inspectResponse.message }}
                  </div>
                </div>
                <div class="inspect-row" v-show="inspectResponse.is_resolved">
                  <div class="inspect-title">
                    <span>{{ $t("你可能想输入:") }}</span
                    ><span
                      class="inspect-keyword-replace"
                      @click="handleInspectKeywordReplace"
                      >{{ $t("替换") }}</span
                    >
                  </div>
                  <div class="inspect-message">
                    <span>{{ inspectResponse.keyword }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div
            v-if="showCopy"
            v-bk-tooltips="$t('复制当前查询')"
            :class="[
              'bklog-icon bklog-copy-4',
              ,
              { disabled: isInputLoading || !isCopyBtnActive },
            ]"
            @click="handleCopyQueryValue"
          ></div>
          <div
            v-if="showClear"
            v-bk-tooltips="$t('清理当前查询')"
            :class="[
              'bklog-icon bklog-qingkong',
              { disabled: isInputLoading || !isCopyBtnActive },
            ]"
            @click="handleClearBtnClick"
          ></div>
          <div
            v-if="showQuerySetting"
            v-bk-tooltips="$t('常用查询设置')"
            :class="[
              'bklog-icon bklog-setting',
              { disabled: isInputLoading, 'is-focused': isFilterSecFocused },
            ]"
            @click="handleFilterSecClick"
          />
          <BookmarkPop
            v-if="showFavorites"
            :active-favorite="!activeFavorite?.id"
            :addition="uiQueryValue"
            :class="{ disabled: isInputLoading }"
            :match-s-q-l-str="matchSQLStr"
            :search-mode="SEARCH_MODE_DIC[activeIndex]"
            :sql="sqlQueryValue"
            @refresh="handleRefresh"
            @save-current-active-favorite="saveCurrentActiveFavorite"
          />
        </div>
        <div class="search-tool search-btn" @click="handleBtnQueryClick">
          <bk-button
            :loading="isInputLoading"
            icon="search"
            size="small"
            theme="primary"
          />
        </div>
      </div>
    </div>
    <template v-if="isFilterSecFocused">
      <CommonFilterSelect></CommonFilterSelect>
    </template>
  </div>
</template>
<style scoped lang="scss">
@import "./index.scss";
</style>
<style lang="scss">
.bklog-sql-input-loading {
  .bk-loading-wrapper {
    left: 30px;
  }
}

[data-tippy-root] .tippy-box {
  &[data-theme*="transparent"] {
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
