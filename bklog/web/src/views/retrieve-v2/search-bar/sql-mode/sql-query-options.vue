<script lang="ts" setup>
import { ComputedRef, Ref, computed, nextTick, ref, watch } from 'vue';

import useFieldNameHook from '@/hooks/use-field-name';
// @ts-ignore
import useLocale from '@/hooks/use-locale';
// @ts-ignore
import useStore from '@/hooks/use-store';

import jsCookie from 'js-cookie';
// @ts-ignore
import { debounce } from 'lodash-es';

import { getOsCommandLabel } from '@/common/util';
import useFieldEgges from '@/hooks/use-field-egges';
import { FieldInfoItem } from '@/store/store.type';
import { excludesFields } from '../utils/const.common'; // @ts-ignore
import FavoriteList from '../components/favorite-list';

const props = defineProps({
  value: {
    type: String,
    default: '',
    required: true,
  },
  focusPosition: {
    type: Number,
    default: null,
  },
});

const emits = defineEmits(['change', 'cancel', 'retrieve', 'active-change', 'text-to-query']);

const store = useStore();
const { $t } = useLocale();
const { getQualifiedFieldName, getQualifiedFieldAttrs } = useFieldNameHook({ store });

const shortCutClsName = computed(() => {
  const iconMap = {
    cmd: 'bklog-icon bklog-command',
    ctrl: 'bklog-icon bklog-ctrl',
  };

  const osName = getOsCommandLabel()?.toLocaleLowerCase() ?? 'ctrl';

  return iconMap[osName] ?? iconMap.ctrl;
});

/**
 * @description 是否显示 AI 助手快捷键提示
 * @returns {boolean}
 */
const isAiAssistantActive = computed(() => store.state.features.isAiAssistantActive);

// eslint-disable-next-line no-unused-vars
enum OptionItemType {
  // eslint-disable-next-line no-unused-vars
  Colon = 'Colon',
  // eslint-disable-next-line no-unused-vars
  Continue = 'Continue',
  // eslint-disable-next-line no-unused-vars
  Fields = 'Fields',
  // eslint-disable-next-line no-unused-vars
  Operator = 'Operator',
  // eslint-disable-next-line no-unused-vars
  Value = 'Value',
}

// 定义一个类型来表示生成对象的类型
type ShowOptionValueType = {
  [K in keyof typeof OptionItemType as `show${(typeof OptionItemType)[K]}`]: boolean;
};

const defShowOptionValueType: Partial<ShowOptionValueType> = {};
const showOption = computed(() => {
  return Object.values(OptionItemType).reduce(
    (output, key) => ({
      ...output,
      [`show${key}`]: activeType.value.includes(key),
    }),
    defShowOptionValueType,
  );
});

const retrieveDropdownData = computed(() => store.state.retrieveDropdownData);
const totalFields: ComputedRef<FieldInfoItem[]> = computed(() => store.state.indexFieldInfo.fields);

const { isRequesting, requestFieldEgges, isValidateEgges } = useFieldEgges();

/** 获取数字类型的字段name */
const getNumTypeFieldList = computed(() => {
  return totalFields.value
    .filter(item => ['long', 'integer', 'float'].includes(item.field_type))
    .map(item => item.field_name);
});

/**
 * @description 是否显示 AI 助手
 * @returns {boolean}
 */
const showAiAssistant = computed(() => {
  return props.value.length > 0;
});

/**
 * @description AI 预览文本
 * @returns {string}
 */
// const aiPreviewText = computed(() => {
//   return props.value;
// });

/** 所有字段的字段名 */
const totalFieldsNameList = computed(() => {
  const filterFn = field => field.field_type !== '__virtual__' && !excludesFields.includes(field.field_name);
  return totalFields.value.filter(filterFn).map((fieldInfo: FieldInfoItem) => fieldInfo.field_name);
});

// 检索后的日志数据如果字段在字段接口找不到则不展示联想的key
const originFieldList = () => totalFieldsNameList.value;

