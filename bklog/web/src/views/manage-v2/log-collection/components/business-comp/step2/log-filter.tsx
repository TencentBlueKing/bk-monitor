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

import { defineComponent, ref, onMounted, watch, computed } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { debounce } from 'throttle-debounce';

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

import './log-filter.scss';

type IConditions = {
  type: 'match' | 'none' | 'separator';
  separator?: string;
  separator_filters?: ITableRowItem[];
  match_content?: string;
  match_type?: string;
};

export default defineComponent({
  name: 'LogFilter',
  props: {
    // 过滤条件配置
    conditions: {
      type: Object as () => IConditions,
      default: () => ({ type: 'none' }),
    },
    // 是否为克隆或更新操作
    isCloneOrUpdate: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['conditions-change'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    // 响应式数据
    const filterSwitcher = ref<boolean>(false); // 过滤器开关状态
    const isFirstClickFilterType = ref<boolean>(true); // 是否首次点击过滤类型
    const activeType = ref<btnType>('match'); // 当前过滤类型
    const separator = ref<string>('|'); // 分隔符
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
    const catchFilterData = ref({
      // 缓存不同过滤类型的数据
      match: structuredClone(filterData.value),
      separator: structuredClone(filterData.value),
    });
    const originalFilterItemSelect = ref<ISelectItem[]>([]); // 原始日志字段选择项
    const logOriginal = ref<string>(''); // 原始日志内容
    const logOriginalLoading = ref<boolean>(false); // 原始日志加载状态
    const validatorInputRefs = ref<Record<string, any>>({});

    // 计算属性
    const globalDataDelimiter = computed<ISelectItem[]>(() => {
      return store.getters['globals/globalsData']?.data_delimiter || [];
    });

    const curCollect = computed<any>(() => {
      return store.getters['collect/curCollect'] || {};
    });

    const isMatchType = computed<boolean>(() => {
      return activeType.value === 'match';
    });

    const shouldWatchValue = computed<{
      filterData: ITableRowItem[][];
      switcher: boolean;
      separator: string;
    }>(() => {
      return {
        filterData: filterData.value,
        switcher: filterSwitcher.value,
        separator: separator.value,
      };
    });

    const operatorShowSelectList = computed<ISelectItem[]>(() => {
      const showSelect = structuredClone(operatorSelectList);
      const targetId = isMatchType.value ? 'include' : 'eq';

      return showSelect.map(el => {
        if (el.id === targetId) {
          return { ...el, id: '=' };
        }
        return el;
      });
    });

    /**
     * 向上传递条件变化
     */
    const conditionsChange = () => {
      emit('conditions-change', getSubmitConditionsData());
    };

    watch(
      () => shouldWatchValue.value,
      () => {
        debounce(100, () => {
          conditionsChange();
        });
      },
      { deep: true, immediate: true },
    );

    /**
     * 初始化容器数据
     */
    const initContainerData = () => {
      const { type, separator: sep, separator_filters, match_content, match_type } = props.conditions;

      switch (type) {
        case 'none':
          filterSwitcher.value = false;
          break;
        case 'match':
          filterSwitcher.value = true;
          activeType.value = type;
          // 处理旧数据兼容
          if (separator_filters?.length) {
            filterData.value = splitFilters(separator_filters);
          } else {
            const op = match_type === 'include' ? 'include' : '=';
            filterData.value = [
              [
                {
                  fieldindex: '-1',
                  word: match_content || '',
                  op,
                  tableIndex: 0,
                },
              ],
            ];
          }
          break;
        case 'separator':
          filterSwitcher.value = true;
          activeType.value = type;
          separator.value = sep || '|';
          filterData.value = separator_filters ? splitFilters(separator_filters) : [[tableRowBaseObj]];
          if (props.isCloneOrUpdate) {
            getLogOriginal();
          }
          break;
        default:
          break;
      }
    };

    /**
     * 分割过滤器为分组
     * @param filters - 过滤器数组
     * @returns 分组后的过滤器数据
     */
    const splitFilters = (filters: ITableRowItem[]): ITableRowItem[][] => {
      const groups: ITableRowItem[][] = [];
      let currentGroup: ITableRowItem[] = [];

      filters.forEach((filter, index) => {
        const mappingFilter: ITableRowItem = {
          ...filter,
          op: operatorMapping[filter.op] ?? filter.op,
          tableIndex: groups.length,
        };
        currentGroup.push(mappingFilter);

        // 遇到or逻辑或最后一个元素时结束当前分组
        if (filters[index + 1]?.logic_op === 'or' || index === filters.length - 1) {
          groups.push(currentGroup);
          currentGroup = [];
        }
      });

      // 处理剩余元素
      if (currentGroup.length > 0) {
        groups.push(currentGroup);
      }

      return groups;
    };

    /**
     * 删除过滤器分组
     * @param index - 分组索引
     */
    const handleClickDeleteGroup = (index: number) => {
      if (filterData.value.length === 1) {
        return;
      }
      filterData.value.splice(index, 1);
      // 重新设置分组索引
      const data = filterData.value; // 缓存外层数组，避免重复访问 .value
      for (const [fIndex, fItem] of data.entries()) {
        for (const item of fItem) {
          item.tableIndex = fIndex;
        }
      }
    };

    /**
     * 新增过滤器分组
     */
    const handleClickNewGroupBtn = () => {
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
     * 组内新增或删除行
     * @param rowIndex - 行索引
     * @param tableIndex - 表格索引
     * @param operateType - 操作类型
     */
    const handleAddNewSeparator = (rowIndex: number, tableIndex: number, operateType: 'add' | 'delete' = 'add') => {
      const currentGroup = filterData.value[tableIndex];
      if (operateType === 'add') {
        currentGroup.push({ ...tableRowBaseObj, tableIndex });
      } else {
        if (currentGroup.length === 1) {
          return;
        }
        currentGroup.splice(rowIndex, 1);
      }
    };

    /**
     * 切换过滤类型
     * @param type - 过滤类型
     */
    const handleClickFilterType = (type: btnType) => {
      // 缓存当前类型数据
      catchFilterData.value[activeType.value] = structuredClone(filterData.value);
      // 切换到新类型数据
      filterData.value = catchFilterData.value[type];
      activeType.value = type;

      // 首次切换到分隔符类型时获取原始日志
      if (props.isCloneOrUpdate && isFirstClickFilterType.value && type === 'separator') {
        isFirstClickFilterType.value = false;
        getLogOriginal(false);
      }
    };

    /**
     * 输入框数据验证
     * @returns Promise验证结果
     */
    const inputValidate = (): Promise<boolean> => {
      return new Promise(async (resolve, reject) => {
        if (!filterSwitcher.value) {
          resolve(true);
          return;
        }

        let isCanSubmit = true;
        const validatePromises: Promise<boolean>[] = [];

        filterData.value.forEach(group => {
          group.forEach((row, rowIndex) => {
            validatePromises.push(Promise.resolve(true));
          });
        });

        try {
          const results = await Promise.all(validatePromises);
          isCanSubmit = results.every(result => result);
          isCanSubmit ? resolve(true) : reject(new Error('验证失败'));
        } catch (error) {
          reject(error);
        }
      });
    };

    /**
     * 获取提交的过滤条件数据
     * @returns 格式化后的条件数据
     */
    const getSubmitConditionsData = (): IConditions => {
      // 过滤空数据
      const filteredData = filterData.value
        .map(fItem => fItem.filter(item => !!item.word))
        .filter(item => item.length > 0);

      // 格式化数据逻辑
      let submitFlatData: Array<ITableRowItem & { logic_op: string }> = filteredData.flatMap((fItem, fIndex) => {
        return fItem.map((item, index) => {
          const { tableIndex, ...reset } = item;
          // 第一组或非首行使用and，其他组首行使用or
          return {
            ...reset,
            logic_op: fIndex === 0 || index !== 0 ? 'and' : 'or',
          };
        });
      });

      // 字符串类型特殊处理字段索引
      if (isMatchType.value) {
        submitFlatData = submitFlatData.map(item => ({
          ...item,
          fieldindex: '-1',
        }));
      }

      if (filterSwitcher.value && submitFlatData.length) {
        return {
          separator: separator.value,
          separator_filters: submitFlatData,
          type: activeType.value,
        };
      }
      return { type: 'none' };
    };

    /**
     * 获取原始日志数据
     * @param isDebug - 是否进行调试
     */
    const getLogOriginal = async (isDebug = true) => {
      try {
        const res = await $http.request(
          'source/dataList',
          {
            params: {
              collector_config_id: curCollect.value.collector_config_id,
            },
          },
          {
            catchIsShowMessage: false,
          },
        );

        if (res.data?.length) {
          const firstData = res.data[0];
          logOriginal.value = firstData.etl.data || '';
          if (logOriginal.value && isDebug) {
            logOriginDebug();
          }
        }
      } catch (error) {
        console.warn('获取原始日志失败:', error);
      }
    };

    /**
     * 原始日志调试，获取字段列表
     */
    const logOriginDebug = async () => {
      try {
        logOriginalLoading.value = true;
        const res = await $http.request('clean/getEtlPreview', {
          data: {
            etl_config: 'bk_log_delimiter',
            etl_params: { separator: separator.value },
            data: logOriginal.value,
          },
        });

        originalFilterItemSelect.value = res.data.fields.map((item: any) => ({
          name: t('第{n}行', { n: item.field_index }) + ` | ${item.value}`,
          id: String(item.field_index),
          value: item.value,
        }));
      } catch (error) {
        console.warn('日志调试失败:', error);
      } finally {
        logOriginalLoading.value = false;
      }
    };

    /**
     * 检查操作符是否可禁用
     */
    const getOperatorDisabled = (index: number, tableIndex: number): boolean => {
      return index === 0 && filterData.value[tableIndex].length === 1;
    };

    /**
     * 设置验证器引用
     */
    const setValidatorRef = (el: any, key: string) => {
      if (el) {
        validatorInputRefs.value[key] = el;
      }
    };

    // 生命周期
    onMounted(() => {
      initContainerData();
      // 如果已有过滤条件，开启开关
      if (props.conditions?.type && props.conditions.type !== 'none') {
        filterSwitcher.value = true;
      }
    });

    // 暴露方法给父组件
    expose({
      inputValidate,
    });

    /**
     * 渲染字段索引输入框
     */
    const renderFieldIndexInput = (groupid: number, row: ITableRowItem, index: number) => (
      <ValidatorInput
        ref={(el: any) => setValidatorRef(el, `match-${groupid}-${row.tableIndex}-${index}`)}
        active-type={activeType.value}
        input-type={'number'}
        original-filter-item-select={originalFilterItemSelect.value}
        placeholder={t('请输入列数')}
        row-data={row}
        table-index={row.tableIndex}
        value={row.fieldindex}
        on-change={(val: string) => {
          row.fieldindex = val;
          conditionsChange();
        }}
      />
    );

    /**
     * 渲染值输入框
     */
    const renderValueInput = (groupId: number, row: ITableRowItem, index: number) => (
      <ValidatorInput
        ref={(el: any) => setValidatorRef(el, `value-${groupId}-${row.tableIndex}-${index}`)}
        active-type={activeType.value}
        placeholder={['regex', 'nregex'].includes(row.op) ? t('支持正则匹配，如18*123') : t('请输入')}
        row-data={row}
        value={row.word}
        on-change={(val: string) => {
          row.word = val;
          conditionsChange();
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
          conditionsChange();
        }}
      >
        {operatorShowSelectList.value.map(option => (
          <bk-option
            id={option.id}
            key={option.id}
            name={option.name}
          />
        ))}
      </bk-select>
    );

    /**
     * 渲染操作按钮
     */
    const renderOperatorButtons = (row: ITableRowItem, index: number) => (
      <div class='item-tool btns-group'>
        <i
          class='bk-icon icon-plus-circle-shape icons'
          on-Click={() => handleAddNewSeparator(index, row.tableIndex, 'add')}
        />
        <i
          class={[
            'bk-icon icon-minus-circle-shape icons',
            {
              disabled: getOperatorDisabled(index, row.tableIndex),
            },
          ]}
          on-Click={() => handleAddNewSeparator(index, row.tableIndex, 'delete')}
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
        {renderOperatorButtons(row, rowIndex)}
      </div>
    );

    /**
     * 渲染表格内容
     */
    const renderTableContent = (group: ITableRowItem[], groupIndex: number) => (
      <div class='table-box-main'>
        {renderTableHeader()}
        <div class='custom-table-body'>{group.map((row, rowIndex) => renderTableRow(row, rowIndex, groupIndex))}</div>
      </div>
    );

    return () => (
      <div class='log-filter-main'>
        {/* 开关控制区域 */}
        <div class='switch-box'>
          <bk-switcher
            size='large'
            theme='primary'
            value={filterSwitcher.value}
            on-change={(val: boolean) => {
              filterSwitcher.value = val;
              conditionsChange();
            }}
          />
          <InfoTips
            class='ml-12'
            tips={t('过滤器支持采集时过滤不符合的日志内容，请保证采集器已升级到最新版本')}
          />
        </div>

        {/* 过滤器配置区域 */}
        {filterSwitcher.value && (
          <div class='log-filter-box'>
            {/* 过滤类型切换 */}
            <div class='bk-button-group'>
              {btnGroupList.map(item => (
                <bk-button
                  key={item.id}
                  class={{ 'is-selected': activeType.value === item.id }}
                  size='small'
                  on-Click={() => handleClickFilterType(item.id as btnType)}
                >
                  {item.name}
                </bk-button>
              ))}
            </div>

            {/* 分隔符配置区域 */}
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
                    on-Click={logOriginDebug}
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

            {/* 过滤器分组表格 - 使用自定义表格实现 */}
            {filterData.value.map((group, groupIndex) => (
              <div
                key={groupIndex}
                class='table-box'
              >
                <div class='table-box-header'>
                  <span>{t('第{n}组', { n: groupIndex + 1 })}</span>
                  <i
                    class='bk-icon icon-delete del-icons'
                    on-Click={() => handleClickDeleteGroup(groupIndex)}
                  />
                </div>
                {renderTableContent(group, groupIndex)}
              </div>
            ))}

            {/* 新增分组按钮 */}
            <div
              class='add-new-group-btn'
              on-Click={handleClickNewGroupBtn}
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
