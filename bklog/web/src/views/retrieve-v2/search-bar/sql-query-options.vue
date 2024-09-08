<script lang="ts" setup>
  import { computed, ref, watch, nextTick, ComputedRef } from 'vue';
  import { debounce } from 'lodash';
  //@ts-ignore
  import useStore from '@/hooks/use-store';
  //@ts-ignore
  import useLocale from '@/hooks/use-locale';
  const props = defineProps({
    value: {
      type: String,
      default: '',
      required: true,
    },
  });

  const emits = defineEmits(['change', 'cancel', 'retrieve']);

  const store = useStore();
  const { $t } = useLocale();

  enum OptionItemType {
    Fields = 'Fields',
    Value = 'Value',
    Colon = 'Colon',
    Continue = 'Continue',
    Operator = 'Operator',
  }

  // 定义一个类型来表示生成对象的类型
type ShowOptionValueType = {
  [K in keyof typeof OptionItemType as `show${typeof OptionItemType[K]}`]: boolean;
};

  const showOption = computed(() => {
    return Object.values(OptionItemType).reduce(
      (output, key) => ({
        ...output,
        [`show${key}`]: activeType.value.includes(key),
      }),
      {} as ShowOptionValueType,
    );
  });

  const retrieveDropdownData = computed(() => store.state.retrieveDropdownData);
  const totalFields = computed(() => store.state.indexFieldInfo.fields ?? []);

  /** 获取数字类型的字段name */
  const getNumTypeFieldList = computed(() => {
    return totalFields.value
      .filter(item => ['long', 'integer', 'float'].includes(item.field_type))
      .map(item => item.field_name);
  });

  /** 语法检查需要的字段信息 */
  const getCheckKeywordsFields = computed(() => {
    return totalFields.value.map(item => ({
      field_name: item.field_name,
      is_analyzed: item.is_analyzed,
      field_type: item.field_type,
    }));
  });

  /** 所有字段的字段名 */
  const totalFieldsNameList = computed(() => {
    return totalFields.value.map(item => item.field_name);
  });

  // 检索后的日志数据如果字段在字段接口找不到则不展示联想的key
  const originFieldList = computed(() =>
    Object.keys(retrieveDropdownData.value).filter(v => totalFieldsNameList.value.includes(v)),
  );

  const activeType = ref([]);
  const separator = /\s(AND|OR)\s/i; // 区分查询语句条件
  const fieldList = ref([]);
  const valueList = ref([]);

  const refDropdownEl = ref(null);
  const activeIndex = ref(0);

  const handleRetrieve = debounce(() => emits('retrieve'));

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
    dropdownList?.[activeIndex.value]?.classList.add('active');
  };

  /**
   * 显示哪个下拉列表
   * @param {String} [param]
   */
  const showWhichDropdown = (param?) => {
    activeType.value.length = 0;
    activeType.value = [];
    if (typeof param === 'string') {
      activeType.value.push(param);
    }

    if (Array.isArray(param)) {
      activeType.value.push(...param);
    }

    activeIndex.value = 0;
  };

  /**
   * 获取某个字段可选的值列表
   * @param {Object} valueMap
   * @return {string[]}
   */
  const getValueList = valueMap => {
    let valueMapList = Object.keys(valueMap);
    if (valueMap.__fieldType === 'string') {
      valueMapList = valueMapList // 清除mark标签
        .map(item => `"${item.replace(/<mark>/g, '').replace(/<\/mark>/g, '')}"`);
    }
    return [...new Set(valueMapList)]; // 清除重复的字段
  };

  /**
   * @desc: 当前是否是数字类型字段
   * @param {string} fieldStr 字段名
   * @returns {boolean}
   */
  const isNumTypeField = (fieldStr = '') => {
    return getNumTypeFieldList.value.includes(fieldStr);
  };

  const showColonOperator = inputField => {
    const showVal = [OptionItemType.Colon];

    if (isNumTypeField(inputField?.trim())) {
      showVal.push(OptionItemType.Operator);
    }
    // 完全匹配字段同时和 : :* 选项
    showWhichDropdown(showVal);
  };

  // 根据当前输入关键字计算提示内容
  const calculateDropdown = () => {
    if (!originFieldList.value.length) {
      return;
    }

    fieldList.value.length = 0;
    fieldList.value = [];

    const value = props.value;
    const trimValue = value.trim();
    const lastFragments = value.split(separator);
    const lastFragment = lastFragments[lastFragments.length - 1];
    // 以 name:"arman" OR age:18 为例，还没开始输入字段
    if (
      !trimValue ||
      trimValue === '*' ||
      /\s+AND\s+$/.test(value) ||
      /\s+OR\s+$/.test(value) ||
      /\s+and\s+$/.test(value) ||
      /\s+or\s+$/.test(value)
    ) {
      showWhichDropdown('Fields');
      fieldList.value.push(...originFieldList.value);
      return;
    }
    // 开始输入字段【nam】
    const inputField = /^\s*(?<field>[\w.]+)$/.exec(lastFragment)?.groups.field;
    if (inputField) {
      fieldList.value = originFieldList.value.filter(item => {
        if (item.includes(inputField)) {
          if (item === inputField) {
            showColonOperator(inputField);
          }
          return true;
        }
      });
      showWhichDropdown(fieldList.value.length ? OptionItemType.Fields : undefined);
      return;
    }
    // 字段输入完毕【name 】
    if (/^\s*(?<field>[\w.]+)\s*$/.test(lastFragment)) {
      showColonOperator(inputField);
      return;
    }
    // 准备输入值【name:】
    const confirmField = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*$/.exec(lastFragment)?.groups.field;
    if (confirmField) {
      const valueMap = retrieveDropdownData.value[confirmField];
      if (valueMap) {
        showWhichDropdown(OptionItemType.Value);
        valueList.value = getValueList(valueMap);
      } else {
        showWhichDropdown();
        valueList.value.splice(0);
      }
      return;
    }
    // 正在输入值【age:1】注意后面没有空格，匹配字段对应值
    const valueResult = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*(?<value>[\S]+)$/.exec(lastFragment);
    if (valueResult) {
      const confirmField = valueResult.groups.field;
      const valueMap = retrieveDropdownData.value[confirmField];
      if (valueMap) {
        const inputValue = valueResult.groups.value;
        valueList.value = getValueList(valueMap).filter(item => item.includes(inputValue));
        showWhichDropdown(valueList.value.length ? OptionItemType.Value : undefined);
      } else {
        showWhichDropdown();
        valueList.value.splice(0);
      }
      return;
    }
    // 一组条件输入完毕【age:18 】提示继续增加条件 AND OR
    if (/^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*(?<value>[\S]+)\s+$/.test(lastFragment)) {
      showWhichDropdown(OptionItemType.Continue);
      return;
    }

    showWhichDropdown();
  };

  /**
   * 选择某个可选字段
   * @param {string} field
   */
  const handleClickField = field => {
    valueList.value = getValueList(retrieveDropdownData.value[field]);
    const currentValue = props.value;
    const trimValue = currentValue.trim();
    if (!trimValue || trimValue === '*') {
      emits('change', `${field} `);
    } else {
      const fragments = currentValue.split(separator);
      if (!fragments[fragments.length - 1].trim()) {
        // 可能的情况 【name:"arman" AND \s】
        emits('change', `${currentValue}${field} `);
      } else {
        // 可能的情况【name:"arman" AND ag】【name】
        emits('change', currentValue.replace(/\s*[\w.]+$/, ` ${field} `));
      }
    }
    showColonOperator(field);
    nextTick(() => {
      activeIndex.value = 0;
      setOptionActive();
    });
  };

  /**
   * 选择 : 或者 :*
   * @param {string} type
   */
  const handleClickColon = type => {
    emits('change', `${props.value + type} `);
    calculateDropdown();
    nextTick(() => {
      activeIndex.value = 0;
      setOptionActive();
    });
  };

  /**
   * 选择某个字段可选值
   * @param {string} value
   */
  const handleClickValue = value => {
    // 当前输入值可能的情况 【name:"a】【age:】
    emits(
      'change',
      props.value.replace(/(:|>=|<=|>|<)\s*[\S]*$/, (match1, matchOperator) => {
        return `${matchOperator} ${value} `;
      }),
    );
    showWhichDropdown(OptionItemType.Continue);
    nextTick(() => {
      activeIndex.value = 0;
      setOptionActive();
    });
  };

  /**
   * 选择 AND 或者 OR
   * @param {string} type
   */
  const handleClickContinue = type => {
    emits('change', `${props.value + type} `);
    showWhichDropdown(OptionItemType.Fields);
    fieldList.value = [...originFieldList.value];
    nextTick(() => {
      activeIndex.value = 0;
      setOptionActive();
    });
  };

  const scrollActiveItemIntoView = () => {
    if (activeIndex.value >= 0) {
      const target = refDropdownEl.value.querySelector('.list-item.active');
      target?.scrollIntoView({ block: 'nearest' });
    }
  };

  const handleKeydown = e => {
    const { code } = e;
    if (code === 'Escape') {
      emits('cancel');
      return;
    }

    const dropdownEl = refDropdownEl.value;
    if (!dropdownEl) {
      return;
    }

    const dropdownList = dropdownEl.querySelectorAll('.list-item');
    if (code === 'NumpadEnter' || code === 'Enter') {
      e.preventDefault();
      if (activeIndex.value !== null && dropdownList[activeIndex.value] !== undefined) {
        // enter 选中下拉选项
        dropdownList[activeIndex.value].click();
      } else {
        emits('change', props.value);
        nextTick(() => {
          handleRetrieve();
        });
      }
    }

    if (code === 'ArrowUp') {
      if (activeIndex.value) {
        activeIndex.value -= 1;
      } else {
        activeIndex.value = dropdownList.length - 1;
      }
    }

    if (code === 'ArrowDown') {
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
    document.addEventListener('keydown', handleKeydown);
  };

  const beforeHideFn = () => {
    document.removeEventListener('keydown', handleKeydown);
  };

  defineExpose({
    beforeShowndFn,
    beforeHideFn,
  });

  watch(
    props,
    () => {
      calculateDropdown();
      nextTick(() => {
        setOptionActive();
      })
    },
    { immediate: true },
  );
</script>
<template>
  <!-- 搜索提示 -->
  <ul
    class="sql-query-options"
    ref="refDropdownEl"
  >
    <!-- 字段列表 -->
    <template v-if="showOption.showFields">
      <li
        v-for="item in fieldList"
        class="list-item field-list-item"
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
    </template>
    <!-- 字段对应值 -->
    <template v-if="showOption.showValue">
      <li
        v-for="item in valueList"
        class="list-item value-list-item"
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
    </template>
    <!-- : :* -->
    <template v-if="showOption.showColon">
      <li
        class="list-item colon-list-item"
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
      <template v-if="showOption.showOperator">
        <template>
          <li
            v-for="(item, key) in operatorSelectList"
            class="list-item continue-list-item"
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
        </template>
      </template>
    </template>
    <!-- AND OR -->
    <template v-if="showOption.showContinue">
      <li
        class="list-item continue-list-item"
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
    </template>
  </ul>
</template>
<style scoped>
  .sql-query-options {
    width: 100%;
    max-height: 360px;
    margin-top: 4px;
    overflow: auto;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .list-item {
      display: flex;
      align-items: center;
      font-size: 12px;
      line-height: 32px;
      background-color: #fff;

      .item-type-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;

        .bklog-icon {
          font-size: 16px;
        }
      }

      .item-text {
        flex: 1;
        min-width: 150px;
        padding: 0 8px;
        font-family: 'Roboto Mono', Consolas, Menlo, Courier, monospace;
        color: #63656e;
      }

      .item-description {
        flex: 2;
        margin-left: 24px;
        color: #979ba5;

        .item-callout {
          padding: 0 4px;
          font-family: 'Roboto Mono', Consolas, Menlo, Courier, monospace;
          color: #313238;
          background-color: #f4f6fa;
        }
      }

      &:hover,
      &.active {
        background-color: #f4f6fa;

        .item-text {
          color: #313238;
        }

        .item-callout {
          background-color: #fff;
        }
      }

      &:hover {
        cursor: pointer;
        background-color: #eaf3ff;
      }
    }

    /* 字段 icon 样式 */
    .field-list-item.list-item {
      .item-type-icon {
        color: #936501;
        background-color: #fef6e6;
      }

      &:hover,
      &.active {
        .item-type-icon {
          color: #010101;
          background-color: #fdedcc;
        }
      }
    }

    /* 值 icon 样式 */
    .value-list-item.list-item {
      /* stylelint-disable-next-line no-descending-specificity */
      .item-type-icon {
        color: #02776e;
        background-color: #e6f2f1;
      }

      &:hover,
      &.active {
        .item-type-icon {
          color: #010101;
          background-color: #cce5e3;
        }
      }
    }

    /* AND OR icon 样式 */
    .continue-list-item.list-item {
      /* stylelint-disable-next-line no-descending-specificity */
      .item-type-icon {
        color: #7800a6;
        background-color: #f2e6f6;
      }

      &:hover,
      &.active {
        .item-type-icon {
          color: #000;
          background-color: #e4cced;
        }
      }
    }

    /* : :* icon 样式 */
    .colon-list-item.list-item {
      /* stylelint-disable-next-line no-descending-specificity */
      .item-type-icon {
        color: #006bb4;
        background-color: #e6f0f8;
      }

      &:hover,
      &.active {
        .item-type-icon {
          color: #000;
          background-color: #cce1f0;
        }
      }
    }

    .history-title-item.list-item {
      cursor: default;
      background-color: #fff;
      border-top: 1px solid #dcdee5;

      .item-text {
        color: #979ba5;
      }
    }
  }
</style>
