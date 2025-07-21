<script lang="ts" setup>
import { computed, ref, watch, nextTick, Ref } from 'vue';

import useFieldNameHook from '@/hooks/use-field-name';
// @ts-ignore
import useLocale from '@/hooks/use-locale';
// @ts-ignore
import useStore from '@/hooks/use-store';

import jsCookie from 'js-cookie';
// @ts-ignore
import { debounce } from 'lodash';

import { excludesFields } from './const.common'; // @ts-ignore
import FavoriteList from './favorite-list';
import useFieldEgges from './use-field-egges';

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

const emits = defineEmits(['change', 'cancel', 'retrieve', 'active-change']);

const store = useStore();
const { $t } = useLocale();
const { getFieldNames } = useFieldNameHook({ store });

enum OptionItemType {
  Colon = 'Colon',
  Continue = 'Continue',
  Fields = 'Fields',
  Operator = 'Operator',
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
    defShowOptionValueType
  );
});

const retrieveDropdownData = computed(() => store.state.retrieveDropdownData);
const totalFields = computed(() => store.state.indexFieldInfo.fields ?? []);
const { isRequesting, requestFieldEgges, isValidateEgges } = useFieldEgges();

/** 获取数字类型的字段name */
const getNumTypeFieldList = computed(() => {
  return totalFields.value
    .filter((item: { field_type: string }) => ['long', 'integer', 'float'].includes(item.field_type))
    .map((item: { field_name: any }) => item.field_name);
});

/** 所有字段的字段名 */
const totalFieldsNameList = computed(() => {
  const filterFn = field => field.field_type !== '__virtual__' && !excludesFields.includes(field.field_name);
  return getFieldNames(totalFields.value.filter(filterFn));
});

// 检索后的日志数据如果字段在字段接口找不到则不展示联想的key
const originFieldList = () => totalFieldsNameList.value;

const activeType: Ref<string[]> = ref([]);
// const separator = /\s+(AND\s+NOT|OR|AND)\s+/i; // 区分查询语句条件
const fieldList: Ref<string[]> = ref([]);
const valueList: Ref<string[]> = ref([]);

const refDropdownEl: Ref<HTMLElement | null> = ref(null);
const activeIndex = ref(null);

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
  if (activeIndex.value === null) {
    return;
  }

  const dropdownList = refDropdownEl?.value?.querySelectorAll('.list-item');
  refDropdownEl?.value?.querySelector('.list-item.active')?.classList.remove('active');
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
  const fieldInfo = store.state.indexFieldInfo.fields.find(item => item.field_name === fieldName);
  if (fieldInfo && isValidateEgges(fieldInfo)) {
    valueList.value = [];
    requestFieldEgges(fieldInfo, value, resp => {
      if (typeof resp === 'boolean') {
        valueList.value = getValueList(retrieveDropdownData.value[fieldName] ?? {});
        return;
      }

      valueList.value = store.state.indexFieldInfo.aggs_items[fieldName] ?? [];
    });
    return;
  }

  valueList.value = getValueList(retrieveDropdownData.value[fieldName] ?? {});
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

const emitValueChange = (appendValue: string, retrieve = false, replace = false, focusPosition = undefined) => {
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

  const lastValues = /(:|>=|<=|>|<)\s*(\d+|"((?:[^"\\]|\\.)*)"?)/.exec(lastFragment);
  const matchValue = lastValues?.[3] ?? lastValues?.[2];
  const matchValueWithQuotes = lastValues?.[2];

  if (matchValueWithQuotes && lastFragment.length >= matchValue.length) {
    const lastValue = lastFragment.slice(0, lastFragment.length - matchValueWithQuotes.length);
    const confirmField = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*$/.exec(lastValue)?.groups?.field;

    if (confirmField) {
      showWhichDropdown(OptionItemType.Value);
      setValueList(confirmField, matchValue);
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
    fieldList.value = originFieldList().filter(item => item.includes(inputField));
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

  const lastValues = /(:|>=|<=|>|<)\s*(\d+|"((?:[^"\\]|\\.)*)"?)/.exec(lastFragment);
  const matchValueWithQuotes = lastValues?.[2] ?? '';
  const matchLeft = sqlValue.slice(0, sqlValue.length - matchValueWithQuotes.length);
  const targetValue = value.replace(/^"|"$/g, '').replace(/"/g, '\\"');

  const rightFirstValue =
    matchValueWithQuotes.length >= 1 ? (rightValue.split(/\s+(AND\s+NOT|OR|AND)\s+/i)?.shift() ?? '') : '';

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
  if (activeIndex.value >= 0) {
    const target = refDropdownEl.value?.querySelector('.list-item.active');
    target?.scrollIntoView({ block: 'nearest' });
  }
};

