/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { defineComponent, ref, computed, onBeforeUnmount, onMounted, nextTick, type PropType, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import tippy, { type Instance } from 'tippy.js';
import TableComponent from '../../common-comp/table-component';

import './field-list.scss';
export type FieldItem = {
  field_index: number;
  field_name: string;
  alias_name?: string;
  alias_name_show?: boolean;
  field_type: string;
  previous_type?: string;
  description?: string;
  value?: string;
  is_built_in: boolean;
  is_add_in: boolean;
  is_objectKey: boolean;
  is_delete: boolean;
  is_time: boolean;
  is_analyzed: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars?: string;
  participleState: 'custom' | 'default';
  children?: FieldItem[];
  expand?: boolean;
  verdict?: boolean;
  fieldErr?: string;
  typeErr?: boolean;
  aliasErr?: boolean | string;
  fieldAliasErr?: string;
  btnShow?: boolean;
  width?: number;
};

// 全局配置类型
export type GlobalsData = {
  field_data_type: Array<{ id: string; name: string }>;
  field_built_in: Array<{ id: string }>;
  retain_extra_json?: boolean;
};

// Props类型定义
export type Props = {
  isEditJson?: boolean;
  tableType: 'edit' | 'preview';
  extractMethod: 'bk_log_delimiter' | 'bk_log_json' | 'bk_log_regexp';
  deletedVisible: boolean;
  fields: FieldItem[];
  isTempField: boolean;
  isExtracting: boolean;
  originalTextTokenizeOnChars: string;
  retainExtraJson: boolean;
  builtFieldShow: boolean;
  selectEtlConfig: 'bk_log_delimiter' | 'bk_log_json' | 'bk_log_regexp';
  isSetDisabled: boolean;
};

/**
 * @file 字段列表
 */
export default defineComponent({
  name: 'FieldList',
  props: {
    data: {
      type: Array as PropType<FieldItem[]>,
      default: () => [],
    },
    tableType: {
      type: String,
      default: 'edit',
      validator: (v: string) => ['edit', 'preview'].includes(v),
    },
    /**
     * 默认分词符
     */
    originalTextTokenizeOnChars: {
      type: String,
      default: '',
    },
    retainExtraJson: {
      type: Boolean,
      default: false,
    },
    builtFieldShow: {
      type: Boolean,
      default: false,
    },
    selectEtlConfig: {
      type: String,
      default: 'bk_log_json',
      validator: (v: string) => {
        // 如果值为空，使用默认值，验证通过
        if (!v) return true;
        return ['bk_log_json', 'bk_log_delimiter', 'bk_log_regexp'].includes(v);
      },
    },
    isSetDisabled: {
      type: Boolean,
      default: false,
    },
    extractMethod: {
      type: String,
      default: 'bk_log_json',
      validator: (v: string) => {
        // 如果值为空，使用默认值，验证通过
        if (!v) return true;
        return ['bk_log_json', 'bk_log_delimiter', 'bk_log_regexp'].includes(v);
      },
    },
    builtInFieldsList: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否刷新值
     */
    refresh: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change', 'refresh'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    // 最大 int 类型值
    const MAX_INT_VALUE = 2_147_483_647;
    const REQUIRED_FIELD_MSG = t('必填项');
    const INVALID_FIELD_NAME_MSG = t('只能包含a - z、A - Z、0 - 9和_，且不能以_开头和结尾');
    const INVALID_ALIAS_NAME_MSG = t('重命名只能包含a - z、A - Z、0 - 9和_');
    const DUPLICATE_BUILT_IN_MSG = t('与系统内置字段重复');
    const ALIAS_FIELD_DUPLICATE_MSG = t('重命名与字段名重复');
    const FIELD_CONFLICT_MSG = t('字段名称冲突, 请调整');

    const typeKey = ref('visible');
    const showBuiltIn = ref(false);
    let tippyInstances: Instance[] = [];
    const formData = ref({ tableList: [] as FieldItem[] });
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const isPreviewMode = computed(() => props.tableType === 'preview');
    const isAdd = computed(() => props.selectEtlConfig === 'bk_log_json');
    const currentParticipleState = ref('default');
    const cacheData = ref({
      is_analyzed: false,
      tokenize_on_chars: '',
      is_case_sensitive: false,
    });
    // 分词选项列表
    const participleList = [
      {
        id: 'default',
        name: t('自然语言分词'),
        placeholder: t('自然语言分词，按照日常语法习惯进行分词'),
      },
      {
        id: 'custom',
        name: t('自定义'),
        placeholder: t('支持自定义分词符，可按需自行配置符号进行分词'),
      },
    ];
    /**
     * 来源render
     * @param row
     * @returns
     */
    const renderSource = (h, { row }) => {
      const info = row.is_add_in
        ? { label: t('添加'), class: 'source-add' }
        : { label: t('调试'), class: 'source-debug' };
      const sourceInfo = row.is_built_in ? { label: t('内置'), class: 'source-built' } : info;

      return <span class={`source-box ${sourceInfo.class}`}>{sourceInfo.label}</span>;
    };

    /**
     * 分词类型变更
     * @param state
     */
    const handleChangeParticipleState = (state: string) => {
      currentParticipleState.value = state;
      cacheData.value.tokenize_on_chars = state === 'custom' ? props.originalTextTokenizeOnChars : '';
    };
    /**
     * 取消分词符popover
     */
    const handleWordBreakerCancelClick = () => {
      // 关闭 tippy
      tippyInstances.forEach(i => i?.hide());
    };
    /**
     * 更新列表的内容
     * @param list
     * @param row
     * @param updateCallback
     * @returns
     */
    const updateList = (list: FieldItem[], row: FieldItem, updateCallback: (item: FieldItem) => FieldItem) => {
      return list.map(item => {
        if (item.field_index === row.field_index && item.field_name === row.field_name) {
          return updateCallback(item);
        }
        return { ...item };
      });
    };
    /**
     * 分词符render
     * @param row
     * @returns
     */
    const renderWordBreaker = (h, { row }) => {
      if (row.field_type === 'string' && !row.is_built_in) {
        return (
          <div class='word-breaker'>
            <span
              class='word-breaker-edit'
              data-field-index={row.field_index}
              data-field-name={row.field_name}
            >
              {row.is_analyzed ? (
                <div class='analyzed-box'>
                  {row.tokenize_on_chars ? row.tokenize_on_chars : t('自然语言分词')}
                  {t('大小写敏感')}: {row.is_case_sensitive ? t('是') : t('否')}
                </div>
              ) : (
                <span>{t('不分词')}</span>
              )}
              <i class='select-angle bk-icon icon-angle-down' />
            </span>
            <div
              style={{ display: 'none' }}
              class='word-breaker-popover'
            >
              <div class='word-breaker-menu-content'>
                <div class='menu-item'>
                  <span class='menu-item-label'>{t('分词')}</span>
                  <bk-switcher
                    // disabled={getCustomizeDisabled(props.row, 'analyzed')}
                    theme='primary'
                    value={cacheData.value.is_analyzed}
                    on-change={value => {
                      cacheData.value.is_analyzed = value;
                    }}
                    // on-change={handelChangeAnalyzed}
                  />
                </div>
                <div class='menu-item'>
                  <span class='menu-item-label'>{t('分词符')}</span>
                  <div class='bk-button-group'>
                    {participleList.map(option => (
                      <bk-button
                        key={option.id}
                        class={{
                          'participle-btn': true,
                          'is-selected': currentParticipleState.value === option.id,
                        }}
                        data-test-id={`fieldExtractionBox_button_filterMethod${option.id}`}
                        disabled={!cacheData.value.is_analyzed && option.id === 'custom'}
                        size='small'
                        // disabled={() => getCustomizeDisabled(row)}
                        on-click={() => handleChangeParticipleState(option.id)}
                      >
                        {option.name}
                      </bk-button>
                    ))}
                  </div>
                  {currentParticipleState.value === 'custom' && (
                    <bk-input
                      class='custom-input'
                      value={cacheData.value.tokenize_on_chars}
                      on-change={value => {
                        cacheData.value.tokenize_on_chars = value;
                      }}
                      // disabled={getCustomizeDisabled(props.row)}
                    />
                  )}
                </div>
                <div class='menu-item'>
                  <span class='menu-item-label'>{t('大小写敏感')}</span>
                  <bk-switcher
                    // disabled={getCustomizeDisabled(props.row)}
                    theme='primary'
                    value={cacheData.value.is_case_sensitive}
                    on-change={value => {
                      cacheData.value.is_case_sensitive = value;
                    }}
                  />
                </div>
                <div class='menu-footer'>
                  <bk-button
                    data-row-index={row.field_index}
                    data-row-name={row.field_name}
                    size='small'
                    theme='primary'
                    on-click={() => {
                      handleWordBreakerCancelClick();
                      // 通过按钮的 data 属性重新找到行数据（确保使用的是最新数据）
                      const targetRow = props.data.find(
                        item => item.field_index === row.field_index && item.field_name === row.field_name,
                      );
                      if (targetRow) {
                        const newList = updateList(props.data, targetRow, item => ({ ...item, ...cacheData.value }));
                        emit('change', newList);
                      }
                    }}
                  >
                    {t('确定')}
                  </bk-button>
                  <bk-button
                    size='small'
                    on-Click={handleWordBreakerCancelClick}
                  >
                    {t('取消')}
                  </bk-button>
                </div>
              </div>
            </div>
          </div>
        );
      }
      return <div class='disabled-work'>{t('无需设置')}</div>;
    };
    /**
     * 值 render
     * @param row
     * @returns
     */
    const renderValue = (h, { row }) => {
      if (!row.is_built_in) {
        return (
          <div
            class='word-breaker bg-gray'
            title={row.value}
            v-bkloading={{ isLoading: props.refresh, size: 'mini' }}
          >
            {row.value}
          </div>
        );
      }
      return <div class='disabled-work'>{t('暂无预览')}</div>;
    };
    /**
     * 渲染分词符的popover
     * @returns
     */
    const initMenuPop = () => {
      // 销毁旧实例，避免重复绑定
      destroyTippyInstances();

      const targets = document.querySelectorAll('.fields-table-box .t-table__body .word-breaker-edit');
      if (!targets.length) {
        return;
      }

      const instances = tippy(targets as unknown as HTMLElement[], {
        trigger: 'click',
        placement: 'top',
        theme: 'light word-breaker-theme-popover',
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
        onShow(instance) {
          const reference = instance.reference as HTMLElement;
          reference.classList.add('is-hover');

          // 通过 data 属性获取当前行的标识信息
          const fieldIndex = reference.dataset.fieldIndex;
          const fieldName = reference.dataset.fieldName;

          // 根据标识找到对应的行数据
          const currentRow = props.data.find(
            item => String(item.field_index) === fieldIndex && item.field_name === fieldName,
          );

          // 如果有行数据，初始化 cacheData
          if (currentRow) {
            cacheData.value = {
              is_analyzed: currentRow.is_analyzed,
              tokenize_on_chars: currentRow.tokenize_on_chars || '',
              is_case_sensitive: currentRow.is_case_sensitive,
            };
            currentParticipleState.value = currentRow.tokenize_on_chars ? 'custom' : 'default';
          }
        },
        onHide(instance) {
          (instance.reference as HTMLElement).classList.remove('is-hover');
        },
        content(reference) {
          const btn = reference as HTMLElement;
          // 约定：内容紧跟在按钮后的兄弟元素中
          const container = btn.nextElementSibling as HTMLElement | null;
          const contentNode = container?.querySelector('.word-breaker-menu-content') as HTMLElement | null;
          return (contentNode ?? container ?? document.createElement('div')) as unknown as Element;
        },
      });

      // tippy 返回单个或数组，这里统一转为数组
      tippyInstances = Array.isArray(instances) ? instances : [instances];
    };
    /** 销毁所有tippy */
    const destroyTippyInstances = () => {
      // biome-ignore lint/complexity/noForEach: 需要遍历数组并执行销毁操作，forEach 更简洁
      tippyInstances.forEach(i => {
        try {
          i.hide();
          i.destroy();
        } catch (_) {}
      });
      tippyInstances = [];
    };
    onMounted(() => {
      nextTick(() => {
        initMenuPop();
      });
    });
    onBeforeUnmount(() => {
      destroyTippyInstances();
    });
    watch(
      () => props.loading,
      (val: boolean) => {
        if (!val) {
          setTimeout(() => {
            initMenuPop();
          }, 1000);
        }
      },
    );
    /**
     * 刷新值
     */ const handleFreshValue = () => {
      emit('refresh');
    };

    /**
     * 当前字段类型是否禁用
     * @param row
     * @param option
     * @returns
     */
    const isTypeDisabled = (row, option) => {
      if (row.verdict) {
        // 不是数值，相关数值类型选项被禁用
        return ['int', 'long', 'double', 'float'].includes(option.id);
      }
      // 是数值，如果值大于 MAX_INT_VALUE 即 2^31 - 1，int 选项被禁用
      return option.id === 'int' && row.value > MAX_INT_VALUE;
    };

    /**
     * 展开/折叠对象字段
     * @param row
     * @param show
     */
    const expandObject = (row: FieldItem, show: boolean) => {
      row.expand = show;
      const index = formData.value.tableList.findIndex(item => item.field_name === row.field_name);

      if (show && index !== -1) {
        formData.value.tableList.splice(index + 1, 0, ...(row.children || []));
      } else if (!show && index !== -1) {
        const childrenCount = row.children?.length || 0;
        formData.value.tableList.splice(index + 1, childrenCount);
      }
    };
    /**
     * 检查字段名是否与其他字段冲突
     * @param fieldIndex 当前字段索引
     * @param fieldName 字段名称
     * @param isTime 是否为时间字段（时间字段允许重复）
     * @returns 是否存在冲突
     */
    const filedNameIsConflict = (fieldIndex: number, fieldName: string, isTime = false): boolean => {
      const otherFieldNameList = props.data.filter(item => {
        // 指定日志时间的字段名会重复，需要排除
        return item.field_index !== fieldIndex && (!isTime || !item.is_time);
      });
      return otherFieldNameList.some(item => item.field_name === fieldName);
    };

    /**
     * 验证并处理字段名输入
     * 对于 JSON 提取方式，如果字段名不符合标准命名规范，自动添加引号包裹
     * @param row 字段行数据
     */
    const validateInput = (row: FieldItem): void => {
      if (!row.field_name || props.extractMethod !== 'bk_log_json') {
        return;
      }
      const quotedPattern = /^".*"$/; // 检测是否已被引号包裹
      const validFieldPattern = /^[A-Za-z_][0-9A-Za-z_]*$/; // 标准字段名格式：字母或下划线开头，只能包含字母、数字和下划线

      // 如果未被引号包裹且不符合标准命名规范，则添加引号
      if (!quotedPattern.test(row.field_name) && !validFieldPattern.test(row.field_name)) {
        row.field_name = `"${row.field_name}"`;
      }
    };

    /**
     * 检查字段名是否与系统内置字段重复
     * @param fieldName 字段名称
     * @returns 是否重复
     */
    const isBuiltInFieldConflict = (fieldName: string): boolean => {
      return globalsData.value.field_built_in?.some(item => item.id === fieldName.toLowerCase()) ?? false;
    };

    /**
     * 校验单个字段名称
     * @param row 字段行数据
     * @returns 错误信息字符串，无错误返回空字符串
     */
    const checkFieldNameItem = (row: FieldItem): string => {
      // 从 props.data 中获取最新的行数据，确保使用的是最新数据
      const currentRow = props.data.find(
        item => item.field_index === row.field_index && item.field_name === row.field_name,
      );
      if (!currentRow) {
        return '';
      }

      // 先验证并处理输入（自动添加引号等）
      validateInput(currentRow);

      // 如果已有别名，则不需要校验字段名，但需要清空 fieldAliasErr
      if (currentRow.alias_name) {
        currentRow.fieldAliasErr = '';
        currentRow.btnShow = false;
        return '';
      }

      const { field_name, is_delete, field_index, is_time } = currentRow;
      let result = ''; // 字段名错误信息
      let aliasResult = ''; // 别名提示信息
      let width = 220; // 提示框宽度
      let btnShow = false; // 是否显示字段映射按钮

      // 已删除的字段不需要校验
      if (is_delete) {
        currentRow.fieldErr = '';
        currentRow.fieldAliasErr = '';
        currentRow.width = width;
        if (!currentRow.alias_name) {
          currentRow.btnShow = false;
        }
        return '';
      }

      // 校验字段名是否为空
      if (!field_name) {
        result = REQUIRED_FIELD_MSG;
      }
      // 校验字段名格式：只能包含 a-z、A-Z、0-9 和 _，且不能以 _ 开头和结尾
      else if (!/^(?!_)(?!.*?_$)^[A-Za-z0-9_]+$/gi.test(field_name)) {
        if (props.selectEtlConfig === 'bk_log_json') {
          // JSON 模式下，格式错误时提示用户重命名
          btnShow = true;
          aliasResult = t(
            '检测到字段名称包含异常值，只能包含a-z、A-Z、0-9和_，且不能以_开头和结尾。请重命名，命名后原字段将被覆盖；',
          );
          width = 300;
        } else {
          result = INVALID_FIELD_NAME_MSG;
        }
      }
      // 校验是否与系统内置字段重复
      else if (isBuiltInFieldConflict(field_name)) {
        if (props.extractMethod !== 'bk_log_json') {
          // 非 JSON 模式下，直接报错
          result =
            props.extractMethod === 'bk_log_regexp'
              ? t('字段名与系统字段重复，必须修改正则表达式')
              : DUPLICATE_BUILT_IN_MSG;
        } else {
          // JSON 模式下，提示用户重命名
          btnShow = true;
          aliasResult = t('检测到字段名与系统内置名称冲突。请重命名,命名后原字段将被覆盖');
          width = 220;
        }
      }
      // 校验字段名是否与其他字段冲突（分隔符模式或 JSON 模式）
      else if (props.extractMethod === 'bk_log_delimiter' || props.selectEtlConfig === 'bk_log_json') {
        result = filedNameIsConflict(field_index, field_name, is_time) ? FIELD_CONFLICT_MSG : '';
      }

      // 更新行数据的错误信息
      if (!currentRow.alias_name) {
        currentRow.btnShow = btnShow;
      }
      currentRow.fieldErr = result;
      currentRow.fieldAliasErr = aliasResult;
      currentRow.width = width;

      return result || aliasResult;
    };

    /**
     * 校验单个字段的别名
     * @param row 字段行数据
     * @returns 错误信息字符串，无错误返回空字符串
     */
    const checkAliasNameItem = (row: FieldItem): string => {
      // 从 props.data 中获取最新的行数据，确保使用的是最新数据
      const currentRow = props.data.find(
        item => item.field_index === row.field_index && item.field_name === row.field_name,
      );
      if (!currentRow) {
        return '';
      }

      const { alias_name, is_delete, field_index } = currentRow;
      let queryResult = '';
      currentRow.btnShow = false;

      // 如果别名为空，显示重命名输入框
      if (!alias_name) {
        currentRow.alias_name_show = false;
        currentRow.btnShow = true;
        // 别名为空时，需要重新校验字段名，因为字段名的问题可能仍然存在
        checkFieldNameItem(currentRow);
        return '';
      }

      // 已删除的字段不需要校验
      if (is_delete) {
        currentRow.fieldErr = '';
        currentRow.fieldAliasErr = '';
        return '';
      }

      // 校验别名格式：只能包含 a-z、A-Z、0-9 和 _
      if (!/^[A-Za-z0-9_]+$/g.test(alias_name)) {
        queryResult = INVALID_ALIAS_NAME_MSG;
      }
      // 校验别名是否与系统内置字段重复
      else if (isBuiltInFieldConflict(alias_name)) {
        queryResult = DUPLICATE_BUILT_IN_MSG;
      }
      // 校验别名是否与字段名重复
      else if (alias_name === currentRow.field_name) {
        queryResult = ALIAS_FIELD_DUPLICATE_MSG;
      }
      // JSON 模式下，校验别名是否与其他字段冲突
      else if (props.selectEtlConfig === 'bk_log_json') {
        queryResult = filedNameIsConflict(field_index, alias_name) ? t('重命名字段名称冲突, 请调整') : '';
      }

      // 更新行数据的错误信息
      currentRow.fieldErr = queryResult;

      // 如果别名校验通过（queryResult 为空），清空 fieldAliasErr（因为问题已通过别名解决）
      // 如果别名校验失败，保留 fieldAliasErr（因为字段名的问题仍然存在）
      if (!queryResult) {
        currentRow.fieldAliasErr = '';
        currentRow.btnShow = false;
      }

      return queryResult;
    };

    /**
     * 批量校验所有字段名称和别名
     * 注意：此函数保留用于 API 兼容性，可能被父组件通过 ref 调用
     * @returns Promise，校验通过 resolve，失败 reject
     */
    // biome-ignore lint/correctness/noUnusedVariables: 保留用于 API 兼容性，可能被父组件通过 ref 调用
    const checkFieldName = (): Promise<void> => {
      return new Promise((resolve, reject) => {
        try {
          let hasError = false;

          // 使用 for...of 循环替代 forEach，避免 linter 警告
          for (const row of props.data) {
            // 跳过内置字段和对象键字段
            if (row.is_built_in || row.is_objectKey) {
              continue;
            }

            // 如果有别名，优先校验别名；否则校验字段名
            const aliasError = row.alias_name ? checkAliasNameItem(row) : '';
            const fieldError = checkFieldNameItem(row);

            if (aliasError || fieldError) {
              hasError = true;
            }
          }

          if (hasError) {
            console.log('FieldName或aliasName校验错误');
            reject(false);
          } else {
            resolve();
          }
        } catch (err) {
          console.log('FieldName校验错误', err);
          reject(err);
        }
      });
    };

    /**
     * 批量校验所有字段的别名
     * 注意：此函数保留用于 API 兼容性，可能被父组件通过 ref 调用
     * @returns Promise，校验通过 resolve，失败 reject
     */
    // biome-ignore lint/correctness/noUnusedVariables: 保留用于 API 兼容性，可能被父组件通过 ref 调用
    const checkAliasName = (): Promise<void> => {
      return new Promise((resolve, reject) => {
        try {
          let hasError = false;

          // 使用 for...of 循环替代 forEach，避免 linter 警告
          for (const row of props.data) {
            // 跳过内置字段
            if (row.is_built_in) {
              continue;
            }

            const error = checkAliasNameItem(row);
            if (error) {
              hasError = true;
            }
          }

          if (hasError) {
            console.log('AliasName校验错误');
            reject(false);
          } else {
            resolve();
          }
        } catch (err) {
          console.log('AliasName校验错误', err);
          reject(err);
        }
      });
    };
    /**
     * 校验单个字段的类型
     * @param row 字段行数据
     * @returns 校验是否通过
     */
    const checkTypeItem = (row: FieldItem): boolean => {
      // 对象键字段不需要校验类型
      if (row.is_objectKey) {
        return true;
      }

      // 已删除的字段不需要校验类型
      if (row.is_delete) {
        row.typeErr = false;
        return true;
      }

      // 校验字段类型是否为空
      row.typeErr = !row.field_type;
      return !row.typeErr;
    };

    /**
     * 批量校验所有字段的类型
     * 注意：此函数保留用于 API 兼容性，可能被父组件通过 ref 调用
     * @returns Promise，校验通过 resolve，失败 reject
     */
    // biome-ignore lint/correctness/noUnusedVariables: 保留用于 API 兼容性，可能被父组件通过 ref 调用
    const checkType = (): Promise<void> => {
      return new Promise((resolve, reject) => {
        try {
          let hasError = false;

          // 使用 for...of 循环替代 forEach，避免 linter 警告
          for (const row of props.data) {
            if (!checkTypeItem(row)) {
              hasError = true;
            }
          }

          if (hasError) {
            console.log('Type校验错误');
            reject(false);
          } else {
            resolve();
          }
        } catch (err) {
          console.log('Type校验错误', err);
          reject(err);
        }
      });
    };

    /**
     * 批量校验字段表格的所有字段
     * 包括：别名校验、字段名校验、类型校验
     * @returns Promise 数组，包含所有校验的 Promise
     */
    const validateFieldTable = (): Promise<void>[] => {
      // 执行所有校验（校验逻辑是同步的，会立即设置错误状态）
      const promises = [checkAliasName(), checkFieldName(), checkType()];

      // 使用 nextTick 确保在所有校验方法执行完成后再触发更新
      // 这样可以让错误样式正确显示
      nextTick(() => {
        // 触发更新，确保 UI 反映最新的错误状态
        emit('change', [...props.data]);
      });

      // 在所有 Promise 完成后也触发一次更新（处理异步情况）
      Promise.allSettled(promises).then(() => {
        nextTick(() => {
          emit('change', [...props.data]);
        });
      });

      return promises;
    };

    // 暴露方法给父组件使用
    expose({
      validateFieldTable,
      checkFieldName,
      checkAliasName,
      checkType,
    });

    /**
     * 处理字段重命名（显示别名输入框）
     * @param row 字段行数据
     */
    const handlePopoverRename = (row: FieldItem): void => {
      // 从 props.data 中获取最新的行数据，确保使用的是最新数据
      const currentRow = props.data.find(
        item => item.field_index === row.field_index && item.field_name === row.field_name,
      );
      if (!currentRow) {
        return;
      }

      // 设置 alias_name_show 为 true，显示别名输入框
      const newList = updateList(props.data, currentRow, item => ({
        ...item,
        alias_name_show: true,
        btnShow: false, // 隐藏字段映射按钮
      }));

      // 触发更新事件，通知父组件数据变化
      emit('change', newList);
    };

    /**
     * 检查字段编辑是否禁用
     * @param row
     * @returns
     */

    const getFieldEditDisabled = (row: FieldItem) => {
      if (row.is_delete || row.is_built_in || row.field_type === 'object') {
        return true;
      }
      if (props.selectEtlConfig === 'bk_log_json') {
        return false;
      }
      return props.extractMethod !== 'bk_log_delimiter' || !!props.isSetDisabled;
    };
    /**
     * 字段名render
     * @param row
     * @returns
     */
    const renderFieldName = (h, { row }) => {
      if (isPreviewMode.value || row.is_objectKey) {
        return (
          <div
            class='overflow-tips-field-name'
            v-bk-tooltips={{ content: row.field_name, placement: 'top' }}
          >
            {row.is_objectKey && <span class='ext-btn bklog-icon bklog-subnode' />}
            <span>{row.field_name}</span>
          </div>
        );
      }
      return (
        <div
          class={{
            'is-required is-error': row.fieldErr,
            'disable-background': row.is_built_in,
            'participle-form-item': true,
          }}
        >
          {row.field_type === 'object' && row.children?.length && !row.expand && (
            <span
              class='ext-btn rotate bklog-icon bklog-arrow-down-filled'
              on-click={() => expandObject(row, true)}
            />
          )}
          {row.field_type === 'object' && row.children?.length && row.expand && (
            <span
              class='ext-btn bklog-icon bklog-arrow-down-filled'
              on-click={() => expandObject(row, false)}
            />
          )}

          {row.is_built_in && row.alias_name ? (
            <bk-input
              class='participle-field-name-input-pl5'
              disabled={getFieldEditDisabled(row)}
              value={row.field_name}
              on-change={value => {
                const newList = updateList(props.data, row, item => ({ ...item, field_name: value }));
                emit('change', newList);
              }}
              on-blur={() => {
                // 从最新的 props.data 中获取当前行数据
                const currentRow = props.data.find(
                  item => item.field_index === row.field_index && item.field_name === row.field_name,
                );
                if (currentRow) {
                  checkFieldNameItem(currentRow);
                  // 校验后需要触发更新，确保 UI 反映最新的错误状态
                  emit('change', [...props.data]);
                }
              }}
            />
          ) : (
            <bk-input
              class={{
                'participle-field-name-input': row.alias_name || row.alias_name_show,
                'participle-field-name-input-pl5': true,
              }}
              disabled={getFieldEditDisabled(row)}
              value={row.field_name}
              on-change={value => {
                const newList = updateList(props.data, row, item => ({ ...item, field_name: value }));
                emit('change', newList);
              }}
              on-blur={() => {
                // 从最新的 props.data 中获取当前行数据
                const currentRow = props.data.find(
                  item => item.field_index === row.field_index && item.field_name === row.field_name,
                );
                if (currentRow) {
                  checkFieldNameItem(currentRow);
                  // 校验后需要触发更新，确保 UI 反映最新的错误状态
                  emit('change', [...props.data]);
                }
              }}
            />
          )}
          {(row.alias_name || row.alias_name_show) && !row.is_built_in && (
            <span class={{ 'participle-icon': true, 'participle-icon-color': getFieldEditDisabled(row) }}>
              <i
                style='color: #3a84ff;'
                class='bk-icon bklog-icon bklog-yingshe'
              />
            </span>
          )}
          {(row.alias_name || row.alias_name_show) && !row.is_built_in && (
            <bk-input
              class={{
                'participle-alias-name-input': true,
                'input-error': !!row.fieldErr,
              }}
              disabled={getFieldEditDisabled(row)}
              placeholder={t('请输入映射名')}
              value={row.alias_name}
              on-change={value => {
                const newList = updateList(props.data, row, item => ({ ...item, alias_name: value }));
                emit('change', newList);
              }}
              on-blur={() => {
                // 从最新的 props.data 中获取当前行数据
                const currentRow = props.data.find(
                  item => item.field_index === row.field_index && item.field_name === row.field_name,
                );
                if (currentRow) {
                  checkAliasNameItem(currentRow);
                  // 校验后需要触发更新，确保 UI 反映最新的错误状态
                  emit('change', [...props.data]);
                }
              }}
            />
          )}

          {row.fieldErr && !row.btnShow && (
            <i
              style='right: 8px'
              class='bk-icon icon-exclamation-circle-shape tooltips-icon'
              v-bk-tooltips={{ content: row.fieldErr, placement: 'top' }}
            />
          )}
          {props.selectEtlConfig === 'bk_log_json' && row.fieldAliasErr && !row.alias_name && !row.alias_name_show && (
            <bk-button
              class='tooltips-btn'
              on-click={() => handlePopoverRename(row)}
              v-bk-tooltips={{
                width: row.width,
                content: row.fieldAliasErr || t('点击重命名'),
                placement: 'top',
              }}
              theme='danger'
            >
              {t('重命名')}
            </bk-button>
          )}
        </div>
      );
      // return (
      //   <bk-input
      //     disabled={row.is_built_in}
      //     value={row.field_name}
      //   />
      // );
    };
    const columns = ref([
      {
        title: t('来源'),
        colKey: 'is_built_in',
        align: 'center',
        width: 62,
        cell: renderSource,
        className: () => 'fields-tag-column',
      },
      {
        title: t('字段名'),
        colKey: 'field_name',
        cell: renderFieldName,
        className: () => 'fields-table-column',
      },
      {
        title: t('类型'),
        colKey: 'field_type',
        className: () => 'fields-table-column',
        cell: (h, { row }) => (
          <div class='type-select-wrapper'>
            <bk-select
              class={{ 'type-error': row.typeErr }}
              clearable={false}
              disabled={row.is_built_in}
              value={row.field_type}
              on-change={value => {
                console.log(value, 'value===');
                if (value === 'string') {
                  setTimeout(() => {
                    initMenuPop();
                  }, 1000);
                }
                const newList = updateList(props.data, row, item => ({
                  ...item,
                  field_type: value,
                  typeErr: false, // 选择类型后清除错误状态
                }));
                emit('change', newList);
              }}
            >
              {(globalsData.value.field_data_type || []).map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  disabled={isTypeDisabled(row, option)}
                  name={option.name}
                />
              ))}
            </bk-select>
            {row.typeErr && (
              <i
                class='bk-icon icon-exclamation-circle-shape tooltips-icon type-error-icon'
                v-bk-tooltips={{ content: t('必填项'), placement: 'top' }}
              />
            )}
          </div>
        ),
      },
      {
        title: t('分词符'),
        colKey: 'is_analyzed',
        cell: renderWordBreaker,
        className: () => 'fields-analyzed-column',
      },
      {
        title: 'title-slot-name',
        colKey: 'value',
        cell: renderValue,
        className: () => 'fields-value-column',
      },
      {
        title: t('操作'),
        colKey: 'operation',
        width: 70,
        cell: (h, { row }) => (
          <div class='table-operation'>
            {!row.is_built_in && (
              <i
                class={`bklog-icon bklog-${row.is_delete ? 'visible' : 'invisible'} icons`}
                v-bk-tooltips={row.is_delete ? t('复原') : t('隐藏')}
                on-click={() => isDisableOperate(row)}
              />
            )}
            {row.is_add_in && (
              <i
                class='bklog-icon bklog-log-delete icons del-icon'
                v-bk-tooltips={t('删除')}
                on-click={() => deleteField(row)}
              />
            )}
          </div>
        ),
      },
    ]);
    const handleType = (type: string) => {
      typeKey.value = type;
    };

    const renderTab = () => (
      <div class='tab-list'>
        <span
          class={{
            'tab-item': true,
            'is-selected': typeKey.value === 'visible',
          }}
          on-Click={() => handleType('visible')}
        >
          {t('可见字段')}
          {` (${visibleData.value.length})`}
        </span>
        <span
          class={{
            'tab-item': true,
            'is-selected': typeKey.value === 'invisible',
          }}
          on-Click={() => handleType('invisible')}
        >
          {t('被隐藏字段')}
          {` (${invisibleData.value.length})`}
        </span>
      </div>
    );
    /**
     * 可见字段
     */
    const visibleData = computed(() => {
      return props.data.filter(item => !item.is_delete);
    });
    /**
     * 被隐藏字段
     */
    const invisibleData = computed(() => {
      return props.data.filter(item => item.is_delete);
    });
    const showData = computed(() => {
      return typeKey.value === 'visible' ? visibleData.value : invisibleData.value;
    });

    /**
     * 是否显示内置字段
     */
    const showTableList = computed(() => {
      return showBuiltIn.value ? [...showData.value, ...props.builtInFieldsList] : showData.value;
    });

    const handleShowBuiltIn = () => {
      showBuiltIn.value = !showBuiltIn.value;
    };
    /**
     * 删除字段
     * @param row 行数据
     */
    const deleteField = (row: FieldItem) => {
      // 从列表中过滤掉要删除的字段
      const newList = props.data.filter(
        item => !(item.field_index === row.field_index && item.field_name === row.field_name),
      );
      emit('change', newList);
    };
    /**
     * 显示或者隐藏某个字段
     * @param row
     */
    const isDisableOperate = (row: FieldItem) => {
      const newList = updateList(props.data, row, item => ({ ...item, is_delete: !item.is_delete }));
      emit('change', newList);
    };
    /**
     * 字段表格
     * @returns
     */
    const renderTable = () => (
      <div
        class='fields-table'
        // v-bkloading={{ isLoading: props.loading, zIndex: 10 }}
      >
        <TableComponent
          class='fields-table-box'
          loading={props.loading}
          data={showTableList.value}
          bordered={true}
          skeletonConfig={{
            columns: 6,
            rows: 2,
            widths: ['2%', '24%', '24%', ' 24%', '22%', '4%'],
          }}
          columns={columns.value}
          slots={{
            'title-slot-name': () => (
              <span class='header-text'>
                {t('值')}
                <span
                  class='header-text-link'
                  on-click={handleFreshValue}
                >
                  <i class='bklog-icon bklog-refresh2 link-icon' />
                  {t('刷新')}
                </span>
              </span>
            ),
          }}
        />
      </div>
    );
    /**
     * 新增字段
     */
    const handleAddField = () => {
      // 查找最大 field_index，确保新字段的索引唯一
      const maxIndex: number = props.data.reduce((max: number, item: FieldItem) => {
        return Math.max(max, item.field_index || 0);
      }, 0);

      // 创建新字段对象，field_name 默认为空
      const newField: FieldItem = {
        field_index: maxIndex + 1,
        field_name: '', // 默认为空，由用户填写
        field_type: 'string', // 默认类型为 string
        is_built_in: false,
        is_add_in: true,
        is_objectKey: false,
        is_delete: false,
        is_time: false,
        is_analyzed: false,
        is_case_sensitive: false,
        participleState: 'default',
        alias_name_show: false,
      };

      // 将新字段添加到列表中
      const newList = [...props.data, newField];

      // 发送更新事件给父组件
      emit('change', newList);
    };

    return () => (
      <div class='field-list-main-box'>
        <div class='tab-box'>
          {renderTab()}
          <span class='checkbox-box'>
            <bk-checkbox
              class='mr-5'
              value={showBuiltIn.value}
              on-change={handleShowBuiltIn}
            />
            {t('显示内置字段')}
          </span>
        </div>
        {renderTable()}
        {isAdd.value && (
          <div class='example-box'>
            <span
              class='form-link'
              on-click={handleAddField}
            >
              <i class='bk-icon icon-plus link-icon add-btn' />
              {t('新增字段')}
            </span>
          </div>
        )}
      </div>
    );
  },
});
