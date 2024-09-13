<script setup>
  import { computed, ref, watch, onBeforeUnmount, nextTick, getCurrentInstance } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import imgEnterKey from '@/images/icons/enter-key.svg';
  import imgUpDownKey from '@/images/icons/up-down-key.svg';
  import { debounce } from 'lodash';
  import tippy from 'tippy.js';
  import PopInstanceUtil from './pop-instance-util';
  // @ts-ignore
  import { getCharLength } from '@/common/util';
  const INPUT_MIN_WIDTH = 12;

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

  const svgImg = ref({ imgUpDownKey, imgEnterKey });

  const store = useStore();
  const { t } = useLocale();
  const searchValue = ref('');
  const refConditionInput = ref(null);
  const refUiValueOperator = ref(null);
  const refUiValueOperatorList = ref(null);
  const activeIndex = ref(0);
  const refSearchResultList = ref(null);
  const refFilterInput = ref(null);
  const isFocusFieldList = ref(true);
  // 条件Value选择列表
  const refValueTagInputOptionList = ref(null);

  // 操作符下拉当前激活Index
  const operatorActiveIndex = ref(0);

  // 操作符下拉实例
  const operatorInstance = new PopInstanceUtil({
    refContent: refUiValueOperatorList,
    arrow: false,
    newInstance: false,
    onHiddenFn: () => {
      operatorActiveIndex.value = 0;
    },
    tippyOptions: {
      flip: false,
    },
  });

  // 条件Value弹出下拉实例
  const conditionValueInstance = new PopInstanceUtil({
    refContent: refValueTagInputOptionList,
    arrow: false,
    newInstance: false,
    watchElement: refConditionInput,
    onHiddenFn: instance => {
      refValueTagInputOptionList.value?.querySelector('li.is-hover')?.classList.remove('is-hover');
    },
    tippyOptions: {
      flip: false,
      placement: 'bottom',
      popperOptions: {
        placement: 'bottom', // 或者其他你想要的位置
        modifiers: [
          {
            name: 'preventOverflow',
            options: {
              boundary: document.body,
            },
          },
          {
            name: 'flip',
            options: {
              boundary: document.body,
            },
          },
        ],
      },
    },
  });

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

  // 需要排除的字段
  const excludesFields = ['__ext', '__module__', ' __set__', '__ipv6__', '__ext'];

  // 无需配置值（Value）的条件列表
  const withoutValueConditionList = ['does not exists', 'exists'];

  // 判定当前选中条件是否需要设置Value
  const isShowConditonValueSetting = computed(() => !withoutValueConditionList.includes(condition.value.operator));

  const filterFieldList = computed(() => {
    const regExp = getRegExp(searchValue.value);
    const filterFn = field =>
      field.field_type !== '__virtual__' &&
      !excludesFields.includes(field.field_name) &&
      (field.is_full_text || regExp.test(field.field_alias) || regExp.test(field.field_name));
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
    operatorInstance.initInistance(refUiValueOperator.value);
  };

  const unInstallOperatorSelect = () => {
    operatorInstance.uninstallInstance();
  };

  const restoreFieldAndCondition = () => {
    const matchedField = fieldList.value.find(field => field.field_name === props.value.field);
    Object.assign(activeFieldItem.value, matchedField ?? {});
    const { operator, relation = 'AND', isInclude, value = [] } = props.value;
    Object.assign(condition.value, { operator, relation, isInclude, value });

    let filterIndex = filterFieldList.value.findIndex(
      field =>
        field.field_type === activeFieldItem.value.field_type && field.field_name === activeFieldItem.value.field_name,
    );

    if (filterIndex === -1) {
      Object.assign(activeFieldItem.value, filterFieldList.value[0]);
      Object.assign(condition.value, { operator: activeFieldItem.value.field_operator?.[0]?.operator });
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
      relation: 'AND',
    };

    activeIndex.value = 0;
  };

  const handleFieldItemClick = (item, index) => {
    // 避免重复提交设置
    if (activeFieldItem.value.field_name === item.field_name) {
      return;
    }

    resetActiveFieldItem();
    Object.assign(activeFieldItem.value, item);
    activeIndex.value = index;
    condition.value.operator = activeFieldItem.value.field_operator?.[0]?.operator;
    condition.value.relation = 'AND';

    if (props.value.field === item.field_name) {
      restoreFieldAndCondition();
    }
  };

  const handleCancelBtnClick = () => {
    resetActiveFieldItem();
    emit('cancel');
  };

  const handelSaveBtnClick = () => {
    // 如果条件值为空 并且当前条件需要条件值
    // 禁止提交
    if (isShowConditonValueSetting.value && !condition.value.value.length && !showFulltextMsg) {
      return;
    }

    const isFulltextValue = activeFieldItem.value.field_name === '';
    const result = isFulltextValue
      ? undefined
      : {
          field: activeFieldItem.value.field_name,
          ...condition.value,
        };

    // 如果是空操作符禁止提交
    if (result && !result.operator) {
      return;
    }

    resetActiveFieldItem();
    emit('save', result);
  };

  const refValueTagInput = ref(null);
  const isConditionValueInputFocus = ref(false);
  const conditionValueActiveIndex = ref(-1);

  const activeItemMatchList = computed(() => {
    return store.state.indexFieldInfo.aggs_items[activeFieldItem.value.field_name] ?? [];
  });

  const handleConditionValueClick = () => {
    refValueTagInput.value.focus();
    conditionValueActiveIndex.value = -1;

    if (activeItemMatchList.value.length > 0) {
      nextTick(() => {
        const target = refValueTagInput.value.closest('.condition-value-container');
        conditionValueInstance.show(target);
      });
    }
  };

  /**
   * 当前快捷键操作是否命中条件相关弹出
   */
  const isConditionValueFocus = () => {
    const instance = conditionValueInstance.getTippyInstance();
    return isConditionValueInputFocus.value && instance?.state.isShown;
  };

  /**
   * 条件值下拉选择设置当前hover项
   */
  const activeConditionValueOption = () => {
    const instance = conditionValueInstance.getTippyInstance();
    if (instance?.state.isShown) {
      instance.popper?.querySelector('li.is-hover')?.classList.remove('is-hover');
      instance.popper?.querySelectorAll('li')[conditionValueActiveIndex.value]?.classList.add('is-hover');
      instance.popper?.querySelector('li.is-hover')?.scrollIntoView({ block: 'nearest' });
    }
  };

  const handleInputVlaueChange = e => {
    const input = e.target;
    if (input !== undefined) {
      const value = input.value;
      const charLen = getCharLength(value);
      input.style.setProperty('width', `${charLen * INPUT_MIN_WIDTH}px`);
    }
  };

  const handleConditionValueInputFocus = () => {
    isConditionValueInputFocus.value = true;
  };

  const hanleDeleteTagItem = index => {
    condition.value.value.splice(index, 1);
  };

  const handleOperatorBtnClick = () => {
    operatorInstance.show(refUiValueOperator.value);
  };

  const handleTagItemClick = value => {
    if (!condition.value.value.includes(value)) {
      condition.value.value.push(value);
    }
  };

  /**
   * 通用方法：根据键盘上下键操作，设置对应参数当前激活Index的值
   */
  const setActiveObjectIndex = (objIndex, matchList, isIncrease = true) => {
    const maxIndex = matchList.length - 1;
    if (isIncrease) {
      if (objIndex.value < maxIndex) {
        objIndex.value++;
        return;
      }

      objIndex.value = 0;
      return;
    }

    if (objIndex.value > 0) {
      objIndex.value--;
      return;
    }

    objIndex.value = maxIndex;
  };

  /**
   * 设置当前条件值激活Index
   */
  const setConditionValueActiveIndex = (isIncrease = true) => {
    setActiveObjectIndex(conditionValueActiveIndex, activeItemMatchList.value, isIncrease);
  };

  /**
   * 判断当前操作符选择下拉是否激活
   */
  const isOperatorInstanceActive = () => {
    return operatorInstance.getTippyInstance()?.state?.isShown && activeFieldItem.value.field_operator?.length;
  };

  /**
   * 手动选择操作符值改变之后
   * 判定是否已有值，如果条件值为空
   * 自动弹出选择值
   */
  const afterOperatorValueEnter = () => {
    if (isShowConditonValueSetting.value && !condition.value.value.length) {
      nextTick(() => {
        handleConditionValueClick();
      });
    }
  };

  const resolveConditonValueInputEnter = () => {
    if (isOperatorInstanceActive()) {
      operatorInstance?.hide();
      afterOperatorValueEnter();
      return;
    }

    // 如果需要设置条件
    // 条件选择或者输入框已经渲染出来
    if (refValueTagInput.value) {
      const instance = conditionValueInstance.getTippyInstance();

      // 如果是条件选择下拉已经展开，查询当前选中项
      if (instance?.state.isShown) {
        const val = activeItemMatchList.value[conditionValueActiveIndex.value];
        if (val !== undefined) {
          handleTagItemClick(val);
          refValueTagInput.value.value = '';
          setConditionValueActiveIndex(true);
          activeConditionValueOption();
          return;
        }
      }

      // 如果当前没有自动focus条件选择
      if (!isConditionValueInputFocus.value) {
        handleConditionValueClick();
        return;
      }

      // 如果有可以自动联想的内容 & 没有自动展开下拉提示
      // 此时，自动展开下拉提示
      if (!instance?.state.isShown && activeItemMatchList.value.length) {
        handleConditionValueClick();
      }

      // 如果是条件输入框内有数据执行数据填入操作
      // 清空输入框
      if (refValueTagInput.value.value) {
        condition.value.value.push(refValueTagInput.value.value);
        refValueTagInput.value.value = '';
        return;
      }

      if (condition.value.value.length) {
        handelSaveBtnClick();
      }

      return;
    }

    handelSaveBtnClick();
  };

  /**
   * 设置当前条件激活Index
   */
  const setOperatorActiveIndex = (isIncrease = true) => {
    setActiveObjectIndex(operatorActiveIndex, activeFieldItem.value.field_operator, isIncrease);
    const operator = activeFieldItem.value.field_operator[operatorActiveIndex.value]?.operator;
    if (condition.value.operator !== operator) {
      condition.value.operator = operator;
      nextTick(() => {
        const target = refUiValueOperatorList.value?.querySelector('.ui-value-option.active');
        target?.scrollIntoView({ block: 'nearest' });
      });
    }
  };

  /**
   * 设置待选择字段列表条件激活Index
   */
  const setFieldListActiveIndex = (isIncrease = true) => {
    setActiveObjectIndex(activeIndex, filterFieldList.value, isIncrease);
  };

  /**
   * 字段列表键盘上下键响应事件
   */
  const handleFieldListKeyupAndKeydown = () => {
    if (!isConditionValueFocus() && !isOperatorInstanceActive()) {
      if (activeIndex.value < filterFieldList.value.length && activeIndex.value >= 0) {
        handleFieldItemClick(filterFieldList.value[activeIndex.value], activeIndex.value);
        scrollActiveItemIntoView();
        return;
      }
    }
  };

  const handleArrowUpKeyEvent = () => {
    if (isConditionValueFocus()) {
      setConditionValueActiveIndex(false);
      activeConditionValueOption();
      return;
    }

    if (isOperatorInstanceActive()) {
      setOperatorActiveIndex(false);
      return;
    }

    setFieldListActiveIndex(false);
    handleFieldListKeyupAndKeydown();
    return;
  };

  const handleArrowDownKeyEvent = () => {
    if (isConditionValueFocus()) {
      setConditionValueActiveIndex(true);
      activeConditionValueOption();
      return;
    }

    if (isOperatorInstanceActive()) {
      setOperatorActiveIndex(true);
      return;
    }

    setFieldListActiveIndex(true);
    handleFieldListKeyupAndKeydown();
  };

  const handleEscKeyEvent = () => {
    if (isConditionValueFocus()) {
      conditionValueInstance.hide();
      return;
    }

    if (isOperatorInstanceActive()) {
      operatorInstance?.hide();
      return;
    }
  };

  const stopEventPreventDefault = e => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();
  };

  const handleKeydownClick = e => {
    if (!isFocusFieldList.value) {
      return;
    }
    // key up
    if (e.keyCode === 38) {
      stopEventPreventDefault(e);
      handleArrowUpKeyEvent();
      return;
    }

    // key down
    if (e.keyCode === 40) {
      stopEventPreventDefault(e);
      handleArrowDownKeyEvent();
      return;
    }

    // key enter
    if (e.keyCode === 13) {
      stopEventPreventDefault(e);
      resolveConditonValueInputEnter();
      return;
    }

    // key esc
    if (e.keyCode === 27) {
      stopEventPreventDefault(e);
      handleEscKeyEvent();
      return;
    }
  };

  const handleUiValueOptionClick = option => {
    if (condition.value.operator !== option.operator) {
      condition.value.operator = option.operator;
      condition.value.value.length = 0;
      condition.value.value = [];
    }

    operatorInstance.hide();
    afterOperatorValueEnter();
  };

  const beforeShowndFn = () => {
    isFocusFieldList.value = true;
    document.addEventListener('keydown', handleKeydownClick);

    restoreFieldAndCondition();
    scrollActiveItemIntoView();

    nextTick(() => {
      // 如果是外层检索输入，这里不能自动focus到搜索
      if (!props.isInputFocus) {
        refFilterInput.value?.focus();
      }
    });
  };

  const afterHideFn = () => {
    document.removeEventListener('keydown', handleKeydownClick);
    handleFieldItemClick(filterFieldList.value[0], 0);
    isFocusFieldList.value = false;
  };

  const setActiveIndex = (index = 0) => {
    activeIndex.value = index;
  };

  const handleValueInputEnter = e => {
    stopEventPreventDefault(e);

    if (e.target.value) {
      condition.value.value.push(e.target.value);
      e.target.value = '';
    }
  };

  const handleConditionValueInputBlur = e => {
    isConditionValueInputFocus.value = false;
    if (e.target.value) {
      condition.value.value.push(e.target.value);
      e.target.value = '';
    }
  };

  let needDeleteItem = false;
  const handleDeleteInputValue = e => {
    stopEventPreventDefault(e);

    if (e.target.value) {
      needDeleteItem = false;
    }

    if (!e.target.value) {
      if (needDeleteItem) {
        if (condition.value.value.length >= 1) {
          condition.value.value.splice(-1, 1);
        }
      }

      needDeleteItem = true;
    }
  };

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
  <div class="ui-query-options">
    <div class="ui-query-option-content">
      <div class="field-list">
        <div class="ui-search-input">
          <bk-input
            style="width: 100%"
            v-model="searchValue"
            ref="refFilterInput"
            :placeholder="$t('请输入关键字')"
            behavior="simplicity"
            left-icon="bk-icon icon-search"
          >
          </bk-input>
        </div>
        <div
          ref="refSearchResultList"
          class="ui-search-result"
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
              v-if="!item.is_full_text"
              class="field-name"
              >({{ item.field_name }})</span
            >
          </div>
        </div>
      </div>
      <div :class="['value-list', { 'is-full-text': showFulltextMsg }]">
        <template v-if="showFulltextMsg">
          <div class="full-text-title">{{ $t('全文检索') }}</div>
          <div class="full-text-sub-title">
            <img :src="svgImg.imgEnterKey" /><span>{{ $t('Enter 键') }}</span>
          </div>
          <div class="full-text-content">{{ $t('可将想要检索的内容输入至搜索框中，并点击「Enter」键进行检索') }}</div>
          <div class="full-text-sub-title">
            <img :src="svgImg.imgUpDownKey" /><span>{{ $t('上下键') }}</span>
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
                @click.stop="handleOperatorBtnClick"
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
          <div
            class="ui-value-row"
            v-if="isShowConditonValueSetting"
          >
            <div class="ui-value-label">
              <span>Value</span
              ><span
                ><bk-checkbox v-model="condition.isInclude">{{ $t('使用通配符') }}</bk-checkbox></span
              >
            </div>
            <div :class="['condition-value-container', { 'is-focus': isConditionValueInputFocus }]">
              <ul
                class="condition-value-input"
                ref="refConditionInput"
                @click.stop="handleConditionValueClick"
              >
                <li
                  class="tag-item"
                  v-for="(item, index) in condition.value"
                  :key="`${item}-${index}`"
                >
                  <span class="tag-item-text">{{ item }}</span>
                  <span
                    class="tag-item-del bk-icon icon-close"
                    @click.stop="e => hanleDeleteTagItem(index)"
                  ></span>
                </li>
                <li>
                  <input
                    type="text"
                    ref="refValueTagInput"
                    class="tag-option-focus-input"
                    @keyup.enter="handleValueInputEnter"
                    @keyup.delete="handleDeleteInputValue"
                    @blur.stop="handleConditionValueInputBlur"
                    @input.stop="handleInputVlaueChange"
                    @focus.stop="handleConditionValueInputFocus"
                  />
                </li>
                <div style="display: none">
                  <ul
                    ref="refValueTagInputOptionList"
                    class="condition-value-options"
                  >
                    <li
                      :class="{ active: (condition.value ?? []).includes(item) }"
                      v-for="(item, index) in activeItemMatchList"
                      :key="`${item}-${index}`"
                      @click.stop="() => handleTagItemClick(item)"
                    >
                      <span>{{ item }}</span>
                    </li>
                  </ul>
                </div>
              </ul>
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
        <span><img :src="svgImg.imgUpDownKey" />{{ $t('移动光标') }}</span>
        <span><img :src="svgImg.imgEnterKey" />{{ $t('确认结果') }}</span>
      </div>
      <div class="ui-btn-opts">
        <bk-button
          style="width: 64px; margin-right: 8px"
          theme="primary"
          @click.stop="handelSaveBtnClick"
          >{{ $t('确定') }}</bk-button
        >
        <bk-button
          style="width: 64px"
          @click.stop="handleCancelBtnClick"
          >{{ $t('取消') }}</bk-button
        >
      </div>
    </div>
  </div>
