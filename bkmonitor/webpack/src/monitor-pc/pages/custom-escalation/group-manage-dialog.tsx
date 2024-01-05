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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { modifyCustomTsGroupingRuleList } from '../../../monitor-api/modules/custom_report';
import { Debounce, random } from '../../../monitor-common/utils/utils';

import MoreList from './more-list';

import './group-manage-dialog.scss';

/* 匹配规则通过正则匹配 */
export const matchRuleFn = (str: string, matchStr: string) => {
  let isMatch = false;
  try {
    const regex = new RegExp(matchStr);
    isMatch = regex.test(str);
  } catch (err) {
    isMatch = false;
  }
  return isMatch;
};

interface IGroup {
  name: string;
  matchRules: string[];
  manualList: string[];
}

interface IGroupItem {
  name: string;
  manualList: string[];
  matchRules: string[];
  isEditName: boolean;
  key: string;
  ruleCount?: number;
  isManualActive?: boolean;
}
interface IMetricItem {
  name: string;
  description: string;
}

interface IProps {
  show?: boolean;
  metricList?: IMetricItem[];
  groups?: IGroup[];
  id: number | string;
}
interface IEvents {
  onShow?: boolean;
}

interface IPreviewListItem {
  type: 'manual' | 'rule';
  name: string;
  list: IMetricItem[];
}

