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
import { Component, Emit, Model, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { getDashboardList } from 'monitor-api/modules/grafana';
import { buildInMetric, getPanelsByDashboard } from 'monitor-api/modules/report';
import { deepClone } from 'monitor-common/utils/utils';

import SpaceSelect from '../../../components/space-select/space-select';
import { IAddChartToolData, IChartDataItem, IChartListAllItem, IDefaultRadioList, IGraphValueItem } from '../types';

import checkboxGroup from './checkboxGroup.vue';
import { defaultRadioList } from './store';

import './select-chart.scss';

interface SelectChartProps {
  value: string[];
}

@Component({
  components: {
    checkboxGroup
  }
})
export default class SelectChart extends tsc<SelectChartProps> {
  // value双向绑定
  @Model('valueChange', { type: Array }) value: string[];

  isLoading = false;
  isRightListLoading = false;
  // 选择图表工具的数据
  tool: IAddChartToolData = {
    show: false,
    active: 'grafana',
    tabList: [
      { name: 'default', label: window.i18n.t('内置') },
      { name: 'grafana', label: window.i18n.t('仪表盘') }
    ]
  };

  // active状态与列表数据
  selectedActive: string = null;
  selectedList: IGraphValueItem[] = [];
  rightList: IChartDataItem[] = [];
  // leftList: IChartListAllItem[] = []
  curBizId = `${window.cc_biz_id}`;
  DefaultCurBizIdList: string[] = [`${window.cc_biz_id}`];
  bizIdList: any = [];
  leftActive: string = null;
  rightSelect: IGraphValueItem[] = [];
  allGrafanaListMap: any = [];
  allDefaultList: any = [];
  defaultRadioList: IDefaultRadioList[] = defaultRadioList;
  radioMap: string[] = ['all', 'settings', 'notify'];

  // 拖拽数据状态记录
  DragData: any = {
    from: null,
    to: null,
    toActive: null
  };

  get leftList(): IChartListAllItem[] {
    const isDefault = this.tool.active === 'default';
    const list = isDefault ? this.allDefaultList : this.allGrafanaListMap;
    return list || [];
  }
  // get rightList(): IChartDataItem[] {
  //   if (this.tool.active === 'default' && !this.DefaultCurBizIdList.length) return [];
  //   const allList = this.leftList.reduce((total, cur) => {
  //     cur.panels.forEach((item) => {
  //       const bizId = this.tool.active === 'default' ? this.DefaultCurBizIdList.sort().join(',') : this.curBizId;
  //       item.fatherId = cur.uid;
  //       item.key = `${bizId}-${this.leftActive}-${item.id}`;
  //     });
  //     total = total.concat(cur.panels);
  //     return total;
  //   }, []);
  //   return allList.filter(item => this.leftActive === item.fatherId && !/^-1/.test(item.key));
  // }

  get handleBizIdList() {
    return [
      ...this.defaultRadioList,
      ...this.bizIdList.map(item => ({
        id: String(item.id),
        text: item.text
      }))
    ];
  }

  // 限制最多选择图表数
  get isDisabled(): boolean {
    const MAX = 20;
    return this.rightSelect.length >= MAX;
  }

  @Emit('valueChange')
  handleValueChange(v?: string) {
    return v || this.selectedList;
  }
  // 值更新
  @Watch('value', { immediate: true, deep: true })
  watchValueChange(v: IGraphValueItem[]) {
    this.selectedList = v;
    this.rightSelect = deepClone(v);
  }

  async created() {
    this.isLoading = true;
    await Promise.all([this.getChartList(), this.getBuildInMetric()]).finally(() => (this.isLoading = false));
    this.bizIdList = this.$store.getters.bizList.map(item => ({
      id: String(item.id),
      text: item.text
    }));
  }

  /**
   * 获取内置图表数据
   */
  getBuildInMetric() {
    return buildInMetric().then(list => {
      this.allDefaultList = list;
    });
  }

  /**
   * 获取图表的panels列表数据
   */
  getPanelsList(uid: string) {
    return getPanelsByDashboard({ uid }).finally(() => (this.isRightListLoading = false));
  }

  /**
   * 获取图表列表数据
   */
  getChartList(needLoading = false) {
    // const noPermission = !this.bizIdList.some(item => `${item.id}` === `${this.curBizId}`)
    if (+this.curBizId === -1) return;
    needLoading && (this.isLoading = true);
    return getDashboardList({ bk_biz_id: this.curBizId })
      .then(list => {
        this.allGrafanaListMap = Array.isArray(list) ? list : list[this.curBizId] || [];
      })
      .catch(() => [])
      .finally(() => (this.isLoading = false));
  }

  /**
   * 删除已选择
   * @params index 数据索引
   */
  handleDelSelected(e: Event, index: number) {
    e.stopPropagation();
    this.selectedList.splice(index, 1);
    const isEixstActive = this.selectedList.find(checked => checked.id === this.selectedActive);
    !isEixstActive && (this.selectedActive = null);
    this.handleValueChange();
  }

  /**
   * 选择
   * @params index 数据索引
   */
  handleSelectItem(item: IGraphValueItem) {
    if (this.selectedActive === item.id) return;
    this.selectedActive = item.id;
    const ids = item.id.split('-');
    const isDefault = !(typeof +ids[0] === 'number' && this.bizIdList.find(item => item.id === ids[0]));
    if (!isDefault && !this.bizIdList.find(item => item.id === ids[0])) return;
    // eslint-disable-next-line prefer-destructuring
    this.leftActive = ids[1];
    this.tool.show = true;
    this.tool.active = isDefault ? 'default' : 'grafana';
    // eslint-disable-next-line prefer-destructuring
    this.tool.active === 'default' ? (this.DefaultCurBizIdList = ids[0].split(',')) : (this.curBizId = ids[0]);
    this.rightSelect = deepClone(this.selectedList);
  }

  /**
   * 新建图表
   */
  handleAddChart() {
    this.rightSelect = deepClone(this.selectedList);
    this.tool.show = true;
  }

  /**
   * 左侧选中操作
   */
  async handleSelectLeftItem(item: IChartListAllItem) {
    item.bk_biz_id && (this.curBizId = `${item.bk_biz_id}`);
    this.leftActive = item.uid;
    this.isRightListLoading = true;
    let graphPanelsList = [];
    if (this.tool.active === 'default') {
      graphPanelsList = this.allDefaultList.find(i => i.panels).panels;
      this.isRightListLoading = false;
    } else {
      graphPanelsList = await this.getPanelsList(this.leftActive);
    }
    graphPanelsList.forEach(panel => {
      const bizId = this.tool.active === 'default' ? this.DefaultCurBizIdList.sort().join(',') : this.curBizId;
      panel.fatherId = item.uid;
      panel.key = `${bizId}-${this.leftActive}-${panel.id}`;
    });
    this.rightList = graphPanelsList.filter(item => this.leftActive === item.fatherId && !/^-1/.test(item.key)) || [];
  }

  /**
   * 确认操作
   */
  handleComfirm() {
    this.selectedList = deepClone(this.rightSelect);
    this.rightSelect = [];
    this.handleValueChange();
    this.tool.show = false;
    this.selectedActive = null;
  }

  /**
   * 取消操作
   */
  handleCancel() {
    this.tool.show = false;
    this.selectedActive = null;
    this.rightSelect = [];
  }

  handleTabChange(name: string) {
    this.tool.active = name;
    this.tool.active === 'default'
      ? (this.DefaultCurBizIdList = [`${+window.cc_biz_id > -1 ? window.cc_biz_id : 'all'}`])
      : (this.curBizId = `${window.cc_biz_id}`);
    this.selectedActive = '';
    this.rightList = [];
    this.leftActive = null;
  }

  handleChangeBizIdList(list) {
    this.DefaultCurBizIdList = list;
    // const leng = list.length;
    // const lastChild = list[leng - 1];
    // const firstChild = list[0];
    // const { radioMap } = this;
    // const isAllRadio = list.every(item => radioMap.includes(item));
    // if (radioMap.includes(lastChild)) {
    //   this.DefaultCurBizIdList = [lastChild];
    // }
    // if (radioMap.includes(firstChild) && !isAllRadio && leng > 1) {
    //   this.DefaultCurBizIdList = this.DefaultCurBizIdList.filter(item => !radioMap.includes(item));
    // }
  }

  handleGraphBizid(v) {
    if (this.tool.active === 'default') return;
    if (v.length) {
      [this.curBizId] = v;
    }
    this.rightList = [];
    this.getChartList(true);
  }

  handleBelonging(item) {
    const res = item.id.split('-');
    const str = this.radioMap.includes(res[0]) ? this.defaultRadioList.find(item => item.id === res[0])?.title : res[0];
    return str;
  }

  /**
   * 以下为拖拽操作
   */
  handleDragStart(e: DragEvent, index: number) {
    this.DragData.from = index;
  }
  handleDragOver(e: DragEvent) {
    e.preventDefault();
    e.dataTransfer.effectAllowed = 'move';
  }
  handleDragEnd() {
    this.DragData = {
      from: null,
      to: null,
      toActive: null
    };
  }
  handleDrop() {
    const { from, to } = this.DragData;
    if (from === to) return;
    const list = deepClone(this.selectedList);
    const temp = list[from];
    list.splice(from, 1);
    list.splice(to, 0, temp);
    this.handleValueChange(list);
  }
  handleDragEnter(e: DragEvent, index: number) {
    this.DragData.to = index;
    this.DragData.toActive = index;
  }
  render() {
    return (
      <div
        class='select-chart-wrap'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        {!!this.selectedList.length && (
          <transition-group
            name='flip-list'
            tag='ul'
            class='selected-list-wrap'
          >
            {this.selectedList.map((item, index) => (
              <li
                key={item.id}
                class={[
                  'selected-item',
                  {
                    active: this.DragData.toActive === index || this.selectedActive === item.id
                  }
                ]}
                draggable={true}
                onClick={() => this.handleSelectItem(item)}
                onDragstart={e => this.handleDragStart(e, index)}
                onDragend={this.handleDragEnd}
                onDrop={this.handleDrop}
                onDragenter={e => this.handleDragEnter(e, index)}
                onDragover={e => this.handleDragOver(e)}
              >
                <span class='icon-drag' />
                <span class='item-title'>
                  <span class='title'>{item.name}</span>
                  <span
                    class='des'
                    v-bk-tooltips={{ content: this.handleBelonging(item), delay: 300, allowHTML: false }}
                  >
                    &nbsp;{`- ${this.$t('所属:')}${this.handleBelonging(item)}`}
                  </span>
                </span>
                <span
                  onClick={e => this.handleDelSelected(e, index)}
                  class='icon-monitor icon-mc-close'
                />
              </li>
            ))}
          </transition-group>
        )}

        <div
          class='add-btn-wrap'
          v-show={!this.tool.show && !this.isDisabled}
        >
          <span
            class='add-btn'
            onClick={this.handleAddChart}
          >
            <span class='icon-monitor icon-mc-add' />
            {this.$t('添加图表')}
          </span>
        </div>
        {this.tool.show && (
          <div class='select-tool-wrap'>
            <div class='tool-left-wrap'>
              <bk-tab
                class='tab-wrap'
                active={this.tool.active}
                type='unborder-card'
                on-tab-change={this.handleTabChange}
              >
                {this.tool.tabList.map((tab, index) => (
                  <bk-tab-panel
                    {...{ props: tab }}
                    key={index}
                  />
                ))}
              </bk-tab>
              <div
                class='biz-list-wrap'
                v-show={this.tool.active === 'default'}
              >
                <SpaceSelect
                  value={this.DefaultCurBizIdList}
                  space-list={this.$store.getters.bizList}
                  need-authority-option={false}
                  need-alarm-option={false}
                  need-defalut-options={true}
                  onChange={this.handleChangeBizIdList}
                />
              </div>
              {this.tool.active === 'grafana' && (
                <div class='biz-list-wrap'>
                  <SpaceSelect
                    value={[this.curBizId]}
                    space-list={this.$store.getters.bizList}
                    need-authority-option={false}
                    need-alarm-option={false}
                    multiple={false}
                    onChange={this.handleGraphBizid}
                  />
                </div>
              )}

              <div class='left-list-wrap'>
                {this.leftList.map((item, index) => (
                  <div
                    key={index}
                    class={['left-list-item', { active: this.leftActive === item.uid }]}
                    onClick={() => this.handleSelectLeftItem(item)}
                  >
                    {item.name}
                  </div>
                ))}
              </div>
            </div>
            <div
              class='tool-right-wrap'
              v-bkloading={{ isLoading: this.isRightListLoading }}
            >
              <div class='right-title'>{this.$t('可选图表({num})', { num: this.rightList.length })}</div>
              <div class='right-list-wrap'>
                <checkbox-group
                  v-model={this.rightSelect}
                  list={this.rightList}
                  active={this.selectedActive}
                  disabled={this.isDisabled}
                />
              </div>
              <div class='right-btn-wrap'>
                <bk-button
                  size='small'
                  theme='primary'
                  disabled={false}
                  onClick={this.handleComfirm}
                >
                  {this.$t('确认')}
                </bk-button>
                <bk-button
                  size='small'
                  onClick={this.handleCancel}
                >
                  {this.$t('取消')}
                </bk-button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
}
