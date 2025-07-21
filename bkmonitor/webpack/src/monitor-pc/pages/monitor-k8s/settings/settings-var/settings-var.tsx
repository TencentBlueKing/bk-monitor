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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getSceneViewDimensionValue, getSceneViewDimensions } from 'monitor-api/modules/scene_view';
import { deepClone, random } from 'monitor-common/utils/utils';
import DragItem from 'monitor-ui/monitor-draggable/drag-item';
import MonitorDraggable, { type IOnDrop } from 'monitor-ui/monitor-draggable/monitor-draggable';

import ConditionInput, {
  type IVarOption,
} from '../../../strategy-config/strategy-config-set-new/monitor-data/condition-input';
import { SETTINGS_POP_Z_INDEX, handleCheckVarWhere, handleReplaceWhereVar } from '../../utils';

import type { IBookMark, ICurVarItem, IOption, IViewOptions, IWhere, SettingsVarType } from '../../typings';

import './settings-var.scss';
/**
 * 变量设置弹窗
 */
@Component
export default class SettingsVar extends tsc<SettingsVarType.IProps, SettingsVarType.IEvents> {
  /** 页签数据 */
  @Prop({ default: () => [], type: Array }) bookMarkData: IBookMark[];
  /** 选中的页签 */
  @Prop({ default: '', type: String }) activeTab: string;
  /** 场景id */
  @Prop({ default: '', type: String }) sceneId: string;
  /** 场景类型 */
  @Prop({ default: '', type: String }) viewType: string;
  /** 请求页签数据接口 */
  @Prop({ default: () => {}, type: Function }) getTabDetail: (tabId: string) => void;
  /** 场景名称 */
  @Prop({ default: '', type: String }) title: string;
  /** 是否为自动添加状态 */
  @Prop({ default: false, type: Boolean }) needAutoAdd: boolean;
  /** 接口的筛选条件 */
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  /** 禁止动画 */
  disabledAnimation = true;

  /** 变量列表 */
  localVarList: ICurVarItem[] = [];
  /** 变量列表缓存 */
  localVarListCache: ICurVarItem[] = [];

  /** 变量设置 */
  localActiveTab = '';

  /** 维度列表 */
  groupByList = [];

  /** 维度可选值的缓存 */
  groupByVarListMap: Map<string, IOption[]> = new Map();

  /** 维度下拉的可选项，避免添加重复的变量 */
  get groupByListOptional() {
    const selectedSet: Set<string> = new Set();
    this.localVarList.forEach(item => {
      selectedSet.add(item.groupBy);
    });
    return this.groupByList.map(item => ({
      ...item,
      disabled: selectedSet.has(item.id),
    }));
  }

  /** 带有$开头的变量可选值 */
  get varOptionalMap(): Map<string, string[]> {
    const varMap = new Map();
    const filterDict = {
      ...this.viewOptions,
      ...this.viewOptions.variables,
    };
    Object.entries(filterDict).forEach(item => {
      const [key, value] = item;
      const list = Array.isArray(value) ? value : value ? [value] : [];
      varMap.set(key, list);
    });
    return varMap;
  }

  /** 当前页签配置是否存在差异 */
  get localVarListIsDiff(): boolean {
    return this.localVarList.some((item, index) => {
      const cacheItem = this.localVarListCache[index];
      if (cacheItem) {
        return (
          JSON.stringify(cacheItem.groupBy) !== JSON.stringify(item.groupBy) ||
          JSON.stringify(cacheItem.where) !== JSON.stringify(item.where)
        );
      }
      return true;
    });
  }

  created() {
    this.localActiveTab = this.activeTab;
    this.getSceneViewGroupBy();
  }

  @Watch('bookMarkData', { immediate: true, deep: true })
  bookMarkDataChange(bookMark: IBookMark[]) {
    if (bookMark.length) {
      this.$nextTick(() => {
        this.initData(this.localActiveTab);
        this.internalVarsFilter();
      });
    }
  }

  @Watch('groupByList')
  groupByListChange() {
    this.handleUpdateLocalVarListAlias();
  }

  async initData(id: string) {
    if (!id) return;
    await this.handleUpdateLocalVarList(id);
    this.updateLocalVarListCache();
  }

