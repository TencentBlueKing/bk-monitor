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
import { TranslateResult } from 'vue-i18n';
import { Component, Inject, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SetMealDetail from '../../../fta-solutions/pages/setting/set-meal-detail/set-meal-detail';
import {
  createAssignGroup,
  listActionConfig,
  listAssignGroup,
  listAssignRule,
  listUserGroup,
  partialUpdateAssignGroup
} from '../../../monitor-api/modules/model';
import { Debounce, random } from '../../../monitor-common/utils';
import emptyImageSrc from '../../static/images/png/empty.png';
import AlarmGroupDetail from '../alarm-group/alarm-group-detail/alarm-group-detail';

import AlarmBatchEdit from './components/alarm-batch-edit';
import AlarmDispatchAction from './components/alarm-dispatch-action';
import AlarmUpdateContent from './components/alarm-update-content';
import CommonCondition from './components/common-condition-new';
import DebuggingResult from './components/debugging-result';
import { allKVOptions, GROUP_KEYS, TGroupKeys, TValueMap } from './typing/condition';
import { RuleGroupData } from './typing/index';

import './alarm-dispatch.scss';

@Component
export default class AlarmDispatch extends tsc<{}> {
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Ref() addForm: any;
  /* 规则组 */
  ruleGroups: RuleGroupData[] = [];
  cacheRuleGroups = [];
  /* 搜索 */
  search = '';
  /** 是否能查询，需要依赖 getAlarmGroupList 和 getAlarmDispatchGroupData两个函数都请求完成 */
  isSearch = false;
  /** 新建规则组弹窗 */
  visible = false;

  btnLoading = false;
  loading = false;
  groupLoading = false;

  filed = null;
  dataSource = null;
  popoverInstance = null;
  currentFiledElement = null;
  currentId = null;
  /** 查看调试效果 */
  isViewDebugEffect = false;
  emptyText = window.i18n.tc('查无数据');
  /** 优先级检验提示*/
  priorityErrorMsg: string | TranslateResult = '';
  /* 流程套餐*/
  processPackage = [];

  /** 告警组 */
  alarmGroupList = [];
  /** 表单 */
  formData: {
    name: string;
    priority: number;
  } = {
    name: '',
    priority: 100
  };

  /** 校验规则 */
  rules = {
    name: [
      {
        required: true,
        message: window.i18n.t('输入规则组名'),
        trigger: 'blur'
      },
      {
        validator: value =>
          !/(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(value),
        message: window.i18n.t('不能输入emoji表情'),
        trigger: 'blur'
      }
    ]
  };

  /** 告警组详情*/
  alarmGroupDetail: { id: number; show: boolean } = {
    id: 0,
    show: false
  };

  /** 套餐详情*/
  detailData = {
    id: 0,
    isShow: false
  };

  showDebug = false;

  /* kv 选项数据 */
  conditionProps: {
    keys: { id: string; name: string }[];
    valueMap: TValueMap;
    groupKeys: TGroupKeys;
  } = {
    keys: [],
    valueMap: new Map(),
    groupKeys: new Map()
  };
  conditiongsKey = random(8);

  /* 删除并调试数据 */
  delGroups = [];
  /** 展开全部分组 */
  isExpandAll = false;

  handleToConfig(id: number) {
    this.$router.push({
      name: 'alarm-dispatch-config',
      params: { id: String(id) }
    });
  }

  get polymerizeRuleGroups() {
    return this.cacheRuleGroups.map(item => ({
      ...item,
      user_groups: item.ruleData.reduce((result, item) => {
        item.user_groups.forEach(groups => {
          const { id, name } = this.alarmGroupList.find(alarm => alarm.id === groups);
          if (!result.map(g => g.id).includes(id)) {
            result.push({ id, name });
          }
        });
        return result;
      }, []),
      tag: item.ruleData.reduce((result, item) => {
        item.additional_tags.forEach(tag => {
          if (!result.includes()) {
            result.push(`${tag.key}:${tag.value}`);
          }
        });
        return result;
      }, [])
    }));
  }

  /** 优先级列表 */
  get priorityList() {
    return this.ruleGroups.map(item => item.priority);
  }

  created() {
    this.getRouteParams();
    this.getAlarmDispatchGroupData();
    this.getAlarmGroupList();
    this.getKVOptionsData();
    this.getProcessPackage();
    this.$store.commit('app/SET_NAV_ROUTE_LIST', [{ name: this.$t('route-告警分派'), id: '' }]);
  }

  getRouteParams() {
    const { groupName, group_id: groupId } = this.$route.query;
    if (groupName) {
      this.search = groupName as string;
    }
    if (groupId) {
      this.search = groupId as string;
    }
  }

  // 获取告警组数据
  async getAlarmGroupList() {
    const data = await listUserGroup().catch(() => []);
    this.alarmGroupList = data.map(item => ({
      id: item.id,
      name: item.name,
      receiver: item.users?.map(rec => rec.display_name) || []
    }));

    /** 能否查询需要依赖 getAlarmGroupList 和 getAlarmDispatchGroupData两个函数都请求完成 */
    if (this.isSearch && this.search) {
      this.handleSearch();
    }
    this.isSearch = true;
  }

  /**
   * 获取告警分派分组数据
   */
  async getAlarmDispatchGroupData() {
    this.loading = true;
    const list = await listAssignGroup().catch(() => {
      this.loading = false;
    });
    this.ruleGroups =
      list?.map(
        item =>
          new RuleGroupData({
            id: item.id,
            name: item.name,
            priority: item.priority,
            isExpan: true,
            ruleData: [],
            editAllowed: !!item?.edit_allowed
          })
      ) || [];
    this.loading = false;
    this.getAlarmAssignGroupsRules(list?.map(item => item.id));
  }

  /**
   *  获取规则集
   * @param ids 规则组
   */
  async getAlarmAssignGroupsRules(ids: number[] = []) {
    this.groupLoading = true;
    const list = await listAssignRule().catch(() => (this.groupLoading = false));
    const groupData = ids.reduce((result, item) => {
      result[item] = list.filter(rule => item === rule.assign_group_id);
      return result;
    }, {});
    this.groupLoading = false;
    this.ruleGroups.forEach(item => {
      if (!groupData[item.id].length) item.setExpan(false);
      item.setRuleData(groupData?.[item.id] || []);
    });
    this.cacheRuleGroups = this.ruleGroups;
    this.loading = false;
    if (this.isSearch && this.search) {
      this.handleSearch();
    }
    this.isSearch = true;
  }

  // 获取流程套餐
  async getProcessPackage() {
    const data = await listActionConfig().catch(() => []);
    this.processPackage = data.filter(item => item.plugin_type === 'itsm');
  }

  /** 新增分组 */
  handleAddAlarmDispatch() {
    this.visible = true;
    if (this.ruleGroups.length) {
      const { priority } = this.ruleGroups[0];
      const remainder = priority % 5;
      const targetPriority = remainder === 0 ? priority + 5 : priority + 10 - remainder;

      this.formData.priority = targetPriority >= 10000 ? undefined : targetPriority;
    } else {
      this.formData.priority = 100;
    }
  }

  /**
   * 删除规则组
   * @param id 规则组ID
   */
  handleDeleteGroup(e: Event, item: RuleGroupData) {
    e.stopPropagation();
    this.$bkInfo({
      type: 'warning',
      extCls: 'alarm-dispatch-bk-info',
      okText: window.i18n.t('调试并删除'),
      title: window.i18n.t('是否删除{name}?', { name: item.name }),
      subTitle: window.i18n.t('删除该组及组内规则会一起删除,且不可恢复'),
      confirmFn: async () => {
        this.delGroups = [item.id];
        this.showDebug = true;
        // await destroyAssignGroup(id);
        // this.$bkMessage({
        //   theme: 'success',
        //   message: this.$t('删除成功')
        // });
        // this.getAlarmDispatchGroupData();
      }
    });
  }

  /**
   *  新建规则组
   */
  async handleAddAlarmDispatchGroup() {
    const result = await this.addForm?.validate();

    if (!this.formData.priority) {
      this.priorityErrorMsg = window.i18n.t('输入优先级');
      return;
    }
    if (this.priorityList.includes(this.formData.priority)) return;

    if (result) {
      const data = await createAssignGroup({ ...this.formData });
      if (data) {
        this.visible = false;
        this.getAlarmDispatchGroupData();
        this.$bkMessage({
          theme: 'success',
          message: this.$t('创建成功')
        });
        this.formData = {
          name: '',
          priority: 0
        };
        setTimeout(() => {
          this.$router.push({
            name: 'alarm-dispatch-config',
            params: { id: String(data.id) }
          });
        });
      }
    }
  }

  /** 取消创建规则组 */
  handleCancelAlarmGroup() {
    this.visible = false;
    this.priorityErrorMsg = '';
    this.formData.name = '';
    this.addForm?.clearError();
  }

  /** *
   * 告警组信息编辑
   */
  handleAlarmGroupInfoEdit(e: Event, field: 'priority' | 'name', id: number, data) {
    e.stopPropagation();
    this.removePopoverInstance();
    this.currentFiledElement = e.target;
    this.filed = field;
    this.dataSource = data;
    this.currentId = id;

    this.popoverInstance = this.$bkPopover(e.target, {
      content: (this.$refs.alarmBatchEdit as any).$el,
      trigger: 'click',
      arrow: true,
      hideOnClick: 'toggle',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      onShow: () => {
        document.addEventListener('click', this.handleClickOutSide, false);
      },
      onHide: () => {
        document.removeEventListener('click', this.handleClickOutSide, false);
      }
    });
    this.popoverInstance?.show(100);
  }

  handleClickOutSide(e: Event) {
    const targetEl = e.target as HTMLBaseElement;
    if (targetEl === this.currentFiledElement) return;
    if (this.popoverInstance) {
      const result = this.popoverInstance.popper.contains(targetEl);
      if (!result) this.removePopoverInstance();
    }
  }

  renderEditAttribute(title: string, count: number, field: 'priority' | 'name', id: number) {
    return (
      <div class={field === 'priority' ? 'priority-wrap' : 'title-wrap'}>
        <span
          class='title'
          v-bk-overflow-tips
        >
          {title}
        </span>
        {field === 'name' && <span class='rule-count'>{`(${count})`}</span>}
        {field === 'priority' && <span class='count'>{count}</span>}
        <span
          class='icon-monitor icon-bianji'
          onClick={e => {
            this.handleAlarmGroupInfoEdit(e, field, id, field === 'priority' ? count : title);
          }}
        />
      </div>
    );
  }

  // 告警组详情
  handleSelcetAlarmGroup(id: number) {
    this.alarmGroupDetail.id = id;
    this.alarmGroupDetail.show = true;
  }

  handleShowDetail(id: number) {
    this.detailData.id = id;
    this.detailData.isShow = true;
  }

  /**
   *  优先级change
   * @param value
   * @returns
   */
  handlePriorityChange(value: string | number) {
    if (typeof value === 'string') {
      if (!value) return;
      if (isNaN(Number(value))) {
        this.formData.priority = 1;
        (this.$refs.priorityInput as any).curValue = 1;
      } else {
        if (Number(value) >= 10000) {
          this.formData.priority = 10000;
        } else if (Number(value) === 0) {
          this.formData.priority = 1;
        } else if (parseFloat(value) === parseInt(value)) {
          this.formData.priority = Number(value);
        } else {
          (this.$refs.priorityInput as any).curValue = Math.round(Number(value));
          this.formData.priority = Math.round(Number(value));
        }
      }
    } else {
      if (isNaN(value)) {
        this.formData.priority = 1;
        (this.$refs.priorityInput as any).curValue = 1;
      } else {
        this.formData.priority = value;
      }
    }
    if (this.priorityList.includes(this.formData.priority)) {
      this.priorityErrorMsg = window.i18n.t('注意: 优先级冲突');
    } else {
      this.priorityErrorMsg = '';
    }
  }

  /** 获取告警组名 */
  getAlarmGroupByID(id: number) {
    return this.alarmGroupList.find(item => item.id === id)?.name || id;
  }

  /* 清空pop */
  removePopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.currentFiledElement = null;
    this.filed = null;
    this.dataSource = null;
  }

  /** 修改组名、优先级 */
  async handleBatchEditSubmit(value: string | number) {
    await partialUpdateAssignGroup(this.currentId, { [this.filed]: value });
    this.$bkMessage({
      theme: 'success',
      message: this.$t('修改成功')
    });
    this.getAlarmDispatchGroupData();
  }

  /** 搜索 */
  @Debounce(200)
  handleSearch() {
    if (this.search) {
      const value = this.search.replace(/(^\s*)|(\s*$)/g, '');
      const reg = new RegExp(value, 'ig');
      const filterRuleGroupList = this.polymerizeRuleGroups
        .filter(
          item =>
            item.tag.includes(value) ||
            item.tag.map(key => key.split(':')[0]).includes(value) ||
            item.tag.map(value => value.split(':')[1]).includes(value) ||
            reg.test(item.user_groups.map(g => g.name)) ||
            String(item.id) === value
          // item.user_groups.map(g => String(g.id)).includes(value)
        )
        .map(item => item.id);
      this.ruleGroups = this.cacheRuleGroups.filter(item => filterRuleGroupList.includes(item.id));
      this.emptyText = window.i18n.tc('搜索结果为空');
    } else {
      this.emptyText = window.i18n.tc('查无数据');
      this.ruleGroups = this.cacheRuleGroups;
      const { groupName, groupId, ...arg } = this.$route.query;
      this.$router.replace({
        query: {
          ...arg
        }
      });
    }
  }

  handleShowChange(v: boolean) {
    this.showDebug = v;
    if (!v) this.isViewDebugEffect = false;
  }
  handleDebug() {
    this.delGroups = [];
    this.handleShowChange(true);
    this.isViewDebugEffect = true;
  }

  handleDelSucess() {
    this.delGroups = [];
    this.handleShowChange(false);
    this.getAlarmDispatchGroupData();
  }

  /* 匹配规则key对应的value值获取 */
  async getKVOptionsData() {
    allKVOptions(
      [this.$store.getters.bizId],
      (type: string, key: string, values: any) => {
        if (!!key) {
          (this.conditionProps[type] as Map<string, any>).set(key, values);
        } else {
          this.conditionProps[type] = values;
        }
      },
      () => {
        this.conditiongsKey = random(8);
      }
    );
  }

  handleEditGroup(id) {
    this.alarmGroupDetail.show = false;
    this.$router.push({
      name: 'alarm-group-edit',
      params: { id }
    });
  }

  /** 展开收起全部 */
  handleExpandAll() {
    this.isExpandAll = !this.isExpandAll;
    this.ruleGroups.forEach(item => item.setExpan(!this.isExpandAll));
  }

  render() {
    return (
      <div
        class='alarm-dispath-page'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='alarm-dispath-page-wrap'>
          <div class='wrap-header'>
            <bk-button
              icon='plus'
              theme='primary'
              class='mr10'
              onClick={this.handleAddAlarmDispatch}
            >
              {this.$t('新建')}
            </bk-button>
            <bk-button
              class='mr10'
              disabled={!this.ruleGroups.length}
              onClick={this.handleDebug}
            >
              {this.$t('调试')}
            </bk-button>
            <bk-button
              class='expand-up-btn'
              onClick={this.handleExpandAll}
            >
              <span class={['icon-monitor', this.isExpandAll ? 'icon-zhankai1' : 'icon-shouqi1']}></span>
              {this.$t(this.isExpandAll ? '展开所有分组' : '收起所有分组')}
            </bk-button>
            <bk-input
              class='search-input'
              placeholder={`ID/${this.$t('告警组名称')}`}
              right-icon='bk-icon icon-search'
              v-model={this.search}
              onInput={this.handleSearch}
            ></bk-input>
          </div>
          <div class='wrap-content'>
            {this.ruleGroups.length > 0 ? (
              this.ruleGroups.map((item, index) => (
                <div
                  class='expan-item'
                  key={index}
                >
                  <div
                    class='expan-item-header'
                    onClick={() => item.setExpan(!item.isExpan)}
                  >
                    <div class={['expan-status', { 'is-expan': item.isExpan }]}>
                      <i class='icon-monitor icon-mc-triangle-down'></i>
                    </div>
                    {this.renderEditAttribute(item.name, item.ruleData.length, 'name', item.id)}
                    {this.renderEditAttribute(`${this.$t('优先级')}:`, item.priority, 'priority', item.id)}
                    <div
                      class={['edit-btn-wrap', { 'edit-btn-disabled': !item.editAllowed }]}
                      v-bk-tooltips={{
                        placements: ['top'],
                        content: this.$t('内置的分派规则组不允许修改'),
                        disabled: item.editAllowed
                      }}
                      onClick={() => item.editAllowed && this.handleToConfig(item.id)}
                    >
                      <span class='icon-monitor icon-bianji'></span>
                      <span>{this.$t('配置规则')}</span>
                    </div>
                    <div
                      class={['del-btn-wrap', { 'del-btn-disabled': !item.editAllowed }]}
                      v-bk-tooltips={{
                        placements: ['top'],
                        content: this.$t('内置的分派规则组不允许修改'),
                        disabled: item.editAllowed
                      }}
                      onClick={e => {
                        item.editAllowed && this.handleDeleteGroup(e, item);
                      }}
                    >
                      <span class='icon-monitor icon-mc-delete-line'></span>
                    </div>
                  </div>
                  <div class={['expan-item-content', { 'is-expan': item.isExpan }]}>
                    <bk-table
                      v-bkloading={{ isLoading: this.groupLoading }}
                      data={item.ruleData}
                      stripe
                    >
                      <bk-table-column
                        label={this.$t('告警组')}
                        prop='user_groups'
                        min-width={100}
                        scopedSlots={{
                          default: ({ row }) => (
                            <div class='alarm-group-list'>
                              {row.user_groups.map(groupId => (
                                <bk-tag
                                  class='alarm-tag'
                                  v-bk-overflow-tips
                                  onClick={() => {
                                    this.handleSelcetAlarmGroup(groupId);
                                  }}
                                >
                                  {this.getAlarmGroupByID(groupId)}
                                </bk-tag>
                              ))}
                            </div>
                          )
                        }}
                      ></bk-table-column>
                      <bk-table-column
                        label={this.$t('匹配规则')}
                        prop='rule'
                        min-width={400}
                        scopedSlots={{
                          default: ({ row }) =>
                            !!row.conditions?.length ? (
                              <CommonCondition
                                class='rule-wrap'
                                key={this.conditiongsKey}
                                value={row.conditions}
                                keyList={this.conditionProps.keys}
                                groupKey={GROUP_KEYS}
                                groupKeys={this.conditionProps.groupKeys}
                                valueMap={this.conditionProps.valueMap}
                                readonly={true}
                              ></CommonCondition>
                            ) : (
                              '--'
                            )
                        }}
                      ></bk-table-column>
                      <bk-table-column
                        label={this.$t('分派动作')}
                        prop='action'
                        min-width={400}
                        scopedSlots={{
                          default: ({ row }) => (
                            <AlarmDispatchAction
                              alarmGroupList={this.alarmGroupList}
                              showAlarmGroup={this.handleSelcetAlarmGroup}
                              showDetail={this.handleShowDetail}
                              detailData={this.detailData}
                              processPackage={this.processPackage}
                              actions={row.actions}
                              userType={row.user_type}
                            />
                          )
                        }}
                      ></bk-table-column>
                      <bk-table-column
                        label={this.$t('修改告警内容')}
                        min-width={300}
                        prop='content'
                        scopedSlots={{
                          default: ({ row }) => (
                            <AlarmUpdateContent
                              severity={row.alert_severity}
                              tag={row.additional_tags}
                            />
                          )
                        }}
                      ></bk-table-column>
                      <bk-table-column
                        label={this.$t('状态')}
                        prop='is_enabled'
                        width={160}
                        scopedSlots={{
                          default: ({ row }) => (
                            <bk-tag class={['tag-status', row.is_enabled ? 'start' : 'stop']}>
                              {this.$t(row.is_enabled ? '启用' : '停用')}
                            </bk-tag>
                          )
                        }}
                      ></bk-table-column>
                      <div
                        slot='empty'
                        class='alarm-group-empty'
                      >
                        <div>
                          <img
                            src={emptyImageSrc}
                            alt=''
                          />
                        </div>
                        <div class='mb15 empty-text'>{this.$t('当前组暂无规则，需去配置新规则')}</div>
                        <div
                          class='empty-rule-config mt15'
                          onClick={() => this.handleToConfig(item.id)}
                        >
                          {this.$t('配置规则')}
                        </div>
                      </div>
                    </bk-table>
                  </div>
                </div>
              ))
            ) : (
              <div class='empty-dispatch-content'>
                <img
                  src={emptyImageSrc}
                  alt=''
                />
                <span class='empty-dispatch-text'>{this.emptyText}</span>
              </div>
            )}
          </div>
        </div>
        <div style='display: none'>
          <AlarmBatchEdit
            ref='alarmBatchEdit'
            filed={this.filed}
            dataSource={this.dataSource}
            isListPage={true}
            priorityList={this.priorityList}
            onSubmit={this.handleBatchEditSubmit}
            close={this.removePopoverInstance}
          />
        </div>
        <bk-dialog
          value={this.visible}
          header-position='left'
          confirmFn={this.handleAddAlarmDispatchGroup}
          onCancel={this.handleCancelAlarmGroup}
          title={this.$t('新建规则组')}
        >
          <bk-form
            form-type='vertical'
            ref='addForm'
            {...{
              props: {
                model: this.formData,
                rules: this.rules
              }
            }}
          >
            <bk-form-item
              label={this.$t('规则组名')}
              required
              property='name'
              error-display-type='normal'
            >
              <bk-input v-model={this.formData.name} />
            </bk-form-item>
            <bk-form-item
              label={this.$t('优先级')}
              property='priority'
              required
              error-display-type='normal'
            >
              <bk-input
                ref='priorityInput'
                type='number'
                max={10000}
                min={1}
                onInput={this.handlePriorityChange}
                value={this.formData.priority}
              />
              <span style={{ color: this.priorityErrorMsg ? '#ea3636' : '#979BA5' }}>
                {this.priorityErrorMsg ? this.priorityErrorMsg : this.$t('数值越高优先级越高,最大值为10000')}
              </span>
            </bk-form-item>
          </bk-form>
        </bk-dialog>
        <AlarmGroupDetail
          id={this.alarmGroupDetail.id as any}
          v-model={this.alarmGroupDetail.show}
          onEditGroup={this.handleEditGroup}
          customEdit
        />
        <SetMealDetail
          isShow={this.detailData.isShow}
          id={this.detailData.id}
          width={540}
          onShowChange={v => (this.detailData.isShow = v)}
        ></SetMealDetail>
        {/* 调试结果 */}
        {this.showDebug && (
          <DebuggingResult
            isShow={this.showDebug}
            isViewDebugEffect={this.isViewDebugEffect}
            conditionProps={this.conditionProps}
            alarmGroupList={this.alarmGroupList}
            ruleGroupsData={[]}
            excludeGroups={this.delGroups}
            onShowChange={this.handleShowChange}
            onDelSuccess={this.handleDelSucess}
          />
        )}
      </div>
    );
  }
}
