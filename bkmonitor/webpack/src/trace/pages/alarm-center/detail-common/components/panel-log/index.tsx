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
import { type PropType, defineComponent, shallowReactive } from 'vue';
import { shallowRef } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import RetrievalFilter from '../../../../../components/retrieval-filter/retrieval-filter';
import { useAlarmLog } from '../../../composables/use-alarm-log';
import IndexSetSelector from './index-set-selector/index-set-selector';
import LogTable from './log-table/log-table';

import type { AlarmDetail } from '../../../typings/detail';

import './index.scss';

export default defineComponent({
  name: 'PanelLog',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const loading = shallowRef(false);
    const indexSetList = shallowRef([]);
    const selectIndexSet = shallowRef('');
    const tableData = shallowReactive({
      data: [],
      total: 0,
      columns: [],
      limit: 30,
      offset: 0,
    });

    const { getIndexSetList, updateTableData } = useAlarmLog(props.detail);

    async function init() {
      loading.value = true;
      indexSetList.value = await getIndexSetList();
      selectIndexSet.value = indexSetList.value[0]?.index_set_id || '';
      const data = await updateTableData({
        index_set_id: selectIndexSet.value,
        keyword: '',
        limit: tableData.limit,
        offset: tableData.offset,
      });
      console.log(data);
      tableData.data = data?.data || [];
      tableData.total = data?.total || 0;
      tableData.columns = data?.columns || [];
      loading.value = false;
    }

    init();

    return {
      indexSetList,
      tableData,
      t,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-log'>
        <div class='panel-log-header'>
          <IndexSetSelector indexSetList={this.indexSetList} />
          <Button
            class='ml-16'
            theme='primary'
            text
          >
            <span>{this.t('更多日志')}</span>
            <span class='icon-monitor icon-fenxiang ml-5' />
          </Button>
        </div>
        <div class='panel-log-filter'>
          <RetrievalFilter zIndex={4000} />
        </div>
        <LogTable tableData={this.tableData} />
      </div>
    );
  },
});
