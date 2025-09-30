<script setup>
import { ref, computed, set } from "vue";

import {
  getOperatorKey,
  formatDateTimeField,
  getOsCommandLabel,
} from "@/common/util";
import useFieldNameHook from "@/hooks/use-field-name";
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";

import {
  getInputQueryDefaultItem,
  getInputQueryIpSelectItem,
  FulltextOperatorKey,
  FulltextOperator,
} from "./const.common";
import { operatorMapping, translateKeys } from "./const-values";
import IPSelector from "./ip-selector";
import UiInputOptions from "./ui-input-option.vue";
import useFocusInput from "./use-focus-input";
const props = defineProps({
  value: {
    type: Array,
    required: true,
    default: () => [],
  },
});

const emit = defineEmits(["input", "change", "height-change", "popup-change"]);
const store = useStore();
const { t } = useLocale();
const popoverRefs = ref(new Map());
const morePopoverRefs = ref([]);
const setPopoverRef = (el, parentIndex, childIndex) => {
  const key = `${parentIndex}-${childIndex}`;
  if (el) {
    popoverRefs.value.set(key, el);
  } else {
    popoverRefs.value.delete(key);
  }
};
const setMorePopoverRef = (el, index) => {
  if (el) {
    morePopoverRefs.value[index] = el;
  }
};
const inputValueLength = ref(0);
// 动态设置placeHolder
const inputPlaceholder = computed(() => {
  if (inputValueLength.value === 0) {
    return `${t("快捷键")} /，${t("请输入")}...`;
  }

  return "";
});

const bkBizId = computed(() => store.state.bkBizId);

/**
 * 格式化搜索标签渲染格式
 * @param {*} item
 */
const formatModelValueItem = (item) => {
  if (typeof item?.value === "string") {
    item.value = item.value.split(",");
  }

  item.showAll = item?.value?.length < 3;
  if (!item?.relation) item.relation = "OR";
  return { disabled: item.disabled ?? false, ...(item ?? {}) };
};

const handleHeightChange = (height) => {
  emit("height-change", height);
};

const operatorDictionary = computed(() => {
  const defVal = {
    [getOperatorKey(FulltextOperatorKey)]: {
      label: t("包含"),
      operator: FulltextOperator,
    },
  };
  return {
    ...defVal,
    ...store.state.operatorDictionary,
  };
});

/**
 * 获取操作符展示文本
 * @param {*} item
 */
const getOperatorLabel = (item) => {
  if (item.field === "_ip-select_") {
    return "";
  }

  const key =
    item.field === "*"
      ? getOperatorKey(`*${item.operator}`)
      : getOperatorKey(item.operator);
  if (translateKeys.includes(operatorMapping[item.operator])) {
    const operator = operatorMapping[item.operator] ?? item.operator;
    if (/[\u4e00-\u9fff]/.test(operator)) {
      return t(operator);
    }

    return operator;
  }

  return (
    operatorMapping[item.operator] ??
    operatorDictionary.value[key]?.label ??
    item.operator
  );
};

const refPopInstance = ref(null);
const refUlRoot = ref(null);
const refSearchInput = ref(null);
const refHiddenFocus = ref(null);
const queryItem = ref("");
const activeIndex = ref(null);

const showIpSelector = ref(false);

const getSearchInputValue = () => {
  return refSearchInput.value?.value ?? "";
};

const setSearchInputValue = (val) => {
  refSearchInput.value.value = val ?? "";
  inputValueLength.value = refSearchInput.value?.value?.length ?? 0;
};

const handleWrapperClickCapture = (e, { getTippyInstance }) => {
  const instance = getTippyInstance();
  const reference = instance?.reference;

  const target = refSearchInput.value?.closest(".search-item");
  if (reference) {
    // 如果当前是input focus激活的弹出提示
    // 判定当前是否为点击 ui 搜索框
    if (reference === target) {
      return e.target === refUlRoot.value;
    }

    // 判定当前点击是否为某一个条件选项
    return reference.contains(e.target);
  }

  return false;
};

