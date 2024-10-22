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

import { Component, Prop, Emit, InjectReactive, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import { CommonSimpleChart } from '../../common-simple-chart';
import { PERSPECTIVE_TYPE, SYMBOL_LIST } from '../utils';
import TabBtnGroup from './common-comp/tab-btn-group';
import MultiViewTable from './multi-view-table';

import type { IServiceConfig, IColumn, IDataItem } from '../type';

import './caller-callee-table-chart.scss';
interface ICallerCalleeTableChartProps {
  tableColumn: IColumn[];
  tableColData: IColumn[];
  searchList: IServiceConfig[];
  tableListData: IDataItem[];
  tableTabData: IDataItem[];
}
interface ICallerCalleeTableChartEvent {
  onChange?: () => void;
}
@Component({
  name: 'CallerCalleeTableChart',
  components: {},
})
export default class CallerCalleeTableChart extends tsc<ICallerCalleeTableChartProps, ICallerCalleeTableChartEvent> {
  @Prop({ required: true, type: Array }) filterData: IServiceConfig[];
  @Prop({ required: true, type: Array }) searchList: IServiceConfig[];
  @Prop({ required: true, type: Array }) tableColData: IColumn[];
  @Prop({ required: true, type: Array }) tableListData: IDataItem[];
  @Prop({ required: true, type: Array }) tableTabData: IDataItem[];
  tabList = PERSPECTIVE_TYPE;
  activeKey = 'single';
  chooseList = [];
  singleChooseField = 'time';
  tableColumn = [
    {
      label: '时间',
      prop: 'time',
    },
  ];
  /** 是否为单视图 */
  get isSingleView() {
    return this.activeKey === 'single';
  }

  get tagFilterList() {
    return (this.filterData || []).filter(item => item.value.length > 0);
  }
  get chooseKeyList() {
    return [
      ...[
        {
          value: 'time',
          text: '时间',
          // operate: 'eq',
          // values: [],
        },
      ],
      ...this.searchList,
    ];
  }
  changeTab(id: string) {
    this.activeKey = id;
    if (id === 'multiple') {
      this.chooseList = [this.singleChooseField];
      this.tableColumn.map(item => this.chooseList.push(item.value));
    } else {
      const option = this.chooseKeyList.find(item => item.value === this.chooseList[0]);
      this.chooseSingleField(option);
    }
  }
  // 单视角时选择key
  @Emit('change')
  chooseSingleField(item) {
    this.singleChooseField = item.value;
    this.tableColumn = [
      {
        label: item.text,
        prop: item.value,
      },
    ];
    return [item.value];
  }
  // 多视角时选择key
  handleMultiple(val) {
    this.tableColumn = [];
    this.chooseKeyList.map(item => {
      if (this.chooseList.includes(item.value)) {
        this.tableColumn.push({
          label: item.text,
          prop: item.value,
        });
      }
      return item;
    });
    this.$emit('change', this.chooseList);
  }
  @Emit('closeTag')
  handleCloseTag(item) {
    return item;
  }
  handleGetKey(key: string) {
    return this.chooseKeyList.find(item => item.value === key).text;
  }
  handleOperate(key: number) {
    return SYMBOL_LIST.find(item => item.value === key).label;
  }
  @Emit('handleDetail')
  handleShowDetail({ row, key }) {
    return { row, key };
  }
  // 下钻handle
  handleDrill(option) {
    if (this.activeKey === 'multiple') {
      this.chooseList.push(option.value);
      this.handleMultiple(this.chooseList);
    } else {
      this.chooseSingleField(option);
    }
  }

  renderMainList() {
    if (this.isSingleView) {
      return this.chooseKeyList.map(item => (
        <span
          key={item.value}
          class={['aside-item', { active: this.singleChooseField === item.value }]}
          onClick={() => this.chooseSingleField(item)}
        >
          {item.text}
        </span>
      ));
    }
    return (
      <bk-checkbox-group
        v-model={this.chooseList}
        onChange={this.handleMultiple}
      >
        {this.chooseKeyList.map(item => (
          <bk-checkbox
            key={item.value}
            class='aside-item'
            disabled={this.chooseList.length === 1 && this.chooseList.includes(item.value)}
            value={item.value}
          >
            {item.text}
          </bk-checkbox>
        ))}
      </bk-checkbox-group>
    );
  }

  render() {
    return (
      <div class='caller-callee-tab-table-view'>
        <bk-resize-layout
          class='tab-table-view-layout'
          initial-divide={160}
          max={400}
          min={160}
          placement='left'
          collapsible
        >
          <div
            class='layout-aside'
            slot='aside'
          >
            <div class='aside-head'>
              <TabBtnGroup
                height={26}
                activeKey={this.activeKey}
                list={this.tabList}
                type='block'
                onChange={this.changeTab}
              />
            </div>
            <div class='aside-main'>{this.renderMainList()}</div>
          </div>
          <div
            class='layout-main'
            slot='main'
          >
            <div class='layout-main-head'>
              {this.tagFilterList.map(item => (
                <bk-tag
                  key={item.key}
                  closable
                  onClose={() => this.handleCloseTag(item)}
                >
                  {this.handleGetKey(item.key)}
                  <span class='tag-symbol'>{this.handleOperate(item.method)}</span>
                  {item.value.join('、')}
                </bk-tag>
              ))}
            </div>
            <div class='layout-main-table'>
              <MultiViewTable
                searchList={this.chooseKeyList}
                tableColData={this.tableColData}
                tableColumn={this.tableColumn}
                tableListData={this.tableListData}
                tableTabData={this.tableTabData}
                onDrill={this.handleDrill}
                onShowDetail={this.handleShowDetail}
              />
            </div>
          </div>
        </bk-resize-layout>
      </div>
    );
  }
}