const stopEventPreventDefault = e => {
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

  const beforeShownValue =
    showOption.value.showFields ||
    showOption.value.showValue ||
    showOption.value.showColon ||
    showOption.value.showContinue ||
    (showOption.value.showOperator && operatorSelectList.value.length);

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

// 查询语法按钮部分
const isRetractShow = ref(true);

const matchList = ref([
  {
    name: $t('精确匹配(支持AND、OR):'),
    value: 'author:"John Smith" AND age:20',
  },
  {
    name: $t('字段名匹配(*代表通配符):'),
    value: `status:active \n title:(quick brown)`,
  },
  {
    name: $t('字段名模糊匹配:'),
    value: 'vers\*on:(quick brown)',
  },
  {
    name: $t('通配符匹配:'),
    value: `qu?ck bro*`,
  },
  {
    name: $t('正则匹配:'),
    value: `name:/joh?n(ath[oa]n)/`,
  },
  {
    name: $t('范围匹配:'),
    value: `count:[1 TO 5] \n  count:[1 TO 5} \n count:[10 TO *]`,
  },
]);

const handleFavoriteClick = item => {
  emitValueChange(item.params?.keyword, true, true);
};

const handleSQLReadmeClick = () => {
  const lang = /^en/.test(jsCookie.get('blueking_language')) ? 'EN' : 'ZH';
  window.open(
    `${(window as any).BK_DOC_URL}/markdown/${lang}/LogSearch/4.6/UserGuide/ProductFeatures/data-visualization/query_string.md`,
    '_blank'
  );
};

const debounceUpdate = debounce(() => {
  calculateDropdown();
  nextTick(() => {
    setOptionActive();
  });
});

defineExpose({
  beforeShowndFn,
  beforeHideFn,
});

watch(
  () => [props.value, props.focusPosition],
  () => {
    debounceUpdate();
  },
  { immediate: true, deep: true }
);

watch(activeIndex, () => {
  emits('active-change', activeIndex.value);
});
</script>
<template>
  <div class="sql-query-container">
    <div class="sql-field-list">
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
              class="list-item field-list-item"
              data-bklog-v3-pop-click-item
              :key="item"
              @click="handleClickField(item)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-field"></span>
              </div>
              <div
                class="item-text text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
              >
                {{ item }}
              </div>
            </li>
          </div>
        </template>

        <!-- 字段对应值 -->
        <template v-if="showOption.showValue">
          <div class="control-list">
            <li
              v-for="item in valueList"
              class="list-item value-list-item"
              data-bklog-v3-pop-click-item
              :key="item"
              @click="handleClickValue(item)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-value"></span>
              </div>
              <div
                class="item-text text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
                <span class="bklog-icon bklog-equal"></span>
              </div>
              <div class="item-text">:</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
                <span class="bklog-icon bklog-equal"></span>
              </div>
              <div class="item-text">:*</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
              class="list-item continue-list-item"
              data-bklog-v3-pop-click-item
              :key="key"
              @click="handleClickColon(item.operator)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-equal"></span>
              </div>
              <div class="item-text">{{ item.operator }}</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
                <span class="bklog-icon bklog-and"></span>
              </div>
              <div class="item-text">AND</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
                <span class="bklog-icon bklog-and"></span>
              </div>
              <div class="item-text">OR</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
                <span class="bklog-icon bklog-and"></span>
              </div>
              <div class="item-text">AND NOT</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
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
      ></FavoriteList>
      <!-- 移动光标and确认结果提示 -->
      <div class="ui-shortcut-key">
        <div class="ui-shortcut-item">
          <span class="bklog-icon bklog-arrow-down-filled label up" />
          <span class="bklog-icon bklog-arrow-down-filled label" />
          <span class="value">{{ $t('移动光标') }}</span>
        </div>
        <div class="ui-shortcut-item">
          <span class="label">Enter</span>
          <span class="value">{{ $t('确认结果') }}</span>
        </div>
      </div>
    </div>
    <div :class="['sql-syntax-tips', { 'is-show': isRetractShow }]">
      <div class="sql-query-fold">
        <div>
          <div class="sql-query-fold-title">
            <div>{{ $t('如何查询') }}?</div>
            <div
              class="fold-title-right"
              @click="handleSQLReadmeClick"
            >
              <span>{{ $t('查询语法') }}</span>
              <span class="fold-title-icon bklog-icon bklog-jump"></span>
            </div>
          </div>
          <div
            v-for="item in matchList"
            class="sql-query-list"
            :key="item.value"
          >
            <div class="sql-query-name">{{ item.name }}</div>
            <div class="sql-query-value">{{ item.value }}</div>
          </div>
        </div>
      </div>
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
      width: 100%;
      padding-bottom: 48px;

      /* 移动光标and确认结果提示 样式 */
      .ui-shortcut-key {
        position: absolute;
        bottom: 0;
        width: 100%;
        height: 48px;
        padding: 0 16px;
        line-height: 48px;
        background-color: #fafbfd;
        border: 1px solid #dcdee5;
        border-radius: 0 0 0 2px;

        .ui-shortcut-item {
          display: inline-flex;
          align-items: center;
          margin-right: 24px;
          font-size: 12px;
          line-height: 16px;

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

            &.bklog-arrow-down-filled {
              padding: 0;
              font-size: 14px;
            }

            &.up {
              margin-right: 2px;
              transform: rotate(-180deg);
            }
          }

          .value {
            margin-left: 4px;
            color: #7a8599;
          }
        }
      }
    }

    .sql-syntax-tips {
      position: relative;
      width: 240px;
      min-width: 240px;
      background-color: #f5f7fa;
      border-radius: 0 2px 2px 0;

      .sql-query-retract {
        position: absolute;
        top: 50%;
        left: 0;
        display: inline-block;
        width: 20px;
        padding: 4px 2px;

        font-size: 12px;
        color: #63656e;
        cursor: pointer;
        background: #f0f1f5;
        border: 1px solid #dcdee5;
        border-radius: 4px 0 0 4px;
        transform: translate(-100%, -50%);
      }

      /*   收起内容 样式*/
      .sql-query-fold {
        width: 100%;
        height: 100%;
        padding: 12px;
        background: #f5f7fa;
        border-radius: 0 2px 2px 0;
        outline: 1px solid #dcdee5;

        &-title {
          display: flex;
          justify-content: space-between;
          margin-bottom: 16px;
          font-size: 12px;
          line-height: 20px;
          color: #313238;

          .fold-title-right {
            display: flex;
            align-items: center;
            height: 100%;
            color: #3a84ff;
            cursor: pointer;

            .fold-title-icon {
              margin-left: 5px;
              font-size: 16px;
            }
          }
        }

        .sql-query-list {
          margin-bottom: 12px;
          overflow-y: auto;
          font-size: 12px;
          white-space: pre-line;

          .sql-query-name {
            margin-bottom: 2px;
            font-weight: 700;
            line-height: 16px;
            color: #313238;
          }

          .sql-query-value {
            /* stylelint-disable-next-line font-family-no-missing-generic-family-keyword */
            font-family: 'Roboto Mono', monospace;
            line-height: 18px;
            color: #4d4f56;
            word-break: break-all;
          }

          &:first-child {
            .sql-query-value {
              line-height: 20px;
            }
          }
        }
      }

      &:not(.is-show) {
        width: 1px;
        border: none;

        .sql-query-fold {
          display: none;
        }
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
