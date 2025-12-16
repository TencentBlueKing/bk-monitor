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
import { type PropType, defineComponent } from 'vue';

import { eventLogs } from 'monitor-api/modules/apm_event';
import { random } from 'monitor-common/utils/utils';

import EventTable from './components/event-table';

import type { AlarmDetail } from '../../../typings/detail';

import './index.scss';

export default defineComponent({
  name: 'PanelEvent',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
  },
  setup(props) {
    const getData = async (params: { limit: number; offset: number; sort: string[]; where: unknown[] }) => {
      const res = await eventLogs({
        query_configs: [
          {
            data_source_label: 'apm',
            data_type_label: 'event',
            table: 'builtin',
            query_string: '',
            where: params.where,
            group_by: ['type'],
            filter_dict: {},
          },
        ],
        app_name: 'tilapia',
        service_name: 'example.greeter',
        start_time: props.detail.begin_time,
        end_time: props.detail.latest_time,
        bk_biz_id: props.detail.bk_biz_id,
        limit: params.limit,
        offset: params.offset,
        sort: params.sort,
      }).catch(() => {
        return {
          list: [],
          total: 0,
        };
      });
      return {
        data: (res.list || []).map(item => ({
          ...item,
          key: random(8),
        })),
        total: res?.total || 0,
      };
    };

    return {
      getData,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event'>
        {this.detail?.id ? (
          <EventTable
            key={this.detail.id}
            getTableData={this.getData}
          />
        ) : undefined}
      </div>
    );
  },
});
