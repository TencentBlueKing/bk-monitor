<script setup lang="ts">
  import { computed, ref, watch, onBeforeUnmount, nextTick, Ref } from 'vue';

  // @ts-ignore
  import { getCharLength, getRegExp, formatDateTimeField, getOsCommandLabel } from '@/common/util';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import imgEnterKey from '@/images/icons/enter-key.svg';
  import imgUpDownKey from '@/images/icons/up-down-key.svg';
  import { bkIcon } from 'bk-magic-vue';
  import { Props } from 'tippy.js';

  import PopInstanceUtil from '../../../global/pop-instance-util';
  import { excludesFields, withoutValueConditionList } from './const.common';
  import { getInputQueryDefaultItem, getFieldConditonItem, FulltextOperator } from './const.common';
  import { translateKeys } from './const-values';
  import useFieldEgges from '@/hooks/use-field-egges';
  import { BK_LOG_STORAGE, FieldInfoItem } from '../../../store/store.type';
  import BatchInput from '../components/batch-input';
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

  const emit = defineEmits(['save', 'cancel', 'batch-input-change']);

  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const isNotIpSelectShow = computed(() =>
    indexFieldInfo.value.fields?.some(item => item.field_name === '__ext.container_id'),
  );

  const svgImg = ref({ imgUpDownKey, imgEnterKey });
  const isArrowDown = ref(true);

  const store = useStore();
  const { t } = useLocale();
  const searchValue = ref('');
  const refConditionInput: Ref<HTMLInputElement | null> = ref(null);
  const refFullTexarea: Ref<HTMLElement | null> = ref(null);
  const refUiValueOperator: Ref<HTMLElement | null> = ref(null);
  const refUiValueOperatorList: Ref<HTMLElement | null> = ref(null);
  const activeIndex: Ref<number> = ref(0);
  const refSearchResultList: Ref<HTMLElement | null> = ref(null);
  const refFilterInput: Ref<HTMLElement | null> = ref(null);
  // 条件Value选择列表
  const refValueTagInputOptionList: Ref<HTMLElement | null> = ref(null);

  // 操作符下拉当前激活Index
  const operatorActiveIndex = ref(0);

  const tippyOptions: Partial<Props> = {
    // flip: false,
    placement: 'bottom',
    delay: [0, 300],
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
  };


  const getOperatorLable = operator => {
    if (translateKeys.includes(operator)) {
      if (/[\u4e00-\u9fff]/.test(operator)) {
        return t(operator);
      }

      return operator;
    }

    return operator;
  };

  const fieldOptionListInstance = new PopInstanceUtil({
    refContent: '',
    arrow: true,
    newInstance: true,
    tippyOptions: {
      placement: 'auto',
      theme: 'log-dark',
      delay: [0, 300],
    },
  });

  // 操作符下拉实例
  const operatorInstance = new PopInstanceUtil({
    refContent: refUiValueOperatorList,
    arrow: false,
    newInstance: true,
    onHiddenFn: () => {
      isArrowDown.value = true;
      operatorActiveIndex.value = 0;
      return true;
    },
    tippyOptions,
  });

  let conditionBlurTimer = null;

  // 条件Value弹出下拉实例
  const conditionValueInstance = new PopInstanceUtil({
    refContent: refValueTagInputOptionList,
    arrow: false,
    newInstance: true,
    watchElement: refConditionInput,
    onShowFn: () => {
      conditionBlurTimer && clearTimeout(conditionBlurTimer);
      conditionBlurTimer = null;
      return true;
    },
    onHiddenFn: () => {
      refValueTagInputOptionList.value?.querySelector('li.is-hover')?.classList.remove('is-hover');
      return true;
    },
    tippyOptions: {
      ...tippyOptions,
      hideOnClick: false,
    },
  });

  const fullTextField = ref({
    field_name: '*',
    is_full_text: true,
    field_alias: t('全文检索'),
    query_alias: t('全文检索'),
    field_type: '',
    field_operator: [
      {
        operator: FulltextOperator,
        label: t('包含'),
        placeholder: t('请选择或直接输入，Enter分隔'),
      },
    ],
  });

  const activeFieldItem = ref(getFieldConditonItem());
  const condition = ref(getInputQueryDefaultItem());
  const hasConditionValueTip = computed(() => {
    return !['_ip-select_', '*'].includes(activeFieldItem.value.field_name);
  });

  const { requestFieldEgges, isRequesting, setIsRequesting, isValidateEgges } = useFieldEgges();

  const getFieldWeight = (field: FieldInfoItem) => {
    if (field.is_virtual_alias_field) {
      return 102;
    }

    if (field.field_name === '*') {
      return 101;
    }

    if (field.field_name === 'log') {
      return 100;
    }

    if (['text'].includes(field.field_type)) {
      return 50;
    }

    return 0;
  };

  const fieldList = computed(() => {
    let list = [fullTextField.value];
    list = list.concat(indexFieldInfo.value.fields, indexFieldInfo.value.alias_field_list ?? []);
    if (!isNotIpSelectShow.value) {
      list.push({
        field_name: '_ip-select_',
        field_type: '',
        query_alias: '',
        is_full_text: true,
        field_alias: t('IP目标'),
        field_operator: [],
      });
    }
    return list.map((field: any) => ({ ...field, weight: getFieldWeight(field) })).sort((a, b) => b.weight - a.weight);
  });

  const textDir = computed(() => {
    const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
    return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
  });

  // 判定当前选中条件是否需要设置Value
  const isShowConditonValueSetting = computed(() => !withoutValueConditionList.includes(condition.value.operator));

  /**
   * 是否有检验错误
   */
  const isExitErrorTag = computed(() => {
    if (['long', 'integer', 'float'].includes(activeFieldItem.value.field_type)) {
      let regex = new RegExp(/^-?\d+\.?\d*$/);
      const result = condition.value.value.map(val => regex.test(val));
      return result.some(val => !val);
    }

    return false;
  });

  /**
   * 确定按钮是否激活
   */
  const isSaveBtnActive = computed(() => {
    if ((typeof props.value === 'string' && props.value.length) || activeFieldItem.value.field_name === '_ip-select_') {
      return true;
    }

    if (isShowConditonValueSetting.value) {
      return condition.value.value.length > 0 && !isExitErrorTag.value;
    }

    return condition.value.operator.length > 0;
  });

  const filterFieldList = computed(() => {
    const searchText = searchValue.value.trim().toLowerCase();
    const regExp = getRegExp(searchText, 'i');
    const filterFn = field =>
      field.field_type !== '__virtual__' &&
      !excludesFields.includes(field.field_name) &&
      regExp.test(`${field.query_alias || ''}${field.field_name}`) 

     
    const mapFn = item =>
      {
        const fullText =`${item.query_alias|| ''}${item.field_name}`.toLowerCase()
        return Object.assign({}, item, {
          first_name: item.query_alias || item.field_name,
          last_name: item.field_name,
          matchIndex: item.field_name === '*' ? 0 : fullText.indexOf(searchText),
          matchType: item.field_name === '*' ? 2 : fullText === searchText ? 2 : 1,
        });
      }
     
      const sortByMatch = (a, b) => {
        if (a.matchType !== b.matchType) {
          return b.matchType - a.matchType;
        }
        if (a.matchIndex !== b.matchIndex) {
          return a.matchIndex - b.matchIndex;
        }
        return a.matchIndex - b.matchIndex;
      };
    
    return fieldList.value.filter(filterFn).map(mapFn).sort(sortByMatch);
  });

  const handleBatchShowChange = val => {
    emit('batch-input-change', val);
  }

  const handleBatchInputChange = (selectData) => {
    condition.value.value = [...new Set([
      ...(condition.value.value || []), 
      ...selectData                    
    ])];
  };
  const tagValidateFun = item => {
    // 如果是数值类型， 返回一个检验的函数
    if (['long', 'integer', 'float'].includes(activeFieldItem.value.field_type)) {
      return /^-?\d+\.?\d*$/.test(item);
    }

    return true;
  };

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
    const matchedField = fieldList.value.find(field => field.field_name === (props.value as any).field);
    Object.assign(activeFieldItem.value, matchedField ?? {});
    const { operator, relation = 'OR', isInclude, value = [] } = (props.value ?? {}) as Record<string, any>;
    Object.assign(condition.value, { operator, relation, isInclude, value: [...value] });

    let filterIndex = filterFieldList.value.findIndex(
      (field: any) =>
        field.field_type === activeFieldItem.value.field_type && field.field_name === activeFieldItem.value.field_name,
    );

    if (filterIndex === -1) {
      Object.assign(activeFieldItem.value, filterFieldList.value[0]);
      Object.assign(condition.value, { operator: activeFieldItem.value.field_operator?.[0]?.operator });
      filterIndex = 0;
    }

    activeIndex.value = filterIndex;
  };

  /**
   * 接口返回结果是否为空
   */
  const isFieldListEmpty = computed(() => !indexFieldInfo.value.fields.length);
  const isSearchEmpty = computed(() => !isFieldListEmpty.value && !filterFieldList.value.length);
  const exceptionType = computed(() => (isFieldListEmpty.value ? 'empty' : 'search-empty'));

  /**
   * 全文检索输入是否为空值
   */
  const isFulltextInput = computed(() => typeof props.value === 'string' && props.value.length > 0);

  /**
   * 是否显示全文检索文本 & 快捷键使用说明
   * 如果当前是光标在input输入框之内 & 当前激活字段索引为0时，说明当前选中的是全文检索
   * 如果当前激活条目为IP目标，此时判定也为生效，用于展示IP选择器使用说明
   */
  const showFulltextMsg = computed(() => {
    return (
      activeFieldItem.value.field_name === '_ip-select_' ||
      (props.isInputFocus && activeFieldItem.value.field_name === '*')
    );
  });

  const setDefaultActiveIndex = () => {
    activeIndex.value = searchValue.value.length ? null : 0;
  };

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

  watch(
    searchValue,
    () => {
      nextTick(() => {
        setDefaultActiveIndex();
      });
    },
    { immediate: true },
  );

  const getFieldIcon = fieldType => {
    return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
  };

  const getFieldIconColor = type => {
    return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
  };

  const getFieldIconTextColor = type => {
    return fieldTypeMap.value?.[type]?.textColor;
  };

  const resetActiveFieldItem = () => {
    activeFieldItem.value = getFieldConditonItem();
    condition.value = getInputQueryDefaultItem();
    activeIndex.value = null;
  };

  const resetParams = () => {
    resetActiveFieldItem();
    searchValue.value = '';
    activeIndex.value = null;
    isConditionValueInputFocus.value = false;
  };

  const setFullTextFocus = () => {
    if (activeFieldItem.value.field_name === '*' && !isConditionValueInputFocus.value) {
      refFullTexarea?.value?.focus();
    }
  };

  /**
   * 字段列表点击事件
   * @param item 当前字段信息
   * @param index 当前字段索引信息
   * @param activeCondition 是否自动激活匹配值
   */
  const handleFieldItemClick = (item, index, activeCondition = true) => {
    conditionValueInputVal.value = '';

    // 避免重复提交设置
    if (!item || activeFieldItem.value.field_name === item?.field_name) {
      return;
    }

    resetActiveFieldItem();
    Object.assign(activeFieldItem.value, item);
    activeIndex.value = index;
    condition.value.operator = activeFieldItem.value.field_operator?.[0]?.operator;
    condition.value.relation = 'OR';
    condition.value.isInclude = ['text', 'string'].includes(activeFieldItem.value.field_type) ? false : null;

    if ((props.value as any).field === item.field_name) {
      restoreFieldAndCondition();
    }

    if (activeCondition) {
      handleConditionValueClick({ target: refConditionInput.value } as any, true);

      if (isValidateEgges(item)) {
        setIsRequesting(true);

        nextTick(() => {
          if (!conditionValueInstance.isShown()) {
            const target = refConditionInput.value?.parentNode;
            target && conditionValueInstance.show(target, true);
          }
        });

        if (isShowConditonValueSetting.value && hasConditionValueTip.value) {
          requestFieldEgges(item, null, () => {
            if (!conditionValueInstance.repositionTippyInstance()) {
              if (!isOperatorInstanceActive()) {
                if (!conditionValueInstance.isShown()) {
                  const target = refConditionInput.value?.parentNode;
                  target && conditionValueInstance.show(target, true);
                }
              }
            }
          });
        } else {
          conditionValueInstance.hide(100);
          setIsRequesting(false);
        }
      }
    }

    if (!isValidateEgges(item)) {
      conditionValueInstance.hide(100);
    }

    setFullTextFocus();
  };

  const handleCancelBtnClick = () => {
    resetParams();
    emit('cancel');
  };

  const handelSaveBtnClick = () => {
    if (!isSaveBtnActive.value) {
      return;
    }

    const isIpSelect = activeFieldItem.value.field_name === '_ip-select_';
    if (isIpSelect) {
      resetParams();
      emit('save', 'ip-select-show');
      return;
    }
    // 如果条件值为空 并且当前条件需要条件值
    // 禁止提交
    if (
      isShowConditonValueSetting.value &&
      !condition.value.value.length &&
      !showFulltextMsg.value &&
      !isFieldListEmpty.value &&
      !isFulltextInput.value &&
      !isSearchEmpty.value
    ) {
      return;
    }

    const isFulltextValue = activeFieldItem.value.field_name === '*';
    let result: any = {
      ...condition.value,
      field: activeFieldItem.value.field_name,
    };

    // 如果是全文检索 | 字段列表为空 | 搜索结果为空
    if (isFulltextValue || isFieldListEmpty.value || isSearchEmpty.value || isFulltextInput.value) {
      // 全文检索值为空，说明是是新增全文检索
      // 此时，检索值还在Input输入框内，这里result设置为 undefined；
      if (!condition.value.value.length) {
        result = undefined;
      }
    }

    // 如果是空操作符禁止提交
    // 或者当前校验不通过禁止提交
    if (
      (result && (!result.operator || (isShowConditonValueSetting.value && result.value.length === 0))) ||
      isExitErrorTag.value
    ) {
      return;
    }

    // 如果是不需要条件值，清理掉缓存的条件值
    if (!isShowConditonValueSetting.value) {
      result.value = [];
    }

    resetParams();
    emit('save', result);
  };

  const refValueTagInput: Ref<HTMLInputElement | null> = ref(null);
  const isConditionValueInputFocus = ref(false);
  const conditionValueActiveIndex: Ref<number | null> = ref(-1);
  const conditionValueInputVal = ref('');

  /**
   * 获取当前选中字段的匹配列表
   */
  const activeItemMatchList = computed(() => {
    return (store.state.indexFieldInfo.aggs_items[activeFieldItem.value.field_name] ?? []).filter(
      item => !(condition.value.value ?? []).includes(item),
    );
  });

  /**
   * 判定当前如果展示空状态
   * 判定是搜索为空还是数据为空
   */
  const conditionValueEmptyType = computed(() => {
    if (!(store.state.indexFieldInfo.aggs_items[activeFieldItem.value.field_name] ?? []).length) {
      return 'empty';
    }

    if (conditionValueInputVal.value.length) {
      return 'search-empty';
    }

    return 'empty';
  });

  const currentEditTagIndex: Ref<number | null> = ref(null);

  const handleConditonValueTagItemClick = () => {
    isConditionValueInputFocus.value = true;

    tagInputTimer && clearTimeout(tagInputTimer);
    tagInputTimer = null;
  };

  const handleEditTagDBClick = (e, tagContent, tagIndex) => {
    const parent = e.target.parentNode;
    tagInputTimer && clearTimeout(tagInputTimer);
    tagInputTimer = null;

    currentEditTagIndex.value = tagIndex;
    setTimeout(() => {
      parent.querySelector('.tag-item-input').focus();
    }, 500);
  };

  const handleConditionValueClick = (e?: MouseEvent, autoFocus = false) => {
    conditionValueInstance.cancelHide();
    conditionBlurTimer && clearTimeout(conditionBlurTimer);
    conditionBlurTimer = null;

    // tag-item-input edit-input
    if (!e || (e.target as HTMLElement)?.classList?.contains('edit-input')) {
      return;
    }

    conditionValueActiveIndex.value = null;

    if (autoFocus) {
      refValueTagInput?.value?.focus();
      conditionValueActiveIndex.value = 0;
    }

    if (activeItemMatchList.value.length > 0) {
      if (!conditionValueInstance.isShown()) {
        const target = refConditionInput.value?.parentNode;
        conditionValueInstance.show(target, true);
      }
    }
  };

  let tagInputTimer: NodeJS.Timeout | null = null;

  const handleTagInputBlur = () => {
    currentEditTagIndex.value = null;

    tagInputTimer = setTimeout(() => {
      isConditionValueInputFocus.value = false;
    }, 300);
  };

  const handleTagInputEnter = () => {
    currentEditTagIndex.value = null;
  };
  /**
   * 当前快捷键操作是否命中条件相关弹出
   */
  const isConditionValueFocus = () => {
    const instance = conditionValueInstance.getTippyInstance();
    return isConditionValueInputFocus.value && instance?.state.isShown;
  };

  const handleInputValueChange = e => {
    const input = e.target;
    const value = input.value;
    const charLen = Math.max(getCharLength(value), 1);

    input.style.setProperty('width', `${charLen * INPUT_MIN_WIDTH}px`);
    conditionValueInputVal.value = input.value;

    // 如果当前输入框有值，此时设置当前Active Index为null
    // 避免Enter时校验 conditionValueActiveIndex 所对应的值
    if (conditionValueInputVal.value.length) {
      conditionValueActiveIndex.value = null;
    }

    // 如果当前输入框没有值，此时设置当前Active Index为0， 默认选中第一个
    if (conditionValueActiveIndex.value === null && conditionValueInputVal.value.length === 0) {
      conditionValueActiveIndex.value = 0;
    }

    if (!isValidateEgges(activeFieldItem.value)) {
      if (conditionValueInputVal.value.length) {
        const target = refConditionInput.value?.parentNode;
        if (target) {
          conditionValueInstance.show(target, true);
        }
        return;
      }

      conditionValueInstance.hide(100);
      return;
    }

    setIsRequesting(true);

    const target = refConditionInput.value?.parentNode;
    if (!operatorInstance.isShown() && target) {
      nextTick(() => {
        conditionValueInstance.show(target, true);
      });
    }

    requestFieldEgges(activeFieldItem.value, conditionValueInputVal.value, () => {
      if (!operatorInstance.isShown()) {
        conditionValueInstance.repositionTippyInstance();

        if (!conditionValueInstance.isShown() && !conditionValueInstance.isInstanceShowing()) {
          if (target) {
            conditionValueInstance.show(target, true);
          }
        }
      }
    });
  };

  const handleConditionValueInputFocus = e => {
    isConditionValueInputFocus.value = true;
    conditionBlurTimer && clearTimeout(conditionBlurTimer);
    conditionBlurTimer = null;

    // handleConditionValueClick(e);
  };

  const handleDeleteTagItem = index => {
    condition.value.value.splice(index, 1);
  };

  const handleOperatorBtnClick = () => {
    operatorInstance.show(refUiValueOperator.value);
    setTimeout(() => {
      conditionValueInstance.hide(100);
    });
  };

  const appendConditionValue = value => {
    if (!condition.value.value.includes(value)) {
      condition.value.value.push(value);
      return true;
    }

    return false;
  };

  /**
   * 点击条件值下拉选项
   * 如果条件列表已有此值，取消选中
   * @param {*} value
   * @param {*} index
   */
  const handleTagItemClick = (value, index) => {
    refValueTagInput.value.value = '';
    conditionValueInputVal.value = '';
    conditionBlurTimer && clearTimeout(conditionBlurTimer);
    conditionBlurTimer = null;

    if (!appendConditionValue(value)) {
      condition.value.value.splice(index, 1);
    }
  };

  /**
   * 通用方法：根据键盘上下键操作，设置对应参数当前激活Index的值
   */
  const setActiveObjectIndex = (objIndex, matchList, isIncrease = true) => {
    const maxIndex = matchList.length - 1;
    if (objIndex.value === null) {
      objIndex.value = -1;
    }

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
    return (
      operatorInstance.isInstanceShowing() ||
      (operatorInstance.isShown() && activeFieldItem.value.field_operator?.length)
    );
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

  /**
   * 键盘enter键事件处理
   */
  const resolveConditonValueInputEnter = () => {
    // 判断当前操作符选择下拉是否激活
    if (isOperatorInstanceActive()) {
      operatorInstance?.hide();
      afterOperatorValueEnter();
      return;
    }

    // 如果需要设置条件
    // 条件选择或者输入框已经渲染出来
    if (
      refValueTagInput.value &&
      !isSearchEmpty.value &&
      !isFieldListEmpty.value &&
      activeIndex.value !== null &&
      activeIndex.value >= 0
    ) {
      const instance = conditionValueInstance.getTippyInstance();

      // 如果当前没有自动focus条件选择
      if (!isConditionValueInputFocus.value) {
        handleConditionValueClick({ target: refConditionInput.value } as any, true);
        return;
      }

      // 如果是条件选择下拉已经展开，查询当前选中项
      if (instance?.state.isShown && conditionValueActiveIndex.value >= 0) {
        const val = activeItemMatchList.value[conditionValueActiveIndex.value];
        if (val !== undefined) {
          handleTagItemClick(val, conditionValueActiveIndex.value);
          refValueTagInput.value.value = '';

          // 自动选中条件值列表的下一步个匹配项
          setConditionValueActiveIndex(true);

          // 设置当前行样式，避免Vue实例渲染，这里直接操作DOM进行class赋值
          // activeConditionValueOption();
          return;
        }
      }

      // 如果有可以自动联想的内容 & 没有自动展开下拉提示
      // 此时，自动展开下拉提示
      if (!instance?.state.isShown && activeItemMatchList.value.length) {
        handleConditionValueClick({ target: refConditionInput.value } as any);
      }

      // 如果是条件输入框内有数据执行数据填入操作
      // 清空输入框
      if (refValueTagInput.value.value) {
        appendConditionValue(refValueTagInput.value.value);
        refValueTagInput.value.value = '';
        return;
      }
      return;
    }

    setFullTextFocus();
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
    if (filterFieldList.value.length && !isConditionValueFocus() && !isOperatorInstanceActive()) {
      if (activeIndex.value < filterFieldList.value.length && activeIndex.value >= 0) {
        handleFieldItemClick(filterFieldList.value[activeIndex.value], activeIndex.value, false);
        scrollActiveItemIntoView();
        return;
      }
    }
  };

  const handleArrowUpKeyEvent = () => {
    if (isConditionValueFocus()) {
      setConditionValueActiveIndex(false);
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
      return;
    }

    if (isOperatorInstanceActive()) {
      setOperatorActiveIndex(true);
      return;
    }

    setFieldListActiveIndex(true);
    handleFieldListKeyupAndKeydown();
  };

  const handleEscKeyEvent = e => {
    if (isConditionValueFocus()) {
      stopEventPreventDefault(e);
      refValueTagInput?.value.blur();
      conditionValueInstance.hide(100);
      return;
    }

    if (isOperatorInstanceActive()) {
      stopEventPreventDefault(e);
      operatorInstance?.hide();
      return;
    }

    return;
  };

  const stopEventPreventDefault = e => {
    e.stopPropagation?.();
    e.preventDefault?.();
    e.stopImmediatePropagation?.();
  };

  const handleKeydownClick = e => {
    // key arrow-up
    if (e.keyCode === 38) {
      stopEventPreventDefault(e);
      handleArrowUpKeyEvent();
      return;
    }

    // key arrow-down
    if (e.keyCode === 40) {
      stopEventPreventDefault(e);
      handleArrowDownKeyEvent();
      return;
    }

    // ctrl + enter  e.ctrlKey || e.metaKey兼容Mac的Command键‌
    if ((e.ctrlKey || e.metaKey) && e.keyCode === 13) {
      stopEventPreventDefault(e);
      handelSaveBtnClick();
      return;
    }

    // key enter
    if (e.keyCode === 13 || e.code === 'NumpadEnter') {
      stopEventPreventDefault(e);
      resolveConditonValueInputEnter();
      return;
    }

    // key esc
    if (e.keyCode === 27) {
      handleEscKeyEvent(e);
      return;
    }
  };

  const handleUiValueOptionClick = option => {
    if (condition.value.operator !== option.operator) {
      condition.value.operator = option.operator;
    }
    operatorInstance.hide();
    afterOperatorValueEnter();
  };

  let isMountedEventAdded = false;

  const beforeShowndFn = () => {
    if (!isMountedEventAdded) {
      isMountedEventAdded = true;
      setDefaultActiveIndex();
      document.addEventListener('keydown', handleKeydownClick, { capture: true });
      document.addEventListener('click', handleDocumentClick);

      restoreFieldAndCondition();
      scrollActiveItemIntoView();

      nextTick(() => {
        // 如果是外层检索输入，这里不能自动focus到搜索
        if (!props.isInputFocus) {
          refFilterInput.value?.focus();
        }
      });
    }

    return true;
  };

  const afterHideFn = () => {
    document.removeEventListener('keydown', handleKeydownClick, { capture: true });
    document.removeEventListener('click', handleDocumentClick);
    isMountedEventAdded = false;
    resetParams();
  };

  const handleValueInputEnter = e => {
    stopEventPreventDefault(e);
    conditionValueInputVal.value = '';

    if (e.target.value) {
      const value = e.target.value;
      e.target.value = '';
      appendConditionValue(value);
    }

    handleInputValueChange(e);
  };

  const handleConditionValueInputBlur = e => {
    conditionBlurTimer && clearTimeout(conditionBlurTimer);
    conditionBlurTimer = setTimeout(() => {
      isConditionValueInputFocus.value = false;
      conditionValueInputVal.value = '';
      e.target.value = '';
      conditionValueInstance.hide();
    }, 180);
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

  const handleOptionListMouseEnter = (e, item) => {
    const { offsetWidth, scrollWidth } = e.target.lastElementChild;
    if (offsetWidth < scrollWidth) {
      fieldOptionListInstance.setContent(
        `${item.query_alias || item.field_alias || item.field_name}(${item.field_name})`,
      );
      fieldOptionListInstance.show(e.target);
    }
  };
  const handleOptionListMouseLeave = () => {
    fieldOptionListInstance.uninstallInstance();
  };

  const handleCustomTagItemClick = () => {
    conditionBlurTimer && clearTimeout(conditionBlurTimer);
    handleValueInputEnter({ target: refValueTagInput.value });
  };

  const handleDocumentClick = e => {
    if (
      refSearchResultList?.value?.contains(e.target) ||
      refConditionInput?.value?.contains(e.target) ||
      refValueTagInputOptionList?.value?.contains(e.target) ||
      refValueTagInputOptionList?.value?.contains(e.target)
    ) {
      return;
    }

    if (conditionValueInstance?.isShown()) {
      conditionValueInstance?.hide(100);
    }
  };

  onBeforeUnmount(() => {
    afterHideFn();
    fieldOptionListInstance.uninstallInstance();
    operatorInstance.uninstallInstance();
    conditionValueInstance.uninstallInstance();
  });

  defineExpose({
    beforeShowndFn,
    afterHideFn,
  });
</script>
<template>
  <div class="ui-query-options">
    <div class="ui-query-option-content">
      <div class="field-list">
        <div class="ui-search-input">
          <bk-input
            ref="refFilterInput"
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
          class="ui-search-result bklog-v3-popover-tag"
        >
          <div
            v-for="(item, index) in filterFieldList"
            :class="['ui-search-result-row', { active: activeIndex === index }]"
            :data-tab-index="index"
            :key="item.field_name"
            @click="() => handleFieldItemClick(item, index, true)"
            @mouseenter="e => handleOptionListMouseEnter(e, item)"
            @mouseleave="handleOptionListMouseLeave"
          >
            <span
              :style="{
                backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type),
                color: item.is_full_text ? false : getFieldIconTextColor(item.field_type),
              }"
              :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
            >
            </span>
            <div
              class="display-container rtl-text"
              :dir="textDir"
            >
              <bdi>
                <span class="field-alias">
                  {{ item.first_name }}
                </span>
                <span
                  v-if="!item.is_full_text && item.first_name !== item.last_name"
                  class="field-name"
                >
                  ({{ item.last_name }})
                </span>
              </bdi>
            </div>
          </div>
          <template v-if="isFieldListEmpty || isSearchEmpty">
            <bk-exception
              style="justify-content: center; height: 260px"
              :type="exceptionType"
              scene="part"
            >
            </bk-exception>
          </template>
        </div>
      </div>
      <div :class="['value-list', { 'is-full-text': showFulltextMsg }]">
        <template v-if="isSearchEmpty">
          <bk-exception
            style="justify-content: center; height: 260px"
            scene="part"
            type="500"
          >
            搜索为空，无需条件设置
          </bk-exception>
        </template>
        <template v-else-if="showFulltextMsg">
          <template v-if="activeIndex === 0 || activeIndex === null">
            <div class="full-text-title">{{ $t('全文检索') }}</div>
            <div class="full-text-sub-title">
              <img :src="svgImg.imgEnterKey" /><span>{{ getOsCommandLabel() }}+ Enter</span>
            </div>
            <div class="full-text-content">
              {{ $t('输入文本后按') }} [{{ getOsCommandLabel() }}+ Enter] {{ $t('键进行检索') }}
            </div>
            <div class="full-text-sub-title">
              <img :src="svgImg.imgUpDownKey" /><span>{{ $t('上下键') }}</span>
            </div>
            <div class="full-text-content">{{ $t('可通过上下键快速切换选择字段值') }}</div>
          </template>
          <template v-if="activeIndex === filterFieldList.length - 1 && !isNotIpSelectShow">
            <div class="full-text-title">{{ $t('IP目标') }}</div>
            <div class="full-text-content">
              {{ $t('平台获取蓝鲸 CMDB 主机信息，您可通过 IP 选择器选择主机，快速过滤日志') }}
            </div>
            <div class="full-text-sub-title">
              <img :src="svgImg.imgEnterKey" /><span>{{ $t('Enter 键') }}</span>
            </div>
            <div class="full-text-content">{{ $t('【Enter】唤起IP选择器，点击取消关闭窗口') }}</div>
          </template>
        </template>
        <template v-else>
          <div
            v-if="activeFieldItem.field_name !== '*'"
            class="ui-value-row"
          >
            <div class="ui-value-label">{{ $t('条件') }}</div>
            <div class="ui-value-component">
              <div
                ref="refUiValueOperator"
                class="ui-value-operator"
                @click.stop="handleOperatorBtnClick"
              >
                <span class="operator-content">
                  {{ getOperatorLable(activeOperator.label) }}
                </span>
                <bk-icon :type="isArrowDown ? 'angle-down' : 'angle-up'" />
              </div>
              <div style="display: none">
                <div
                  ref="refUiValueOperatorList"
                  class="ui-value-select"
                >
                  <div
                    v-if="!activeFieldItem.field_operator.length"
                    class="empty-section"
                  >
                    <bk-exception
                      style="height: 94px"
                      :type="conditionValueEmptyType"
                      scene="part"
                    >
                    </bk-exception>
                  </div>
                  <template v-else>
                    <div
                      v-for="option in activeFieldItem.field_operator"
                      :class="['ui-value-option', { active: condition.operator === option.operator }]"
                      :key="option.operator"
                      @click="() => handleUiValueOptionClick(option)"
                    >
                      {{ getOperatorLable(option.label) }}
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
          <div
            v-if="isShowConditonValueSetting"
            class="ui-value-row"
          >
            <div class="ui-value-label">
              <span>
                {{ $t('检索内容') }}
                <BatchInput  v-if="activeFieldItem.field_name !== '*'" @value-change="handleBatchInputChange" @show-change="handleBatchShowChange"/>
              </span>
              <span v-show="['text', 'string'].includes(activeFieldItem.field_type)">
                <bk-checkbox v-model="condition.isInclude">{{ $t('使用通配符') }}</bk-checkbox>
              </span>
            </div>
            <template v-if="activeFieldItem.field_name === '*'">
              <bk-input
                ref="refFullTexarea"
                class="ui-value-search-textarea"
                v-model="condition.value[0]"
                :rows="12"
                maxlength="100"
                type="textarea"
              ></bk-input>
            </template>
            <div
              v-else
              :class="['condition-value-container', { 'is-focus': isConditionValueInputFocus }]"
            >
              <ul
                ref="refConditionInput"
                :style="{ maxHeight: isConditionValueInputFocus ? '300px' : '90px' }"
                class="condition-value-input"
                @click.stop="e => handleConditionValueClick(e, true)"
              >
                <li
                  v-for="(item, index) in condition.value"
                  class="tag-item"
                  :class="!tagValidateFun(item) ? 'tag-validate-error' : ''"
                  :key="`-${index}`"
                >
                  <template v-if="currentEditTagIndex === index">
                    <textarea
                      class="tag-item-input edit-input"
                      v-model="condition.value[index]"
                      type="text"
                      @focus.stop="handleConditionValueInputFocus"
                      @blur.stop="handleTagInputBlur"
                      @input="handleInputValueChange"
                      @keyup.enter="handleTagInputEnter"
                    />
                  </template>
                  <template>
                    <span
                      class="tag-item-text"
                      @click.stop="handleConditonValueTagItemClick"
                      @dblclick.stop="e => handleEditTagDBClick(e, item, index)"
                      >{{ formatDateTimeField(item, activeFieldItem.field_type) }}</span
                    >
                    <span
                      class="tag-item-del bk-icon icon-close"
                      @click.stop="e => handleDeleteTagItem(index)"
                    ></span>
                  </template>
                </li>
                <li class="tag-item no-selected-tag-item">
                  <input
                    ref="refValueTagInput"
                    class="tag-option-focus-input"
                    type="text"
                    @input="handleInputValueChange"
                    @keyup.delete="handleDeleteInputValue"
                    @keyup.enter="handleValueInputEnter"
                    @blur.stop="handleConditionValueInputBlur"
                    @focus.stop="handleConditionValueInputFocus"
                  />
                </li>
                <div style="display: none">
                  <ul
                    ref="refValueTagInputOptionList"
                    class="condition-value-options"
                  >
                    <li
                      v-show="conditionValueInputVal.length > 0"
                      :class="{ active: conditionValueInputVal.length > 0, 'is-custom-tag': true }"
                      @click.stop="handleCustomTagItemClick"
                    >
                      {{ $t('生成“{n}”标签', { n: conditionValueInputVal }) }}
                    </li>
                    <li
                      v-show="isRequesting || activeItemMatchList.length === 0"
                      v-bkloading="{ isLoading: isRequesting, size: 'small' }"
                      style="min-height: 32px"
                    >
                      {{ $t('暂无数据') }}
                    </li>

                    <template v-if="!isRequesting && activeItemMatchList.length > 0">
                      <li
                        v-for="(item, index) in activeItemMatchList"
                        :class="{
                          active: (condition.value ?? []).includes(item),
                          'is-system-tag': true,
                          'is-hover': index === conditionValueActiveIndex && isConditionValueInputFocus,
                        }"
                        :key="`${item}-${index}`"
                        :title="formatDateTimeField(item, activeFieldItem.field_type)"
                        @click.stop="() => handleTagItemClick(item, index)"
                      >
                        <div>{{ formatDateTimeField(item, activeFieldItem.field_type) }}</div>
                      </li>
                    </template>
                  </ul>
                </div>
              </ul>
            </div>
          </div>
          <div
            v-if="isExitErrorTag"
            class="tag-error-text"
          >
            {{ $t('仅支持输入数值类型') }}
          </div>
          <div
            class="ui-value-row"
            v-show="condition.value.length > 1 && activeFieldItem.field_type === 'text'"
          >
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
        <div class="ui-shortcut-item">
          <span class="bklog-icon bklog-arrow-down-filled label up" />
          <span class="bklog-icon bklog-arrow-down-filled label" />
          <span class="value">{{ $t('移动光标') }}</span>
        </div>
        <div class="ui-shortcut-item">
          <span class="label">Enter</span>
          <span class="value">{{ $t('选中') }}</span>
        </div>
        <div class="ui-shortcut-item">
          <span class="label">Esc</span>
          <span class="value">{{ $t('收起查询') }}</span>
        </div>
        <div class="ui-shortcut-item">
          <span class="label">{{ getOsCommandLabel() }} +Enter</span>
          <span class="value">{{ $t('提交查询') }}</span>
        </div>
      </div>
      <div class="ui-btn-opts">
        <bk-button
          style="padding: 0 4px; margin-right: 8px"
          class="save-btn"
          :disabled="!isSaveBtnActive"
          theme="primary"
          @click.stop="handelSaveBtnClick"
        >
          {{ $t('确定') }} {{ getOsCommandLabel() }} + Enter
        </bk-button>
        <bk-button
          class="cancel-btn"
          @click="handleCancelBtnClick"
          >{{ $t('取消') }}</bk-button
        >
      </div>
    </div>
  </div>
</template>
<style scoped lang="scss">
  @import './ui-input-option.scss';
</style>