const activeType: Ref<string[]> = ref([]);
// const separator = /\s+(AND\s+NOT|OR|AND)\s+/i; // 区分查询语句条件
const fieldList: Ref<string[]> = ref([]);
const valueList: Ref<string[]> = ref([]);

const refDropdownEl: Ref<HTMLElement | null> = ref(null);
const activeIndex: Ref<number | null> = ref(null);

const operatorSelectList = ref([
  {
    operator: '>',
    label: $t('大于'),
  },
  {
    operator: '<',
    label: $t('小于'),
  },
  {
    operator: '>=',
    label: $t('大于或等于'),
  },
  {
    operator: '<=',
    label: $t('小于或等于'),
  },
]);

const setOptionActive = () => {
  const dropdownList = refDropdownEl?.value?.querySelectorAll('.list-item');
  refDropdownEl?.value?.querySelector('.list-item.active')?.classList.remove('active');
  if (activeIndex.value === null) {
    return;
  }

  dropdownList?.[activeIndex.value]?.classList.add('active');
};

/**
   * 显示哪个下拉列表
   * @param {String} [param]
   */
const showWhichDropdown = (param?: OptionItemType[] | string) => {
  activeType.value.length = 0;
  activeType.value = [];
  if (typeof param === 'string') {
    activeType.value.push(param);
  }

  if (Array.isArray(param)) {
    activeType.value.push(...param);
  }
  activeIndex.value = null;
};

/**
   * 获取某个字段可选的值列表
   * @param {Object} valueMap
   * @return {string[]}
   */
const getValueList = (valueMap: { __fieldType?: any }) => {
  const resolveValueMap = valueMap ?? {};
  let valueMapList = Object.keys(resolveValueMap);
  if (resolveValueMap.__fieldType === 'string') {
    valueMapList = valueMapList // 清除mark标签
      .map(item => `"${item.replace(/<mark>/g, '').replace(/<\/mark>/g, '')}"`);
  }
  return [...new Set(valueMapList)]; // 清除重复的字段
};

const setValueList = (fieldName: string, value: string) => {
  const fieldInfo = totalFields.value.find(item => item.field_name === fieldName);
  if (fieldInfo && isValidateEgges(fieldInfo)) {
    valueList.value = [];
    requestFieldEgges(fieldInfo, value, (resp) => {
      if (typeof resp === 'boolean') {
        valueList.value = getValueList(retrieveDropdownData.value[fieldName] ?? {});
        return;
      }

      valueList.value = store.state.indexFieldInfo.aggs_items[fieldName] ?? [];
    });
    return;
  }

  valueList.value = (getValueList(retrieveDropdownData.value[fieldName] ?? {}) ?? [])
    .filter(item => item?.indexOf(value) !== -1);
};

/**
   * @desc: 当前是否是数字类型字段
   * @param {string} fieldStr 字段名
   * @returns {boolean}
   */
const isNumTypeField = (fieldStr = '') => {
  return getNumTypeFieldList.value.includes(fieldStr);
};

const showColonOperator = (inputField: string) => {
  const showVal = [OptionItemType.Colon];

  if (isNumTypeField(inputField?.trim())) {
    showVal.push(OptionItemType.Operator);
  }
  // 完全匹配字段同时和 : :* 选项
  showWhichDropdown(showVal);
};

/**
   * @description 获取当前输入框左侧内容
   */
const getFocusLeftValue = () => {
  if (props.focusPosition !== null && props.focusPosition >= 0) {
    return props.value.slice(0, props.focusPosition);
  }

  return props.value;
};

const getFocusRightValue = () => {
  if (props.focusPosition !== null && props.focusPosition >= 0) {
    return props.value.slice(props.focusPosition);
  }

  return '';
};

const emitValueChange = (appendValue: string,
  retrieve = false,
  replace = false,
  focusPosition: number | undefined = undefined,
) => {
  emits('change', appendValue, retrieve, replace, focusPosition);
};