  /**
   * @description: 切换页签
   * @param {string} tab
   */
  async handleChangeTab(tab: string) {
    this.localActiveTab = tab;
    await this.getTabDetail(tab);
    this.handleUpdateLocalVarList(tab);
    this.updateLocalVarListCache();
  }

  /**
   * @description: 更新localVarList
   * @param {string} tab
   */
  async handleUpdateLocalVarList(tab: string = this.localActiveTab) {
    const curPageData = this.bookMarkData.find(item => item.id === tab);
    this.localVarList = [];
    await this.$nextTick();
    this.localVarList = curPageData.variables
      .filter(item => !item?.options?.variables?.internal)
      .map(item => {
        const { data } = item.targets[0];
        const localVarItem = {
          key: random(8),
          alias: '',
          loading: false,
          groupBy: data.field,
          where: data.where,
          optionalValue: [],
        };
        return localVarItem;
      });
    this.handleGetVarOption();
    this.handleUpdateLocalVarListAlias();
  }

  /**
   * @description: 获取变量的可选值
   */
  handleGetVarOption(): Promise<any[]> {
    return Promise.all(
      this.localVarList.map(async item => {
        item.loading = true;
        const options = await this.getGroupByOptionalValueList(item.groupBy, item.where).finally(
          () => (item.loading = false)
        );
        item.optionalValue = options;
      })
    );
  }

  /**
   * @description: 更新维度的别名
   */
  handleUpdateLocalVarListAlias() {
    this.localVarList.forEach(item => {
      const curGroupBy = this.groupByList.find(set => item.groupBy === set.id);
      curGroupBy && (item.alias = curGroupBy.name);
    });
  }

  /**
   * @description: 获取场景视图可用维度
   */
  getSceneViewGroupBy() {
    const params = {
      scene_id: this.sceneId,
      type: this.viewType,
      id: this.activeTab,
    };
    getSceneViewDimensions(params).then(res => {
      this.groupByList = res;
      this.internalVarsFilter();
      setTimeout(() => {
        if (this.needAutoAdd) {
          this.$nextTick(() => {
            this.handleAddVar();
          });
        }
      }, 300);
    });
  }

  /* 内置变量不可新增 */
  internalVarsFilter() {
    if (!!this.bookMarkData.length && !!this.groupByList.length) {
      const curPageData = this.bookMarkData.find(item => item.id === this.localActiveTab);
      const internalVars =
        curPageData?.variables
          .filter(item => !!item?.options?.variables?.internal)
          .map(item => {
            const { data, fields } = item.targets[0];
            return data.field || fields.id;
          }) || [];
      this.groupByList = this.groupByList.filter(item => !internalVars.includes(item.id));
    }
  }

  /**
   * @description: 变量排序
   * @param {IOnDrop} 顺序变更索引
   */
  handleDrop({ fromIndex, toIndex }: IOnDrop) {
    if (fromIndex === toIndex) return;
    const temp = this.localVarList[fromIndex];
    this.localVarList.splice(fromIndex, 1);
    this.localVarList.splice(toIndex, 0, temp);
    setTimeout(() => {
      this.disabledAnimation = true;
    }, 500);
  }

  /** 拖拽开始时 */
  handleDragstrart() {
    this.disabledAnimation = false;
  }

  /** 新建一条变量 */
  async handleAddVar() {
    const selectedList = this.localVarList.map(item => item.groupBy);
    const groupByItem = this.groupByList.find(item => !selectedList.includes(item.id));
    if (!groupByItem) return;
    const item = {
      key: random(8),
      loading: false,
      alias: groupByItem?.name || '',
      groupBy: groupByItem?.id || '',
      optionalValue: [],
      where: [],
    };
    this.localVarList.push(item);
    // this.updateAnimation();
    item.loading = true;
    const options = await this.getGroupByOptionalValueList(groupByItem?.id, []).finally(() => (item.loading = false));
    item.optionalValue = options || [];
  }

  /**
   * @description: 删除一条变量
   * @param {number} index 变量索引
   */
  handleDeleteVar(index: number) {
    this.$bkInfo({
      zIndex: SETTINGS_POP_Z_INDEX,
      title: this.$t('确认删除变量吗？'),
      confirmFn: () => {
        this.localVarList.splice(index, 1);
      },
    });
  }