const { getFieldName } = useFieldNameHook({ store });
const {
  modelValue,
  isInputTextFocus,
  setIsInputTextFocus,
  setIsDocumentMousedown,
  isInstanceShown,
  delayShowInstance,
  repositionTippyInstance,
  hideTippyInstance,
  getTippyUtil,
} = useFocusInput(props, {
  refContent: refPopInstance,
  refTarget: refHiddenFocus,
  refWrapper: refUlRoot,
  onHeightChange: handleHeightChange,
  formatModelValueItem,

  onShowFn: () => {
    setIsDocumentMousedown(true);
    refPopInstance.value?.beforeShowndFn?.();
    emit("popup-change", { isShow: true });
  },
  onHiddenFn: () => {
    emit("popup-change", { isShow: false });
    refPopInstance.value?.afterHideFn?.();
    return true;
  },
  handleWrapperClick: handleWrapperClickCapture,
  onInputFocus: () => {
    queryItem.value = "";
    activeIndex.value = null;
  },
  tippyOptions: {
    hideOnClick: true,
    placement: "top",
  },
});

const debounceShowInstance = () => {
  const target = refSearchInput.value?.closest(".search-item");
  if (target) {
    delayShowInstance(target);
  }
};

const closeTippyInstance = () => {
  setIsDocumentMousedown(false);
  hideTippyInstance();
};

/**
 * 执行点击弹出操作项方法
 * @param {*} target 目标元素
 */
const showTagListItems = (target) => {
  if (isInstanceShown()) {
    repositionTippyInstance();
    return;
  }

  delayShowInstance(target);
};

const getMatchName = (field) => {
  if (field === "*") return t("全文");
  if (field === "_ip-select_") return t("IP目标");

  return getFieldName(field);
};

const emitChange = (value) => {
  emit("input", value);
  emit("change", value);
};

const handleAddItem = (e) => {
  setIsInputTextFocus(false);
  const target = e.target.closest(".search-item");
  queryItem.value = "";
  activeIndex.value = null;
  showTagListItems(target);
};

const handleTagItemClick = (e, item, index) => {
  if (item.field === "_ip-select_") {
    showIpSelector.value = true;
    return;
  }
  const { changeFieldName } = useFieldNameHook({ store });
  const itemCopy = structuredClone(item);
  itemCopy.field = changeFieldName(itemCopy.field);
  queryItem.value = {};
  setIsInputTextFocus(false);

  if (!Array.isArray(item.value)) item.value = item.value.split(",");
  if (!item.relation) item.relation = "OR";
  Object.assign(queryItem.value, itemCopy);
  const target = e.target.closest(".search-item");
  activeIndex.value = index;
  showTagListItems(target);
};

const handleDisabledTagItem = (item) => {
  set(item, "disabled", !item.disabled);
  set(item, "hidden_values", []);
  if (item.disabled) {
    set(item, "hidden_values", [...item.value]);
  }

  emitChange(modelValue.value);
};

const handleDeleteTagItem = (index, item) => {
  modelValue.value.splice(index, 1);
  emitChange(modelValue.value);
};

/**
 * 点击查询
 * @param payload
 */
