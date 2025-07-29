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

interface IProps {
  hasColumns?: string[];
  tableColumns?: ITableColumn[];
  tableData?: ITableData[];
}
interface ITableColumn {
  label?: string;
  prop?: string;
}

interface ITableData {
  label?: string;
  target?: string;
  tip?: string;
}

@Component
export default class NoticeStatusTable extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) tableData: ITableData[];
  @Prop({ default: () => [], type: Array }) tableColumns: ITableColumn[];
  @Prop({ default: () => [], type: Array }) hasColumns: string[];
  classMap = {
    失败: 'failed',
    成功: 'success',
  };
  render() {
    return (
      <div class='notice-status-table'>
        <bk-table
          border={false}
          data={this.tableData}
          outer-border={false}
        >
          <bk-table-column
            label={window.i18n.t('通知对象')}
            prop={'target'}
            resizable={false}
          />
          {this.tableColumns.map((item, i) =>
            this.hasColumns.includes(item.prop) ? (
              <bk-table-column
                key={i}
                scopedSlots={{
                  default: ({ row }) =>
                    !Object.keys(this.classMap).includes(row?.[item.prop]?.label) ? (
                      <span
                        v-bk-tooltips={{
                          allowHtml: false,
                          html: false,
                          allowHTML: false,
                          width: 200,
                          content: row[item.prop]?.tip,
                          placements: ['top'],
                          disabled: !row[item.prop]?.tip,
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
                          width: 200,
                          content: row[item.prop]?.tip,
                          placements: ['top'],
                          disabled: !row[item.prop]?.tip,
                        }}
                      />
                    ),
                }}
                align='center'
                label={item.label}
                prop={item.prop}
                resizable={false}
              />
            ) : undefined
          )}
        </bk-table>
      </div>
    );
  }
}