</template>
<style scoped lang="scss">
  @import './ui-input-option.scss';

  .condition-value-container {
    width: 100%;
    min-height: 32px;
    background: #ffffff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;

    &.is-focus {
      border-color: #2c77f4;
    }

    ul.condition-value-input {
      display: inline-flex;
      flex-wrap: wrap;
      width: 100%;
      max-height: 110px;
      padding: 0 5px;
      margin: 0;
      overflow: auto;

      > li {
        display: inline-flex;
        align-items: center;
        height: 22px;
        margin: 4px 5px 4px 0;
        overflow: hidden;
        font-size: 12px;
        border: solid 1px transparent;
        border-radius: 2px;

        &.tag-item {
          background: #f0f1f5;
          border-color: #f0f1f5;

          .tag-item-text {
            max-width: 80px;
            padding: 0 4px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;

            &:hover {
              background-color: #dcdee5;
            }
          }

          .tag-item-del {
            font-size: 16px;
            cursor: pointer;
          }
        }

        input.tag-option-focus-input {
          width: 8px;
          height: 38px;
          font-size: 12px;
          color: #63656e;
          border: none;
        }
      }
    }
  }
</style>
<style lang="scss">
  [data-theme='log-light'] {
    .ui-value-select {
      width: 338px;
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

    .condition-value-options {
      width: 338px;
      max-height: 300px;
      overflow: auto;
      border: 1px solid #dcdee5;
      box-shadow: 0 2px 6px 0 #0000001a;

      > li {
        display: inline-block;
        width: 100%;
        max-width: 100%;
        height: 32px;
        padding: 6px 8px;
        overflow: hidden;
        font-size: 12px;
        color: #63656e;
        text-overflow: ellipsis;
        white-space: nowrap;
        cursor: pointer;
        background: #ffffff;

        &.active {
          background: #f5f7fa;
        }

        &.is-hover,
        &:hover {
          background: #e1ecff;
        }
      }
    }
  }
</style>
