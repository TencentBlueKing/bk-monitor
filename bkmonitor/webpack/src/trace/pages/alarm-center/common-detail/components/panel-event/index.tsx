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
import { type PropType, defineComponent, watch } from 'vue';
import { shallowReactive } from 'vue';

import { searchEvent } from 'monitor-api/modules/alert';

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
    const tableData = shallowReactive({
      page: 1,
      pageSize: 10,
      data: [],
      total: 0,
    });

    const init = async () => {
      const params = {
        bk_biz_id: props.detail.bk_biz_id,
        alert_id: props.detail.id,
        query_string: '',
        start_time: props.detail.begin_time,
        end_time: props.detail.end_time,
        page: tableData.page,
        page_size: tableData.pageSize,
        record_history: true,
        ordering: ['create_time'],
      };
      const res = await searchEvent(params, { needRes: true })
        .then(res => {
          return (
            res.data || {
              events: [],
              total: 0,
            }
          );
        })
        .catch(_res => {
          return {
            events: [],
            total: 0,
          };
        })
        .finally(() => {});
      tableData.data = res.events;
      tableData.total = res.total;
    };

    watch(
      () => props.detail,
      val => {
        if (val) {
          init();
        }
      },
      {
        immediate: true,
      }
    );

    return {
      tableData,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event'>
        <EventTable tableData={this.tableData} />
      </div>
    );
  },
});