  /**
   * @description: 切换维度
   * @param {number} index
   */
  async handleChangeGroupBy(index: number, groupBy: string) {
    const curVar = this.localVarList[index];
    const curGroupBy = this.groupByList.find(item => item.id === groupBy);
    curVar.groupBy = groupBy;
    curVar.alias = curGroupBy.name;
    curVar.loading = true;
    const options = await this.getGroupByOptionalValueList(groupBy, curVar.where).finally(
      () => (curVar.loading = false)
    );
    curVar.optionalValue = options;
  }

  /**
   * @description: 获取维度的可选值
   * @param {string} groupBy 维度
   * @param {SettingsVarType} where 条件
   * @return {*}
   */
  getGroupByOptionalValueList(groupBy = '', where: IWhere[] = []): Promise<IOption[]> {
    const cacheKey = `${groupBy}-${JSON.stringify(where)}`;
    let temp = deepClone(where);

    temp = handleReplaceWhereVar(temp, this.varOptionalMap);
    const params = {
      scene_id: this.sceneId,
      type: this.viewType,
      id: this.activeTab,
      field: groupBy,
      where: temp.filter(item => !!item.value.length),
    };
    if (this.groupByVarListMap.has(cacheKey)) return Promise.resolve(this.groupByVarListMap.get(cacheKey));
    return getSceneViewDimensionValue(params).then(data => {
      /** 缓存维度可选值 */
      this.groupByVarListMap.set(cacheKey, data);
      return data;
    });
  }

  /**
   * @description: 条件的值变更
   * @param {number} index 变量的索引
   * @param {SettingsVarType} condition 条件值
   */
  async handleConditionChange(index: number, condition: IWhere[]) {
    const curVar = this.localVarList[index];
    curVar.where = condition;
    const options = await this.getGroupByOptionalValueList(curVar.groupBy, condition);
    curVar.optionalValue = options;
  }

  /**
   * @description: 保存变量的修改前的状态 用于重置操作
   */
  updateLocalVarListCache() {
    this.localVarListCache = deepClone(this.localVarList);
  }

  /** 重置当前页签的变量操作 */
  async handleReset() {
    const temp = deepClone(this.localVarListCache);
    this.localVarList = [];
    await this.$nextTick();
    // this.handleUpdateLocalVarList();
    this.localVarList = temp.map(item => {
      const localVarItem = {
        key: random(8),
        alias: '',
        loading: false,
        groupBy: item.groupBy,
        where: item.where,
        optionalValue: [],
      };
      return localVarItem;
    });
    this.handleGetVarOption();
    this.handleUpdateLocalVarListAlias();
  }

  /**
   * @description: tab切换前置校验
   * @param {string} id
   */
  async handleChangeTabBefore(id: string) {
    /** 编辑后存在差异 */
    if (this.localVarListIsDiff) {
      const res = await new Promise((resolve, reject) => {
        this.$bkInfo({
          zIndex: SETTINGS_POP_Z_INDEX,
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => resolve(true),
          cancelFn: () => reject(false),
        });
      });
      return !!res;
    }
    return id;
  }

  /**
   * @description: 保存变量
   */
  @Emit('save')
  handleSave(): SettingsVarType.IEvents['onSave'] {
    this.updateLocalVarListCache();
    const curTab = this.bookMarkData.find(item => item.id === this.localActiveTab);
    return {
      id: this.localActiveTab,
      name: curTab.name,
      data: this.localVarList,
    };
  }
  /** 保存之前进行变量循环引用检查 */
  handleSaveValidate() {
    const whereObj = {};
    this.localVarList.forEach(item => {
      whereObj[item.groupBy] = deepClone(item.where);
    });
    const isClosedLoop = handleCheckVarWhere(whereObj);
    if (isClosedLoop) {
      this.$bkMessage({
        message: this.$t('变量不能存在循环引用关系'),
        theme: 'error',
        extCls: 'common-settings-z-index',
      });
      return;
    }
    this.handleSave();
  }

  /** 自定义条件组件的请求接口 */
  handleConditionCustomApi(field: string): Promise<IVarOption[]> {
    return this.getGroupByOptionalValueList(field, []) as Promise<IVarOption[]>;
  }