// 如果是当前位置 AND | OR | AND NOT 结尾
const regExpAndOrNot = /\s(AND|OR|AND\s+NOT)\s*$/i;

// 如果当前位置是 : 结尾，说明需要显示字段值列表
const regExpFieldValue = /(:\s*)$/;

// 根据当前输入关键字计算提示内容
const calculateDropdown = () => {
  if (!originFieldList().length) {
    return;
  }

  fieldList.value.length = 0;
  fieldList.value = [];

  const value = getFocusLeftValue();

  if (!value.length) {
    showWhichDropdown('Fields');
    fieldList.value.push(...originFieldList());
    return;
  }

  const isEndOrNot = regExpAndOrNot.test(value);
  const isEndWidthEmpty = /\s+$/.test(value);

  // 如果是以 AND | OR | AND NOT 结尾，弹出 Feidl选择
  if (isEndOrNot) {
    if (isEndWidthEmpty) {
      showWhichDropdown('Fields');

      fieldList.value.push(...originFieldList());
      return;
    }

    showWhichDropdown();
    return;
  }

  const lastFragments = value.split(/\s+(AND\s+NOT|OR|AND)\s+/i);
  const lastFragment = lastFragments?.[lastFragments.length - 1] ?? '';

  // 如果是以 : 结尾，说明需要显示字段值列表
  if (regExpFieldValue.test(value)) {
    const confirmField = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*$/.exec(lastFragment)?.groups?.field;

    if (confirmField) {
      showWhichDropdown(OptionItemType.Value);
      setValueList(confirmField, '');
      return;
    }

    showWhichDropdown();
    return;
  }

  const lastValues = /(:|>=|<=|>|<)\s*(\d+|\w+|"((?:[^"\\]|\\.)*)"?)/.exec(lastFragment);
  const matchValue = lastValues?.[3] ?? lastValues?.[2];
  const matchValueWithQuotes = lastValues?.[2];

  if (matchValueWithQuotes && lastFragment.length >= (matchValue?.length ?? 0)) {
    const lastValue = lastFragment.slice(0, lastFragment.length - matchValueWithQuotes.length);
    const confirmField = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*$/.exec(lastValue)?.groups?.field;

    if (confirmField) {
      showWhichDropdown(OptionItemType.Value);
      setValueList(confirmField, matchValue ?? '');
      return;
    }
  }

  // 如果是空格 & 已有条件不为空，追加弹出 AND OR 等连接符
  if (/\S+\s+$/.test(value)) {
    showWhichDropdown(OptionItemType.Continue);
    return;
  }

  if (lastFragment && totalFieldsNameList.value.includes(lastFragment)) {
    showColonOperator(lastFragment);
    return;
  }

  // 开始输入字段【nam】
  const inputField = /^\s*(?<field>[\w.]+)$/.exec(lastFragment)?.groups?.field;
  if (inputField) {
    fieldList.value = originFieldList()
      .reduce((acc: { index: number; fieldName: string }[], item) => {
        const { field_name: fieldName, is_virtual_alias_field: isVirtualAliasField } = getQualifiedFieldAttrs(item, totalFields.value, false, ['is_virtual_alias_field']);
        const index = fieldName.toLowerCase().indexOf(inputField.toLowerCase());
        if (index >= 0) {
          acc.push({ index: index * 10 - (isVirtualAliasField ? 1 : 0), fieldName: item });
        }
        return acc;
      }, [])
      .sort((a, b) => a.index - b.index)
      .map(item => item.fieldName);
    if (fieldList.value.length) {
      showWhichDropdown(OptionItemType.Fields);
      return;
    }
  }

  showWhichDropdown();
};

const setNextActive = () => {
  nextTick(() => {
    activeIndex.value = null;
    setOptionActive();
  });
};

/**
 * 选择某个可选字段
 * @param {string} field
 */
