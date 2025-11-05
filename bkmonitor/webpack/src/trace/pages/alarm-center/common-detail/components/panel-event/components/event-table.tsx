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
import { defineComponent, shallowRef } from 'vue';
import type { PropType } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Checkbox } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import EventTableExpandContent from './event-table-expand-content';

import './event-table.scss';

export enum SourceTypeEnum {
  ALL = 'ALL',
  /** Kubernetes/BCS */
  BCS = 'BCS',
  /** BKCI/蓝盾 */
  BKCI = 'BKCI',
  /** 其他类型事件来源 */
  DEFAULT = 'DEFAULT',
  /** 系统/主机 */
  HOST = 'HOST',
}

const SourceIconMap = {
  [SourceTypeEnum.BCS]: 'icon-explore-bcs',
  [SourceTypeEnum.BKCI]: 'icon-explore-landun',
  [SourceTypeEnum.HOST]: 'icon-explore-host',
  [SourceTypeEnum.DEFAULT]: 'icon-explore-default',
};

export default defineComponent({
  name: 'EventTable',
  props: {
    tableData: {
      type: Object as PropType<{
        data: any[];
        page: number;
        pageSize: number;
        total: number;
      }>,
      default: () => ({
        page: 1,
        pageSize: 10,
        data: [],
        total: 0,
      }),
    },
  },
  setup(_props) {
    const { t } = useI18n();
    const columns = shallowRef<TdPrimaryTableProps['columns']>([
      {
        colKey: 'time',
        title: window.i18n.t('时间'),
        width: 150,
        cell: (_h, { row }) => {
          return dayjs.tz(row.time * 1000).format('YYYY-MM-DD HH:mm');
        },
      },
      {
        colKey: 'event_name',
        title: window.i18n.t('事件名'),
        width: 160,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return row.alert_name;
        },
      },
      {
        colKey: 'event.content',
        title: window.i18n.t('内容'),
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        minWidth: 150,
        cell: (_h, { row }) => {
          return row.description;
        },
      },
      {
        colKey: 'target',
        title: window.i18n.t('目标'),
        width: 190,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return row.target || '--';
        },
      },
    ]);
    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h, { _row }): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });
    const expandedRowKeys = shallowRef([]);
    const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row }): any => {
      return <EventTableExpandContent data={row} />;
    });
    const sourceType = shallowRef([]);
    const sourceTypeOptions = shallowRef([
      {
        label: window.i18n.t('全部'),
        value: SourceTypeEnum.ALL,
        count: 0,
        icon: '',
      },
      {
        label: window.i18n.t('容器'),
        value: SourceTypeEnum.BCS,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.BCS],
      },
      {
        label: window.i18n.t('蓝盾'),
        value: SourceTypeEnum.BKCI,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.BKCI],
      },
      {
        label: window.i18n.t('主机'),
        value: SourceTypeEnum.HOST,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.HOST],
      },
    ]);

    const handleExpandChange = (keys: (number | string)[]) => {
      console.log(keys);
      expandedRowKeys.value = keys;
    };

    const handleGoEvent = () => {};

    return {
      columns,
      sourceType,
      sourceTypeOptions,
      expandIcon,
      expandedRow,
      expandedRowKeys,
      handleExpandChange,
      t,
      handleGoEvent,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event-table'>
        <div class='header-operate'>
          <span style='margin-right: 8px;'>{window.i18n.t('事件来源')}:</span>
          <Checkbox.Group class='header-operate-item'>
            {{
              default: () => {
                return this.sourceTypeOptions.map(item => (
                  <Checkbox
                    key={item.value}
                    label={item.value}
                  >
                    <span class='source-item'>
                      {item.icon ? <span class={`source-icon icon-monitor ${item.icon}`} /> : undefined}
                      <span>{item.label}</span>
                    </span>
                  </Checkbox>
                ));
              },
            }}
          </Checkbox.Group>
          <Button
            style='margin-left: 16px;'
            theme='primary'
            text
            onClick={this.handleGoEvent}
          >
            <span>{this.t('更多事件')}</span>
            <span
              style='margin-left: 5px; font-size: 12px;'
              class='icon-monitor icon-fenxiang'
            />
          </Button>
        </div>
        <PrimaryTable
          class='relation-event-table'
          columns={this.columns}
          data={this.tableData.data}
          expandedRow={this.expandedRow}
          expandedRowKeys={this.expandedRowKeys}
          expandIcon={this.expandIcon}
          expandOnRowClick={true}
          rowClassName={({ row }) => `row-event-status-${row.severity}`}
          rowKey={'event_id'}
          size={'small'}
          onExpandChange={this.handleExpandChange}
        />
      </div>
    );
  },
});