const handleSaveQueryClick = (payload) => {
  if (payload === "ip-select-show") {
    const copyValue = getInputQueryIpSelectItem();
    if (!modelValue.value.some((f) => f.field === copyValue.field)) {
      modelValue.value.push({ ...copyValue, disabled: false });
    }

    repositionTippyInstance();
    setTimeout(() => {
      showIpSelector.value = true;
    }, 100);

    refSearchInput.value?.focus();
    return;
  }

  const isPayloadValueEmpty = !(payload?.value?.length ?? 0);
  const isFulltextEnterVlaue =
    isInputTextFocus.value && isPayloadValueEmpty && !payload?.field;

  const inputVal = getSearchInputValue();
  // 如果是全文检索，未输入任何内容就点击回车
  // 此时提交无任何意义，禁止后续逻辑
  if (isFulltextEnterVlaue && !inputVal.length) {
    refSearchInput.value?.focus();
    return;
  }

  const targetValue = formatModelValueItem(
    isFulltextEnterVlaue ? getInputQueryDefaultItem(inputVal) : payload
  );

  if (isInputTextFocus.value) {
    setSearchInputValue("");
  }

  if (activeIndex.value !== null && activeIndex.value >= 0) {
    Object.assign(modelValue.value[activeIndex.value], targetValue);
    emitChange(modelValue.value);
    hideTippyInstance();
    activeIndex.value = null;

    return;
  }

  modelValue.value.push({ ...targetValue, disabled: false });
  emitChange(modelValue.value);
  repositionTippyInstance();
  refSearchInput.value?.focus();
};

// 用于判定当前 key.enter 是全局绑定触发还是 input.key.enter触发
const isGlobalKeyEnter = ref(false);
const handleGlobalSaveQueryClick = (payload) => {
  isGlobalKeyEnter.value = true;
  handleSaveQueryClick(payload);
  refSearchInput.value.style.setProperty("width", "12px");
};

/**
 * input key enter
 * @param e
 */
const handleInputValueEnter = (e) => {
  if (!isGlobalKeyEnter.value) {
    handleSaveQueryClick(undefined);
    repositionTippyInstance();
    e.target.style.setProperty("width", "12px");
  }

  isGlobalKeyEnter.value = false;
};

const handleCancelClick = () => {
  setSearchInputValue("");
  closeTippyInstance();
};

const handleInputTextClick = () => {
  if (isInstanceShown() || isInputTextFocus.value) {
    return;
  }

  debounceShowInstance();
};

const handleFullTextInputBlur = (e) => {
  setIsInputTextFocus(false);
  inputValueLength.value = 0;
  e.target.style.setProperty("width", "12px");
  e.target.value = "";
  queryItem.value = "";
};

const handleInputValueChange = (e) => {
  if (inputValueLength.value === 0 && e.target.value.length > 0) {
    inputValueLength.value = e.target.value.length;
    debounceShowInstance();
  }

  queryItem.value = e.target.value;
};

// 键盘删除键
const needDeleteItem = ref(false);
const handleDeleteItem = (e) => {
  if (e.target.value) {
    needDeleteItem.value = false;
  }

  if (!e.target.value) {
    if (needDeleteItem.value) {
      if (modelValue.value.length >= 1) {
        modelValue.value.splice(-1, 1);
        emitChange(modelValue.value);
        repositionTippyInstance();
      }
    }

    needDeleteItem.value = true;
  }
};

const handleIPChange = () => {
  emitChange(modelValue.value);
};
const handlePopoverShow = (parentIndex, childIndex) => {
  const popover = popoverRefs.value.get(`${parentIndex}-${childIndex}`);
  popover?.showHandler();
};
const changeOptionShow = (item, child, parentIndex, childIndex) => {
  if (!item.hidden_values) {
    item.hidden_values = [];
  }

  if (item.hidden_values.includes(child)) {
    const index = item.hidden_values.indexOf(child);
    item.hidden_values.splice(index, 1);
    item.disabled = false;
  } else {
    item.hidden_values.push(child);
  }

  emitChange(structuredClone(modelValue.value));
  const popover = popoverRefs.value.get(`${parentIndex}-${childIndex}`);
  popover?.hideHandler();
};
const onlyOptionShow = (item, child, parentIndex, childIndex) => {
  item.hidden_values.length = 0;
  item.hidden_values = [];
  item.disabled = false;

  item.value.forEach((v) => {
    if (v !== child) {
      item.hidden_values.push(v);
    }
  });

  emitChange(structuredClone(modelValue.value));
  const popover = popoverRefs.value.get(`${parentIndex}-${childIndex}`);
  popover?.hideHandler();
};
const moreOption = (index) => {
  morePopoverRefs.value[index].showHandler();
};