const handleClickField = (field: string) => {
  const sqlValue = getFocusLeftValue();
  const lastFieldStr = sqlValue.split(/\s+(AND\s+NOT|OR|AND)\s+/i)?.pop() ?? '';
  let leftValue = sqlValue.slice(0, sqlValue.length - lastFieldStr.replace(/^\s/, '').length);

  if (leftValue.length && !/\s$/.test(leftValue)) {
    leftValue = `${leftValue} `;
  }

  const isEndWithConnection = regExpAndOrNot.test(leftValue);

  const rightValue = getFocusRightValue();

  const rightEndPosition = isEndWithConnection ? 0 : rightValue.indexOf(':');
  const targetPosition = rightEndPosition >= 0 ? rightEndPosition : 0;
  const rightFieldStr = rightValue.slice(targetPosition);
  const result = `${leftValue}${field}${rightFieldStr}`;

  emitValueChange(result, false, true, leftValue.length + field.length);
  showColonOperator(field as string);
  setNextActive();
};

/**
   * 选择 : 或者 :*
   * @param {string} type
   */
const handleClickColon = (type: string) => {
  let target = type;
  if (type === ': *') {
    target = `${target} `;
  }

  const sqlValue = getFocusLeftValue();
  const rightValue = getFocusRightValue();
  const result = `${sqlValue}${target}${rightValue}`;

  emitValueChange(result, false, true, sqlValue.length + target.length);
  calculateDropdown();
  setNextActive();
};

/**
   * 选择某个字段可选值
   * @param {string} value
   */
const handleClickValue = (value: string) => {
  const sqlValue = getFocusLeftValue();
  const rightValue = getFocusRightValue();
  const lastFragment = sqlValue.split(/\s+(AND\s+NOT|OR|AND)\s+/i)?.pop() ?? '';

  const lastValues = /(:|>=|<=|>|<)\s*(\d+|\w+|"((?:[^"\\]|\\.)*)"?)/.exec(lastFragment);
  const matchValueWithQuotes = lastValues?.[2] ?? '';
  const matchLeft = sqlValue.slice(0, sqlValue.length - matchValueWithQuotes.length);
  const targetValue = value.replace(/^"|"$/g, '').replace(/"/g, '\\"');

  const rightFirstValue =      matchValueWithQuotes.length >= 1 ? rightValue.split(/\s+(AND\s+NOT|OR|AND)\s+/i)?.shift() ?? '' : '';

  const formatRightValue = `${rightValue.slice(rightFirstValue.length).replace(/\s+$/, '')}`;
  const appendSpace = formatRightValue === '' ? ' ' : '';
  const result = `${matchLeft}"${targetValue}"${formatRightValue}${appendSpace}`;
  const focusPosition = matchLeft.length + targetValue.length + 3;

  // 当前输入值可能的情况 【name:"a】【age:】
  emitValueChange(result, false, true, focusPosition);
  setNextActive();
};

/**
   * 选择 AND 或者 OR
   * @param {string} type
   */
const handleClickContinue = (type: string) => {
  const sqlValue = getFocusLeftValue();
  const rightValue = getFocusRightValue();
  const result = `${sqlValue}${type} ${rightValue}`;
  emitValueChange(result, false, true, sqlValue.length + type.length + 1);
  showWhichDropdown(OptionItemType.Fields);
  fieldList.value = [...originFieldList()];
  setNextActive();
};

const scrollActiveItemIntoView = () => {
  if ((activeIndex.value ?? -1) >= 0) {
    const target = refDropdownEl.value?.querySelector('.list-item.active');
    target?.scrollIntoView({ block: 'nearest' });
  }
};

const stopEventPreventDefault = (e) => {
  e.stopPropagation();
  e.preventDefault();
  e.stopImmediatePropagation();
};

