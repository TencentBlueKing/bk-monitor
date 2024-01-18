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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { deepClone } from '../../../../../monitor-common/utils/utils';
import MonitorImport from '../../../../components/monitor-import/monitor-import.vue';
import GroupSelectMultiple from '../../../custom-escalation/group-select-multiple';
import { csvToArr } from '../../../custom-escalation/utils';
import SortPanel from '../../../performance/performance-detail/sort-panel.vue';
import { downCsvFile } from '../../../view-detail/utils';
import { IBookMark, SettingsDashboardType } from '../../typings';
import { matchRuleFn, SETTINGS_POP_ZINDEX } from '../../utils';

import './settings-dashboard.scss';

/**
 * 视图设置弹窗
 */
@Component
export default class SettingsDashboard extends tsc<SettingsDashboardType.IProps, SettingsDashboardType.IEvents> {
  /** 页签数据 */
  @Prop({ default: () => [], type: Array }) bookMarkData: IBookMark[];
  @Prop({ default: '', type: String }) activeTab: string;
  /** 场景名称 */
  @Prop({ default: '', type: String }) title: string;
  @Prop({ default: false, type: Boolean }) enableAutoGrouping: boolean;
  @Ref('sortPanel') sortPanelRef: any;

  tabActive = '';
  showChartSort = true;
  rangeType = 'tiled'; // 排列方式
  isCreate = false; // 创建分组切换输入框
  createName = ''; // 创建分组名
  isChecked = false; // 是否选中了分组
  loading = true;
  order = ''; // 当前分组名
  orderList: SettingsDashboardType.IPanelGroup[] = [];
  groupList = []; // 分组
  defaultOrderList = [];
  allPanels: { id: string; title: string }[] = [];
  groupSelectList = []; // 加入分组
  groupSelect = [];
  curSelectCount = 0; /* 当前选中的视图数量 批量加入分组部分 */

  /** 当前视图配置是否存在差异 */
  get localDashBoardIsDiff() {
    if (!this.orderList.length) return false;
    return JSON.stringify(this.orderList) !== JSON.stringify(this.sortPanelRef?.groups);
  }

  get curPageData() {
    return this.bookMarkData.find(data => data.id === this.activeTab);
  }

  created() {
    this.tabActive = this.activeTab;
    this.updateLocalPanel(this.tabActive);
  }

  @Watch('bookMarkData', { immediate: true, deep: true })
  handleBookMarkDataChange() {
    if (this.tabActive) {
      this.updateLocalPanel(this.tabActive);
      this.updateDefaultPanel(this.tabActive);
    }
  }

  /**
   * @description: 保存页签
   */
  @Emit('save')
  handleSave(orderList): SettingsDashboardType.IEvents['onSave'] {
    const temporderList = [];
    if (this.enableAutoGrouping) {
      /* 去重 */
      orderList.forEach(item => {
        const panels = [];
        const tempSets = new Set();
        item?.panels?.forEach(p => {
          if (!tempSets.has(p.id)) {
            panels.push(p);
          }
          tempSets.add(p.id);
        });
        temporderList.push({
          ...item,
          panels
        });
      });
    }
    return {
      id: this.tabActive,
      name: this.curPageData.name,
      data: this.enableAutoGrouping ? temporderList : orderList
    };
  }

  /**
   * @description: 更新当前页签视图
   * @param {string} tab
   */
  updateLocalPanel(tab) {
    this.loading = true;
    const curPageData = this.bookMarkData.find(item => item.id === tab);
    this.orderList.splice(0, this.orderList.length);
    if (curPageData) {
      this.$emit('tab-change', tab);
      // eslint-disable-next-line no-prototype-builtins
      if (!curPageData.isReady) {
        // 未获取页签数据详情，调用接口获取
        this.$emit('getTabDetail', tab);
        return;
      }
      this.handleFormatPanel(curPageData);
    }
  }

  updateDefaultPanel(tab) {
    const target = this.bookMarkData.find(data => data.id === tab);
    this.defaultOrderList = this.enableAutoGrouping ? deepClone(this.orderList) : deepClone(target.panels);
  }

  /**
   * @description: 处理返回的panels配置格式化分组
   * @param {IBookMark} data
   */
  handleFormatPanel(data) {
    this.orderList = deepClone(data.order);
    if (this.enableAutoGrouping) {
      this.tidyOrderList();
    }
    setTimeout(() => {
      this.loading = false;
    }, 100);
  }

