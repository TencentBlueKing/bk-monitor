<script setup>
  import { ref, nextTick, getCurrentInstance } from 'vue';
  import useFocusInput from './use-focus-input';
  import SqlQueryOptions from './sql-query-options';

  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  const refSqlQueryOption = ref(null);
  const isInputFocus = ref(false);
  const refUlRoot = ref(null);

  const formatModelValueItem = item => {
    return item;
  };
  const { modelValue, inputValue, handleInputBlur, delayShowInstance, getTippyInstance } = useFocusInput(props, {
    formatModelValueItem,
    refContent: refSqlQueryOption,
    arrow: false,
    onShowFn: () => {
      refSqlQueryOption.value?.beforeShowndFn?.();
    },
    onHiddenFn: () => {
      refSqlQueryOption.value?.beforeHideFn?.();
    },
  });

  const handleTextInputBlur = e => {
    isInputFocus.value = false;
    inputValue.value = '';
    handleInputBlur(e);
    getTippyInstance()?.hide();
  };

  const handleFocusInput = e => {
    isInputFocus.value = true;
    nextTick(() => {
      delayShowInstance(refUlRoot.value);
    });
  };

  const handleQueryChange = value => {
    console.log('handleQueryChange', value)
    modelValue.value.push(value);
  }
  const handleCancel = () => {}
  const hadnleRetrieve = () => {}
</script>
<template>
  <ul
    class="search-sql-query"
    ref="refUlRoot"
  >
    <li
      class="search-result-item"
      v-for="(item, index) in modelValue"
      :key="`${item.field}-${index}`"
    >
      <template v-if="item.is_focus_input">
        <input
          class="tag-option-focus-input"
          type="text"
          v-model="inputValue"
          @focus.stop="handleFocusInput"
          @blur="handleTextInputBlur"
        />
      </template>
      <template v-else>
        <span>{{ item }}</span>
      </template>
    </li>
    <div style="display: none">
      <SqlQueryOptions
        ref="refSqlQueryOption"
        :value="inputValue"
        @change="handleQueryChange"
        @cancel="handleCancel"
        @retrieve="hadnleRetrieve"
      ></SqlQueryOptions>
    </div>
  </ul>
</template>
<style scoped>
  .search-sql-query {
    display: inline-flex;
    flex-wrap: wrap;
    width: 100%;
    max-height: 135px;
    padding: 4px 16px;
    padding-bottom: 0;
    margin: 0;
    overflow: auto;

    li {
      input.tag-option-focus-input {
        width: 8px;
        height: 38px;
        font-size: 12px;
        color: #63656e;
        border: none;
      }
    }
  }
</style>

<style scoped>
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
