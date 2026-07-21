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
    /** 进程列表数据 hook（含加载状态、搜索、排序） */
    const { loading, keyword, displayList, sortInfo, handleKeywordChange, handleSortChange } = useProcessList({
      host: toRef(props, 'host'),
    });

    /** 展示列（默认勾选项对齐设计稿，可在「字段设置」中调整） */
    const visibleColumns = shallowRef<string[]>(PROCESS_LIST_COLUMNS.filter(c => c.checked).map(c => c.id));
    /** 进程详情抽屉显隐状态（点击进程名打开） */
    const detailShow = shallowRef(false);
    /** 当前选中展示的进程详情 */
    const activeProcess = shallowRef<null | ProcessItem>(null);

    /**
     * @description 点击进程行，打开进程详情抽屉
     * @param {ProcessItem} row - 被点击的进程数据
     */
    const handleRowClick = (row: ProcessItem) => {
      activeProcess.value = row;
      detailShow.value = true;
    };

    return {
      t,
      loading: loading,
      keyword: keyword,
      displayList: displayList,
      sortInfo: sortInfo,
      visibleColumns,
      detailShow,
      activeProcess,
      handleRowClick,
      handleKeywordChange,
      handleSortChange,
    };
  },
  render() {
    return (
      <Loading
        class='host-process'
        loading={this.loading}
      >
        <div class='host-process__search'>
          <Input
            modelValue={this.keyword}
            placeholder={this.t('输入 进程名 / PID')}
            type='search'
            clearable
            onClear={() => this.handleKeywordChange('')}
            onInput={(v: string) => this.handleKeywordChange(v)}
          />
        </div>
        <ProcessTable
          data={this.displayList}
          sort={this.sortInfo}
          visibleColumns={this.visibleColumns}
          onColumnsChange={(cols: string[]) => (this.visibleColumns = cols)}
          onRowClick={this.handleRowClick}
          onSortChange={this.handleSortChange}
        />
        <ProcessDetail
<<<<<<< HEAD
          compareHostList={props.compareHostList}
          process={activeProcess.value}
          selectedNode={props.host}
          show={detailShow.value}
          onUpdate:show={(v: boolean) => (detailShow.value = v)}
=======
          process={this.activeProcess}
          show={this.detailShow}
          onUpdate:show={(v: boolean) => (this.detailShow = v)}
>>>>>>> ca7be03ed (feat: 进程列表表格对齐新版设计稿 --story=136308029)
        />
      </Loading>
    );
  },
});