  /**
   * @param {string | number} tab
   */
  handleTabChange(tab) {
    this.tabActive = tab;
    this.updateLocalPanel(this.tabActive);
  }

  async handleBeforeToggle(tab) {
    if (this.localDashBoardIsDiff) {
      this.$bkInfo({
        zIndex: SETTINGS_POP_ZINDEX,
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          this.handleTabChange(tab);
        }
      });
      return false;
    }

    return true;
  }

  /**
   * @description: 创建分组输入框
   * @param {*} isCreate
   * @return {*}
   */
  createGroup(isCreate = false) {
    this.isCreate = !this.isCreate;
    if (isCreate) {
      this.sortPanelRef.handleSaveNewGroup(this.createName);
    }
    this.createName = '';
  }

  /**
   * @description: 创建分组
   */
  addGroupPanels() {
    this.order !== '' && this.sortPanelRef.checkedSortSet(this.order);
  }

  /**
   * @description: 分组变更
   * @param {object} list
   * @return {*}
   */
  groupsChange(list: { id: string; name: string }[]) {
    this.groupList = list;
    this.order = this.groupList[0].id;
    this.getGroupSelectList();
  }

  /**
   * @description: 还原默认
   */
  handleRestore() {
    this.$bkInfo({
      zIndex: SETTINGS_POP_ZINDEX,
      title: this.$t('是否还原默认配置？'),
      extCls: 'reset-default',
      confirmFn: () => {
        this.handleSave([]);
      }
    });
  }

  /**
   * @description: 保存配置
   * @param {any} arr
   * @return {*}
   */
  async handleSortChange(list: SettingsDashboardType.IPanelGroup[]) {
    this.loading = true;
    this.orderList = deepClone(list);
    this.handleSave(this.orderList);
  }

  /* 整理数据 */
  tidyOrderList() {
    this.getGroupSelectList();
    const autoRuleFn = (title: string, match_type: string[], auto_rules: string[], match_rules: string[]) => {
      if (match_type?.length) {
        return {
          match_type,
          match_rules
        };
      }
      const tempRules = [];
      auto_rules?.forEach(rule => {
        if (matchRuleFn(title, rule)) {
          tempRules.push(rule);
        }
      });
      return {
        match_type: tempRules.length ? ['manual', 'auto'] : ['manual'],
        match_rules: match_rules?.length ? match_rules : tempRules
      };
    };
    const allPanelsSet = new Set();
    this.allPanels = [];
    this.orderList = this.orderList.map(item => ({
      ...item,
      manual_list: item?.manual_list || item.panels.map(p => p.id),
      auto_rules: item?.auto_rules || [],
      panels: item.panels.map(panel => {
        if (!allPanelsSet.has(panel.id)) {
          this.allPanels.push(panel);
        }
        allPanelsSet.add(panel.id);
        return {
          ...panel,
          ...(autoRuleFn(panel.title, panel.match_type, item.auto_rules, panel.match_rules) as any)
        };
      })
    }));
    this.defaultOrderList = deepClone(this.orderList);
  }

  /* 获取加入分组的分组选项列表 */
  getGroupSelectList() {
    const groupSelectList = [];
    this.orderList.forEach(item => {
      if (item.id !== '__UNGROUP__') {
        groupSelectList.push({
          id: item.id,
          name: item.title
        });
      }
    });
    this.groupSelectList = groupSelectList;
  }

  /* 更新匹配规则后同步更新组内的视图 */
  handleAutoRuleChange(data: { id: string; value: string[] }) {
    const targetIndex = this.orderList.findIndex(item => item.id === data.id);
    this.orderList[targetIndex].auto_rules = data.value;
    if (targetIndex > -1) {
      const tempAutoPanels: { [key: string]: string[] } = {}; /* 需要添加panel */
      this.allPanels.forEach(panel => {
        const tempRules = [];
        data.value.forEach(rule => {
          if (matchRuleFn(panel.title, rule)) {
            tempRules.push(rule);
          }
        });
        if (tempRules.length) {
          // const targetRules = tempAutoPanels[panel.id];
          // if (targetRules) {
          //   tempAutoPanels[panel.id] = [... new Set(targetRules.concat(tempRules))];
          // } else {
          //   tempAutoPanels[panel.id] = tempRules;
          // }
          tempAutoPanels[panel.id] = tempRules;
        }
      });
      const notInTargetOrderOfPanels = []; /* 需要剔除的panel */
      const noAutoTagPanels = []; /* 需要去除自动标签的panel */
      this.orderList[targetIndex].panels.forEach(panel => {
        if (!tempAutoPanels[panel.id]) {
          if (panel.match_type.length === 1 && panel.match_type[0] === 'auto') {
            notInTargetOrderOfPanels.push(panel);
          } else {
            // 仅自动去除标签
            noAutoTagPanels.push(panel);
          }
        }
      });
      const notInTargetOrderOfPanelsIds = notInTargetOrderOfPanels.map(item => item.id);
      const noAutoTagPanelsIds = noAutoTagPanels.map(item => item.id);
      this.orderList.forEach(item => {
        if (item.id === data.id) {
          const tempPanels = item.panels
            .filter(p => !notInTargetOrderOfPanelsIds.includes(p.id))
            .map(p => {
              if (noAutoTagPanelsIds.includes(p.id)) {
                return {
                  ...p,
                  match_rules: [],
                  match_type: p.match_type?.length ? ['manual'] : []
                };
              }
              return p;
            });
          const tempPanelsIds = tempPanels.map(t => t.id);
          Object.keys(tempAutoPanels).forEach(key => {
            if (!tempPanelsIds.includes(key)) {
              const tempPanel = this.allPanels.find(a => a.id === key);
              tempPanels.unshift({
                ...tempPanel,
                match_rules: tempAutoPanels[key],
                match_type: ['auto']
              } as any);
            } else {
              const tempPanel = tempPanels.find(t => t.id === key);
              tempPanel.match_rules = tempAutoPanels[key];
              tempPanel.match_type = [...new Set(tempPanel.match_type.concat(['auto']))];
            }
          });
          item.panels = tempPanels as any;
        } else if (item.id === '__UNGROUP__') {
          item.panels = item.panels.filter(panel => !tempAutoPanels[panel.id]?.length);
          const tempIds = new Set();
          item.panels.forEach(p => {
            tempIds.add(p.id);
          });
          const temp = [];
          this.allPanels.forEach(p => {
            if (!tempIds.has(p.id) && notInTargetOrderOfPanelsIds.includes(p.id)) {
              temp.push(p);
            }
          });
          const targetPanels = temp.map(t => ({ ...t, match_rules: [], match_type: ['manual'] }));
          item.panels.unshift(...targetPanels);
        }
      });
      this.orderList = this.orderList.slice();
    }
  }

  handleGroupSelectChange(value: string[]) {
    this.groupSelect = value;
  }
  handleGroupSelectToggle(value: boolean) {
    if (!value && this.groupSelect.length) {
      // 加入分组
      this.sortPanelRef.checkedAddGroup(this.groupSelect);
      this.groupSelect = [];
    }
  }

  /* 导入 */
  handleImportChange(data: string) {
    const arr = csvToArr(data);
    const allPanelIdsSet = new Map();
    this.allPanels.forEach(p => {
      allPanelIdsSet.set(p.id, p);
    });
    const orderList = [];
    const panelsUpdate = (panels: { id: string; hidden: boolean }[], autoRules: string[]) => {
      const targetPanels = [];
      const oldIds = new Set();
      panels.forEach(p => {
        const panelData = allPanelIdsSet.get(p.id);
        if (panelData) {
          const matchRules = [];
          autoRules.forEach(rule => {
            if (matchRuleFn(panelData.title, rule)) {
              matchRules.push(rule);
            }
          });
          const temp = {
            ...panelData,
            hidden: p.hidden || false,
            match_type: matchRules.length ? ['manual', 'auto'] : ['manual'],
            match_rules: matchRules
          };
          oldIds.add(temp.id);
          targetPanels.push(temp);
        }
      });
      this.allPanels.forEach(p => {
        if (!oldIds.has(p.id)) {
          const matchRules = [];
          autoRules.forEach(rule => {
            if (matchRuleFn(p.title, rule)) {
              matchRules.push(rule);
            }
          });
          if (matchRules.length) {
            targetPanels.push({
              ...p,
              match_type: ['auto'],
              match_rules: matchRules
            });
          }
        }
      });
      return targetPanels;
    };
    /* 去重 */
    const tempIds = new Set();
    arr.forEach((row, index) => {
      if (index !== 0) {
        const id = row[0];
        const title = row[1];
        let panels = [];
        try {
          panels = row[2] ? JSON.parse(row[2].replace(/;/g, ',')) : [];
        } catch (err) {
          panels = [];
        }
        const autoRules = !!row[3] ? row[3].split(';') : [];
        if (!tempIds.has(id)) {
          if (id !== '__UNGROUP__') {
            orderList.push({
              id,
              title,
              auto_rules: autoRules,
              panels: panelsUpdate(panels, autoRules)
            });
          } else {
            orderList.push({
              id,
              title,
              auto_rules: [],
              panels: []
            });
          }
        }
        tempIds.add(id);
      }
    });
    /* 以分组的无需出现在未分组栏 */
    const hasGroupPanelIds = new Set();
    orderList.forEach(item => {
      if (item.id !== '__UNGROUP__') {
        item.panels.forEach(p => {
          hasGroupPanelIds.add(p.id);
        });
      }
    });
    const unGroupPanels = [];
    this.allPanels.forEach(p => {
      if (!hasGroupPanelIds.has(p.id)) {
        unGroupPanels.push({
          ...p,
          hidden: false,
          match_type: ['manual'],
          match_rules: []
        });
      }
    });
    const unGroup = orderList.find(item => item.id === '__UNGROUP__');
    if (unGroup) {
      unGroup.panels = unGroupPanels;
    } else {
      orderList.push({
        id: '__UNGROUP__',
        title: this.$t('未分组的指标'),
        panels: unGroupPanels,
        auto_rules: []
      });
    }
    this.orderList = orderList;
    this.orderList.slice();
  }
  /* 导出 */
  handleExportChange() {
    const transformTableDataToCsvStr = (tableThArr: string[], tableTdArr: Array<string[]>): string => {
      const csvList: string[] = [tableThArr.join(',')];
      tableTdArr.forEach(row => {
        const rowString = row.reduce((str, item, index) => str + (!!index ? ',' : '') + item, '');
        csvList.push(rowString);
      });
      const csvString = csvList.join('\n');
      return csvString;
    };
    const thArr = ['id', 'title', 'panels', 'auto_rules'];
    const tdArr = [];
    this.orderList.forEach(item => {
      const row = [
        item.id,
        item.title,
        item.panels.length
          ? JSON.stringify(item.panels.map(p => ({ id: p.id, hidden: p.hidden }))).replace(/,/g, ';')
          : '',
        item.auto_rules.length ? item.auto_rules.join(';') : ''
      ];
      tdArr.push(row);
    });
    const csvStr = transformTableDataToCsvStr(thArr, tdArr);
    downCsvFile(csvStr, `${this.title}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.csv`);
  }
  /* 添加组 */
  handleAddGroupChange(group) {
    if (this.enableAutoGrouping) {
      this.orderList.unshift({
        ...group,
        auto_rules: []
      });
      this.getGroupSelectList();
    }
  }
  /* 更新orderList */
  handleOrderListChange(groups) {
    this.orderList = groups;
  }

  /* 重置 */
  handleReset() {
    if (this.enableAutoGrouping) {
      this.orderList = deepClone(this.defaultOrderList);
      this.tidyOrderList();
    }
  }

  render() {
    /** 页签选择tab */
    const tabItemTpl = (_, id) => {
      const item = this.bookMarkData.find(item => item.id === id);
      return (
        <span class={['tab-label-wrap', { active: id === this.tabActive }]}>
          <span class='tab-label-text'>{item.name}</span>
          {item.show_panel_count && <span class='tab-label-count'>{item.panel_count}</span>}
        </span>
      );
    };

    return (
      <div class='settings-dashboard-wrap'>
        <div class='settings-title'>{this.title}</div>
        {this.bookMarkData.length ? (
          <bk-tab
            class='settings-tab'
            active={this.tabActive}
            type='unborder-card'
            before-toggle={this.handleBeforeToggle}
            on-tab-change={this.handleTabChange}
          >
            {this.bookMarkData.map(
              item =>
                item.mode === 'auto' && (
                  <bk-tab-panel
                    key={item.id}
                    name={item.id}
                    label={item.name}
                    render-label={tabItemTpl}
                  ></bk-tab-panel>
                )
            )}
          </bk-tab>
        ) : null}
        {this.orderList?.length ? (
          <div class='settings-dashboard-content'>
            <div class='bk-button-group'>
              <bk-button class={['range-button', { 'is-selected': this.rangeType === 'tiled' }]}>
                {this.$t('平铺')}
              </bk-button>
              <bk-button
                class={['range-button']}
                disabled={true}
              >
                {this.$t('自定义')}
              </bk-button>
            </div>
            <div
              class='sort-setting-title'
              v-bkloading={{ isLoading: this.loading, zIndex: 2000 }}
            >
              {/* 创建分组 */}
              {!this.isCreate ? (
                <span class='title-label'>
                  <span
                    class='add-btn'
                    onClick={() => this.createGroup(false)}
                  >
                    <i class='bk-icon icon-plus-circle-shape'></i>
                    <span>{this.$t('创建分组')}</span>
                  </span>
                  {this.enableAutoGrouping ? (
                    <span class='import-or-export'>
                      <span
                        class='import-btn'
                        onClick={this.handleExportChange}
                      >
                        <span class='icon-monitor icon-shangchuan'></span>
                        <span>{this.$t('导出')}</span>
                      </span>
                      <span class='export-btn'>
                        <MonitorImport
                          accept={'.csv'}
                          return-text={true}
                          base64={false}
                          onChange={this.handleImportChange}
                        >
                          <span class='icon-monitor icon-xiazai2'></span>
                          <span>{this.$t('导入')}</span>
                        </MonitorImport>
                      </span>
                    </span>
                  ) : undefined}
                </span>
              ) : (
                <div class='create-input'>
                  <bk-input
                    v-model={this.createName}
                    maxlength={20}
                    show-word-limit
                  ></bk-input>
                  <i
                    class='ml5 bk-icon icon-check-1'
                    onClick={() => this.createGroup(true)}
                  ></i>
                  <i
                    class='ml5 icon-monitor icon-mc-close'
                    onClick={() => this.createGroup(false)}
                  ></i>
                </div>
              )}
              {/* 加进分组 */}
              {(() => {
                if (this.enableAutoGrouping) {
                  return this.isChecked ? (
                    <div class='add-group-content'>
                      <div class='count-msg'>
                        <i18n path='当前已选择{0}个视图'>
                          <span class='blod'>{this.curSelectCount}</span>
                        </i18n>
                        ，
                      </div>
                      <div class='add-group'>
                        <GroupSelectMultiple
                          list={this.groupSelectList}
                          value={this.groupSelect}
                          onChange={this.handleGroupSelectChange}
                          onToggle={this.handleGroupSelectToggle}
                        >
                          <span class='prepend-add-btn'>
                            {this.$t('加入分组')}
                            <span class='icon-monitor icon-mc-triangle-down'></span>
                          </span>
                        </GroupSelectMultiple>
                      </div>
                    </div>
                  ) : undefined;
                }
                return this.isChecked ? (
                  <div class='sort-setting-content'>
                    <bk-select
                      ext-cls='setting-content-select'
                      v-model={this.order}
                      searchable
                    >
                      {this.groupList.map(item => (
                        <bk-option
                          id={item.id}
                          name={item.title}
                          key={item.id}
                        ></bk-option>
                      ))}
                    </bk-select>
                    <bk-button
                      theme='primary'
                      outline
                      onClick={this.addGroupPanels}
                    >
                      {this.$t('加进分组')}
                    </bk-button>
                  </div>
                ) : undefined;
              })()}
              <SortPanel
                ref='sortPanel'
                is-not-dialog={true}
                is-dashboard-panel={true}
                enableAutoGrouping={this.enableAutoGrouping}
                v-model={this.showChartSort}
                groups-data={this.orderList}
                default-order-list={this.defaultOrderList}
                on-reset={this.handleReset}
                on-restore={this.handleRestore}
                on-save={this.handleSortChange}
                on-groups-change={this.groupsChange}
                on-auto-rule-change={this.handleAutoRuleChange}
                on-add-group-change={this.handleAddGroupChange}
                on-order-list-change={this.handleOrderListChange}
                on-checked-change={v => (this.isChecked = v)}
                on-checked-count={v => (this.curSelectCount = v)}
              ></SortPanel>
            </div>
          </div>
        ) : (
          <bk-exception
            class='set-var-no-data'
            type='empty'
            scene='part'
          />
        )}
      </div>
    );
  }
}