/**
 * 根据 hidden_values 动态获取当前展示文本
 * @param item
 * @param child
 */
const getItemActionShowText = (item, child) => {
  if (item.hidden_values?.includes(child)) {
    return "恢复这个选项";
  }

  return "隐藏这个选项";
};

/**
 * 批量添加分词弹出事件
 * @param isShow
 */
const handleBatchInputChange = (isShow) => {
  const instance = getTippyUtil();
  if (instance) {
    instance.setProps({ hideOnClick: !isShow });
  }
};
</script>

<template>
  <ul ref="refUlRoot" class="search-items">
    <li class="search-item btn-add" @click.stop="handleAddItem">
      <div class="tag-add">+</div>
      <div class="tag-text">{{ t("添加条件") }}</div>
    </li>
    <li
      v-for="(item, index) in modelValue"
      :class="[
        'search-item',
        'tag-item',
        { 'is-common-fixed': item.isCommonFixed },
      ]"
      :key="`${item.field}-${index}`"
      @click.stop="(e) => handleTagItemClick(e, item, index)"
    >
      <div class="tag-row match-name">
        <span class="match-name-label">{{ getMatchName(item.field) }}</span>
        <span class="symbol" :data-operator="item.operator">{{
          getOperatorLabel(item)
        }}</span>
      </div>
      <div class="tag-row match-value">
        <template v-if="item.field === '_ip-select_'">
          <span
            :class="[
              'match-value-text',
              { 'is-show-tooltip': item.value.length > 20 },
            ]"
          >
            <IPSelector
              v-model="item.value[0]"
              :bk-biz-id="bkBizId"
              :is-show.sync="showIpSelector"
              @change="handleIPChange"
            ></IPSelector>
          </span>
        </template>
        <template v-else-if="Array.isArray(item.value)">
          <span v-for="(child, childIndex) in item.value" :key="childIndex">
            <template v-if="item.showAll ? true : childIndex < 3">
              <bk-popover
                :ref="(el) => setPopoverRef(el, index, childIndex)"
                placement="bottom"
                theme="light"
                trigger="click"
              >
                <span
                  v-bk-tooltips="{
                    content: item.value,
                    disabled: item.value.length < 21,
                  }"
                  :class="[
                    'match-value-text',
                    { 'has-ellipsis': item.value.length > 20 },
                    { 'delete-line': item.hidden_values?.includes(child) },
                  ]"
                  @click.stop="() => handlePopoverShow(index, childIndex)"
                >
                  {{ formatDateTimeField(child, item.field_type) }}
                </span>
                <div slot="content">
                  <div
                    class="match-value-select"
                    @click="changeOptionShow(item, child, index, childIndex)"
                  >
                    {{ getItemActionShowText(item, child) }}
                  </div>
                  <div
                    class="match-value-select"
                    @click="onlyOptionShow(item, child, index, childIndex)"
                  >
                    只看这个选项
                  </div>
                </div>
              </bk-popover>
              <span
                v-if="
                  childIndex < item.value.length - 1 &&
                  (childIndex < 2 || item.showAll)
                "
                class="match-value-relation"
              >
                {{ item.relation }}
              </span>
            </template>
          </span>
          <bk-popover
            :ref="(el) => setMorePopoverRef(el, index)"
            placement="bottom"
            theme="light"
            trigger="click"
          >
            <span
              v-if="item.value.length > 3 && !item.showAll"
              style="color: #f59500"
              @click.stop="moreOption(index)"
              class="match-value-more"
            >
              +{{ item.value.length - 3 }}
            </span>
            <div slot="content">
              <div class="match-value-content">
                <bk-popover
                  v-for="(child, childIndex) in item.value.slice(3)"
                  :ref="(el) => setPopoverRef(el, index, childIndex + 3)"
                  :key="childIndex"
                  placement="right"
                  theme="light"
                  trigger="click"
                  extCls="match-value-popover"
                >
                  <div
                    class="match-value-child"
                    :class="[
                      { 'delete-line': item.hidden_values?.includes(child) },
                    ]"
                  >
                    {{ child }}
                  </div>
                  <div slot="content">
                    <div
                      class="match-value-select"
                      @click="changeOptionShow(item, child, index, childIndex)"
                    >
                      {{ getItemActionShowText(item, child) }}
                    </div>
                    <div
                      class="match-value-select"
                      @click="onlyOptionShow(item, child, index, childIndex)"
                    >
                      只看这个选项
                    </div>
                  </div>
                </bk-popover>
              </div>
            </div>
          </bk-popover>
        </template>
        <template v-else>
          <span>{{ item.value }}</span>
        </template>
      </div>
      <div class="tag-options">
        <span
          :class="[
            'bklog-icon',
            {
              'bklog-eye': !item.disabled,
              disabled: item.disabled,
              'bklog-eye-slash': item.disabled,
            },
          ]"
          @click.stop="handleDisabledTagItem(item)"
        />
        <span
          class="bklog-icon bklog-shanchu tag-options-close"
          @click.stop="handleDeleteTagItem(index, item)"
        />
      </div>
    </li>
    <li ref="refHiddenFocus" class="search-item-focus hidden-pointer"></li>
    <li class="search-item is-focus-input" :data-attr-txt="inputPlaceholder">
      <input
        ref="refSearchInput"
        class="tag-option-focus-input"
        type="text"
        @blur.stop="handleFullTextInputBlur"
        @click.stop="handleInputTextClick"
        @input="handleInputValueChange"
        @keyup.delete="handleDeleteItem"
        @keyup.enter.stop="handleInputValueEnter"
      />
    </li>
    <div style="display: none">
      <UiInputOptions
        ref="refPopInstance"
        :is-input-focus="isInputTextFocus"
        :value="queryItem"
        @cancel="handleCancelClick"
        @save="handleGlobalSaveQueryClick"
        @batch-input-change="handleBatchInputChange"
      ></UiInputOptions>
    </div>
  </ul>
