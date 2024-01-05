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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from '../../../monitor-common/utils';

import { IInfluxdbChildData } from './type';

import './influxdb-child.scss';

interface IProps {
  value?: IInfluxdbChildData[];
}

@Component
export default class InfluxdbChild extends tsc<IProps> {
  @Prop({ default: () => ({}), type: Object }) value: IInfluxdbChildData[];
  localValue: IInfluxdbChildData[] = [
    {
      id: random(8),
      name: 'Influxdb-Proxy',
      isExpand: true,
      data: {
        columns: [
          { id: 'host', name: '域名' },
          { id: 'port', name: '端口' }
        ],
        data: [
          { host: '102.11.1000.1', port: '9092' },
          { host: '102.11.1000.1', port: '9092' }
        ]
      }
    },
    {
      id: random(8),
      name: 'Influxdb-Proxy',
      isExpand: true,
      data: {
        columns: [
          { id: 'host', name: '域名' },
          { id: 'port', name: '端口' }
        ],
        data: [
          { host: '102.11.1000.1', port: '9092' },
          { host: '102.11.1000.1', port: '9092' }
        ]
      }
    }
  ];
  @Emit('group-operation')
  handleGroupOperation(type = 'clone', data: any) {
    return { operationType: type, data };
  }
  handleExpand(index: number) {
    this.localValue[index].isExpand = !this.localValue[index].isExpand;
  }

  handleCopy(e: Event, _index: number) {
    e.stopPropagation();
    const { data } = this.localValue[_index].data;
    this.handleGroupOperation('clone', data);
  }
  handleEdit(e: Event, _index: number) {
    e.stopPropagation();
    const { data } = this.localValue[_index].data;
    this.handleGroupOperation('edit', data);
  }

  /* 状态 */
  statusContent(status: 'normal' | 'failure') {
    return (
      <div class='status-info'>
        <div class={['status-point']}>
          <div></div>
        </div>
        <div>{status === 'normal' ? this.$t('正常') : this.$t('失败')}</div>
      </div>
    );
  }

  handleSetFormatter(column, row, _index) {
    switch (column) {
      case 'status': {
        return this.statusContent('normal');
      }
      default: {
        return row[column] || '--';
      }
    }
  }

  render() {
    return (
      <div class='resource-register-page-influxdb-child'>
        {this.localValue.map((item, index) => (
          <div
            class='expand-item'
            key={item.id}
          >
            <div
              class='item-header'
              onClick={() => this.handleExpand(index)}
            >
              <span class={['icon-monitor icon-mc-triangle-down', { active: item.isExpand }]}></span>
              <span class='name'>{item.name}</span>
              <span
                class='icon-monitor icon-mc-copy'
                v-bk-tooltips={{
                  content: this.$t('克隆')
                }}
                onClick={(e: Event) => this.handleCopy(e, index)}
              ></span>
              <span
                class='icon-monitor icon-bianji'
                v-bk-tooltips={{
                  content: this.$t('编辑组')
                }}
                onClick={(e: Event) => this.handleEdit(e, index)}
              ></span>
            </div>
            <div class={['item-content', { active: item.isExpand }]}>
              <bk-table
                outer-border={false}
                header-border={false}
                {...{
                  props: {
                    data: item.data.data
                  }
                }}
              >
                {item.data.columns.map(column => {
                  const key = `column_${column.id}`;
                  return (
                    <bk-table-column
                      key={key}
                      prop={column.id}
                      label={column.name}
                      column-key={column.id}
                      formatter={(row, _column, _cellValue, index) => this.handleSetFormatter(column.id, row, index)}
                    ></bk-table-column>
                  );
                })}
              </bk-table>
            </div>
          </div>
        ))}
      </div>
    );
  }
}