  render() {
    /** 页签选择tab */
    const tabItemTpl = (_, id) => {
      const item = this.bookMarkData.find(item => item.id === id);
      return (
        <span class={['tab-label-wrap', { active: id === this.localActiveTab }]}>
          <span class='tab-label-text'>{item.name}</span>
          {item.show_panel_count && <span class='tab-label-count'>{item.panel_count}</span>}
        </span>
      );
    };
    return (
      <div class='settings-var-wrap'>
        <div class='settings-var-title'>{this.title}</div>
        <div>
          {this.bookMarkData.length ? (
            <bk-tab
              class='tab-wrap'
              active={this.localActiveTab}
              before-toggle={this.handleChangeTabBefore}
              type='unborder-card'
              {...{ on: { 'update:active': this.handleChangeTab } }}
            >
              {this.bookMarkData.map(item => (
                <bk-tab-panel
                  key={item.id}
                  label={item.name}
                  name={item.id}
                  render-label={tabItemTpl}
                />
              ))}
            </bk-tab>
          ) : undefined}
        </div>
        <div class='set-var-main'>
          <bk-button
            class='set-var-add-btn'
            theme='primary'
            onClick={this.handleAddVar}
          >
            <i class='icon-monitor icon-mc-add' />
            <span class='set-var-btn-text'>{this.$t('新增')}</span>
          </bk-button>
          {this.localVarList.length ? (
            <MonitorDraggable
              class='set-var-item-list'
              onDragstart={this.handleDragstrart}
              onDrop={this.handleDrop}
            >
              <transition-group
                class='set-var-item-wrap'
                name={this.disabledAnimation ? '' : 'flip-list'}
                tag='div'
              >
                {this.localVarList.map((item, index) => (
                  <DragItem
                    key={item.key}
                    class='drag-item'
                    v-bkloading={{ isLoading: item.loading, zIndex: 2000 }}
                    index={index}
                  >
                    <div class='set-var-item'>
                      <div class='set-var-item-header drag-handle'>
                        <span class='set-var-item-header-left'>
                          <i class='icon-monitor icon-mc-tuozhuai' />
                          <span class='set-var-item-title'>{`$${item.groupBy}`}</span>
                          <bk-select
                            class='set-var-select'
                            behavior='simplicity'
                            placeholder={this.$t('选择')}
                            disabled
                          />
                        </span>
                        <i
                          class='icon-monitor icon-mc-delete-line'
                          onClick={() => this.handleDeleteVar(index)}
                        />
                      </div>
                      <div class='set-var-item-content'>
                        <div class='set-var-form-group'>
                          <div class='set-var-form-item'>
                            <div class='set-var-form-label'>{this.$t('维度')}</div>
                            <div class='set-var-form-value'>
                              <bk-select
                                class='set-var-group-by'
                                vModel={item.groupBy}
                                onSelected={val => this.handleChangeGroupBy(index, val)}
                              >
                                {this.groupByListOptional.map(opt => (
                                  <bk-option
                                    id={opt.id}
                                    disabled={opt.disabled}
                                    name={opt.id}
                                  />
                                ))}
                              </bk-select>
                            </div>
                          </div>
                          <div class='set-var-form-item'>
                            <div class='set-var-form-label'>{this.$t('别名')}</div>
                            <div class='set-var-form-value'>
                              <bk-input
                                class='set-var-alias'
                                value={item.alias}
                                disabled
                              />
                            </div>
                          </div>
                          <div class='set-var-form-item'>
                            <div class='set-var-form-label'>{this.$t('可选项')}</div>
                            <div class='set-var-form-value'>
                              <ul class='set-var-preview-val'>
                                {item.optionalValue.map((item, index) => {
                                  if (index >= 3) return undefined;
                                  return <li class='set-var-preview-item'>{item.name}</li>;
                                })}
                              </ul>
                            </div>
                          </div>
                        </div>
                        <div class='set-var-form-item'>
                          <div class='set-var-form-label'>{this.$t('条件')}</div>
                          <div class='set-var-form-value'>
                            <ConditionInput
                              class={['query-where-selector', { 'is-empty': false }]}
                              conditionList={item.where}
                              dimensionsList={this.groupByList}
                              getDataApi={this.handleConditionCustomApi}
                              on-change={val => this.handleConditionChange(index, val)}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </DragItem>
                ))}
              </transition-group>
            </MonitorDraggable>
          ) : (
            <bk-exception
              class='set-var-no-data'
              scene='part'
              type='empty'
            />
          )}
          <div class='set-var-btn-group'>
            <bk-button
              theme='primary'
              onClick={this.handleSaveValidate}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button onClick={this.handleReset}>{this.$t('重置')}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
