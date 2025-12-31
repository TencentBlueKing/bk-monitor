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

import { defineComponent, ref, onMounted, watch, computed, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
// import { debounce } from 'throttle-debounce';

import {
  type btnType,
  type ISelectItem,
  type ITableRowItem,
  operatorSelectList,
  btnGroupList,
  operatorMapping,
  tableRowBaseObj,
} from '../../../utils';
import InfoTips from '../../common-comp/info-tips';
import ValidatorInput from './validator-input';
import $http from '@/api';

import type { IConditions } from '../../../type';
import './log-filter.scss';

/**
 * 日志过滤组件
 */

export default defineComponent({
  name: 'LogFilter',
  props: {
    // 过滤条件配置，用于初始化组件
    conditions: {
      type: Object as () => IConditions,
      default: () => ({ type: 'none' }),
    },
    // 是否为克隆或更新操作，影响日志数据加载逻辑
    isCloneOrUpdate: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['conditions-change'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    // -------------------------- 响应式数据 --------------------------
    /** 过滤器开关状态 */
    const filterSwitcher = ref<boolean>(false);
    /** 是否首次切换到分隔符过滤类型 */
    const isFirstSwitchToSeparator = ref<boolean>(true);
    /** 当前激活的过滤类型（match/separator） */
    const activeFilterType = ref<btnType>('match');
    /** 分隔符（默认|） */
    const separator = ref<string>('|');
    /**
     * 过滤规则数据结构：
     * 外层数组表示过滤组（组间为OR关系）
     * 内层数组表示组内规则（组内为AND关系）
     */
    const filterData = ref<ITableRowItem[][]>([
      [
        {
          fieldindex: '',
          word: '',
          op: '=',
          tableIndex: 0,
        },
      ],
    ]);
    /** 缓存不同过滤类型的规则数据，切换类型时恢复 */
    const filterDataCache = ref({
      match: structuredClone(filterData.value),
      separator: structuredClone(filterData.value),
    });
    /** 原始日志字段选择项（从日志样例解析而来） */
    const originalFilterItemSelect = ref<ISelectItem[]>([]);
    /** 原始日志内容（用于调试分隔符） */
    const logOriginal = ref<string>('');
    /** 原始日志加载状态 */
    const logOriginalLoading = ref<boolean>(false);
    /** 验证器组件引用集合 */
    const validatorInputRefs = ref<Record<string, any>>({});
    /** 是否正在初始化，用于避免初始化时触发 emit */
    const isInitializing = ref<boolean>(false);

    // -------------------------- 计算属性 --------------------------
    /** 全局数据分隔符选项（从store获取） */
    const globalDataDelimiter = computed<ISelectItem[]>(() => {
      return store.getters['globals/globalsData']?.data_delimiter || [];
    });

    /** 当前选中的采集配置（从store获取） */
    const currentCollect = computed<any>(() => {
      return store.getters['collect/curCollect'] || {};
    });

    /** 是否为匹配类型过滤 */
    const isMatchType = computed<boolean>(() => {
      return activeFilterType.value === 'match';
    });
    /** 需要监听的响应式数据集合（用于触发条件变更） */
    //  const watchTarget = computed<{
    //   filterData: ITableRowItem[][];
    //   switcher: boolean;
    //   separator: string;
    // }>(() => ({
    //   filterData: filterData.value,
    //   switcher: filterSwitcher.value,
    //   separator: separator.value,
    // }));

    /** 操作符选择列表（根据当前过滤类型动态调整） */
    const operatorOptions = computed<ISelectItem[]>(() => {
      const targetId = isMatchType.value ? 'include' : 'eq';
      return operatorSelectList.map(option => (option.id === targetId ? { ...option, id: '=' } : option));
    });

    // -------------------------- 核心方法 --------------------------
    /**
     * 向父组件传递过滤条件变更
     */
    const emitConditionsChange = () => {
      // 初始化期间不触发 emit，避免循环调用
      if (isInitializing.value) {
        return;
      }
      emit('conditions-change', getSubmitConditions());
    };

    /**
     * 初始化过滤数据（根据props.conditions）
     */
    const initFilterData = () => {
      // 设置初始化标志，避免触发 emit
      isInitializing.value = true;

      const { type, separator: sep, separator_filters, match_content, match_type } = props.conditions;
      switch (type) {
        case 'none':
          filterSwitcher.value = false;
          break;
        case 'match':
          handleMatchTypeInit(separator_filters, match_content, match_type);
          break;
        case 'separator':
          handleSeparatorTypeInit(sep, separator_filters);
          break;
        default:
          break;
      }

      // 使用 nextTick 确保所有响应式更新完成后再清除标志
      nextTick(() => {
        isInitializing.value = false;
      });
    };

    /**
     * 初始化匹配类型过滤数据
     */
    const handleMatchTypeInit = (separatorFilters?: ITableRowItem[], matchContent?: string, matchType?: string) => {
      filterSwitcher.value = true;
      activeFilterType.value = 'match';

      // 兼容旧数据格式
      if (separatorFilters?.length) {
        filterData.value = splitFiltersIntoGroups(separatorFilters);
      } else {
        const op = matchType === 'include' ? 'include' : '=';
        filterData.value = [
          [
            {
              fieldindex: '-1',
              word: matchContent || '',
              op,
              tableIndex: 0,
            },
          ],
        ];
      }
    };

    /**
     * 初始化分隔符类型过滤数据
     */
    const handleSeparatorTypeInit = (sep?: string, separatorFilters?: ITableRowItem[]) => {
      filterSwitcher.value = true;
      activeFilterType.value = 'separator';
      separator.value = sep || '|';
      filterData.value = separatorFilters
        ? splitFiltersIntoGroups(separatorFilters)
        : [[{ ...tableRowBaseObj, tableIndex: 0 }]];

      // 克隆/更新操作时加载原始日志
      if (props.isCloneOrUpdate) {
        fetchLogOriginal();
      }
    };

    /**
     * 将扁平的过滤规则拆分为分组结构
     * @param filters 扁平的过滤规则数组
     * @returns 分组后的规则（组间OR，组内AND）
     */
    const splitFiltersIntoGroups = (filters: ITableRowItem[]): ITableRowItem[][] => {
      const groups: ITableRowItem[][] = [];
      let currentGroup: ITableRowItem[] = [];

      filters.forEach((filter, index) => {
        // 映射操作符并设置组索引
        const mappedFilter: ITableRowItem = {
          ...filter,
          op: operatorMapping[filter.op] ?? filter.op,
          tableIndex: groups.length,
        };
        currentGroup.push(mappedFilter);

        // 遇到OR逻辑或最后一个元素时，结束当前分组
        if (filters[index + 1]?.logic_op === 'or' || index === filters.length - 1) {
          groups.push(currentGroup);
          currentGroup = [];
        }
      });

      // 处理剩余未分组的规则
      if (currentGroup.length > 0) {
        groups.push(currentGroup);
      }

      return groups;
    };

    /**
     * 更新所有规则的组索引（删除分组后调用）
     */
    const updateTableIndexes = () => {
      filterData.value.forEach((group, groupIndex) => {
        for (const item of group) {
          item.tableIndex = groupIndex;
        }
      });
    };

    /**
     * 删除过滤组
     * @param groupIndex 要删除的组索引
     */
    const deleteFilterGroup = (groupIndex: number) => {
      // 至少保留一个组
      if (filterData.value.length === 1) {
        return;
      }

      filterData.value.splice(groupIndex, 1);
      updateTableIndexes();
    };

    /**
     * 新增过滤组（最多10个）
     */
    const addFilterGroup = () => {
      if (filterData.value.length >= 10) {
        return;
      }

      filterData.value.push([
        {
          ...tableRowBaseObj,
          tableIndex: filterData.value.length,
        },
      ]);
    };

    /**
     * 在组内添加/删除规则行
     * @param rowIndex 行索引
     * @param groupIndex 组索引
     * @param operation 操作类型（add/delete）
     */
    const modifyGroupRows = (rowIndex: number, groupIndex: number, operation: 'add' | 'delete' = 'add') => {
      const currentGroup = filterData.value[groupIndex];

      if (operation === 'add') {
        currentGroup.push({ ...tableRowBaseObj, tableIndex: groupIndex });
      } else {
        // 每组至少保留一行
        if (currentGroup.length === 1) {
          return;
        }
        currentGroup.splice(rowIndex, 1);
      }
    };

    /**
     * 切换过滤类型（match/separator）
     * @param type 目标过滤类型
     */
    const switchFilterType = (type: btnType) => {
      // 缓存当前类型数据
      filterDataCache.value[activeFilterType.value] = structuredClone(filterData.value);
      // 切换到目标类型数据
      filterData.value = filterDataCache.value[type];
      activeFilterType.value = type;

      // 首次切换到分隔符类型且为克隆/更新操作时，加载日志样例
      if (props.isCloneOrUpdate && isFirstSwitchToSeparator.value && type === 'separator') {
        isFirstSwitchToSeparator.value = false;
        fetchLogOriginal(false);
      }
      emitConditionsChange();
    };

    /**
     * 验证输入合法性
     * @returns 验证结果Promise
     */
    const validateInputs = (): boolean => {
      if (!filterSwitcher.value) {
        return true;
      }

      const validateResults: boolean[] = [];

      // 遍历所有规则行进行验证
      filterData.value.forEach((group, groupIndex) => {
        group.forEach((row, rowIndex) => {
          // 验证值输入框（所有类型都需要）
          const valueKey = `value-${groupIndex}-${row.tableIndex}-${rowIndex}`;
          const valueValidator = validatorInputRefs.value[valueKey];
          if (valueValidator && typeof valueValidator.validateValue === 'function') {
            const valueResult = valueValidator.validateValue();
            validateResults.push(valueResult);
          } else {
            // 如果 ref 不存在，检查数据是否为空
            if (!row.word || !String(row.word).trim()) {
              validateResults.push(false);
            } else {
              validateResults.push(true);
            }
          }

          // 验证字段索引输入框（仅分隔符类型需要）
          if (!isMatchType.value) {
            const fieldKey = `match-${groupIndex}-${row.tableIndex}-${rowIndex}`;
            const fieldValidator = validatorInputRefs.value[fieldKey];
            if (fieldValidator && typeof fieldValidator.validateValue === 'function') {
              const fieldResult = fieldValidator.validateValue();
              validateResults.push(fieldResult);
            } else {
              // 如果 ref 不存在，检查数据是否为空
              if (!row.fieldindex || !String(row.fieldindex).trim()) {
                validateResults.push(false);
              } else {
                validateResults.push(true);
              }
            }
          }
        });
      });

      // 检查是否有验证失败的情况
      const allValid = validateResults.every(result => result === true);
      if (allValid) {
        return true;
      }
      return false;
    };

    /**
     * 格式化提交的过滤条件数据
     * @returns 符合接口要求的过滤条件
     */
    const getSubmitConditions = (): IConditions => {
      // 过滤空规则（word为空的行）
      const validGroups = filterData.value;

      // 扁平化规则并添加逻辑运算符（组间OR，组内AND）
      let flatConditions: Array<ITableRowItem & { logic_op: string }> = validGroups.flatMap((group, groupIndex) => {
        return group.map((row, rowIndex) => {
          const { tableIndex, ...rest } = row;
          return {
            ...rest,
            // 第一组或组内非首行用AND，其他组首行用OR
            logic_op: groupIndex === 0 || rowIndex !== 0 ? 'and' : 'or',
          };
        });
      });

      // 匹配类型特殊处理：固定字段索引为-1
      if (isMatchType.value) {
        flatConditions = flatConditions.map(item => ({
          ...item,
          fieldindex: '-1',
        }));
      }

      return {
        type: activeFilterType.value,
        separator: separator.value,
        separator_filters: flatConditions,
      };
    };

    /**
     * 获取原始日志数据（用于分隔符调试）
     * @param isDebug 是否在获取后自动调试
     */
    const fetchLogOriginal = async (isDebug = true) => {
      try {
        const res = await $http.request(
          'source/dataList',
          {
            params: {
              collector_config_id: currentCollect.value.collector_config_id,
            },
          },
          { catchIsShowMessage: false },
        );

        if (res.data?.length) {
          logOriginal.value = res.data[0].etl.data || '';
          if (logOriginal.value && isDebug) {
            debugLogOrigin(false);
          }
        }
      } catch (error) {
        console.log(t('获取原始日志失败:'), error);
      }
    };

    /**
     * 调试原始日志，解析字段列表
     */
    const debugLogOrigin = async (needLoading = true) => {
      try {
        logOriginalLoading.value = needLoading;
        const res = await $http.request('clean/getEtlPreview', {
          data: {
            etl_config: 'bk_log_delimiter',
            etl_params: { separator: separator.value },
            data: logOriginal.value,
          },
        });

        // 格式化字段选择项
        originalFilterItemSelect.value = res.data.fields.map((item: any) => ({
          name: `${t('第{n}列', { n: item.field_index })} | ${item.value}`,
          id: String(item.field_index),
          value: item.value,
        }));
      } catch (error) {
        console.warn(t('日志调试失败:'), error);
      } finally {
        logOriginalLoading.value = false;
      }
    };

    /**
     * 检查操作符是否可禁用（组内仅一行时删除按钮禁用）
     * @param rowIndex 行索引
     * @param groupIndex 组索引
     * @returns 是否禁用
     */
    const isOperatorDisabled = (rowIndex: number, groupIndex: number): boolean => {
      return rowIndex === 0 && filterData.value[groupIndex].length === 1;
    };

    /**
     * 注册验证器组件引用
     * @param el 组件实例
     * @param key 唯一标识
     */
    const registerValidatorRef = (el: any, key: string) => {
      if (el) {
        validatorInputRefs.value[key] = el;
      }
    };

    // -------------------------- 生命周期 --------------------------
    onMounted(() => {
      initFilterData();
      // 根据初始条件自动开启过滤器
      if (props.conditions?.type && props.conditions.type !== 'none') {
        filterSwitcher.value = true;
      }
    });

    // -------------------------- 监听逻辑 --------------------------
    // 监听目标数据变化，防抖触发条件变更事件
    // watch(() => watchTarget.value, debounce(100, emitConditionsChange), { deep: true, immediate: true });

    watch(
      () => props.conditions,
      (newVal, oldVal) => {
        // 深度比较，避免相同引用时重复初始化
        if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
          initFilterData();
        }
      },
      { deep: true },
    );

    // -------------------------- 暴露方法 --------------------------
    expose({
      validateInputs,
    });

    // -------------------------- 渲染辅助方法 --------------------------
    /**
     * 渲染字段索引输入框（仅分隔符类型显示）
     */
    const renderFieldIndexInput = (groupIndex: number, row: ITableRowItem, rowIndex: number) => (
      <ValidatorInput
        ref={(el: any) => registerValidatorRef(el, `match-${groupIndex}-${row.tableIndex}-${rowIndex}`)}
        active-type={activeFilterType.value}
        input-type={'number'}
        original-filter-item-select={originalFilterItemSelect.value}
        placeholder={t('请输入列数')}
        row-data={row}
        table-index={row.tableIndex}
        value={row.fieldindex}
        on-change={(val: string) => {
          row.fieldindex = val;
          emitConditionsChange();
        }}
      />
    );

    /**
     * 渲染值输入框
     */
    const renderValueInput = (groupIndex: number, row: ITableRowItem, rowIndex: number) => (
      <ValidatorInput
        ref={el => registerValidatorRef(el, `value-${groupIndex}-${row.tableIndex}-${rowIndex}`)}
        active-type={activeFilterType.value}
        placeholder={['regex', 'nregex'].includes(row.op) ? t('支持正则匹配，如18*123') : t('请输入')}
        row-data={row}
        value={row.word}
        on-change={(val: string) => {
          row.word = val;
          emitConditionsChange();
        }}
      />
    );

    /**
     * 渲染操作符选择器
     */
    const renderOperatorSelect = (row: ITableRowItem) => (
      <bk-select
        class='item-select'
        clearable={false}
        value={row.op}
        on-selected={(val: string) => {
          row.op = val;
          emitConditionsChange();
        }}
      >
        {operatorOptions.value.map(option => (
          <bk-option
            id={option.id}
            key={option.id}
            name={option.name}
          />
        ))}
      </bk-select>
    );

    /**
     * 渲染行操作按钮（添加/删除行）
     */
    const renderRowOperators = (row: ITableRowItem, rowIndex: number) => (
      <div class='item-tool btns-group'>
        <i
          class='bk-icon icon-plus-circle-shape icons'
          on-Click={() => modifyGroupRows(rowIndex, row.tableIndex, 'add')}
        />
        <i
          class={{
            'bk-icon icon-minus-circle-shape icons': true,
            disabled: isOperatorDisabled(rowIndex, row.tableIndex),
          }}
          on-Click={() => modifyGroupRows(rowIndex, row.tableIndex, 'delete')}
        />
      </div>
    );

    /**
     * 渲染表格头部
     */
    const renderTableHeader = () => (
      <div class='table-box-head'>
        {!isMatchType.value && <div class='item-default'>{t('过滤参数')}</div>}
        <div class='item-default'>{t('操作符')}</div>
        <div class='item-default'>Value</div>
        <div class='item-tool'>{t('操作')}</div>
      </div>
    );

    /**
     * 渲染表格行
     */
    const renderTableRow = (row: ITableRowItem, rowIndex: number, groupIndex: number) => (
      <div class='table-box-item'>
        {!isMatchType.value && <div class='item-default'>{renderFieldIndexInput(groupIndex, row, rowIndex)}</div>}
        <div class='item-default'>{renderOperatorSelect(row)}</div>
        <div class='item-default'>{renderValueInput(groupIndex, row, rowIndex)}</div>
        {renderRowOperators(row, rowIndex)}
      </div>
    );

    /**
     * 渲染过滤组内容
     */
    const renderFilterGroup = (group: ITableRowItem[], groupIndex: number) => (
      <div class='table-box-main'>
        {renderTableHeader()}
        <div class='custom-table-body'>{group.map((row, rowIndex) => renderTableRow(row, rowIndex, groupIndex))}</div>
      </div>
    );

    // -------------------------- 主渲染函数 --------------------------
    return () => (
      <div class='log-filter-main'>
        {/* 过滤器开关区域 */}
        <div class='switch-box'>
          <bk-switcher
            size='large'
            theme='primary'
            value={filterSwitcher.value}
            on-change={(val: boolean) => {
              filterSwitcher.value = val;
              emitConditionsChange();
            }}
          />
          <InfoTips
            class='ml-12'
            tips={t('过滤器支持采集时过滤不符合的日志内容，请保证采集器已升级到最新版本')}
          />
        </div>

        {/* 过滤器配置区域（开关开启时显示） */}
        {filterSwitcher.value && (
          <div class='log-filter-box'>
            {/* 过滤类型切换按钮组 */}
            <div class='bk-button-group'>
              {btnGroupList.map(item => (
                <bk-button
                  key={item.id}
                  class={{ 'is-selected': activeFilterType.value === item.id }}
                  size='small'
                  on-Click={() => switchFilterType(item.id as btnType)}
                >
                  {item.name}
                </bk-button>
              ))}
            </div>

            {/* 分隔符配置区域（仅分隔符类型显示） */}
            {!isMatchType.value && (
              <div class='separator-box'>
                <div class='separator-box-top'>
                  <bk-select
                    class='separator-box-top-select'
                    clearable={false}
                    value={separator.value}
                    on-selected={(val: string) => {
                      separator.value = val;
                    }}
                  >
                    {globalDataDelimiter.value.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                  <bk-button
                    disabled={!(logOriginal.value && separator.value) || logOriginalLoading.value}
                    theme='primary'
                    on-Click={debugLogOrigin}
                  >
                    {t('调试')}
                  </bk-button>
                </div>
                <div class='input-style'>
                  <bk-input
                    class='separator-box-bottom'
                    v-bkloading={{ isLoading: logOriginalLoading.value }}
                    placeholder={t('请输入日志样例')}
                    rows={3}
                    type='textarea'
                    value={logOriginal.value}
                    on-input={(val: string) => {
                      logOriginal.value = val;
                    }}
                  />
                </div>
              </div>
            )}

            {/* 过滤规则分组列表 */}
            {filterData.value.map((group, groupIndex) => (
              <div
                key={groupIndex}
                class='table-box'
              >
                <div class='table-box-header'>
                  <span>{t('第{n}组', { n: groupIndex + 1 })}</span>
                  {filterData.value.length > 1 && (
                    <i
                      class='bk-icon icon-delete del-icons'
                      on-Click={() => deleteFilterGroup(groupIndex)}
                    />
                  )}
                </div>
                {renderFilterGroup(group, groupIndex)}
              </div>
            ))}

            {/* 新增过滤组按钮 */}
            <div
              class='add-new-group-btn'
              on-Click={addFilterGroup}
            >
              <i class='bk-icon icon-plus-line icons' />
              <span>{t('新增过滤组')}</span>
            </div>
          </div>
        )}
      </div>
    );
  },
});
