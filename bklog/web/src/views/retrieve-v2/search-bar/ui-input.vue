<script setup>
  import { ref, watch, nextTick } from 'vue';
  import tippy from 'tippy.js';
  import UiInputOptions from './ui-input-option.vue';
  import useStore from '@/hooks/use-store';

  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  const emit = defineEmits(['input', 'change']);

  let tippyInstance = null;
  const modelValue = ref([]);
  const refPopInstance = ref(null);
  const queryItem = ref('xxxx');
  const fullTextValue = ref('');
  const activeIndex = ref(null);

  const uninstallInstance = () => {
    if (tippyInstance) {
      tippyInstance.hide();
      tippyInstance.unmount();
      tippyInstance = null;
    }
  };

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
      });
    }
  };

  const showTagListItems = target => {
    initInistance(target);
    tippyInstance.show();
  };

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

  watch(
    props.value,
    val => {
      modelValue.value = val;
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
    queryItem.value = '89898998';
    showTagListItems(target);
    activeIndex.value = null;
  };

  const handleTagItemClick = (e, item, index) => {
    queryItem.value = {};
    Object.assign(queryItem.value, item);
    const target = e.target.closest('.search-item');
    showTagListItems(target);
    activeIndex.value = index;
  };

  const handleDisabledTagItem = item => {
    item.disabled = !item.disabled;
  };

  const handleDeleteTagItem = index => {
    modelValue.value.splice(index, 1);
    emitChange(modelValue.value);
  };

  const handleSaveQueryClick = paylod => {
    tippyInstance.hide();
    if (activeIndex.value!== null && activeIndex.value >= 0) {
      Object.assign(modelValue.value[activeIndex.value], paylod);
      return;
    }

    const focusInputIndex = modelValue.value.findIndex(item => item.is_focus_input);
    if (focusInputIndex === modelValue.value.length - 1) {
      modelValue.value.splice(focusInputIndex - 1, 0, { ...paylod, disabled: false });
      return;
    }
    modelValue.value.push({ ...paylod, disabled: false });
  };

  const handleCancelClick = () => {
    tippyInstance.hide();
  };

  const handleContainerClick = e => {
    const input = e.target?.querySelector('.tag-option-focus-input');
    nextTick(() => {
      input?.focus();
    });
  };
</script>
<template>
  <ul
    class="search-items"
    @click.stop="handleContainerClick"
  >
    <li
      class="search-item btn-add"
      @click.stop="handleAddItem"
    >
      <div class="tag-add"><i class="bklog-icon bklog-plus"></i></div>
      <div class="tag-text">{{ $t('添加条件') }}</div>
    </li>
    <li
      :class="[
        'search-item',
        { disabled: item.disabled, 'is-focus-input': item.is_focus_input, 'tag-item': !item.is_focus_input },
      ]"
      v-for="(item, index) in modelValue"
      @click.stop="e => handleTagItemClick(e, item, index)"
    >
      <template v-if="!item.is_focus_input">
        <div class="tag-row match-name">
          {{ item.field }}<span class="symbol">{{ item.operator }}</span>
        </div>
        <div class="tag-row match-value">
          <span v-for="(child, childInex) in item.value" :key="childInex">
            <span>{{ child }}</span>
            <span v-if="childInex < item.value.length - 1">{{ item.relation }}</span>
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
          type="text"
          class="tag-option-focus-input"
          v-model="fullTextValue"
        />
      </template>
    </li>
    <div style="display: none">
      <UiInputOptions
        ref="refPopInstance"
        @save="handleSaveQueryClick"
        @cancel="handleCancelClick"
        :value="queryItem"
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
