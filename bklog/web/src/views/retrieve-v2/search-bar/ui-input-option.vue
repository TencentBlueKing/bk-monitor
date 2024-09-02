<script setup>
  import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';

  import { debounce } from 'lodash';
  import useStore from '@/hooks/use-store';
  import useLocale from '@/hooks/use-locale';
  import tippy from 'tippy.js';

  const props = defineProps({
    value: {
      type: [String, Object],
      default: '',
      required: true,
    },
    isInputFocus: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['save', 'cancel']);

  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);

  const store = useStore();
  const { t } = useLocale();
  const searchValue = ref('');
  const refUiValueOperator = ref(null);
  const refUiValueOperatorList = ref(null);
  const activeIndex = ref(0);
  const refSearchResultList = ref(null);
  const isFocusFieldList = ref(true);
  const enterStepIndex = ref(0);
  // 匹配条件值Enter键点击次数
  // 用于计数当前Enter键是否为切换为提交
  let conditionValueEnterCount = 0;
  let refUiValueOperatorInstance = null;

  const fullTextField = ref({
    field_name: '',
    is_full_text: true,
    field_alias: t('全文检索'),
    field_operator: [
      {
        operator: 'contains',
        label: t('包含'),
        placeholder: t('请选择或直接输入，Enter分隔'),
      },
    ],
  });

  const activeFieldItem = ref({
    field_name: null,
    field_type: null,
    field_alias: null,
    field_id: null,
    field_operator: [],
  });

  const condition = ref({
    operator: '',
    isInclude: true,
    value: [],
    relation: 'AND',
  });

  const getRegExp = (searchValue, flags = 'ig') => {
    return new RegExp(`${searchValue}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'), flags);
  };

  const fieldList = computed(() => [fullTextField.value].concat(indexFieldInfo.value.fields));

  const filterFieldList = computed(() => {
    const regExp = getRegExp(searchValue.value);
    const filterFn = field => field.is_full_text || regExp.test(field.field_alias) || regExp.test(field.field_name);
    return fieldList.value.filter(filterFn);
  });

  const activeOperator = computed(
    () =>
      activeFieldItem.value.field_operator.find(op => op.operator === condition.value.operator) ?? {
        label: condition.value.operator,
        operator: condition.value.operator,
      },
  );
  const scrollActiveItemIntoView = () => {
    if (activeIndex.value >= 0) {
      const target = refSearchResultList.value?.querySelector(`[data-tab-index="${activeIndex.value}"]`);
      target?.scrollIntoView({ block: 'nearest' });
    }
  };

  const installOperatorSelect = () => {
    if (refUiValueOperatorInstance === null) {
      refUiValueOperatorInstance = tippy(refUiValueOperator.value, {
        content: refUiValueOperatorList.value,
        trigger: 'click',
        theme: 'log-light',
        placement: 'bottom-start',
        interactive: true,
        arrow: false,
      });
    }
  };

  const unInstallOperatorSelect = () => {
    refUiValueOperatorInstance?.unmount();
    refUiValueOperatorInstance?.destroy();
    refUiValueOperatorInstance = null;
  };

  const restoreFieldAndCondition = () => {
    const matchedField = fieldList.value.find(field => field.field_name === props.value.field);
    Object.assign(activeFieldItem.value, matchedField ?? {});
    const { operator, relation, isInclude, value } = props.value;
    Object.assign(condition.value, { operator, relation, isInclude, value });

    let filterIndex = filterFieldList.value.findIndex(
      field =>
        field.field_type === activeFieldItem.value.field_type && field.field_name === activeFieldItem.value.field_name,
    );

    if (filterIndex === -1) {
      Object.assign(activeFieldItem.value, filterFieldList.value[0]);
      Object.assign(condition.value, { operator: activeFieldItem.value.field_operator[0].operator });
      filterIndex = 0;
    }

    activeIndex.value = filterIndex;
  };

  const showFulltextMsg = computed(() => activeIndex.value === 0 && props.isInputFocus);

  watch(
    activeIndex,
    () => {
      if (activeIndex.value > 0) {
        nextTick(() => {
          installOperatorSelect();
        });
        return;
      }

      unInstallOperatorSelect();
    },
    { immediate: true },
  );

  const getFieldIcon = fieldType => {
    return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
  };

  const getFieldIconColor = type => {
    return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
  };

  const resetActiveFieldItem = () => {
    activeFieldItem.value = {
      field_name: null,
      field_type: null,
      field_alias: null,
      field_id: null,
      field_operator: [],
    };

    condition.value = {
      operator: '',
      isInclude: true,
      value: [],
      relation: 'and',
    };

    activeIndex.value = -1;
  };

  const handleFieldItemClick = (item, index) => {
    resetActiveFieldItem();
    Object.assign(activeFieldItem.value, item);
    activeIndex.value = index;
    condition.value.operator = activeFieldItem.value.field_operator[0].operator;

    if (props.value.field === item.field_name) {
      restoreFieldAndCondition();
    }
  };

  const handleCancelBtnClick = () => {
    resetActiveFieldItem();
    emit('cancel');
  };

  const handelSaveBtnClick = () => {
    const isFulltextValue = activeFieldItem.value.field_name === '';
    const result = isFulltextValue
      ? undefined
      : {
          field: activeFieldItem.value.field_name,
          ...condition.value,
        };

    resetActiveFieldItem();
    emit('save', result);
  };

  const refValueTagInput = ref(null);
  const keyEnterCallbackFn = computed(() => {
    return [
      () => {
        if (!showFulltextMsg.value) {
          refValueTagInput.value?.focusInputer();
          return;
        }

        handelSaveBtnClick();
      },
      () => {
        handelSaveBtnClick();
      },
    ];
  });

  const debounceSetActiveStep = debounce(() => {
    // 第二次点击Enter键，自动提交
    if (enterStepIndex.value === 1) {
      if (conditionValueEnterCount !== condition.value.value.length) {
        keyEnterCallbackFn.value[enterStepIndex.value]?.();
        enterStepIndex.value++;
      }

      conditionValueEnterCount++;
      return;
    }

    // 第一次点击Enter键，切换为条件值选择
    keyEnterCallbackFn.value[enterStepIndex.value]?.();
    enterStepIndex.value++;
  });

  const handleKeydownClick = e => {
    if (!isFocusFieldList.value) {
      return;
    }

    let stopPropagation = false;
    let isUpDownKeyEvent = false;

    let index = activeIndex.value;
    // key up
    if (e.keyCode === 38) {
      stopPropagation = true;
      isUpDownKeyEvent = true;
      const minValue = 0;
      if (activeIndex.value > minValue) {
        index = index - 1;
      }
    }

    // key down
    if (e.keyCode === 40) {
      stopPropagation = true;
      isUpDownKeyEvent = true;
      if (activeIndex.value < filterFieldList.value.length) {
        index = index + 1;
      }
    }

    // key enter
    if (e.keyCode === 13) {
      stopPropagation = true;
      debounceSetActiveStep();
    }

    if (stopPropagation) {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
    }

    if (isUpDownKeyEvent) {
      if (index >= 0) {
        handleFieldItemClick(filterFieldList.value[index], index);
        scrollActiveItemIntoView();
        return;
      }

      scrollActiveItemIntoView();
    }
  };

  const handleUiValueOptionClick = option => {
    condition.value.operator = option.operator;
    refUiValueOperatorInstance?.hide();
  };

  const beforeShowndFn = () => {
    isFocusFieldList.value = true;
    document.addEventListener('keydown', handleKeydownClick);

    restoreFieldAndCondition();
    scrollActiveItemIntoView();
  };

  const afterHideFn = () => {
    document.removeEventListener('keydown', handleKeydownClick);
    handleFieldItemClick(filterFieldList.value[0], 0);
    enterStepIndex.value = 0;
    isFocusFieldList.value = false;
  };

  const handleRsultListClick = () => {
    // isFocusFieldList.value = true;
  };

  const handleResultOutsideClick = () => {
    // isFocusFieldList.value = false;
  };

  const setActiveIndex = (index = 0) => {
    activeIndex.value = index;
  };

  // 通过计数tag-input选择值的数量和当前键盘enter次数标记当前enter是否为执行提交操作
  // 当tag-input选择值的数量与当前enter次数不一致时，说明为提交操作
  const handleValueTagInputChange = tags => {
    conditionValueEnterCount = tags.length;
  };

  onMounted(() => {
    beforeShowndFn();
  });

  onBeforeUnmount(() => {
    afterHideFn();
  });

  defineExpose({
    beforeShowndFn,
    afterHideFn,
    setActiveIndex,
  });
</script>
<template>
  <div
    class="ui-query-options"
    @click.stop="handleResultOutsideClick"
  >
    <div class="ui-query-option-content">
      <div class="field-list">
        <div class="ui-search-input">
          <bk-input
            style="width: 100%"
            v-model="searchValue"
            :placeholder="$t('请输入关键字')"
            behavior="simplicity"
            left-icon="bk-icon icon-search"
          >
          </bk-input>
        </div>
        <div
          ref="refSearchResultList"
          class="ui-search-result"
          @click.stop="handleRsultListClick"
        >
          <div
            v-for="(item, index) in filterFieldList"
            :class="['ui-search-result-row', { active: activeIndex === index }]"
            :data-tab-index="index"
            :key="item.field_name"
            @click="() => handleFieldItemClick(item, index)"
          >
            <span
              :style="{ backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type) }"
              :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
            >
            </span>
            <span class="field-alias">{{ item.field_alias || item.field_name }}</span>
            <span
              class="field-name"
              v-if="!item.is_full_text"
              >({{ item.field_name }})</span
            >
          </div>
        </div>
      </div>
      <div :class="['value-list', { 'is-full-text': showFulltextMsg }]">
        <template v-if="showFulltextMsg">
          <div class="full-text-title">{{ $t('全文检索') }}</div>
          <div class="full-text-sub-title">
            <span></span><span>{{ $t('Enter 键') }}</span>
          </div>
          <div class="full-text-content">{{ $t('可将想要检索的内容输入至搜索框中，并点击「Enter」键进行检索') }}</div>
          <div class="full-text-sub-title">
            <span></span><span>{{ $t('上下键') }}</span>
          </div>
          <div class="full-text-content">{{ $t('可通过上下键快速切换选择「Key」值') }}</div>
        </template>
        <template v-else>
          <div class="ui-value-row">
            <div class="ui-value-label">{{ $t('条件') }}</div>
            <div class="ui-value-component">
              <div
                ref="refUiValueOperator"
                class="ui-value-operator"
              >
                {{ activeOperator.label }}
              </div>
              <div style="display: none">
                <div
                  ref="refUiValueOperatorList"
                  class="ui-value-select"
                >
                  <div
                    v-for="option in activeFieldItem.field_operator"
                    :class="['ui-value-option', { active: condition.operator === option.operator }]"
                    :key="option.operator"
                    @click="() => handleUiValueOptionClick(option)"
                  >
                    {{ option.label }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="ui-value-row">
            <div class="ui-value-label">
              <span>Value</span
              ><span
                ><bk-checkbox v-model="condition.isInclude">{{ $t('使用通配符') }}</bk-checkbox></span
              >
            </div>
            <div>
              <bk-tag-input
                v-model="condition.value"
                :allow-create="true"
                ref="refValueTagInput"
                @change="handleValueTagInputChange"
              ></bk-tag-input>
            </div>
          </div>
          <div class="ui-value-row">
            <div class="ui-value-label">{{ $t('组间关系') }}</div>
            <div>
              <bk-radio-group v-model="condition.relation">
                <bk-radio
                  style="margin-right: 12px"
                  value="AND"
                  >AND
                </bk-radio>
                <bk-radio value="OR">OR </bk-radio>
              </bk-radio-group>
            </div>
          </div>
        </template>
      </div>
    </div>
    <div class="ui-query-option-footer">
      <div class="ui-shortcut-key">
        <span><i></i>{{ $t('移动光标') }}</span>
        <span><i></i>{{ $t('确认结果') }}</span>
      </div>
      <div class="ui-btn-opts">
        <bk-button
          style="width: 64px; margin-right: 8px"
          theme="primary"
          @click="handelSaveBtnClick"
          >{{ $t('确定') }}</bk-button
        >
        <bk-button
          style="width: 64px"
          @click="handleCancelBtnClick"
          >{{ $t('取消') }}</bk-button
        >
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './ui-input-option.scss';
</style>
<style>
  [data-theme='log-light'] {
    .ui-value-select {
      width: 238px;
      max-height: 200px;
      overflow: auto;

      .ui-value-option {
        display: flex;
        align-items: center;
        width: 100%;
        height: 32px;
        padding: 0 12px;
        cursor: pointer;
        background: #ffffff;

        &:not(.active) {
          &:hover {
            background: #f5f7fa;
          }
        }

        &.active {
          color: #3a84ff;
          background: #e1ecff;
        }
      }
    }
  }
</style>
