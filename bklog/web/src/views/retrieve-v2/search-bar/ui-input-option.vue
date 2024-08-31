<script setup>
  import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
  import useStore from '@/hooks/use-store';
  import tippy from 'tippy.js';

  const props = defineProps({
    value: {
      type: [String, Object],
      default: '',
      required: true,
    },
  });

  const emit = defineEmits(['save', 'cancel']);

  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);

  const store = useStore();
  const searchValue = ref('');
  const fullText = ref(null);
  const refUiValueOperator = ref(null);
  const refUiValueOperatorList = ref(null);
  const activeIndex = ref(-1);
  const refSearchResultList = ref(null);
  let refUiValueOperatorInstance = null;

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
    relation: 'and',
  });

  const getRegExp = (searchValue, flags = 'ig') => {
    return new RegExp(`${searchValue}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'), flags);
  };

  const filterFieldList = computed(() => {
    const regExp = getRegExp(searchValue.value);
    return indexFieldInfo.value.fields.filter(field => regExp.test(field.field_alias) || regExp.test(field.field_name));
  });

  const isFullText = computed(() => fullText.value !== null && fullText.value.length > 0);

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
    refUiValueOperatorInstance = null;
  };

  watch(
    props,
    () => {
      fullText.value = null;
      if (typeof props.value === 'string') {
        fullText.value = props.value;
        activeIndex.value = 0;
        return;
      }

      Object.assign(activeFieldItem.value, props.value);
      let filterIndex =
        filterFieldList.value.findIndex(
          field =>
            field.field_type === activeFieldItem.value.field_type &&
            field.field_name === activeFieldItem.value.field_name,
        ) + 1;

      if (filterIndex === 0) {
        filterIndex = 1;
        Object.assign(activeFieldItem.value, filterFieldList.value[0]);
      }

      activeIndex.value = filterIndex;
      scrollActiveItemIntoView();
    },
    { immediate: true, deep: true },
  );

  watch(
    activeIndex,
    value => {
      if (value > 0) {
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

  const handleFieldItemClick = (item, index) => {
    Object.assign(activeFieldItem.value, item);
    activeIndex.value = index;
  };

  const resetActiveFieldItem = (ignoreFullText = false) => {
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
    if (!ignoreFullText) {
      fullText.value = null;
    }
  };

  const handleCancelBtnClick = () => {
    resetActiveFieldItem();
    emit('cancel');
  };

  const handelSaveBtnClick = () => {
    const result = {
      field: activeFieldItem.value.field_name,
      ...condition.value,
    };

    resetActiveFieldItem();
    emit('save', result);
  };

  const handleFullTextClick = () => {
    resetActiveFieldItem(true);
    activeIndex.value = 0;
  };

  const handleKeydownClick = e => {
    let index = activeIndex.value;

    if (e.keyCode === 38) {
      const minValue = isFullText.value ? 0 : 1;
      if (activeIndex.value > minValue) {
        index = index - 1;
      }
    }

    if (e.keyCode === 40) {
      if (activeIndex.value < filterFieldList.value.length) {
        index = index + 1;
      }
    }

    if (index > 0) {
      handleFieldItemClick(filterFieldList.value[index - 1], index);
      scrollActiveItemIntoView();
      return;
    }

    handleFullTextClick();
    scrollActiveItemIntoView();
  };

  const handleUiValueOptionClick = (option) => {
    condition.value.operator = option.operator;
    refUiValueOperatorInstance?.hide();
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydownClick);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydownClick);
  });
</script>
<template>
  <div class="ui-query-options">
    <div class="ui-query-option-content">
      <div class="field-list">
        <div class="ui-search-input">
          <bk-input
            :placeholder="$t('请输入关键字')"
            v-model="searchValue"
            left-icon="bk-icon icon-search"
            behavior="simplicity"
            style="width: 100%"
          >
          </bk-input>
        </div>
        <div
          class="ui-search-result"
          ref="refSearchResultList"
        >
          <div
            :class="['ui-search-result-row', { active: activeIndex === 0 }]"
            @click="handleFullTextClick"
            data-tab-index="0"
            v-if="isFullText"
          >
            <span class="field-type-icon full-text"></span>
            <span class="field-alias">{{ $t('全文检索') }}</span>
            <span class="field-name"></span>
          </div>
          <div
            v-for="(item, index) in filterFieldList"
            :class="['ui-search-result-row', { active: activeIndex === index + 1 }]"
            :key="item.field_name"
            :data-tab-index="index + 1"
            @click="() => handleFieldItemClick(item, index + 1)"
          >
            <span
              :class="[getFieldIcon(item.field_type), 'field-type-icon']"
              :style="{ backgroundColor: getFieldIconColor(item.field_type) }"
            ></span
            ><span class="field-alias">{{ item.field_alias || item.field_name }}</span
            ><span class="field-name">({{ item.field_name }})</span>
          </div>
        </div>
      </div>
      <div :class="['value-list', { 'is-full-text': activeIndex === 0 }]">
        <template v-if="activeIndex === 0">
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
                class="ui-value-operator"
                ref="refUiValueOperator"
              >{{ condition.operator }}</div>
              <div style="display: none">
                <div
                  ref="refUiValueOperatorList"
                  class="ui-value-select"
                >
                  <div
                    :class="['ui-value-option', { active: condition.operator === option.operator }]"
                    v-for="option in activeFieldItem.field_operator"
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
            <div><bk-tag-input v-model="condition.value" :allow-create="true"></bk-tag-input></div>
          </div>
          <div class="ui-value-row">
            <div class="ui-value-label">{{ $t('组间关系') }}</div>
            <div>
              <bk-radio-group v-model="condition.relation">
                <bk-radio
                  value="and"
                  style="margin-right: 12px"
                  >AND
                </bk-radio>
                <bk-radio value="or">OR </bk-radio>
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
          theme="primary"
          style="width: 64px; margin-right: 8px"
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
