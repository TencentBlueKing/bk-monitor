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

import { type PropType, defineComponent, shallowRef, toRef } from 'vue';

import { Input, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useProcessList } from '../../composables/use-process-list';
import { PROCESS_LIST_COLUMNS } from '../../constants/process';
import ProcessDetail from './process-detail/process-detail';
import ProcessTable from './process-table';

import type { ProcessItem } from '../../types/process';
import type { IHostTopoHostNode } from '../../types/topo';

import './host-process.scss';

export default defineComponent({
  name: 'HostProcess',
  props: {
    /** 当前选中的主机节点（进程列表所属主机） */
    host: {
      type: Object as PropType<IHostTopoHostNode | null>,
      default: null,
    },
    compareHostList: {
      type: Array as PropType<IHostTopoHostNode[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const ctx = useProcessList({ host: toRef(props, 'host') });

    /** 展示列（默认勾选项对齐设计稿，可在「字段设置」中调整） */
    const visibleColumns = shallowRef<string[]>(PROCESS_LIST_COLUMNS.filter(c => c.checked).map(c => c.id));

    /** 进程详情抽屉（点击进程名打开） */
    const detailShow = shallowRef(false);
    const activeProcess = shallowRef<null | ProcessItem>(null);

    const handleRowClick = (row: ProcessItem) => {
      activeProcess.value = row;
      detailShow.value = true;
    };

    return () => (
      <Loading
        class='host-process'
        loading={ctx.loading.value}
      >
        <div class='host-process__search'>
          <Input
            modelValue={ctx.keyword.value}
            placeholder={t('输入 进程名 / PID')}
            type='search'
            clearable
            onClear={() => ctx.handleKeywordChange('')}
            onInput={(v: string) => ctx.handleKeywordChange(v)}
          />
        </div>
        <ProcessTable
          data={ctx.displayList.value}
          sort={ctx.sortInfo.value}
          visibleColumns={visibleColumns.value}
          onColumnsChange={(cols: string[]) => (visibleColumns.value = cols)}
          onRowClick={handleRowClick}
          onSortChange={ctx.handleSortChange}
        />
        <ProcessDetail
          compareHostList={props.compareHostList}
          process={activeProcess.value}
          selectedNode={props.host}
          show={detailShow.value}
          onUpdate:show={(v: boolean) => (detailShow.value = v)}
        />
      </Loading>
    );
  },
});
