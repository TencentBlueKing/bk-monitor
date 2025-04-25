<script setup>
  import { ref, computed, set } from 'vue';

  import { getOperatorKey, formatDateTimeField, getOsCommandLabel } from '@/common/util';
  import useFieldNameHook from '@/hooks/use-field-name';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { cloneDeep } from 'lodash';

  import {
    getInputQueryDefaultItem,
    getInputQueryIpSelectItem,
    FulltextOperatorKey,
    FulltextOperator,
  } from './const.common';
  import { operatorMapping, translateKeys } from './const-values';
  import IPSelector from './ip-selector';
  import UiInputOptions from './ui-input-option.vue';
  import useFocusInput from './use-focus-input';
  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  const emit = defineEmits(['input', 'change', 'height-change', 'popup-change']);
  const store = useStore();
  const { $t } = useLocale();

  const inputValueLength = ref(0);
  // 动态设置placeHolder
  const inputPlaceholder = computed(() => {
    if (inputValueLength.value === 0) {
      return `${$t('快捷键')} /，${$t('请输入')}...`;
    }

    return '';
  });

  const bkBizId = computed(() => store.state.bkBizId);

  /**
   * 格式化搜索标签渲染格式
   * @param {*} item
   */
  const formatModelValueItem = item => {
    if (typeof item?.value === 'string') {
      item.value = item.value.split(',');
    }
    item.showAll = item?.value?.length < 3;
    if (!item?.relation) item.relation = 'OR';
    return { disabled: false, ...(item ?? {}) };
  };

  /**
   * tag数量溢出是否展示所有
   * @param {*} item
   */
  const handleShowAll = item => {
    item.showAll = !item.showAll;
  };

  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const operatorDictionary = computed(() => {
    const defVal = {
      [getOperatorKey(FulltextOperatorKey)]: { label: $t('包含'), operator: FulltextOperator },
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
  const getOperatorLabel = item => {
    if (item.field === '_ip-select_') {
      return '';
    }

    const key = item.field === '*' ? getOperatorKey(`*${item.operator}`) : getOperatorKey(item.operator);
    if (translateKeys.includes(operatorMapping[item.operator])) {
      return $t(operatorMapping[item.operator] ?? item.operator);
    }

    return operatorMapping[item.operator] ?? operatorDictionary.value[key]?.label ?? item.operator;
  };

  const refPopInstance = ref(null);
  const refUlRoot = ref(null);
  const refSearchInput = ref(null);
  const refHiddenFocus = ref(null);
  const queryItem = ref('');
  const activeIndex = ref(null);

  // 表示是否来自input输入的点击弹出
  // 弹出组件依赖此属性展示内容会改变
  const isInputFocus = ref(false);
  const showIpSelector = ref(false);

  // // 表示是否聚焦input输入框，如果聚焦在 input输入框，再次点击弹出内容不会重复渲染
  // let isInputTextFocus = false;

  const getSearchInputValue = () => {
    return refSearchInput.value?.value ?? '';
  };

  const setSearchInputValue = val => {
    refSearchInput.value.value = val ?? '';
    inputValueLength.value = refSearchInput.value?.value?.length ?? 0;
  };

  const handleWrapperClickCapture = (e, { getTippyInstance }) => {
    const instance = getTippyInstance();
    const reference = instance?.reference;

    const target = refSearchInput.value?.closest('.search-item');
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

  // 是否为自动foucus到input
  // 自动focus不用弹出选择提示
  const isAutoFocus = ref(false);
  const { getFieldName } = useFieldNameHook({ store });
  const {
    modelValue,
    isDocumentMousedown,
    isInputTextFocus,
    setIsInputTextFocus,
    setIsDocumentMousedown,
    getTippyInstance,
    isInstanceShown,
    delayShowInstance,
    repositionTippyInstance,
    hideTippyInstance,
  } = useFocusInput(props, {
    refContent: refPopInstance,
    refTarget: refHiddenFocus,
    refWrapper: refUlRoot,
    onHeightChange: handleHeightChange,
    formatModelValueItem,
    onShowFn: instance => {
      setIsDocumentMousedown(true);
      const isTagItemClick =
        instance.reference.classList.contains('search-item') && instance.reference.classList.contains('tag-item');
      if (!isTagItemClick) {
        refSearchInput.value?.focus?.();
      }

      refPopInstance.value?.beforeShowndFn?.();
      isInputFocus.value =
        instance?.reference?.contains(refSearchInput.value) || instance?.reference === refHiddenFocus.value;
      emit('popup-change', { isShow: true });
    },
    onHiddenFn: () => {
      emit('popup-change', { isShow: false });

      if (isDocumentMousedown.value || isInputTextFocus.value) {
        setIsDocumentMousedown(false);
        // 这里blur事件触发会比出发clickoutside收起弹出晚
        // 所以在收起时，需要一个延迟检测
        if (isInputTextFocus.value) {
          requestAnimationFrame(() => {
            if (!isInputTextFocus.value) {
              hideTippyInstance();
            }
          });

          return false;
        }
        return true;
      }

      refPopInstance.value?.afterHideFn?.();
      if (refSearchInput.value) {
        isAutoFocus.value = true;
        refSearchInput.value?.focus();
        setTimeout(() => {
          isAutoFocus.value = false;
        });
      }

      return true;
    },
    handleWrapperClick: handleWrapperClickCapture,
  });

  const debounceShowInstance = () => {
    const target = refSearchInput.value?.closest('.search-item');
    if (target) {
      delayShowInstance(target);
    }
  };

  const closeTippyInstance = () => {
    setIsDocumentMousedown(false);
    getTippyInstance()?.hide();
  };

  /**
   * 执行点击弹出操作项方法
   * @param {*} target 目标元素
   */
  const showTagListItems = target => {
    if (isInstanceShown()) {
      repositionTippyInstance();
      return;
    }

    delayShowInstance(target);
  };

  const getMatchName = field => {
    if (field === '*') return $t('全文');
    if (field === '_ip-select_') return $t('IP目标');

    return getFieldName(field);
  };

  const emitChange = value => {
    emit('input', value);
    emit('change', value);
  };

  const handleAddItem = e => {
    isInputFocus.value = false;
    const target = e.target.closest('.search-item');
    queryItem.value = '';
    activeIndex.value = null;
    showTagListItems(target);
  };

  const handleTagItemClick = (e, item, index) => {
    if (item.field === '_ip-select_') {
      showIpSelector.value = true;
      return;
    }
    const { changeFieldName } = useFieldNameHook({ store });
    const itemCopy = cloneDeep(item);
    itemCopy.field = changeFieldName(itemCopy.field);
    queryItem.value = {};
    isInputFocus.value = false;
    if (!Array.isArray(item.value)) item.value = item.value.split(',');
    if (!item.relation) item.relation = 'OR';
    Object.assign(queryItem.value, itemCopy);
    const target = e.target.closest('.search-item');
    activeIndex.value = isInputFocus.value ? null : index;
    showTagListItems(target);
  };

  const handleDisabledTagItem = item => {
    set(item, 'disabled', !item.disabled);
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
  const handleSaveQueryClick = payload => {
    if (payload === 'ip-select-show') {
      const copyValue = getInputQueryIpSelectItem();
      if (!modelValue.value.some(f => f.field === copyValue.field)) {
        modelValue.value.push({ ...copyValue, disabled: false });
      }

      closeTippyInstance();
      setTimeout(() => {
        showIpSelector.value = true;
      }, 100);
      return;
    }

    const isPayloadValueEmpty = !(payload?.value?.length ?? 0);
    const isFulltextEnterVlaue = isInputFocus.value && isPayloadValueEmpty && !payload?.field;

    const inputVal = getSearchInputValue();
    // 如果是全文检索，未输入任何内容就点击回车
    // 此时提交无任何意义，禁止后续逻辑
    if (isFulltextEnterVlaue && !inputVal.length) {
      return;
    }

    let targetValue = formatModelValueItem(isFulltextEnterVlaue ? getInputQueryDefaultItem(inputVal) : payload);

    if (isInputFocus.value) {
      setSearchInputValue('');
    }

    if (activeIndex.value !== null && activeIndex.value >= 0) {
      Object.assign(modelValue.value[activeIndex.value], targetValue);
      emitChange(modelValue.value);
      closeTippyInstance();
      return;
    }

    modelValue.value.push({ ...targetValue, disabled: false });
    emitChange(modelValue.value);
    closeTippyInstance();
  };

  // 用于判定当前 key.enter 是全局绑定触发还是 input.key.enter触发
  const isGlobalKeyEnter = ref(false);
  const handleGlobalSaveQueryClick = payload => {
    blurTimer && clearTimeout(blurTimer);

    isGlobalKeyEnter.value = true;
    handleSaveQueryClick(payload);
    repositionTippyInstance();
    refSearchInput.value.style.setProperty('width', '12px');
    nextInputBlur?.();
    nextInputBlur = null;
  };

  /**
   * input key enter
   * @param e
   */
  const handleInputValueEnter = e => {
    if (!isGlobalKeyEnter.value) {
      handleSaveQueryClick(undefined);
      repositionTippyInstance();
      e.target.style.setProperty('width', '12px');
    }

    isGlobalKeyEnter.value = false;
  };

  const handleCancelClick = () => {
    closeTippyInstance();
    setSearchInputValue('');
  };

  const handleInputTextClick = () => {
    if (isInstanceShown() || isInputTextFocus.value || isAutoFocus.value) {
      return;
    }

    debounceShowInstance();
  };

  const handleFocusInput = () => {
    if (isInstanceShown()) {
      return;
    }

    setIsInputTextFocus(true);
    isInputFocus.value = true;
    activeIndex.value = null;
    queryItem.value = '';

    if (isAutoFocus.value) {
      return;
    }

    debounceShowInstance();
  };

  let blurTimer = null;
  let nextInputBlur = null;

  const handleFullTextInputBlur = e => {
    nextInputBlur = () => {
      setIsInputTextFocus(false);
      inputValueLength.value = 0;
      e.target.style.setProperty('width', '12px');
      e.target.value = '';
      queryItem.value = '';
    };

    blurTimer = setTimeout(() => {
      nextInputBlur();
      nextInputBlur = null;
    }, 300);
  };

  const handleInputValueChange = e => {
    if (inputValueLength.value === 0 && e.target.value.length > 0) {
      inputValueLength.value = e.target.value.length;
      debounceShowInstance();
    }

    queryItem.value = e.target.value;
  };

  // 键盘删除键
  const needDeleteItem = ref(false);
  const handleDeleteItem = e => {
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
</script>

<template>
  <ul
    ref="refUlRoot"
    class="search-items"
  >
    <li
      class="search-item btn-add"
      @click.stop="handleAddItem"
    >
      <div class="tag-add">+</div>
      <div class="tag-text">{{ $t('添加条件') }}</div>
    </li>
    <li
      v-for="(item, index) in modelValue"
      :class="['search-item', 'tag-item', { disabled: item.disabled, 'is-common-fixed': item.isCommonFixed }]"
      :key="`${item.field}-${index}`"
      @click.stop="e => handleTagItemClick(e, item, index)"
    >
      <div class="tag-row match-name">
        <span class="match-name-label">{{ getMatchName(item.field) }}</span>
        <span
          class="symbol"
          :data-operator="item.operator"
          >{{ getOperatorLabel(item) }}</span
        >
      </div>
      <div class="tag-row match-value">
        <template v-if="item.field === '_ip-select_'">
          <span :class="['match-value-text', { 'is-show-tooltip': item.value.length > 20 }]">
            <IPSelector
              v-model="item.value[0]"
              :bk-biz-id="bkBizId"
              :is-show.sync="showIpSelector"
              @change="handleIPChange"
            ></IPSelector>
          </span>
        </template>
        <template v-else-if="Array.isArray(item.value)">
          <span
            v-for="(child, childIndex) in item.value"
            :key="childIndex"
          >
            <template v-if="item.showAll ? true : childIndex < 3">
              <span
                v-bk-tooltips="{ content: item.value, disabled: item.value.length < 21 }"
                :class="['match-value-text', { 'has-ellipsis': item.value.length > 20 }]"
              >
                {{ formatDateTimeField(child, item.field_type) }}
              </span>
              <span
                v-if="childIndex < item.value.length - 1 && (childIndex < 2 || item.showAll)"
                class="match-value-relation"
              >
                {{ item.relation }}
              </span>
            </template>
          </span>
          <span
            v-if="item.value.length > 3 && !item.showAll"
            style="color: #f59500"
          >
            +{{ item.value.length - 3 }}
          </span>
        </template>
        <template v-else>
          <span>{{ item.value }}</span>
        </template>
      </div>
      <div class="tag-options">
        <span
          :class="[
            'bklog-icon',
            { 'bklog-eye': !item.disabled, disabled: item.disabled, 'bklog-eye-slash': item.disabled },
          ]"
          @click.stop="e => handleDisabledTagItem(item, e)"
        />
        <span
          class="bklog-icon bklog-shanchu tag-options-close"
          @click.stop="handleDeleteTagItem(index, item)"
        />
      </div>
    </li>
    <li
      ref="refHiddenFocus"
      class="search-item-focus hidden-pointer"
    ></li>
    <li
      class="search-item is-focus-input"
      :data-attr-txt="inputPlaceholder"
    >
      <input
        ref="refSearchInput"
        class="tag-option-focus-input"
        type="text"
        @blur.stop="handleFullTextInputBlur"
        @click.stop="handleInputTextClick"
        @focus.stop="handleFocusInput"
        @input="handleInputValueChange"
        @keyup.delete="handleDeleteItem"
        @keyup.enter.stop="handleInputValueEnter"
      />
    </li>
    <div style="display: none">
      <UiInputOptions
        ref="refPopInstance"
        :is-input-focus="isInputFocus"
        :value="queryItem"
        @cancel="handleCancelClick"
        @save="handleGlobalSaveQueryClick"
      ></UiInputOptions>
    </div>
  </ul>
</template>
<style lang="scss">
  @import './ui-input.scss';
  @import 'tippy.js/dist/tippy.css';
</style>
<style lang="scss">
  [data-tippy-root] .tippy-box {
    &[data-theme='log-light'] {
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

    &[data-theme='log-dark'] {
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
</style>
