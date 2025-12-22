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

import { alertEvents } from 'monitor-api/modules/alert_v2';
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
      const res = await alertEvents({
        // query_configs: [
        //   {
        //     data_source_label: 'apm',
        //     data_type_label: 'event',
        //     table: 'builtin',
        //     query_string: '',
        //     where: params.where,
        //     group_by: ['type'],
        //     filter_dict: {},
        //   },
        // ],
        alert_id: props.detail.id,
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

    const handleGoEvent = () => {
      const queryConfig = props.detail?.items?.[0]?.query_configs?.[0];
      const serviceName = queryConfig?.agg_dimension?.service_name?.value || '';
      const appName = queryConfig?.agg_dimension?.app_name?.value || '';
      if (serviceName && appName) {
        const hash = `#/apm/service?filter-service_name=${serviceName}&filter-app_name=${appName}&dashboardId=service-default-event`;
        const url = location.href.replace(location.hash, hash);
        window.open(url, '_blank');
      } else {
        const hash = '#/event-explore';
        const url = location.href.replace(location.hash, hash);
        window.open(url, '_blank');
      }
    };

    return {
      getData,
      handleGoEvent,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event'>
        {this.detail?.id ? (
          <EventTable
            key={this.detail.id}
            getTableData={this.getData}
            onGoEvent={this.handleGoEvent}
          />
        ) : undefined}
      </div>
    );
  },
});
