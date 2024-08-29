<script setup>
  import { ref, watch } from 'vue';
  import tippy from 'tippy.js';
  import UiInputOptions from './ui-input-option.vue';

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
        content: refPopInstance.value.firstChild.cloneNode(true),
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

  watch(
    props.value,
    val => {
      modelValue.value = val;
    },
    { deep: true, immediate: true },
  );

  const emitChange = value => {
    emit('input', value);
    emit('change', value);
  };

  const handleAddItem = e => {
    // const index = Math.ceil(Math.random() * 10);
    // modelValue.value.push({ fieldName: `log-${index}`, fieldValue: 'natural Home', disabled: false });
    // emitChange(modelValue.value);
    const target = e.target.closest('.search-item');
    showTagListItems(target);
  };

  const handleDisabledTagItem = item => {
    item.disabled = !item.disabled;
  };

  const handleDeleteTagItem = index => {
    modelValue.value.splice(index, 1);
    emitChange(modelValue.value);
  };
</script>
<template>
  <ul class="search-items">
    <li
      class="search-item btn-add"
      @click.stop="handleAddItem"
    >
      <div class="tag-add"><i class="bklog-icon bklog-plus"></i></div>
      <div class="tag-text">{{ $t('添加条件') }}</div>
    </li>
    <li
      :class="['search-item tag-item', { disabled: item.disabled }]"
      v-for="(item, index) in modelValue"
    >
      <div class="tag-row match-name">{{ item.fieldName }}<span class="symbol">=</span></div>
      <div class="tag-row match-value">{{ item.fieldValue }}</div>
      <div class="tag-options">
        <span
          :class="['bklog-icon', { 'bklog-eye': !item.disabled, 'bklog-eye-slash': item.disabled }]"
          @click="() => handleDisabledTagItem(item)"
        ></span>
        <span
          class="bk-icon icon-close"
          @click="() => handleDeleteTagItem(index)"
        ></span>
      </div>
    </li>
    <div
      ref="refPopInstance"
      style="display: none"
    >
      <UiInputOptions></UiInputOptions>
    </div>
  </ul>
</template>
<style scoped>
  @import './ui-input.scss';
  @import 'tippy.js/dist/tippy.css';
</style>
<style>
  [data-theme='log-light'] {
    background-color: #fff;
    color: #63656e;
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
