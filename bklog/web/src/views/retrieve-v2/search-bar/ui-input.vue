<script setup>
  import { ref, watch, computed, onBeforeUnmount } from 'vue';

  import { debounce } from 'lodash';
  import { getOperatorKey, getCharLength } from '@/common/util';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import tippy from 'tippy.js';

  import UiInputOptions from './ui-input-option.vue';

  const INPUT_MIN_WIDTH = 12;

  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  const emit = defineEmits(['input', 'change']);
  const store = useStore();
  const { $t } = useLocale();

  const operatorDictionary = computed(() => {
    const defVal = {
      [getOperatorKey('containes')]: { label: $t('包含'), operator: 'contains' },
    };
    return {
      ...defVal,
      ...store.state.operatorDictionary,
    };
  });

  let tippyInstance = null;
  const modelValue = ref([]);
  const refPopInstance = ref(null);
  const refUlRoot = ref(null);
  const queryItem = ref('');
  const fullTextValue = ref('');
  const activeIndex = ref(null);
  const isInputFocus = ref(false);
  const isOptionShowing = ref(false);

  const uninstallInstance = () => {
    if (tippyInstance) {
      tippyInstance.hide();
      tippyInstance.unmount();
      tippyInstance.destroy();
      tippyInstance = null;
    }
  };

  const handleContainerClick = e => {
    const input = e.target?.querySelector('.tag-option-focus-input');
    input?.focus();
    input?.style.setProperty('width', `${1 * INPUT_MIN_WIDTH}px`);
    return input;
  };

  let delayItemClickFn = undefined;

  const initInistance = target => {
    uninstallInstance();
    if (tippyInstance === null) {
      tippyInstance = tippy(target, {
        content: refPopInstance.value.$el,
        trigger: 'manual',
        theme: 'log-light',
        placement: 'bottom-start',
        interactive: true,
        maxWidth: 800,
        onShow: () => {
          isOptionShowing.value = true;
          refPopInstance.value?.beforeShowndFn?.();
        },
        onHidden: () => {
          refPopInstance.value?.afterHideFn?.();
          isOptionShowing.value = false;
          isInputFocus.value = false;

          delayItemClickFn?.();
          setTimeout(() => {
            delayItemClickFn = undefined;
          });
        },
      });
    }
  };


  /**
   * 处理多次点击触发多次请求的事件
   */
  const delayShowInstance = debounce((target) => {
    initInistance(target);
    tippyInstance.show();
  })

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

  /**
   * 点击操作设置输入框位置
   * @param {*} index
   */
  const setFocusInputItem = (index = -1) => {
    const oldIndex = modelValue.value.findIndex(item => item?.is_focus_input);
    if (oldIndex === -1) {
      modelValue.value.push({ is_focus_input: true });
      return;
    }

    if (index >= 0) {
      if (oldIndex > index) {
        modelValue.value.splice(oldIndex, 1);
        modelValue.value.splice(index, 0, { is_focus_input: true });
      } else {
        modelValue.value.splice(index, 0, { is_focus_input: true });
        modelValue.value.splice(oldIndex, 1);
      }
    }
  };

  /**
   * 格式化搜索标签渲染格式
   * @param {*} item
   */
  const formatModelValueItem = item => {
    const key = getOperatorKey(item.operator);
    const label = operatorDictionary.value[key]?.label ?? key;
    return { ...item, operator_label: label, disabled: false };
  };

  const setModelValue = val => {
    modelValue.value = (val ?? []).map(formatModelValueItem);
  };

  watch(
    props.value,
    val => {
      setModelValue(val);
      setFocusInputItem();
    },
    { deep: true, immediate: true },
  );

  const emitChange = value => {
    emit('input', value);
    emit('change', value);
  };

  const handleAddItem = e => {
    const target = e.target.closest('.search-item');
    queryItem.value = '';
    activeIndex.value = null;
    showTagListItems(target);
  };

  const handleTagItemClick = (e, item, index) => {
    queryItem.value = {};
    Object.assign(queryItem.value, item);
    const target = e.target.closest('.search-item');
    activeIndex.value = isInputFocus.value ? -1 : index;
    showTagListItems(target);
  };

  const handleDisabledTagItem = item => {
    item.disabled = !item.disabled;
  };

  const handleDeleteTagItem = index => {
    modelValue.value.splice(index, 1);
    emitChange(modelValue.value);
  };

  const handleSaveQueryClick = paylod => {
    let targetValue = formatModelValueItem(
      isInputFocus.value && paylod === undefined
        ? {
            field: '',
            operator: 'contains',
            isInclude: true,
            value: [fullTextValue.value],
            relation: 'AND',
            disabled: false,
          }
        : paylod,
    );

    if (isInputFocus.value) {
      setTimeout(() => {
        const input = handleContainerClick({ target: refUlRoot.value });
        showTagListItems(input.parentNode);
      }, 300);
    }

    tippyInstance?.hide();

    if (activeIndex.value !== null && activeIndex.value >= 0) {
      Object.assign(modelValue.value[activeIndex.value], targetValue);
      emitChange(modelValue.value);
      return;
    }

    const focusInputIndex = modelValue.value.findIndex(item => item.is_focus_input);
    if (focusInputIndex === modelValue.value.length - 1) {
      modelValue.value.splice(focusInputIndex, 0, { ...targetValue, disabled: false });
      emitChange(modelValue.value);
      return;
    }

    modelValue.value.push({ ...targetValue, disabled: false });
    emitChange(modelValue.value);
  };

  const handleCancelClick = () => {
    tippyInstance.hide();
  };

  const handleFulltextInput = e => {
    const value = e.target.value;
    const charLen = getCharLength(value);
    e.target.style.setProperty('width', `${charLen * INPUT_MIN_WIDTH}px`);
  };

  const handleFullTextInputBlur = e => {
    fullTextValue.value = '';
    e.target?.style.setProperty('width', `${1 * INPUT_MIN_WIDTH}px`);
  };

  const handleFocusInput = e => {
    isInputFocus.value = true;
    activeIndex.value = -1;
    e.target.parentNode?.click();
  };

  onBeforeUnmount(() => {
    uninstallInstance();
  });
</script>

<template>
  <ul
    class="search-items"
    @click.stop="handleContainerClick"
    ref="refUlRoot"
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
          v-model="fullTextValue"
          type="text"
          @blur="handleFullTextInputBlur"
          @focus.stop="handleFocusInput"
          @input="handleFulltextInput"
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
