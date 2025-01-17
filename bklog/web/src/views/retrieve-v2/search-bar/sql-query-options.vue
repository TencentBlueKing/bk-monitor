<script lang="ts" setup>
  import { computed, ref, watch, nextTick, Ref } from 'vue';
  import useFieldNameHook from '@/hooks/use-field-name';
  // @ts-ignore
  import useLocale from '@/hooks/use-locale';
  // @ts-ignore
  import useStore from '@/hooks/use-store';
  // @ts-ignore
  import { debounce } from 'lodash';
  // @ts-ignore
  import FavoriteList from './favorite-list';

  import { excludesFields } from './const.common';
  import jsCookie from 'js-cookie';

  import useFieldEgges from './use-field-egges';

  const props = defineProps({
    value: {
      type: String,
      default: '',
      required: true,
    },
  });

  const emits = defineEmits(['change', 'cancel', 'retrieve', 'active-change']);

  const store = useStore();
  const { $t } = useLocale();

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
      defShowOptionValueType,
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
    const { getFieldNames } = useFieldNameHook({ store });
    return  getFieldNames(totalFields.value.filter(filterFn));
   
  });

  // 检索后的日志数据如果字段在字段接口找不到则不展示联想的key
  const originFieldList = () => totalFieldsNameList.value;

  const activeType: Ref<string[]> = ref([]);
  const separator = /\s(AND|OR)\s/i; // 区分查询语句条件
  const fieldList: Ref<string[]> = ref([]);
  const valueList: Ref<string[]> = ref([]);

  const refDropdownEl: Ref<HTMLElement | null> = ref(null);
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

  // 根据当前输入关键字计算提示内容
  const calculateDropdown = () => {
    if (!originFieldList().length) {
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
      fieldList.value.push(...originFieldList());
      return;
    }
    // 开始输入字段【nam】
    const inputField = /^\s*(?<field>[\w.]+)$/.exec(lastFragment)?.groups?.field;
    if (inputField) {
      fieldList.value = originFieldList().filter(item => {
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
      showColonOperator(lastFragment);
      return;
    }

    // 准备输入值【name:】
    const confirmField = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*$/.exec(lastFragment)?.groups?.field;
    if (confirmField) {
      const valueMap = retrieveDropdownData.value[confirmField];
      if (valueMap) {
        showWhichDropdown(OptionItemType.Value);
        setValueList(confirmField, '');
        // valueList.value = getValueList(valueMap);
      } else {
        showWhichDropdown();
        valueList.value.splice(0);
      }
      return;
    }
    // 正在输入值【age:1】注意后面没有空格，匹配字段对应值
    const valueResult = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*(?<value>[\S]+)$/.exec(lastFragment);
    if (valueResult) {
      const confirmField = valueResult.groups?.field;
      const valueMap = retrieveDropdownData.value[confirmField];
      if (valueMap) {
        const inputValue = valueResult.groups?.value ?? '';
        setValueList(confirmField, inputValue);
        // valueList.value = getValueList(valueMap).filter(item => item.includes(inputValue));
        showWhichDropdown(valueList.value.length ? OptionItemType.Value : undefined);
      } else {
        showWhichDropdown();
        valueList.value.splice(0);
      }
      return;
    }

    // 一组条件输入完毕【age:18 】提示继续增加条件 AND OR
    if (/^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*(?<value>["']?.*["']?)$/.test(lastFragment)) {
      showWhichDropdown(OptionItemType.Continue);
      return;
    }

    showWhichDropdown();
  };

  /**
   * 选择某个可选字段
   * @param {string} field
   */
  const handleClickField = (field: string) => {
    // valueList.value = getValueList(retrieveDropdownData.value[field]);
    // setValueList(field, '');
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
    showColonOperator(field as string);
    nextTick(() => {
      activeIndex.value = null;
      setOptionActive();
    });
  };

  /**
   * 选择 : 或者 :*
   * @param {string} type
   */
  const handleClickColon = (type: string) => {
    emits('change', `${props.value + type} `);
    calculateDropdown();
    nextTick(() => {
      activeIndex.value = null;
      setOptionActive();
    });
  };

  /**
   * 选择某个字段可选值
   * @param {string} value
   */
  const handleClickValue = (value: any) => {
    // 当前输入值可能的情况 【name:"a】【age:】
    emits(
      'change',
      props.value.replace(/(:|>=|<=|>|<)\s*[\S]*$/, (match1, matchOperator) => {
        return `${matchOperator} ${value} `;
      }),
    );
    showWhichDropdown(OptionItemType.Continue);
    nextTick(() => {
      activeIndex.value = null;
      setOptionActive();
    });
  };

  /**
   * 选择 AND 或者 OR
   * @param {string} type
   */
  const handleClickContinue = (type: string) => {
    emits('change', `${props.value + type} `);
    showWhichDropdown(OptionItemType.Fields);
    fieldList.value = [...originFieldList()];
    nextTick(() => {
      activeIndex.value = null;
      setOptionActive();
    });
  };

  const scrollActiveItemIntoView = () => {
    if (activeIndex.value >= 0) {
      const target = refDropdownEl.value?.querySelector('.list-item.active');
      target?.scrollIntoView({ block: 'nearest' });
    }
  };

  const handleKeydown = (e: { preventDefault?: any; code?: any }) => {
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
        (dropdownList[activeIndex.value] as HTMLElement).click();
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
    activeIndex.value = null;
    document.addEventListener('keydown', handleKeydown);

    calculateDropdown();
    nextTick(() => {
      setOptionActive();
    });

    return (
      (showOption.value.showFields && fieldList.value.length) ||
      (showOption.value.showValue && valueList.value.length) ||
      showOption.value.showColon ||
      showOption.value.showContinue ||
      (showOption.value.showOperator && operatorSelectList.value.length)
    );
  };

  const beforeHideFn = () => {
    document.removeEventListener('keydown', handleKeydown);
  };

  // 查询语法按钮部分
  const isRetractShow = ref(true);
  const handleRetract = () => {
    isRetractShow.value = !isRetractShow.value;
  };
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
    emits('change', item.params?.keyword, true);
  };

  const handleSQLReadmeClick = () => {
    const lang = /^en/.test(jsCookie.get('blueking_language')) ? 'EN' : 'ZH';
    window.open(
      `${(window as any).BK_DOC_URL}/markdown/${lang}/LogSearch/4.6/UserGuide/ProductFeatures/data-visualization/query_string.md`,
      '_blank',
    );
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
      });
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
      <!-- 搜索提示 -->
      <ul
        ref="refDropdownEl"
        class="sql-query-options"
        v-bkloading="{ isLoading: isRequesting, size: 'mini' }"
      >
        <!-- 字段列表 -->
        <template v-if="showOption.showFields">
          <div class="control-list">
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
          </div>
        </template>

        <!-- 字段对应值 -->
        <template v-if="showOption.showValue">
          <div class="control-list">
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
          </div>
        </template>
        <!-- : :* -->
        <template v-if="showOption.showColon">
          <div class="control-list">
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
          </div>
          <template
            v-if="showOption.showOperator"
            class="control-list"
          >
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
        <!-- AND OR -->
        <template v-if="showOption.showContinue">
          <div class="control-list">
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
          </div>
        </template>
        <template
          v-if="!showOption.showFields && !showOption.showValue && !showOption.showColon && !showOption.showContinue"
        >
          <bk-exception
            style="height: 40px"
            type="search-empty"
            scene="part"
          >
            当前页面未获取到该字段信息，无法获取联想内容，请手动输入查询内容
          </bk-exception>
        </template>
      </ul>
      <FavoriteList
        @change="handleFavoriteClick"
        :searchValue="value"
      ></FavoriteList>
    </div>
    <div :class="['sql-syntax-tips', { 'is-show': isRetractShow }]">
      <span
        class="sql-query-retract"
        @click="handleRetract"
      >
        <span>{{ isRetractShow ? $t('收起') : $t('查询语法') }}</span>
        <span
          :class="['angle-icon bk-icon', { 'icon-angle-left': !isRetractShow, 'icon-angle-right': isRetractShow }]"
        ></span>
      </span>
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
          >
            <div style="font-weight: 700; line-height: 19px">{{ item.name }}</div>
            <div>{{ item.value }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<style lang="scss" scoped>
  @import './sql-query-options.scss';

  .sql-query-container {
    display: flex;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .sql-field-list {
      width: 100%;
    }

    .sql-syntax-tips {
      position: relative;
      width: 240px;
      background: #fafbfd;
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
        background: #fafbfd;
        border-radius: 0 2px 2px 0;
        outline: 1px solid #dcdee5;

        .sql-query-fold-title {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-size: 12px;

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
          overflow-y: auto;
          font-size: 12px;
          white-space: pre-line;
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