const handleKeydown = (e: {
    preventDefault?: any;
    code?: any;
    ctrlKey?: boolean;
    metaKey: boolean;
    keyCode: number;
  }) => {
  const { code } = e;
  const catchKeyCode = ['ArrowUp', 'ArrowDown', 'Enter', 'NumpadEnter'];

  if (code === 'Escape' || !catchKeyCode.includes(code)) {
    return;
  }

  const dropdownEl = refDropdownEl.value;
  if (!dropdownEl) {
    return;
  }

  const dropdownList = dropdownEl.querySelectorAll('.list-item');
  const hasHover = dropdownEl.querySelector('.list-item.is-hover');
  if (code === 'NumpadEnter' || code === 'Enter') {
    // Ctrl+Enter 操作已由父组件处理，这里不再处理
    if (e.ctrlKey || e.metaKey) {
      return;
    }

    if (activeIndex.value !== null) {
      stopEventPreventDefault(e);
      if (hasHover && !activeIndex.value) {
        activeIndex.value = 0;
      }

      if (activeIndex.value !== null && dropdownList[activeIndex.value] !== undefined) {
        // enter 选中下拉选项
        (dropdownList[activeIndex.value] as HTMLElement).click();
      } else {
        emitValueChange(props.value, false, true);
      }
    }
  }

  if (code === 'ArrowUp') {
    stopEventPreventDefault(e);

    if (hasHover) {
      activeIndex.value = 0;
      hasHover?.classList.remove('is-hover');
    }
    if (activeIndex.value) {
      activeIndex.value -= 1;
    } else {
      activeIndex.value = dropdownList.length - 1;
    }
  }

  if (code === 'ArrowDown') {
    stopEventPreventDefault(e);

    if (hasHover) {
      activeIndex.value = 0;
      hasHover?.classList.remove('is-hover');
    }
    if (activeIndex.value === null || activeIndex.value === dropdownList.length - 1) {
      activeIndex.value = 0;
    } else {
      activeIndex.value += 1;
    }
  }

  setOptionActive();
  scrollActiveItemIntoView();
};

const beforeShowndFn = () => {
  calculateDropdown();
  activeIndex.value = null;
  nextTick(() => {
    setOptionActive();
  });

  const beforeShownValue = showOption.value.showFields
      || showOption.value.showValue
      || showOption.value.showColon
      || showOption.value.showContinue
      || (showOption.value.showOperator && operatorSelectList.value.length);

  if (beforeShownValue) {
    // capture： true 避免执行顺序导致编辑器的 enter 事件误触发
    document.addEventListener('keydown', handleKeydown, { capture: true });
  }

  return beforeShownValue;
};

const beforeHideFn = () => {
  activeIndex.value = null;
  document.removeEventListener('keydown', handleKeydown, { capture: true });
};


const handleFavoriteClick = (item) => {
  emitValueChange(item.params?.keyword, true, true);
};

const handleSQLReadmeClick = () => {
  const lang = /^en/.test(jsCookie.get('blueking_language')) ? 'EN' : 'ZH';
  window.open(
    `${(window as any).BK_DOC_URL}/markdown/${lang}/LogSearch/4.6/UserGuide/ProductFeatures/data-visualization/query_string.md`,
    '_blank',
  );
};

const debounceUpdate = debounce(() => {
  calculateDropdown();
  nextTick(() => {
    setOptionActive();
  });
});
const fieldNameShow = (item) => {
  return getQualifiedFieldName(item, totalFields.value);
};

defineExpose({
  beforeShowndFn,
  beforeHideFn,
});

watch(
  () => [props.value, props.focusPosition],
  () => {
    debounceUpdate();
  },
  { immediate: true, deep: true },
);

