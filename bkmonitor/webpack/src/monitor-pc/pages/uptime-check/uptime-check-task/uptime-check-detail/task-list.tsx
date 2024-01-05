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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, deepClone } from '../../../../../monitor-common/utils/utils';
import { IViewOptions, PanelModel } from '../../../../../monitor-ui/chart-plugins/typings';
import { VariablesService } from '../../../../../monitor-ui/chart-plugins/utils/variable';

import './task-list.scss';

interface TaskDataItem {
  id: number | string;
  name: string;
}

export interface IViewOption {
  filter_dict?: Record<string, any>;
  group_by?: string[];
  method?: string;
  interval?: string;
  time_shift?: string;
}

export interface IProps {
  panel: PanelModel;
  viewOptions: IViewOptions;
  isStatusFilter?: boolean;
  showOverview?: boolean;
  isTargetCompare?: boolean;
}

export interface IEvents {
  onTitleChange: string;
  onChange: IViewOptions;
  onListChange?: { id: string; name: string }[];
  onOverviewChange?: void;
}

@Component({})
export default class TaskList extends tsc<IProps, IEvents> {
  /** 当前输入的viewOptions数据 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 是否存在目标对比 */
  @Prop({ default: false, type: Boolean }) isTargetCompare: boolean;

  loading = false;
  inited = false;
  /** 搜索关键字 */
  searchKeyword = '';
  activeTask = '';
  taskData: TaskDataItem[] = [];
  localTaskData: TaskDataItem[] = [];
  localViewOptions: IViewOptions = {};

  get apiData() {
    return this.panel?.targets?.[0];
  }

  get queryFileds() {
    return Object.keys(this.panel?.targets?.[0]?.fields || {}).length
      ? this.panel?.targets?.[0]?.fields
      : this.panel?.targets?.[0]?.field;
  }

  /** 目标对比选中的主机id */
  get compareNode() {
    return [];
  }

  @Watch('viewOptions', { immediate: true })
  handleViewOptionsUpdate() {
    this.localViewOptions = deepClone(this.viewOptions);
    Object.assign(this.localViewOptions);
    this.checkedNodeChange();
  }

  /** 对外派发title */
  @Emit('titleChange')
  handleTitleChange(data: TaskDataItem) {
    return data.name;
  }

  /** 对外输出一个viewOptions格式数据 */
  @Emit('change')
  handleViewOptionsChange(viewOptions: IViewOptions): IViewOptions {
    return viewOptions;
  }

  created() {
    this.getTaskData();
  }

  /** 获取topo tree数据 */
  getTaskData() {
    if (!this.apiData) return;
    this.loading = true;
    const variablesService = new VariablesService(this.viewOptions);
    this.$api[this.apiData.apiModule]
      [this.apiData.apiFunc]({
        ...variablesService.transformVariables(this.apiData.data, this.viewOptions.filters)
      })
      .then(res => {
        this.taskData = res;
        this.handleSearch();
        this.handleListChange(res);
        if (!this.inited) {
          const curData = this.taskData.find(data => String(data.id) === String(this.activeTask));
          Boolean(curData) && this.handleTitleChange(curData);
          this.inited = true;
        }
      })
      .finally(() => (this.loading = false));
  }

  /** 选中节点 */
  checkedNodeChange() {
    const taskId = this.localViewOptions.filters?.[this.queryFileds?.id];
    this.activeTask = taskId;
  }

  /** 搜索操作 */
  @Debounce(300)
  handleSearch() {
    // eslint-disable-next-line max-len
    this.localTaskData = this.taskData.filter(
      task => task.name?.toLowerCase().indexOf(this.searchKeyword.toLowerCase()) > -1
    );
  }

  /** 刷新数据 */
  handleRefresh() {
    this.searchKeyword = '';
    this.getTaskData();
  }

  handleTaskChange(task: TaskDataItem) {
    if (this.activeTask === task.id) return;
    const filterDictList = this.queryFileds;
    const viewOptions: IViewOptions = deepClone(this.viewOptions);
    this.activeTask = String(task.id);
    this.handleTitleChange(task);
    Object.keys(filterDictList).forEach(item => {
      viewOptions.filters[filterDictList[item]] = task[item] || '';
    });
    this.handleViewOptionsChange(viewOptions);
  }

  @Emit('listChange')
  handleListChange(list: TaskDataItem[]) {
    return list.map(item => ({
      id: item.id || '',
      name: item.name || ''
    }));
  }

  @Emit('overviewChange')
  handleOverviewChange() {}

  render() {
    return (
      <div class='uptime-check-task-list'>
        <div
          class='task-list-wrap'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='task-list-search-row'>
            <bk-input
              v-model={this.searchKeyword}
              right-icon='bk-icon icon-search'
              placeholder={this.$t('搜索')}
              onInput={this.handleSearch}
            ></bk-input>
            <bk-button
              class='refresh-btn'
              onClick={this.handleRefresh}
            >
              <i class='icon-monitor icon-shuaxin'></i>
            </bk-button>
          </div>
          {this.localTaskData.length ? (
            <div class='task-list-content'>
              <ul>
                {this.localTaskData.map(task => (
                  <li
                    class={[
                      'task-item',
                      { active: String(task.id) === String(this.activeTask) },
                      { 'checked-target': this.isTargetCompare && this.compareNode.includes(task.id) }
                    ]}
                    onClick={() => this.handleTaskChange(task)}
                  >
                    {task.name}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <bk-exception
              class='exception-wrap-item exception-part'
              type='search-empty'
              scene='part'
            />
          )}
        </div>
      </div>
    );
  }
}
