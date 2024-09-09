<script setup>
  import { ref, nextTick, computed } from 'vue';

  import SqlQueryOptions from './sql-query-options';
  import useFocusInput from './use-focus-input';

  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  const emit = defineEmits(['retrieve', 'input', 'height-change']);
  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const refSqlQueryOption = ref(null);
  const isInputFocus = ref(false);
  const refUlRoot = ref(null);
  const separator = /\s(AND|OR)\s/i; // 区分查询语句条件

  const formatModelValueItem = item => {
    return item.replace(/^\s*\*\s*$/, '');
  };

  const { modelValue, inputValue, handleInputBlur, delayShowInstance, getTippyInstance, handleContainerClick } =
    useFocusInput(props, {
      onHeightChange: handleHeightChange,
      formatModelValueItem,
      refContent: refSqlQueryOption,
      arrow: false,
      newInstance: false,
      tippyOptions: {
        maxWidth: 'none',
        distance: 0,
      },
      onShowFn: instance => {
        refSqlQueryOption.value?.beforeShowndFn?.();
        instance.popper?.style.setProperty('width', '100%');
      },
      onHiddenFn: () => {
        refSqlQueryOption.value?.beforeHideFn?.();
      },
    });

  const sqlQueryString = computed(() => {
    return `${modelValue.value.filter(val => !val.is_focus_input).join('')}${inputValue.value}`;
  });

  const sqlQueryItemList = computed(() => {
    return modelValue.value
      .map(value => {
        if (typeof value === 'string') {
          return value
            .split(separator)
            .filter(Boolean)
            .map(val => {
              if (/^\s*(AND|OR)\s*$/i.test(val)) {
                return {
                  text: val,
                  operator: val,
                };
              }

              return {
                text: val,
                operator: undefined,
              };
            });
        }

        return value;
      })
      .flat();
  });

  const handleTextInputBlur = e => {
    isInputFocus.value = false;
    inputValue.value = '';
    handleInputBlur(e);
  };

  const handleFocusInput = () => {
    isInputFocus.value = true;
    nextTick(() => {
      delayShowInstance(refUlRoot.value);
      console.log('delayShowInstance');
    });
  };

  const handleQueryChange = value => {
    while (modelValue.value.length > 1) {
      modelValue.value.shift();
    }

    modelValue.value.unshift(value);
    emit('input', [modelValue.value[0]]);
    inputValue.value = '';
    nextTick(() => {
      handleContainerClick();
    });
  };

  const handleInputDelete = () => {
    if (!inputValue.value.length && modelValue.value.length === 2) {
      const result = modelValue.value[0].slice(0, -1);
      modelValue.value.splice(0, 1, result);
      emit('input', [modelValue.value[0]]);
    }
  };

  const handleCancel = () => {
    getTippyInstance()?.hide();
    handleContainerClick();
  };
  const hadnleRetrieve = () => {};
</script>
<template>
  <ul
    ref="refUlRoot"
    class="search-sql-query"
  >
    <li
      v-for="(item, index) in sqlQueryItemList"
      class="search-sql-item"
      :key="`${item.field}-${index}`"
    >
      <span :data-operator="item.operator">{{ item?.text }}</span>
    </li>
    <li class="search-sql-item">
      <input
        class="tag-option-focus-input"
        v-model="inputValue"
        type="text"
        @blur="handleTextInputBlur"
        @focus.stop="handleFocusInput"
        @keyup.delete="handleInputDelete"
      />
    </li>
    <div style="display: none">
      <SqlQueryOptions
        ref="refSqlQueryOption"
        :value="sqlQueryString"
        @cancel="handleCancel"
        @change="handleQueryChange"
        @retrieve="hadnleRetrieve"
      ></SqlQueryOptions>
    </div>
  </ul>
</template>
<style scoped>
  .search-sql-query {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    width: 100%;
    max-height: 135px;
    padding: 4px 16px;
    padding-bottom: 0;
    margin: 0;
    overflow: auto;

    li {
      display: inline-flex;
      flex-direction: column;
      align-content: center;
      justify-content: center;
      height: 20px;
      margin-right: 4px;
      margin-bottom: 4px;

      font-size: 12px;
      color: #63656e;
      cursor: pointer;
      border-radius: 2px;

      input.tag-option-focus-input {
        width: 8px;
        height: 38px;
        font-size: 12px;
        color: #63656e;
        border: none;
      }

      span {
        &[data-operator] {
          padding: 0 2px;
          color: #ff9c01;
          background: #fff3e1;
          border-radius: 2px;
        }
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
