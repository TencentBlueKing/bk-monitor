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

import { defineComponent, type PropType, computed, ref, onMounted, nextTick, onBeforeUnmount, watch } from 'vue';

import { ConfigProvider as TConfigProvider, Table as TTable } from 'tdesign-vue';
import EmptyStatus from '@/components/empty-status/index.vue';
import ItemSkeleton from '@/skeleton/item-skeleton';
import useLocale from '@/hooks/use-locale';
import tippy, { type Instance } from 'tippy.js';
import 'tdesign-vue/es/style/index.css';
import './table-component.scss';

/**
 * 分页信息类型
 */
interface IPaginationInfo {
  current: number;
  pageSize: number;
}

/**
 * 排序配置类型
 */
interface ISortConfig {
  descending?: boolean;
  sortBy?: string;
}

interface IColumns {
  title?: string;
  colKey?: string;
  sorter?: boolean;
  sortType?: string;
  width?: number;
  ellipsis?: boolean;
}

export default defineComponent({
  name: 'TableComponent',
  props: {
    columns: {
      type: Array as PropType<IColumns[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    data: {
      type: Array,
      default: () => [],
    },
    height: {
      type: [Number, String],
      default: undefined,
    },
    pagination: {
      type: Object as PropType<IPaginationInfo>,
      default: () => {},
    },
    sortConfig: {
      type: Object as PropType<ISortConfig>,
      default: () => {},
    },
    emptyType: {
      type: String,
      default: 'empty',
    },
    filterValue: {
      type: Object as PropType<Record<string, string>>,
      default: () => {},
    },
    skeletonConfig: {
      type: Object as PropType<{
        columns?: number;
        gap?: string;
        rowHeight?: string;
        rows?: number;
        widths?: string[];
      }>,
      default: () => ({}),
    },
    slots: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    bordered: {
      type: Boolean,
      default: false,
    },
    colKeyMap: {
      type: Object as PropType<Record<string, string>>,
      default: () => ({}),
    },
    settingFields: {
      type: Array as PropType<Array<{ id: string; label: string; disabled?: boolean }>>,
      default: () => [],
    },
    rowHeight: {
      type: Number,
      default: 32,
    },
  },
  emits: ['sort-change', 'page-change', 'filter-change', 'empty-click', 'cell-click'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const globalLocale = {
      table: {
        sortIcon: () => <i class='bk-icon icon-down-shape sort-icon' />,
        filterIcon: () => <i class='bk-icon icon-funnel filter-icon' />,
      },
    };
    let columnConfigTippyInstance: Instance | null = null;
    const columnConfigTriggerRef = ref<HTMLElement | null>(null);
    const columnConfigContentRef = ref<HTMLElement | null>(null);
    // 列配置相关状态
    const isShowColumnConfig = ref(false);

    // 临时选择的列（用于确认前）
    const tempVisibleColumns = ref<string[]>([]);
    const columnConfigFields = ref([...props.settingFields]);

    // 用户选择的可见列（初始值为所有列）
    const visibleColumns = ref<string[]>(columnConfigFields.value.map(field => props.colKeyMap[field.id] || field.id));

    const isNeedSetting = computed(() => {
      return Object.keys(props.colKeyMap || {}).length > 0 && (props.settingFields || []).length > 0;
    });
    /**
     * 是否有过滤内容
     */
    const hasValidIFilterConditions = computed(() => {
      return Object.values(props.filterValue || {}).some(value => value !== '');
    });
    // 默认显示的列（disabled: true 的列）
    const defaultVisibleColumns = computed(() => {
      return columnConfigFields.value
        .filter(field => field.disabled)
        .map(field => props.colKeyMap[field.id] || field.id);
    });
    /**
     * 获取当前有过滤条件的列的 colKey 列表
     * @returns 有过滤条件的列的 colKey 数组
     */
    const filteredColumnKeys = computed(() => {
      return Object.keys(props.filterValue || {}).filter((key: string) => {
        if (props.filterValue[key] !== '') {
          return key;
        }
      });
    });
    // 根据可见列过滤后的列配置
    const showColumns = computed(() => {
      if (!isNeedSetting.value) {
        return props.columns;
      }
      // 操作列始终显示
      const operationCol = props.columns.find(col => col.colKey === 'operation');
      // 根据 visibleColumns 过滤列，但始终包含默认列和操作列
      const filteredColumns = props.columns.filter((col: IColumns) => {
        if (col.colKey === 'operation') return false; // 操作列单独处理
        // 默认列始终显示
        if (defaultVisibleColumns.value.includes(col.colKey)) return true;
        // 其他列根据 visibleColumns 决定
        return visibleColumns.value.includes(col.colKey);
      });
      // 将操作列添加到末尾
      return operationCol ? [...filteredColumns, operationCol] : filteredColumns;
    });
    /**
     * 检查列是否被选中
     * @param fieldId - 字段ID
     * @returns 是否选中
     */
    const isColumnChecked = (fieldId: string): boolean => {
      const colKey = props.colKeyMap[fieldId] || fieldId;
      return tempVisibleColumns.value.includes(colKey);
    };
    /**
     * 打开列配置
     */
    const handleOpenColumnConfig = () => {
      isShowColumnConfig.value = true;
      // 初始化临时选择为当前可见列，确保包含默认列
      const allCurrentColumns = [
        ...defaultVisibleColumns.value,
        ...visibleColumns.value.filter(key => !defaultVisibleColumns.value.includes(key)),
      ];
      tempVisibleColumns.value = [...allCurrentColumns];
    };
    /**
     * 处理列配置变化
     * @param fieldId - 字段ID
     * @param checked - 是否选中
     */
    const handleColumnConfigChange = (fieldId: string, checked: boolean) => {
      const colKey = props.colKeyMap[fieldId] || fieldId;
      // 如果是默认列，不允许取消
      if (!checked && defaultVisibleColumns.value.includes(colKey)) {
        return;
      }

      if (checked) {
        if (!tempVisibleColumns.value.includes(colKey)) {
          tempVisibleColumns.value.push(colKey);
        }
      } else {
        tempVisibleColumns.value = tempVisibleColumns.value.filter(key => key !== colKey);
      }
    };
    /**
     * 确认列配置
     */
    const handleColumnConfigConfirm = () => {
      // 确保默认列始终包含在内
      const finalColumns = [
        ...defaultVisibleColumns.value,
        ...tempVisibleColumns.value.filter(key => !defaultVisibleColumns.value.includes(key)),
      ];
      visibleColumns.value = finalColumns;
      isShowColumnConfig.value = false;
      columnConfigTippyInstance?.hide();
    };
    /**
     * 关闭列配置
     */
    const handleCloseColumnConfig = () => {
      // 手动关闭 tippy（用于取消按钮点击）
      if (columnConfigTippyInstance) {
        columnConfigTippyInstance.hide();
      }
      isShowColumnConfig.value = false;
    };

    /**
     * 初始化列配置 tippy 实例
     */
    const initColumnConfigTippy = () => {
      // 确保 ref 存在且是有效的 HTMLElement
      const trigger = columnConfigTriggerRef.value;
      const content = columnConfigContentRef.value;

      if (!trigger || !(trigger instanceof HTMLElement) || !content || !(content instanceof HTMLElement)) {
        return;
      }

      // 销毁旧实例
      if (columnConfigTippyInstance) {
        try {
          columnConfigTippyInstance.destroy();
        } catch (error) {
          console.log('销毁列配置 tippy 实例失败:', error);
        }
        columnConfigTippyInstance = null;
      }

      try {
        columnConfigTippyInstance = tippy(trigger, {
          trigger: 'click',
          placement: 'bottom-end',
          theme: 'light column-config-popover',
          interactive: true,
          hideOnClick: 'toggle',
          arrow: false,
          offset: [-52, 4],
          appendTo: () => document.body,
          onShow() {
            handleOpenColumnConfig();
          },
          onHide() {
            // 直接更新状态，不要调用 handleCloseColumnConfig，避免循环
            isShowColumnConfig.value = false;
          },
          content() {
            // 使用函数返回内容，确保能正确获取元素
            const contentRef = columnConfigContentRef.value;
            if (!contentRef || !(contentRef instanceof HTMLElement)) {
              return document.createElement('div');
            }
            return contentRef as unknown as Element;
          },
        });
      } catch (error) {
        console.log('初始化列配置 tippy 实例失败:', error);
        columnConfigTippyInstance = null;
      }
    };
    const renderEmpty = (type: string) => (
      <div class='table-empty-content'>
        <EmptyStatus
          emptyType={props.emptyType}
          on-operation={() => handleEmptyOperation(type)}
        />
      </div>
    );
    /**
     * 更新过滤图标的选中状态
     */
    const updateFilterIconStatus = () => {
      nextTick(() => {
        // 获取所有表头单元格
        const headerCells = document.querySelectorAll('.new-table-component-box .t-table__header th');

        // 获取当前可见的列配置（用于匹配 colKey）
        const visibleColumnsConfig = props.columns;

        // 创建一个映射：表头文本 -> colKey
        const titleToColKeyMap = new Map<string, string>();
        visibleColumnsConfig.forEach(col => {
          if (col.title && typeof col.title === 'string') {
            titleToColKeyMap.set(col.title, col.colKey || '');
          }
        });

        headerCells.forEach((cell, index) => {
          // 获取过滤图标
          const filterIcon = cell.querySelector('.filter-icon');
          if (!filterIcon) return;

          let colKey = '';

          // 方法1: 尝试通过 data-col-key 属性获取
          const dataColKey = cell.getAttribute('data-col-key');
          if (dataColKey) {
            colKey = dataColKey;
          } else {
            // 方法2: 通过列索引获取
            const columnConfig = visibleColumnsConfig[index];
            if (columnConfig) {
              colKey = columnConfig.colKey || '';
            } else {
              // 方法3: 通过表头文本匹配
              const headerText = cell.querySelector('.t-table__th-cell-inner')?.textContent?.trim() || '';
              colKey = titleToColKeyMap.get(headerText) || '';
            }
          }

          // 如果当前列有过滤条件，添加选中样式
          if (colKey && filteredColumnKeys.value.includes(colKey)) {
            filterIcon.classList.add('is-filtered');
          } else {
            filterIcon.classList.remove('is-filtered');
          }
        });
      });
    };

    const sortChange = (sortInfo: ISortConfig): void => {
      emit('sort-change', sortInfo);
    };

    const handlePageChange = (pageInfo: IPaginationInfo) => {
      emit('page-change', pageInfo);
    };

    const handleEmptyOperation = (type: string) => {
      emit('empty-click', type);
    };
    onMounted(() => {
      // 初始化列配置 tippy - 使用 nextTick 确保 DOM 已渲染
      nextTick(() => {
        isNeedSetting.value && initColumnConfigTippy();
      });
    });
    onBeforeUnmount(() => {
      // 销毁列配置 tippy
      if (columnConfigTippyInstance) {
        columnConfigTippyInstance.destroy();
        columnConfigTippyInstance = null;
      }
    });

    /**
     * 处理表格过滤变化
     * @param filters - 过滤对象
     */
    const handleFilterChange = (filters: Record<string, string>) => {
      emit('filter-change', filters);
    };

    const handleCellClick = params => {
      emit('cell-click', params.row);
    };
    watch(
      () => props.loading,
      (val: boolean) => {
        if (!val) {
          setTimeout(() => {
            updateFilterIconStatus();
          }, 1000);
        }
      },
    );
    // 监听过滤条件变化，更新过滤图标状态
    watch(
      () => props.filterValue,
      () => {
        updateFilterIconStatus();
      },
      { deep: true },
    );

    return () => {
      return (
        <div class='new-table-component-box'>
          {isNeedSetting.value && (
            <div class='table-set'>
              <div
                ref={columnConfigTriggerRef}
                class='column-config-trigger'
              >
                <i class='bk-icon icon-cog-shape'></i>
              </div>
              <div
                ref={columnConfigContentRef}
                class='column-config-dropdown'
              >
                <div class='column-config-title'>{t('字段显示设置')}</div>
                <div class='column-config-list'>
                  {columnConfigFields.value.map(field => {
                    const colKey = props.colKeyMap[field.id] || field.id;
                    const isDefault = field.disabled || defaultVisibleColumns.value.includes(colKey);
                    const checked = isColumnChecked(field.id);
                    return (
                      <span
                        key={field.id}
                        class='column-config-item'
                      >
                        <bk-checkbox
                          value={checked}
                          disabled={isDefault}
                          on-change={(val: boolean) => {
                            if (!isDefault) {
                              handleColumnConfigChange(field.id, val);
                            }
                          }}
                        >
                          {field.label}
                        </bk-checkbox>
                      </span>
                    );
                  })}
                </div>
                <div class='column-config-footer'>
                  <bk-button
                    theme='primary'
                    size='small'
                    on-click={handleColumnConfigConfirm}
                  >
                    {t('确定')}
                  </bk-button>
                  <bk-button
                    size='small'
                    on-click={handleCloseColumnConfig}
                  >
                    {t('取消')}
                  </bk-button>
                </div>
              </div>
            </div>
          )}

          {hasValidIFilterConditions.value && props.data.length === 0 && (
            <div class='filter-empty'>{renderEmpty('clear-filter')}</div>
          )}

          <TConfigProvider
            class='new-table-component-main'
            globalConfig={globalLocale}
          >
            {/* @ts-ignore - TTable type definition issue */}
            <TTable
              bordered={props.bordered}
              cellEmptyContent={'--'}
              columns={showColumns.value}
              data={props.data}
              sort={props.sortConfig}
              loading={props.loading}
              loading-props={{ indicator: false }}
              on-page-change={handlePageChange}
              pagination={props.pagination}
              row-key='key'
              height={props.height}
              rowHeight={props.rowHeight}
              scroll={{ type: 'lazy', bufferSize: 10 }}
              on-sort-change={sortChange}
              on-filter-change={handleFilterChange}
              filterValue={props.filterValue}
              on-cell-click={handleCellClick}
              scopedSlots={{
                loading: () => (
                  <div class='table-skeleton-box'>
                    <ItemSkeleton
                      style={{ padding: '0 16px' }}
                      columns={props.skeletonConfig?.columns || 5}
                      gap={props.skeletonConfig?.gap || '14px'}
                      rowHeight={props.skeletonConfig?.rowHeight || '28px'}
                      rows={props.skeletonConfig?.rows || 6}
                      widths={props.skeletonConfig?.widths || ['25%', '25%', '20%', '20%', '10%']}
                    />
                  </div>
                ),
                empty: renderEmpty,
                ...props.slots,
              }}
            />
          </TConfigProvider>
        </div>
      );
    };
  },
});