watch(activeIndex, () => {
  emits('active-change', activeIndex.value);
});
</script>
<template>
  <div class="sql-query-container">
    <div class="sql-field-list">
      <!-- 顶部工具栏 -->
      <div class="sql-query-header">
        <div class="ui-shortcut-key">
          <div
            class="ui-shortcut-item direct-retrieve-item"
          >
            <span class="bklog-icon bklog-enter-3 label" />
            <span class="value">{{ $t('直接检索') }}</span>
          </div>
          <div class="ui-shortcut-item">
            <span class="bklog-icon bklog-arrow-down-filled label up" />
            <span class="bklog-icon bklog-arrow-down-filled label" />
            <span class="value">{{ $t('移动光标') }}</span>
          </div>
          <div
            v-if="isAiAssistantActive"
            class="ui-shortcut-item ai-shortcut-item"
          >
            <span class="label">
              <i :class="shortCutClsName" />
              <i class="bklog-icon bklog-plus" />
              <i class="bklog-icon bklog-enter-3" /></span>
            <span class="value">{{ $t('AI 解析') }}</span>
          </div>
        </div>
        <!-- <span v-if="showAiAssistant" class="ai-parse-value">{{ aiPreviewText }}</span> -->
        <div
          class="sql-syntax-link"
          @click="handleSQLReadmeClick"
        >
          <span>{{ $t('查询语法') }}</span>
          <span class="fold-title-icon bklog-icon bklog-jump" />
        </div>
      </div>
      <!-- 搜索提示 -->
      <ul
        ref="refDropdownEl"
        v-bkloading="{ isLoading: isRequesting, size: 'mini' }"
        :class="['sql-query-options', { 'is-loading': isRequesting }]"
      >
        <!-- 字段列表 -->
        <template v-if="showOption.showFields">
          <div class="control-list">
            <li
              v-for="item in fieldList"
              :key="item"
              class="list-item field-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickField(item)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-field" />
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-text text-overflow-hidden"
              >
                {{ fieldNameShow(item) }}
              </div>
            </li>
          </div>
        </template>

        <!-- 字段对应值 -->
        <template v-if="showOption.showValue">
          <div class="control-list">
            <li
              v-for="item in valueList"
              :key="item"
              class="list-item value-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickValue(item)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-value" />
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-text text-overflow-hidden"
              >
                {{ item }}
              </div>
            </li>
          </div>
        </template>
        <!-- : :* -->
        <template v-if="showOption.showColon">
          <div class="control-list">
            <li
              class="list-item colon-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickColon(':')"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-equal" />
              </div>
              <div class="item-text">
                :
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-description text-overflow-hidden"
              >
                <i18n path="{0}某一值">
                  <span class="item-callout">{{ $t('等于') }}</span>
                </i18n>
              </div>
            </li>
            <li
              class="list-item colon-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickColon(': *')"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-equal" />
              </div>
              <div class="item-text">
                :*
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-description text-overflow-hidden"
              >
                <i18n path="{0}任意形式">
                  <span class="item-callout">{{ $t('存在') }}</span>
                </i18n>
              </div>
            </li>
          </div>
          <div
            v-if="showOption.showOperator"
            class="control-list"
          >
            <li
              v-for="(item, key) in operatorSelectList"
              :key="key"
              class="list-item continue-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickColon(item.operator)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-equal" />
              </div>
              <div class="item-text">
                {{ item.operator }}
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-description text-overflow-hidden"
              >
                <i18n path="{0}某一值">
                  <span class="item-callout">{{ item.label }}</span>
                </i18n>
              </div>
            </li>
          </div>
        </template>
        <!-- AND OR -->
        <template v-if="showOption.showContinue">
          <div class="control-list">
            <li
              class="list-item continue-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickContinue('AND')"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-and" />
              </div>
              <div class="item-text">
                AND
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-description text-overflow-hidden"
              >
                <i18n path="需要{0}为真">
                  <span class="item-callout">{{ $t('两个参数都') }}</span>
                </i18n>
              </div>
            </li>
            <li
              class="list-item continue-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickContinue('OR')"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-and" />
              </div>
              <div class="item-text">
                OR
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-description text-overflow-hidden"
              >
                <i18n path="需要{0}为真">
                  <span class="item-callout">{{ $t('一个或多个参数') }}</span>
                </i18n>
              </div>
            </li>
            <li
              class="list-item continue-list-item"
              data-bklog-v3-pop-click-item
              @click="handleClickContinue('AND NOT')"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-and" />
              </div>
              <div class="item-text">
                AND NOT
              </div>
              <div
                v-bk-overflow-tips="{ placement: 'right' }"
                class="item-description text-overflow-hidden"
              >
                <i18n path="需要{0}为真">
                  <span class="item-callout">{{ $t('一个或多个参数') }}</span>
                </i18n>
              </div>
            </li>
          </div>
        </template>
      </ul>
      <FavoriteList
        :search-value="value"
        @change="handleFavoriteClick"
      />
    </div>
  </div>
