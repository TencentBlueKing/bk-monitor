/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { shallowRef } from 'vue';

import { fieldTypeMap } from 'trace/components/retrieval-filter/utils';
import { useI18n } from 'vue-i18n';

import ExpandContent from '../expand-content';
import LogCell from '../log-cell';
import { formatHierarchy } from '../utils/fields';
import { calculateTableColsWidth } from '../utils/utils';

import type { IFieldInfo, TClickMenuOpt } from '../typing';
import type { TdPrimaryTableProps } from '@blueking/tdesign-ui';

type TUseTableOptions = {
  onAddField?: (fieldName: string) => void;
  onClickMenu?: (opt: TClickMenuOpt) => void;
  onRemoveField?: (fieldName: string) => void;
};

export const useTable = (options: TUseTableOptions) => {
  const { t } = useI18n();
  const tableColumns = shallowRef<TdPrimaryTableProps['columns']>([]);
  const tableData = shallowRef([]);
  const originLogData = shallowRef([]);
  const fieldsData = shallowRef(null);
  const wrapWidth = shallowRef(800);
  const allFields = shallowRef<IFieldInfo[]>([]);

  const getDefaultTableWidth = (visibleFields, tableData, catchFieldsWidthObj = null, staticWidth = 50) => {
    const fieldWidthObj = {};
    try {
      if (tableData.length && visibleFields.length) {
        for (const field of visibleFields) {
          const targetList = [field];
          if (field.alias_mapping_field && !targetList.includes(field.alias_mapping_field)) {
            targetList.push(field.alias_mapping_field);
          }
          for (const item of targetList) {
            const [fieldWidth, minWidth] = calculateTableColsWidth(item, tableData);
            let width = fieldWidth < minWidth ? minWidth : fieldWidth;
            if (catchFieldsWidthObj) {
              const catchWidth = catchFieldsWidthObj[item.field_name];
              width = catchWidth ?? fieldWidth;
            }
            fieldWidthObj[item.field_name] = { width, minWidth };
          }
        }

        const columnsWidth = visibleFields.reduce((prev, next) => prev + next.width, 0);

        // 如果当前表格所有列总和小于表格实际宽度 则对小于800（最大宽度）的列赋值 defalut 使其自适应
        const availableWidth = wrapWidth.value - staticWidth;
        if (columnsWidth && columnsWidth < availableWidth) {
          const longFiels = visibleFields.filter(item => fieldWidthObj[item.field_name].width >= 800);
          if (longFiels.length) {
            const addWidth = (availableWidth - columnsWidth) / longFiels.length;
            for (const item of longFiels) {
              fieldWidthObj[item.field_name].width = fieldWidthObj[item.field_name].width + Math.ceil(addWidth);
            }
          } else {
            const addWidth = (availableWidth - columnsWidth) / visibleFields.length;
            for (const field of visibleFields) {
              fieldWidthObj[field.field_name].width = fieldWidthObj[field.field_name].width + Math.ceil(addWidth);
            }
          }
        }
      }

      return fieldWidthObj;
    } catch (error) {
      console.error(error);
      return false;
    }
  };

  const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row, index }): any => {
    return (
      <div
        style={{
          width: `${wrapWidth.value}px`,
          position: 'sticky',
          left: 0,
        }}
      >
        <ExpandContent
          displayFields={tableColumns.value.map(item => item.colKey)}
          fields={fieldsData.value?.fields || []}
          originLog={originLogData.value?.[index] || {}}
          row={row}
          onAddField={(fieldName: string) => {
            options.onAddField?.(fieldName);
          }}
          onClickMenu={(opt: TClickMenuOpt) => {
            options.onClickMenu?.(opt);
          }}
          onRemoveField={(fieldName: string) => {
            options.onRemoveField?.(fieldName);
          }}
        />
      </div>
    );
  });

  const setTableColumns = (columns: TdPrimaryTableProps['columns']) => {
    tableColumns.value = columns;
  };

  const fieldsDataToColumns = (fields: IFieldInfo[], displayFields: string[]) => {
    const formattedFields = formatHierarchy(fields);
    allFields.value = displayFields
      .map(fieldName => formattedFields.find(item => item.field_name === fieldName))
      .filter((item): item is IFieldInfo => !!item);

    const columns: TdPrimaryTableProps['columns'] = allFields.value.map(item => ({
      colKey: item.field_name,
      ellipsis: false,
      resizable: true,
      width: 200,
      minWidth: 200,
      sorter: item.es_doc_values && item.tag !== 'union-source' && item.field_type !== 'flattened',
      className: ({ type }) => {
        if (type === 'th') {
          return 'col-th';
        } else {
          return 'col-td';
        }
      },
      cell: (_h, { _col, row }) => {
        return (
          <LogCell
            options={{
              onClickMenu: (opt: TClickMenuOpt) => {
                options.onClickMenu?.(opt);
              },
            }}
            field={item}
            row={row}
          />
        );
      },
      title: () => {
        const fieldIcon = fieldTypeMap[item.field_type] || fieldTypeMap.text;
        return (
          <div class='col-title'>
            <span
              style={{
                backgroundColor: fieldIcon.bgColor,
                color: fieldIcon.color,
                marginRight: '5px',
              }}
              class={[fieldIcon.icon, 'col-title-field-icon']}
              v-bk-tooltips={{
                content: fieldIcon.name,
              }}
            />
            <span
              class='col-title-field-alias'
              v-bk-tooltips={{
                content: item.field_name,
              }}
            >
              {item.query_alias || item.field_name}
            </span>
            <span
              class='remove-btn'
              v-bk-tooltips={{
                content: t('将字段从列表中移除'),
              }}
            >
              <span
                class='icon-monitor icon-mc-minus-plus'
                onClick={() => {
                  options.onRemoveField?.(item.field_name);
                }}
              />
            </span>
          </div>
        );
      },
    })) as any;
    setTableColumns(columns);
  };

  const setDefaultFieldWidth = () => {
    const defaultWidthObj = getDefaultTableWidth(allFields.value, tableData.value);
    for (const item of tableColumns.value) {
      item.width = defaultWidthObj?.[item.colKey]?.width || 200;
      item.minWidth = defaultWidthObj?.[item.colKey]?.minWidth || 200;
    }
    setTableColumns(tableColumns.value.slice());
  };

  const setFieldsData = (data: any) => {
    fieldsData.value = data;
  };
  const setWrapWidth = (width: number) => {
    wrapWidth.value = width;
  };

  return {
    tableColumns,
    tableData,
    expandedRow,
    originLogData,
    setTableColumns,
    fieldsDataToColumns,
    setFieldsData,
    setWrapWidth,
    setDefaultFieldWidth,
  };
};