</template>
<style lang="scss">
@import "./ui-input.scss";
@import "tippy.js/dist/tippy.css";
</style>
<style lang="scss">
[data-tippy-root] .tippy-box {
  &[data-theme="log-light"] {
    color: #4d4f56;
    background-color: #ffffff;
    border-radius: 2px;
    box-shadow: 0 2px 15px 0 rgba(0, 0, 0, 0.16);
    transform: translateY(-2px);

    .tippy-content {
      padding: 0;
    }

    .tippy-arrow {
      color: #fff;

      &::after {
        background-color: #fff;
        box-shadow: 0 2px 6px 0 #0000001a;
      }

      &::before {
        top: -9px;
      }
    }

    .ui-query-options {
      border-radius: 2px;

      .ui-query-option-footer {
        border-radius: 0 0 2px 2px;
      }
    }
  }

  &[data-theme="log-dark"] {
    color: #fff;
    background-color: #4d4f56;
    border-radius: 2px;
    box-shadow: 0 2px 6px 0 #fff;
    transform: translateY(-2px);

    .tippy-content {
      padding: 4px 8px;
    }

    .tippy-arrow {
      color: #4d4f56;

      &::after {
        background-color: #4d4f56;
        box-shadow: 0 2px 6px 0 #fff;
      }

      &::before {
        top: -9px;
      }
    }
  }
}

.bk-tooltip-content {
  .match-value-select {
    display: flex;
    align-items: center;
    font-size: 12px;
    line-height: 32px;
    cursor: pointer;
    background-color: #fff;
  }

  .delete-line {
    color: #979ba5;
    text-decoration: line-through;
  }
}

.match-value-content {
  display: flex;
  flex-direction: column;

  .bk-tooltip-ref {
    width: 100%;
    cursor: pointer;
  }

  .match-value-child {
    font-size: 12px;
    line-height: 32px;
  }
}

.match-value-popover {
  // eslint-disable-next-line
  left: 15px;
}
</style>
