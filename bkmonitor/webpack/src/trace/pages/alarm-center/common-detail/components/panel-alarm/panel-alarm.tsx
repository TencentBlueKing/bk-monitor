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
import { type PropType, defineComponent, onActivated, shallowRef, watch } from 'vue';
import { reactive } from 'vue';

import { Input, Pagination } from 'bkui-vue';
import { searchEvent } from 'monitor-api/modules/alert_v2';

import PanelAlarmTable from './panel-alarm-table';
import EmptyStatus, {
  type EmptyStatusOperationType,
  type EmptyStatusType,
} from '@/components/empty-status/empty-status';

import type { AlarmDetail } from '@/pages/alarm-center/typings';

import './panel-alarm.scss';
interface IParams {
  end_time: number;
  start_time: number;
}

export default defineComponent({
  name: 'PanelAlarm',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
    params: { type: Object as PropType<IParams>, default: null },
  },
  setup(props) {
    const emptyType = shallowRef<EmptyStatusType>('empty');
    const queryString = shallowRef('');

    const data = shallowRef({
      events: [],
      total: 0,
    });
    const pagination = reactive({
      count: 0,
      current: 1,
      limit: 10,
    });
    const isLoading = shallowRef(false);
    const tableSort = shallowRef<string[]>([]);

    watch(
      () => props.detail,
      val => {
        if (val) {
          pagination.current = 1;
          getData();
        }
      }
    );

    /**
     * @description: 获取列表数据
     * @param {string} sort
     * @return {*}
     */
    const getData = async () => {
      emptyType.value = queryString.value ? 'search-empty' : 'empty';
      isLoading.value = true;
      const params = {
        bk_biz_id: props.detail.bk_biz_id,
        alert_id: props.detail.id,
        query_string: queryString.value,
        start_time: props.detail.begin_time,
        end_time: props.detail.end_time,
        page: pagination.current,
        page_size: pagination.limit,
        record_history: true,
        ordering: tableSort.value,
      };
      data.value = await searchEvent(params, { needRes: true })
        .then(res => {
          return (
            res.data || {
              events: [],
              total: 0,
            }
          );
        })
        .catch(() => {
          return {
            events: [],
            total: 0,
          };
        })
        .finally(() => {
          isLoading.value = false;
        });
      pagination.count = data.value.total;
      isLoading.value = false;
    };

    const handleQueryStringChange = () => {
      getData();
    };

    const handleEmptyOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        queryString.value = '';
      }
      getData();
    };

    const handleTableSort = sort => {
      tableSort.value = sort;
      getData();
    };

    const handleLimitChange = (limit: number) => {
      pagination.limit = limit;
      pagination.current = 1;
      getData();
    };

    const handlePageChange = (page: number) => {
      pagination.current = page;
      getData();
    };

    onActivated(() => {
      queryString.value = '';
      if (props.params && props.params.start_time !== 0) {
        queryString.value = `time: [${props.params.start_time} TO ${props.params.end_time}]`;
      }
      getData();
    });

    return {
      data,
      emptyType,
      isLoading,
      pagination,
      queryString,
      handleEmptyOperation,
      handleTableSort,
      handleLimitChange,
      handlePageChange,
      handleQueryStringChange,
    };
  },

  render() {
    return (
      <div class='alarm-center-detail-panel-convergent-alarm'>
        <div class='search-input'>
          <Input
            v-model={this.queryString}
            placeholder={this.$t('请输入关键字')}
            type='search'
            clearable
            onBlur={this.handleQueryStringChange}
            onClear={this.handleQueryStringChange}
          />
        </div>

        <PanelAlarmTable
          v-slots={{
            empty: () => (
              <EmptyStatus
                type={this.emptyType}
                onOperation={this.handleEmptyOperation}
              />
            ),
          }}
          data={this.data.events}
          loading={this.isLoading}
          onSortChange={this.handleTableSort}
        />

        <Pagination
          v-model={this.pagination.current}
          align='right'
          count={this.pagination.count}
          layout={['total', 'limit', 'list']}
          limit={this.pagination.limit}
          location='right'
          onChange={this.handlePageChange}
          onLimitChange={this.handleLimitChange}
        />
      </div>
    );
  },
});