</template>
<style lang="scss" scoped>
  @import './sql-query-options.scss';

  div.sql-query-container {
    position: relative;
    display: flex;
    line-height: 1;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .sql-field-list {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 100%;
      min-height: 100px;
      max-height: 400px;

      /* 顶部工具栏样式 */
      .sql-query-header {
        display: flex;
        align-items: center;
        height: 48px;
        padding-left: 16px;
        background-color: #fafbfd;
        border-bottom: 1px solid #dcdee5;
        border-radius: 2px 2px 0 0;
        gap: 16px;

        .ui-shortcut-key {
          display: flex;
          align-items: center;
          flex-shrink: 0;
          white-space: nowrap;

          .ui-shortcut-item {
            display: inline-flex;
            align-items: center;
            margin-right: 24px;
            font-size: 12px;
            line-height: 16px;
            min-width: fit-content;

            .label {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              height: 16px;
              padding: 0 4px;
              font-size: 11px;
              font-weight: 700;
              color: #a3b1cc;
              background-color: #a3b1cc29;
              border: 1px solid #a3b1cc4d;
              border-radius: 2px;

              &.bklog-arrow-down-filled,
              &.bklog-enter-3 {
                width: 16px;
                height: 16px;
                padding: 0;
                background: #a3b1cc;
                border-radius: 2px;
                color: #fff;
                font-size: 12px;
                border: none;
              }

              &.up {
                margin-right: 2px;
                transform: rotate(-180deg);
              }
            }

            .value {
              margin-left: 4px;
              color: #4D4F56;
            }

            &:last-child {
              margin-right: 0;
            }
          }

          .direct-retrieve-item {
            cursor: pointer;

            .label {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              width: 16px;
              height: 16px;
              padding: 0;
              background: #a3b1cc;
              border-radius: 2px;
              font-size: 14px;
              color: #fff;
            }

            .value {
              color: #63656e;
            }
          }

          .ai-shortcut-item {
            .label {
              height: 16px;
              background: #8474f3;
              border-radius: 2px;
              color: #fff;
              border: none;
              padding: 0 4px;
              display: inline-flex;
              align-items: center;
              justify-content: center;
              line-height: 1;

              i {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                line-height: 1;
                font-size: 12px;
                height: 100%;
                flex-shrink: 0;
              }
            }

            .value {
              font-size: 12px;
              color: #8474f3;
            }
          }

          .ai-parse-item {
            cursor: pointer;
            margin-left: 8px;

            .ai-parse-label {
              color: #8474f3;
              font-size: 12px;
              margin-right: 4px;
            }

            .ai-parse-value {
              color: #63656e;
              font-size: 12px;
            }

            &:hover {
              .ai-parse-label {
                color: #6b5dd8;
              }

              .ai-parse-value {
                color: #313238;
              }
            }
          }
        }

        .ai-parse-value {
          flex: 1;
          min-width: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          font-size: 12px;
          color: #313238;
        }

        .sql-syntax-link {
          display: flex;
          align-items: center;
          flex-shrink: 0;
          height: 100%;
          color: #3a84ff;
          cursor: pointer;
          font-size: 12px;
          margin-left: auto;

          .fold-title-icon {
            margin-left: 5px;
            font-size: 16px;
          }
        }
      }

      /* 搜索提示区域自适应高度 */
      .sql-query-options {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
      }

      /* FavoriteList 自适应 */
      :deep(.favorite-list) {
        flex-shrink: 0;
      }
    }
  }
</style>
<style lang="scss">
  .sql-query-options {
    .bk-loading {
      .bk-loading-wrapper {
        left: 5%;
      }
    }
  }
</style>
