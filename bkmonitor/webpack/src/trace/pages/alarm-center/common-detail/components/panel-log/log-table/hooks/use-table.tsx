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

import ExpandContent from '../expand-content';
import LogCell from '../log-cell';
import { formatHierarchy } from '../utils/fields';

import type { IFieldInfo, TClickMenuOpt } from '../typing';
import type { TdPrimaryTableProps } from '@blueking/tdesign-ui';

type TUseTableOptions = {
  onClickMenu?: (opt: TClickMenuOpt) => void;
};

export const useTable = (options: TUseTableOptions) => {
  const tableColumns = shallowRef<TdPrimaryTableProps['columns']>([]);
  const tableData = shallowRef([]);
  const originLogData = shallowRef([]);
  const fieldsData = shallowRef(null);
  const wrapWidth = shallowRef(800);
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
          fields={fieldsData.value?.fields || []}
          originLog={originLogData.value?.[index] || {}}
          row={row}
          onClickMenu={(opt: TClickMenuOpt) => {
            options.onClickMenu?.(opt);
          }}
        />
      </div>
    );
  });

  const setTableColumns = (columns: TdPrimaryTableProps['columns']) => {
    tableColumns.value = columns;
  };

  const fieldsDataToColumns = (fields: IFieldInfo[], displayFields: string[]) => {
    const allFields = formatHierarchy(fields).filter(item => displayFields.includes(item.field_name)) as IFieldInfo[];
    const columns: TdPrimaryTableProps['columns'] = allFields.map(item => ({
      colKey: item.field_name,
      ellipsis: false,
      resizable: true,
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
          </div>
        );
      },
    }));
    setTableColumns(columns);
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
  };
};
