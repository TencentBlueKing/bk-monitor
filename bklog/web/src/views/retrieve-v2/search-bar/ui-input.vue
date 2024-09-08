<script setup>
  import { ref, computed } from 'vue';

  import { getOperatorKey } from '@/common/util';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import UiInputOptions from './ui-input-option.vue';
  import useFocusInput from './use-focus-input';

  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  /**
   * 格式化搜索标签渲染格式
   * @param {*} item
   */
  const formatModelValueItem = item => {
    const key = getOperatorKey(item.operator);
    const label = operatorDictionary.value[key]?.label ?? key;
    return { ...item, operator_label: label, disabled: false };
  };

  const emit = defineEmits(['input', 'change', 'height-change']);
  const store = useStore();
  const { $t } = useLocale();

  const handleHeightChange = height => {
    emit('height-change', height);
  }

  const operatorDictionary = computed(() => {
    const defVal = {
      [getOperatorKey('containes')]: { label: $t('包含'), operator: 'contains' },
    };
    return {
      ...defVal,
      ...store.state.operatorDictionary,
    };
  });

  const refPopInstance = ref(null);
  const refUlRoot = ref(null);
  const queryItem = ref('');
  const activeIndex = ref(null);
  const isInputFocus = ref(false);
  const isOptionShowing = ref(false);
  let delayItemClickFn = undefined;

  const { modelValue, inputValue, hideTippyInstance, getTippyInstance, handleContainerClick, handleInputBlur, delayShowInstance } =
    useFocusInput(props, {
      onHeightChange: handleHeightChange,
      formatModelValueItem,
      refContent: refPopInstance,
      onShowFn: () => {
        isOptionShowing.value = true;
        refPopInstance.value?.beforeShowndFn?.();
      },
      onHiddenFn: () => {
        refPopInstance.value?.afterHideFn?.();
        isOptionShowing.value = false;

        delayItemClickFn?.();
        delayItemClickFn = undefined;
      },
    });

  /**
   * 执行点击弹出操作项方法
   * @param {*} target 目标元素
   */
  const showTagListItems = target => {
    // 如果当前实例是弹出状态
    // 本次弹出操作需要在当前弹出实例收起之后再执行
    // delayItemClickFn 函数会在实例 onHidden 之后执行
    if (isOptionShowing.value) {
      delayItemClickFn = () => {
        delayShowInstance(target);
      };
      return;
    }

    delayShowInstance(target);
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
    queryItem.value = {};
    isInputFocus.value = false;
    Object.assign(queryItem.value, item);
    const target = e.target.closest('.search-item');
    activeIndex.value = isInputFocus.value ? -1 : index;
    showTagListItems(target);
  };

  const handleDisabledTagItem = item => {
    item.disabled = !item.disabled;
    emitChange(modelValue.value);
  };

  const handleDeleteTagItem = index => {
    modelValue.value.splice(index, 1);
    emitChange(modelValue.value);
  };

  const handleSaveQueryClick = payload => {
    const isPayloadValueEmpty = !(payload?.value?.length ?? 0);

    // 如果是全文检索，未输入任何内容就点击回车
    // 此时提交无任何意义，禁止后续逻辑
    if (isInputFocus.value && isPayloadValueEmpty && !inputValue.value) {
      return;
    }

    let targetValue = formatModelValueItem(
      isInputFocus.value && isPayloadValueEmpty
        ? {
            field: '',
            operator: 'contains',
            isInclude: true,
            value: [inputValue.value],
            relation: 'AND',
            disabled: false,
          }
        : payload,
    );

    getTippyInstance()?.hide();

    if (isInputFocus.value) {
      setTimeout(() => {
        handleContainerClick({ target: refUlRoot.value });
      }, 300);
    }

    if (activeIndex.value !== null && activeIndex.value >= 0) {
      Object.assign(modelValue.value[activeIndex.value], targetValue);
      emit('input', modelValue.value);
      return;
    }

    const focusInputIndex = modelValue.value.findIndex(item => item.is_focus_input);
    if (focusInputIndex === modelValue.value.length - 1) {
      modelValue.value.splice(focusInputIndex, 0, { ...targetValue, disabled: false });
      emit('input', modelValue.value);
      return;
    }

    modelValue.value.push({ ...targetValue, disabled: false });
    emit('input', modelValue.value);
  };

  const handleFullTextInputBlur = e => {
    inputValue.value = '';
    handleInputBlur(e);
  };

  const handleCancelClick = () => {
    getTippyInstance()?.hide();
  };

  const handleFocusInput = e => {
    isInputFocus.value = true;
    activeIndex.value = -1;
    queryItem.value = {};
    const target = e.target.closest('.search-item');
    showTagListItems(target);
  };

  const handleDeleteItem = e => {
    if (!e.target.value) {
      if(modelValue.value.length > 1) {
        modelValue.value.splice(-2, 1);
        hideTippyInstance();
        setTimeout(() => {
          handleContainerClick();
        }, 300);
      }
    }
  }
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
      <div class="tag-add"><i class="bklog-icon bklog-plus"></i></div>
      <div class="tag-text">{{ $t('添加条件') }}</div>
    </li>
    <li
      v-for="(item, index) in modelValue"
      :class="[
        'search-item',
        { disabled: item.disabled, 'is-focus-input': item.is_focus_input, 'tag-item': !item.is_focus_input },
      ]"
      :key="`${item.field}-${index}`"
      @click.stop="e => handleTagItemClick(e, item, index)"
    >
      <template v-if="!item.is_focus_input">
        <div class="tag-row match-name">
          {{ item.field !== '' ? item.field : $t('全文') }}
          <span
            class="symbol"
            :data-operator="item.operator"
            >{{ item.operator_label }}</span
          >
        </div>
        <div class="tag-row match-value">
          <span
            v-for="(child, childInex) in item.value"
            :key="childInex"
          >
            <span>{{ child }}</span>
            <span
              v-if="childInex < item.value.length - 1"
              class="match-value-relation"
              >{{ item.relation }}</span
            >
          </span>
        </div>
        <div class="tag-options">
          <span
            :class="['bklog-icon', { 'bklog-eye': !item.disabled, 'bklog-eye-slash': item.disabled }]"
            @click.stop="() => handleDisabledTagItem(item)"
          ></span>
          <span
            class="bk-icon icon-close"
            @click.stop="() => handleDeleteTagItem(index)"
          ></span>
        </div>
      </template>
      <template v-else>
        <input
          class="tag-option-focus-input"
          v-model="inputValue"
          type="text"
          @keyup.delete="handleDeleteItem"
          @focus.stop="handleFocusInput"
          @blur="handleFullTextInputBlur"
        />
      </template>
    </li>
    <div style="display: none">
      <UiInputOptions
        ref="refPopInstance"
        :is-input-focus="isInputFocus"
        :value="queryItem"
        @cancel="handleCancelClick"
        @save="handleSaveQueryClick"
      ></UiInputOptions>
    </div>
  </ul>
</template>
<style scoped>
  @import './ui-input.scss';
  @import 'tippy.js/dist/tippy.css';
</style>
<style>
  [data-theme='log-light'] {
    color: #63656e;
    background-color: #fff;
    box-shadow: 0 2px 6px 0 #0000001a;

    .tippy-content {
      padding: 0;
    }

    .tippy-arrow {
      color: #fff;

      &::after {
        background-color: #fff;
        box-shadow: 0 2px 6px 0 #0000001a;
      }
    }
  }
</style>