@Component
export default class GroupManageDialog extends tsc<IProps, IEvents> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ type: [String, Number], default: '' }) id: number | string;
  @Prop({ default: () => [], type: Array }) metricList: IMetricItem[];
  @Prop({ type: Array, default: () => [] }) groups: IGroup[];
  @Ref('manualDropdown') manualDropdownRef: HTMLDivElement;
  @Ref('previewListWrap') previewListWrapRef: HTMLDivElement;
  @Ref('checkInputForm') checkInputFormRef: any;
  /* 分组列表 */
  groupList: IGroupItem[] = [];
  /* 编辑组名 */
  tempName = '';
  /* 手动添加指标列表数据 */
  manualCheck: {
    search: string;
    list: { description: string; name: string; checked: boolean }[];
    isSelectAll: boolean;
    searchList: { description: string; name: string; checked: boolean }[];
    index: number;
  } = {
    search: '',
    list: [],
    isSelectAll: false,
    searchList: [],
    index: 0
  };
  verifyData = {
    tempName: ''
  };
  editIndex = -1;
  popoverInstance = null;
  /* 新建分组 */
  addName = '';
  isAdd = false;
  /* 预览列表 */
  addErrMsg = '';
  /* 当前预览的组 */
  groupActive = '';
  /* 预览列表的展开 */
  previewActive = [];
  /* 当前预览数据 */
  previewList: IPreviewListItem[] = [];
  /* 编辑组名校验 */
  groupNameErrMsg = '';
  /* 每条匹配规则包含的指标 */
  matchMetricsMap = new Map();
  /* 每个组包含的预览数据 */
  allGroupPreviewMap = new Map();
  /* 指标map */
  metricsMap = new Map();
  loading = false;
  /* 当前匹配规则匹配的指标（用于标识手动选择列表的匹配项） */
  ruleOfMetrics = new Map();

  public rules = {
    tempName: [
      {
        validator: this.checkGroupName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur'
      },
      {
        validator: this.checkGroupRepeat,
        message: window.i18n.t('输入中文、英文、数字、下划线类型的字符'),
        trigger: 'blur'
      },
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur'
      }
    ]
  };

  @Watch('show')
  async handleShow(v: boolean) {
    if (v) {
      this.groupList = this.groups.map(item => ({
        name: item.name,
        manualList: item.manualList,
        matchRules: item.matchRules,
        key: random(8),
        isEditName: false,
        ruleCount: item.manualList.length,
        isManualActive: false
      }));
      this.metricList.forEach(item => {
        this.metricsMap.set(item.name, item);
      });
      this.mapSetMetrics();
      if (this.groupList.length) {
        this.handleClickGroup(0);
      }
    }
  }

  async handleSubmit() {
    const params = {
      time_series_group_id: this.id,
      group_list: this.groupList.map(item => ({
        name: item.name,
        manual_list: item.manualList,
        auto_rules: item.matchRules
      }))
    };
    this.loading = true;
    const res = await modifyCustomTsGroupingRuleList(params).catch(() => false);
    this.loading = false;
    if (res) {
      this.$emit('change', this.groupList);
      this.$emit('show', false);
    }
  }
  handleCancel() {
    this.$emit('show', false);
  }

  /* 点击编辑组名 */
  handleClickEditName(index: number) {
    this.isAdd = false;
    this.groupList.forEach(item => (item.isEditName = false));
    this.verifyData.tempName = this.groupList[index].name;
    this.groupList[index].isEditName = true;
  }
  /* 编辑组名输入框失焦 */
  handleEditBlur() {
    // if (!this.tempName) return;
    // const oldName = this.groupList[index].name;
    // const groupNames = this.groupList.map(item => item.name).filter(name => name !== oldName);
    // if (groupNames.includes(this.tempName)) {
    //   this.groupNameErrMsg = this.$tc('注意: 名字冲突');
    //   return;
    // }
    // if (!(/^[\u4E00-\u9FA5A-Za-z0-9_-]+$/g.test(this.tempName))) {
    //   this.groupNameErrMsg = this.$tc('输入中文、英文、数字、下划线类型的字符');
    //   return;
    // }
  }
  checkGroupName() {
    const oldName = this.groupList[this.editIndex].name;
    const groupNames = this.groupList.map(item => item.name).filter(name => name !== oldName);
    return !groupNames.includes(this.verifyData.tempName);
  }
  checkGroupRepeat() {
    return /^[\u4E00-\u9FA5A-Za-z0-9_-]+$/g.test(this.verifyData.tempName);
  }
  /* 点击手动添加 */
  handleClickAdd(event: Event, index: number) {
    this.manualDropRemovePop();
    this.groupList[index].isManualActive = true;
    const { manualList } = this.groupList[index];
    this.manualCheck.index = index;
    this.manualCheck.list = this.metricList.map(item => ({
      ...item,
      checked: manualList.includes(item.name)
    }));
    this.manualCheck.searchList = [...this.manualCheck.list];
    const target = (event.target as any).parentElement.children[0];
    this.popoverInstance = this.$bkPopover(target, {
      content: this.manualDropdownRef,
      boundary: 'window',
      arrow: false,
      placement: 'bottom-start',
      theme: 'light custom-metric-group-manage-checkbox-list-dropdown-light',
      trigger: 'click',
      distance: 0,
      interactive: true,
      onHide: () => {
        this.groupList[this.manualCheck.index].isManualActive = false;
      }
    });
    this.popoverInstance?.show?.();
  }
  manualDropRemovePop() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }
  /* 点击新建分组 */
  handleClickAddGroup() {
    this.addName = '';
    this.isAdd = true;
    this.groupList.forEach(item => (item.isEditName = false));
  }
  /* 确认新增组 */
  handleClickAddConfirm() {
    this.addErrMsg = '';
    const groupNames = this.groupList.map(item => item.name);
    if (groupNames.includes(this.addName)) {
      this.addErrMsg = this.$tc('注意: 名字冲突');
      return;
    }
    if (!/^[\u4E00-\u9FA5A-Za-z0-9_-]+$/g.test(this.addName)) {
      this.addErrMsg = this.$tc('输入中文、英文、数字、下划线类型的字符');
      return;
    }
    this.isAdd = false;
    this.groupList.unshift({
      name: this.addName,
      manualList: [],
      matchRules: [],
      key: random(8),
      isEditName: false,
      ruleCount: 0,
      isManualActive: false
    });
  }
  handleClickAddCancel() {
    this.addErrMsg = '';
    this.isAdd = false;
  }

  handleAddNameChange() {
    this.addErrMsg = '';
  }

  /* 手动列表搜索 */
  @Debounce(300)
  handleManualSearch(value: string) {
    this.manualCheck.searchList = this.manualCheck.list.filter(item => {
      if (!value) return true;
      const name = item.name.toLowerCase();
      const description = item.description.toLowerCase();
      const search = value.toLowerCase();
      return name.indexOf(search) > -1 || description.indexOf(search) > -1;
    });
  }

  /* 关键字高亮 */
  highLightContent(search: string, content: string) {
    if (!search) {
      return content;
    }
    /* 搜索不区分大小写 */
    const searchValue = search.trim().toLowerCase();
    const contentValue = content.toLowerCase();
    /* 获取分隔下标 */
    const indexRanges: number[][] = [];
    const contentValueArr = contentValue.split(searchValue);
    let tempIndex = 0;
    contentValueArr.forEach(item => {
      const temp = tempIndex + item.length;
      indexRanges.push([tempIndex, temp]);
      tempIndex = temp + search.length;
    });
    return indexRanges.map((range: number[], index: number) => {
      if (index !== indexRanges.length - 1) {
        return [
          <span>{content.slice(range[0], range[1])}</span>,
          <span class='light'>{content.slice(range[1], indexRanges[index + 1][0])}</span>
        ];
      }
      return <span>{content.slice(range[0], range[1])}</span>;
    });
  }
  /* 匹配规则更新 */
  handleMatchRulesChange(index, matchRules: string[]) {
    this.groupList[index].matchRules = matchRules;
    this.mapSetMetrics();
    this.getPreviewList(this.groupActive);
  }
  /** 更新组名字 */
  handleEditNameChange(index: number) {
    this.checkInputFormRef.validate(() => {
      this.groupList[index].name = this.verifyData.tempName;
      this.groupList[index].isEditName = false;
    });
  }
  /* 匹配规则匹配的指标列表 */
  mapSetMetrics() {
    this.groupList.forEach(item => {
      const previewList = [];
      const manualPreviewList = [];
      item.manualList.forEach(name => {
        const metricInfo = this.metricsMap.get(name);
        if (metricInfo) manualPreviewList.push(metricInfo);
      });
      const matchPreviewList = [];
      let allRuleOfmetrics = [];
      item.matchRules.forEach(rule => {
        const metricList = this.metricList.filter(m => matchRuleFn(m.name, rule));
        this.matchMetricsMap.set(rule, metricList);
        matchPreviewList.push({
          type: 'rule',
          name: rule,
          list: metricList
        });
        allRuleOfmetrics = allRuleOfmetrics.concat(metricList);
      });
      previewList.push({
        type: 'manual',
        name: this.$tc('手动'),
        list: manualPreviewList
      });
      previewList.push(...matchPreviewList);
      // eslint-disable-next-line no-param-reassign
      item.ruleCount = [...new Set(allRuleOfmetrics)].length;
      this.allGroupPreviewMap.set(item.name, previewList);
    });
  }
  /* 获取预览数据 */
  getPreviewList(active) {
    this.previewList = this.allGroupPreviewMap.get(active) || [];
    this.previewActive = this.previewList.map(item => item.name);
    const ruleOfMetrics = new Map();
    this.previewList.forEach(item => {
      if (item.type === 'rule') {
        item.list.forEach(l => {
          ruleOfMetrics.set(l.name, item.name);
        });
      }
    });
    this.ruleOfMetrics = ruleOfMetrics;
  }
  /* 点击组 */
  handleClickGroup(index: number) {
    this.groupActive = this.groupList[index].name;
    this.getPreviewList(this.groupActive);
  }
  /* 点击全选 */
  handleSelectAll(isAll) {
    this.manualCheck.isSelectAll = isAll;
    const activeListMap = new Map();
    this.manualCheck.searchList.forEach(item => {
      item.checked = isAll;
      activeListMap.set(item.name, isAll);
    });
    this.manualCheck.list.forEach(item => {
      if (activeListMap.has(item.name)) {
        item.checked = activeListMap.get(item.name);
      }
    });
  }
  /* 点击加入分组 */
  handleManualAdd() {
    const activeList = this.manualCheck.list.filter(item => item.checked).map(item => item.name);
    this.groupList[this.manualCheck.index].manualList = activeList;
    this.mapSetMetrics();
    this.getPreviewList(this.groupActive);
  }
  /* 选中手动列表选项 */
  handleManualCheck(checked: boolean, index: number) {
    this.manualCheck.searchList[index].checked = checked;
    const activeName = this.manualCheck.searchList[index].name;
    this.manualCheck.list.forEach(item => {
      if (item.name === activeName) {
        item.checked = checked;
      }
    });
  }
  handleMatchRuleActive(active: string) {
    setTimeout(() => {
      const index = this.previewList.findIndex(item => item.name === active);
      const element = this.previewListWrapRef?.querySelector?.(`.item-head--${index}`);
      element?.scrollIntoView?.();
    }, 100);
  }
  /* 手动预览部分删除操作 */
  handleDeleteManual(name: string) {
    const setItem = this.groupList.find(item => item.name === this.groupActive);
    const deleteIndex = setItem.manualList.findIndex(item => item === name);
    if (deleteIndex > -1) {
      setItem.manualList.splice(deleteIndex, 1);
    }
    this.mapSetMetrics();
    this.getPreviewList(this.groupActive);
  }
  /* 删除一个组 */
  handleDeleteGroup(index: number) {
    this.groupList.splice(index, 1);
    this.metricsMap = new Map();
    this.matchMetricsMap = new Map();
    this.metricList.forEach(item => {
      this.metricsMap.set(item.name, item);
    });
    this.mapSetMetrics();
  }

  render() {
    return (
      <bk-dialog
        extCls={'custom-metric-group-manage-dialog'}
        value={this.show}
        width={960}
        mask-close={true}
        header-position='left'
        title={this.$t('分组管理')}
        on-cancel={() => this.$emit('show', false)}
      >
        <div
          class='group-manage-content'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='content-left'>
            <div class='header'>
              <span class='title'>{this.$t('分组列表')}</span>
              <span
                class='group-add'
                onClick={this.handleClickAddGroup}
              >
                <span class='icon-monitor icon-mc-plus-fill'></span>
                <span>{this.$t('新建分组')}</span>
              </span>
            </div>
            {this.isAdd && [
              <div class='add-input-wrap'>
                <bk-input
                  class='add-input'
                  placeholder={this.$t('输入分组名称')}
                  v-model={this.addName}
                  onChange={this.handleAddNameChange}
                  onEnter={this.handleClickAddConfirm}
                ></bk-input>
                <bk-button
                  class='confirm'
                  text
                  theme='primary'
                  onClick={this.handleClickAddConfirm}
                >
                  {this.$t('确定')}
                </bk-button>
                <bk-button
                  class='cancel'
                  text
                  theme='primary'
                  onClick={this.handleClickAddCancel}
                >
                  {this.$t('取消')}
                </bk-button>
              </div>,
              !!this.addErrMsg ? <div class='add-err-msg'>{this.addErrMsg}</div> : undefined
            ]}
            <div class={['group-list', { 'add-active': this.isAdd }]}>
              {this.groupList.map((item, index) => (
                <div
                  key={index}
                  class={['group-item', { edit: item.isEditName, 'preivew-active': this.groupActive === item.name }]}
                  onClick={() => this.handleClickGroup(index)}
                >
                  <span class='name-wrap'>
                    <span
                      class='name'
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </span>
                    <span
                      class='icon-monitor icon-bianji'
                      onClick={() => this.handleClickEditName(index)}
                    ></span>
                  </span>
                  <span class='manua-wrap'>
                    <span class='manua-count'>
                      {this.$t('手动')}({item.manualList.length})
                    </span>
                    <span
                      class={['icon-monitor icon-mc-add', { active: item.isManualActive }]}
                      onClick={() => this.handleClickAdd(event, index)}
                    ></span>
                  </span>
                  <span class='match-rule'>
                    <span class='title'>
                      {this.$t('匹配规则')}
                      {`(${item.ruleCount})`}
                    </span>
                    <span class='match-rule-content'>
                      <MoreList
                        list={item.matchRules}
                        onChange={value => this.handleMatchRulesChange(index, value)}
                        onActive={this.handleMatchRuleActive as any}
                      ></MoreList>
                    </span>
                  </span>
                  <span
                    class='icon-monitor icon-mc-delete-line'
                    onClick={() => this.handleDeleteGroup(index)}
                  ></span>
                  {item.isEditName && (
                    <div class='input-wrap'>
                      {/* <bk-input
                    class="temp-input"
                    v-model={this.tempName}
                    onChange={this.handleEditNameChange}
                    onBlur={() => this.handleEditBlur(index)}></bk-input>
                  <span class="back-wrap" onClick={() => this.handleEditBlur(index)}>
                    <span class="err-msg" style={!!this.groupNameErrMsg ? '' :
                    'display:none;'}>{this.groupNameErrMsg}</span>
                  </span>
                  <span class="icon-monitor icon-mc-delete-line"
                  onClick={() => this.handleDeleteGroup(index)}></span> */}
                      <div class='add-input-wrap edit-input-wrap'>
                        <bk-form
                          labelWidth={0}
                          style={{ width: '100%' }}
                          ref='checkInputForm'
                          {...{
                            props: {
                              model: this.verifyData,
                              rules: this.rules
                            }
                          }}
                        >
                          <bk-form-item property='tempName'>
                            <bk-input
                              class='add-input'
                              placeholder={this.$t('输入分组名称')}
                              vModel={this.verifyData.tempName}
                              onFocus={() => (this.editIndex = index)}
                              onEnter={() => this.handleEditNameChange(index)}
                            ></bk-input>
                          </bk-form-item>
                        </bk-form>
                        <bk-button
                          class='confirm'
                          text
                          theme='primary'
                          onClick={() => this.handleEditNameChange(index)}
                        >
                          {this.$t('确定')}
                        </bk-button>
                        <bk-button
                          class='cancel'
                          text
                          theme='primary'
                          onClick={() => (item.isEditName = false)}
                        >
                          {this.$t('取消')}
                        </bk-button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          <div class='content-right'>
            <div class='preview-title'>{this.groupActive ? `${this.groupActive}-${this.$t('预览')}` : ''}</div>
            <div
              class='preview-list-wrap'
              ref='previewListWrap'
            >
              <bk-collapse
                v-model={this.previewActive}
                class='preview-collapse'
              >
                {this.previewList.map((item, index) => (
                  <bk-collapse-item
                    name={item.name}
                    key={item.name}
                    hide-arrow
                  >
                    <div class={['item-head', `item-head--${index}`]}>
                      <span class='icon-monitor icon-arrow-down'></span>
                      {item.type === 'manual' ? (
                        <span class='name'>
                          {`【${this.$t('手动')}】- `}
                          <i18n path='共 {0} 个'>
                            <span class='num'>{item.list.length}</span>
                          </i18n>
                        </span>
                      ) : (
                        <span class='name'>
                          {`【${this.$t('匹配规则')} : ${item.name}】- `}
                          <i18n path='共 {0} 个'>
                            <span class='num'>{item.list.length}</span>
                          </i18n>
                        </span>
                      )}
                    </div>
                    <div
                      slot='content'
                      class='item-list-wrap'
                    >
                      <ul class='item-list'>
                        {item.list.map((row, rowIndex) => (
                          <li
                            class='item'
                            key={rowIndex}
                          >
                            <span
                              class='item-name'
                              v-bk-tooltips={{
                                placements: ['right'],
                                content: !!row.description ? `${row.name}  (${row.description})` : row.name,
                                boundary: 'window',
                                allowHTML: false
                              }}
                            >
                              <span class='name'>{row.name}</span>
                              {!!row.description && <span class='description'>({row.description})</span>}
                            </span>
                            {item.type === 'manual' && (
                              <span
                                class='icon-monitor icon-mc-delete-line'
                                onClick={() => this.handleDeleteManual(row.name)}
                              ></span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </bk-collapse-item>
                ))}
              </bk-collapse>
            </div>
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            style={{ 'margin-right': '8px' }}
            onClick={this.handleSubmit}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
        </div>
        <div style='display: none'>
          <div
            class='custom-metric-group-manage-checkbox-list-dropdown'
            ref='manualDropdown'
          >
            <div>
              <bk-input
                v-model={this.manualCheck.search}
                placeholder={this.$t('输入关键字')}
                left-icon={'bk-icon icon-search'}
                behavior={'simplicity'}
                onChange={this.handleManualSearch}
              ></bk-input>
            </div>
            <div class='check-list-warp'>
              <div class='list-item'>
                <bk-checkbox
                  value={this.manualCheck.isSelectAll}
                  onChange={this.handleSelectAll}
                >
                  {this.$t('全选')}
                </bk-checkbox>
              </div>
              {this.manualCheck.searchList.map((item, index) => (
                <div
                  class={['list-item', { auto: this.ruleOfMetrics.has(item.name) }]}
                  v-bk-tooltips={{
                    content: this.$t('由匹配规则{0}生成', [this.ruleOfMetrics.get(item.name)]),
                    placement: 'right',
                    boundary: 'window',
                    disabled: !this.ruleOfMetrics.has(item.name),
                    allowHTML: false
                  }}
                  key={`${item.name}-${index}`}
                >
                  <bk-checkbox
                    value={item.checked}
                    key={item.name}
                    onChange={v => this.handleManualCheck(v, index)}
                  >
                    <span
                      class='list-item-label'
                      v-bk-tooltips={{
                        placements: ['right'],
                        content: !!item.description ? `${item.name}  (${item.description})` : item.name,
                        boundary: 'window',
                        allowHTML: false
                      }}
                    >
                      <span class='title'>{this.highLightContent(this.manualCheck.search, item.name)}</span>
                      {!!item.description && (
                        <span class='subtitle'>
                          ({this.highLightContent(this.manualCheck.search, item.description)})
                        </span>
                      )}
                    </span>
                  </bk-checkbox>
                </div>
              ))}
            </div>
            {!!this.manualCheck.searchList.length && (
              <div
                class='add-btn'
                onClick={this.handleManualAdd}
              >
                {this.$t('加入分组')}
              </div>
            )}
          </div>
        </div>
      </bk-dialog>
    );
  }
}
