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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './notice-status-table.scss';

interface ITableData {
  target?: string;
  label?: string;
  tip?: string;
}
interface ITableColumn {
  label?: string;
  prop?: string;
}

interface IProps {
  tableData?: ITableData[];
  tableColumns?: ITableColumn[];
  hasColumns?: string[];
}

@Component
export default class NoticeStatusTable extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) tableData: ITableData[];
  @Prop({ default: () => [], type: Array }) tableColumns: ITableColumn[];
  @Prop({ default: () => [], type: Array }) hasColumns: string[];
  classMap = {
    失败: 'failed',
    成功: 'success'
  };
  render() {
    return (
      <div class='notice-status-table'>
        <bk-table
          data={this.tableData}
          border={false}
          outer-border={false}
        >
          <bk-table-column
            label={window.i18n.t('通知对象')}
            prop={'target'}
            resizable={false}
          ></bk-table-column>
          {this.tableColumns.map((item, i) =>
            this.hasColumns.includes(item.prop) ? (
              <bk-table-column
                key={i}
                label={item.label}
                prop={item.prop}
                scopedSlots={{
                  default: ({ row }) =>
                    !Object.keys(this.classMap).includes(row?.[item.prop]?.label) ? (
                      <span
                        v-bk-tooltips={{
                          allowHtml: false,
                          html: false,
                          allowHTML: false,
                          with: 200,
                          content: row[item.prop]?.tip,
                          placements: ['top'],
                          disabled: !row[item.prop]?.tip
                        }}
                      >
                        {row?.[item.prop]?.label || '--'}
                      </span>
                    ) : (
                      <span
                        class={`notice-${this.classMap[row[item.prop].label]}`}
                        v-bk-tooltips={{
                          allowHtml: false,
                          html: false,
                          allowHTML: false,
                          with: 200,
                          content: row[item.prop]?.tip,
                          placements: ['top'],
                          disabled: !row[item.prop]?.tip
                        }}
                      />
                    )
                }}
                resizable={false}
                align='center'
              ></bk-table-column>
            ) : undefined
          )}
        </bk-table>
      </div>
    );
  }
}
