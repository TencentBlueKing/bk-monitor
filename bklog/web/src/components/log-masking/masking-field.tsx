/* eslint-disable @typescript-eslint/no-misused-promises */
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

import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Dialog, Tag, Input, Switcher, Table, TableColumn, Button, Popover, Sideslider } from 'bk-magic-vue';
import VueDraggable from 'vuedraggable';

import $http from '../../api';
import { getFlatObjValues, xssFilter } from '../../common/util';
import { fieldTypeMap } from '../../store/constant';
import EmptyStatus from '../empty-status/index.vue';
import { deepClone } from '../monitor-echarts/utils';
import MaskingFieldInput from './masking-field-input';
import MaskingSelectRuleTable from './masking-select-rule-table';

import './masking-field.scss';

interface IProps {
  value: boolean;
}

interface IOperatorParams {
  preserve_head?: number;
  preserve_tail?: number;
  replace_mark?: string;
  template_string?: string;
}

interface IFieldItem {
  field_name: string;
  field_alias: string;
  field_class: string;
  field_type: string;
  rules: Array<IRuleItem>;
  operatorRules: Array<IRuleItem>;
  preview?: Array<any>;
  is_origin?: boolean;
}

interface IRuleItem {
  id?: number;
  rule_id: number;
  rule_name: string;
  state: string;
  change_state: string;
  match_fields: Array<string>;
  match_pattern: string;
  masking_rule?: string;
  operator: TOperator;
  params: IOperatorParams;
  new_rule?: IRuleItem;
  is_origin?: boolean;
  disabled: boolean;
}

type TOperator = 'mask_shield' | 'text_replace';
type TRuleChangeType = 'allClear' | 'allInit' | 'merge';

@Component
export default class MaskingField extends tsc<IProps> {
  @Prop({ type: Object, required: true }) collectData: any;
  /** 是否是采集项脱敏 */
  @Prop({ type: Boolean, default: true }) isIndexSetMasking: boolean;
  /** 当前采集的操作类型 */
  @Prop({ type: String, default: '' }) operateType: string;
  /** 是否隐藏 原始日志的已同步条数 */
  @Prop({ type: Boolean, default: false }) isHiddenSyncNum: boolean;

  /** 日志查询字符串 */
  configStr = '';

  /** 日志查询缓存的字符串 */
  cacheConfigStr = '';

  /** 定义搜索字符串 */
  searchStr = '';

  /** 预览开关，默认为true */
  previewSwitch = true;

  /** 表格加载状态，默认为false */
  tableLoading = false;

  /** 鼠标悬停的字段名 */
  hoverFieldName = '';

  /** 是否显示规则侧边栏，默认为false */
  isShowRuleSideslider = false;

  /** 重新选择弹窗显示 */
  isShowResetRuleDialog = false;

  /** 一键同步所有规则弹窗 */
  isShowAllSyncDialog = false;

  /** 是否向右边距，默认为false */
  isMarginRight = false;

  /** 标签气泡实例 */
  tagPopoverInstance = null;

  /** 是否显示规则更改对话框 */
  isShowRuleChangeDialog = false;

  /** 是否展示无法同步规则tips */
  isShowCannotCreateRuleTips = false;

  /** JSON格式错误tips */
  isJSONStrError = false;

  /** 是否展示字段分类 */
  isShowFieldClass = true;

  /** 当前变更或删除操作的规则 */
  currentOperateRule: IRuleItem = {
    rule_name: '',
    rule_id: 0,
    state: '',
    change_state: '',
    match_fields: [],
    match_pattern: '',
    operator: 'mask_shield',
    params: {
      preserve_head: 0,
      preserve_tail: 0,
      replace_mark: '*',
    },
    disabled: false,
  };

  /** 当前变更或删除操作的下标 */
  currentOperateRuleIndex = -1;

  /** 当前变更或删除操作的字段 */
  currentOperateField: IFieldItem = {
    field_name: '',
    field_alias: '',
    field_class: '',
    field_type: '',
    rules: [],
    operatorRules: [],
  };

  /** 当前操作的规则 */
  currentRuleState = 'update';

  /** 当前重新选择的规则 */
  currentSelectRule = {
    rule_name: '',
  };

  /** 字段名的字符串key */
  fieldTypeList = [];

  /** 字段类型icon展示列表 */
  fieldTypeObj = {};

  /** 侧边栏提交框样式 */
  sidesliderSubmitBoxStyle = {
    width: '640px',
    position: 'fixed',
    zIndex: '999',
    bottom: '0',
    right: '0',
    height: '48px',
    paddingLeft: '20px',
  };

  /** 默认选中规则的列表 */
  defaultSelectRuleList = [];

  /** 侧边栏推荐规则列表 */
  recommendRuleList = [];

  isPreviewLoading = false;

  /** 当前预览更新的字段 */
  previewLoadingField = '';

  /** 是否点击过一键同步 */
  isAllSync = false;

  /** 当前同步弹窗的信息 */
  ruleDialogBoxValue = {
    oldRule: {
      match_fields: 'xxx',
      match_pattern: 'xxxs',
      masking_rule: 'fadsf',
    },
    newRule: {
      match_fields: 'xxx',
      match_pattern: 'xxxs',
      masking_rule: 'fadsf',
    },
  };

  operatorMap = {
    mask_shield: window.mainComponent.$t('掩码'),
    text_replace: window.mainComponent.$t('替换'),
  };

  ruleDialogI18nMap = {
    oldRule: window.mainComponent.$t('原规则'),
    newRule: window.mainComponent.$t('现规则'),
    match_fields: window.mainComponent.$t('匹配字段'),
    match_pattern: window.mainComponent.$t('匹配正则'),
    masking_rule: window.mainComponent.$t('脱敏算子'),
  };

  /** json列表 */
  jsonParseList = [];

  /** 内置字段 */
  builtInFields = [];

  emptyType = 'empty';

  /** 字段原始数据 */
  fieldOriginValueList = [];

  /** 是否是更新脱敏 */
  isUpdate = false;

  /** 日志查询loading */
  inputLoading = false;

  tableList = [];

  tableShowList = [];

  recommendRuleIDMap = {};

  /** 点击脱敏列表的添加规则时 直接回填字段和采样值 */
  addRuleFieldValue = {
    field: '',
    fieldLog: '',
  };

  @Ref('syncRuleTable') private readonly syncRuleTableRef: HTMLElement;

  /** 原始日志已同步数 */
  get getSyncNum() {
    return this.tableList
      .filter(item => !item.field_class_islog)
      .reduce((pre, cur) => {
        let num = 0;
        cur.fieldList.forEach(item => {
          item.rules.length && (num += 1);
        });
        pre += num;
        return pre;
      }, 0);
  }

  /** 是否展示表头的一键同步按钮 */
  get isShowSyncBtn() {
    let isHaveSync = false;
    const tableFields = this.reductionOriginTable(this.tableList);
    tableFields.forEach(fItem => {
      fItem.rules.forEach(rItem => {
        if (rItem.state === 'update' || rItem.state === 'delate') {
          if (!rItem?.change_state && !isHaveSync) isHaveSync = true;
        }
      });
    });
    return isHaveSync && !this.isAllSync;
  }

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get isShowConfigFiledEmptyTips() {
    return !this.fieldTypeList.length && !this.jsonParseList.length;
  }

  @Emit('changeData')
  emitSyncRule() {
    return true;
  }

  @Emit('initEditComparedData')
  emitEditCompared() {
    return true;
  }

  async created() {
    this.tableLoading = true;
    this.isShowFieldClass = !!this.collectData?.fields; // 判断是否展示字段分类
    this.builtInFields = this.getBuiltInFields(); // 获取内置字段
    const { fieldList, fieldObj } = await this.getFieldType(); // 获取字段类型和别名 用于字段类型icon展示和初始化表格
    this.fieldTypeList = fieldList;
    this.fieldTypeObj = fieldObj;
    try {
      const initFieldConfigs = await this.getMaskingConfig(); // 获取脱敏配置信息
      if (initFieldConfigs.length) {
        // 判断有无脱敏信息 执行不同逻辑的代码
        this.isUpdate = true;
        // 根据当前的日志查询字符串  已保存过脱敏规则 生成日志脱敏列表
        this.tableList = this.initTableList(initFieldConfigs);
        const fieldConfigs = await this.matchMaskingRule();
        this.initMergeTableList(fieldConfigs, 'allInit');
      } else {
        this.isUpdate = false;
        // 未保存过脱敏规则 用输入框的json数组生成脱敏列表
        await this.matchMaskingRule();
        this.tableList = this.initTableList(this.fieldTypeList, 'allClear');
        this.tableShowList = deepClone(this.tableList);
      }
    } catch (err) {
    } finally {
      this.tableLoading = false;
      this.$nextTick(() => {
        this.emitEditCompared();
      });
    }
  }

  getFieldIcon(fieldType) {
    return fieldTypeMap[fieldType] ? fieldTypeMap[fieldType].icon : 'bklog-icon bklog-unkown';
  }
  /** 获取字段列表样式 */
  getFieldItemStyle(fieldItem: IFieldItem) {
    let heightNum = fieldItem.rules.length || 1;
    if (fieldItem?.is_origin && !this.isHiddenSyncNum) heightNum += 1;
    const backgroundColor = this.hoverFieldName === fieldItem.field_name ? '#F5F7FA' : '#FFF';
    return `height:${heightNum * 30 + 12}px; background: ${backgroundColor}`;
  }

  async handleMoveEnd(fieldItem: IFieldItem, fieldItemRules: Array<IRuleItem>) {
    this.tableValueChange(fieldItem, (fItem: IFieldItem) => (fItem.rules = deepClone(fieldItemRules)));
    await this.updatePreview(fieldItem); // 更新脱敏预览
  }

  async handleCloseRule(index: number, fieldItem: IFieldItem) {
    this.tableValueChange(fieldItem, (fItem: IFieldItem) => fItem.rules.splice(index, 1));
    await this.updatePreview(fieldItem); // 更新脱敏预览
  }

  /**
   * @desc: 合并两个脱敏字段列表
   * @param {Array<IFieldItem>} mergeTable 被合并的第一个列表
   * @param {Array<IFieldItem>} newTable 被合并的第二个脱敏列表
   * @param {TRuleChangeType} ruleType 合并类型 不同的类型合并的规则不同
   * @returns {Array}
   */
  getMergeTableValue(mergeTable: Array<IFieldItem> = [], newTable: Array<IFieldItem> = [], ruleType: TRuleChangeType) {
    const allTable = [...mergeTable, ...newTable];
    const map = new Map();
    // 这是字段
    for (const tItem of allTable) {
      if (!map.has(tItem.field_name)) {
        // 新字段 直接更新
        map.set(tItem.field_name, tItem);
      } else {
        // 已有字段, 更新规则
        const catchField = map.get(tItem.field_name);
        if (!catchField.is_origin) {
          // 非原始日志的情况下采取合并推荐的规则
          const pushRules = ruleType === 'merge' ? tItem?.operatorRules : tItem?.rules;
          pushRules.forEach(tRItem => {
            // 从match接口返回的规则中 添加未生成的有的规则
            if (!catchField.rules.some((cRItem: IRuleItem) => cRItem.rule_id === tRItem.rule_id)) {
              catchField.rules.push(tRItem);
            }
          });
        }
        catchField.operatorRules = tItem.operatorRules ?? [];
        map.set(tItem.field_name, catchField);
      }
    }
    return [...map.values()];
  }

  /**
   * @desc: 还原最初始脱敏字段列表
   * @param {Array} oldTableList
   * @returns {Array}
   */
  reductionOriginTable(oldTableList = []) {
    return oldTableList.reduce((pre, cur) => {
      pre = pre.concat(cur.fieldList);
      return pre;
    }, []);
  }

  /**
   * @desc: 合并两个原始字段列表并更新表格
   * @param {*} newOriginTableList
   * @param {String} ruleChange 是否初始化规则
   */
  initMergeTableList(newOriginTableList = [], ruleChange: TRuleChangeType = 'merge') {
    try {
      this.tableLoading = true;
      // 获取当前表格的原始字段表格
      const tableOriginFieldsList = this.reductionOriginTable(this.tableList);

      // 获取旧的和新的原始字段表格
      const mergedFieldsList = this.getMergeTableValue(tableOriginFieldsList, newOriginTableList, ruleChange);
      // 更新表格 更新检索表格
      this.tableList = this.initTableList(mergedFieldsList, ruleChange);
      this.tableShowList = deepClone(this.tableList);
      // 更新所有预览
      this.updatePreview();
    } catch (err) {
      this.tableLoading = false;
    } finally {
      this.tableLoading = false;
    }
  }

  /**
   * @desc: 更新表格的参数 包括检索的表格和全量的表格
   * @param {Object} fieldItem 更新的字段
   * @param {Function} callback 更新的回调函数
   * @param {Array} list 更新的表格
   */
  tableValueChange(fieldItem: IFieldItem, callback: (any) => void, list = [this.tableList, this.tableShowList]) {
    list.forEach(lItem => {
      // 找到对应fieldClass的索引
      const typeIndex = lItem.findIndex(item => item.field_class === fieldItem.field_class);
      // 找到对应fieldName的索引
      const fieldIndex = lItem[typeIndex].fieldList?.findIndex(
        (item: IFieldItem) => item.field_name === fieldItem.field_name,
      );
      callback(lItem[typeIndex].fieldList[fieldIndex]);
    });
  }

  /**
   * @desc: 是否展示添加规则按钮
   * @param {Array} fieldItem 字段数据
   * @returns {Boolean} 是否展示
   */
  getIsShowAddRuleBtn(fieldItem: IFieldItem) {
    if (fieldItem.rules.length >= 1) return true;
    return false;
  }

  /**
   * @desc: 新增规则
   * @param {Array} selectList 选中的规则列表
   */
  async handleSelectRule(selectList: Array<IRuleItem>) {
    // 这里先更新match匹配规则的接口
    await this.matchMaskingRule();
    // 把已删除的过滤掉
    const curIdList = this.currentOperateField.rules
      .filter(rItem => rItem.state !== 'delete')
      .map(item => item.rule_id);
    const selectIdList = selectList.map(item => item.id);
    const differenceIdList = curIdList
      .concat(selectIdList)
      .filter(v => !curIdList.includes(v) || !selectIdList.includes(v)); // 获取新增差集的rule_id

    this.tableValueChange(this.currentOperateField, async (fItem: IFieldItem) => {
      differenceIdList.forEach(dItem => {
        const newRule = selectList.find((sItem: IRuleItem) => sItem.id === dItem);
        if (newRule) {
          newRule.masking_rule = this.getMaskingRuleStr(newRule); // 初始化脱敏规则
          newRule.change_state = 'add'; // 设置提交状态为新增
          newRule.rule_id = newRule.id;
          if (!!this.recommendRuleIDMap[fItem.field_name]) {
            // 给match接口中不生效的规则变灰色
            newRule.disabled = !this.recommendRuleIDMap[fItem.field_name].includes(newRule.rule_id);
          } else if (JSON.stringify(this.recommendRuleIDMap) === '{}') {
            newRule.disabled = true;
          }
          fItem.rules.push(newRule);
        } else {
          // 除去已删除的 删除了的规则 直接删掉
          const spliceIndex = fItem.rules.findIndex(rItem => rItem.rule_id === dItem);
          if (spliceIndex >= 0) fItem.rules.splice(spliceIndex, 1);
        }
      });
      await this.updatePreview(fItem); // 更新脱敏预览
    });

    this.isShowRuleSideslider = false;
  }

  /**
   * @desc: 重选规则规则
   */
  async handleResetSelectRule() {
    const resetRule = (this.syncRuleTableRef as any).getSyncSelectRule(); // 重选的规则
    // 这里先更新match匹配规则的接口
    await this.matchMaskingRule();
    this.tableValueChange(this.currentOperateField, async (fItem: IFieldItem) => {
      resetRule.masking_rule = this.getMaskingRuleStr(resetRule); // 初始化脱敏规则
      resetRule.change_state = 'add'; // 设置提交状态为新增
      resetRule.rule_id = resetRule.id;
      if (!!this.recommendRuleIDMap[fItem.field_name]) {
        // 给match接口中不生效的规则变灰色
        resetRule.disabled = !this.recommendRuleIDMap[fItem.field_name].includes(resetRule.rule_id);
      } else if (JSON.stringify(this.recommendRuleIDMap) === '{}') {
        resetRule.disabled = true;
      }
      fItem.rules.splice(this.currentOperateRuleIndex, 1, resetRule);
      await this.updatePreview(fItem); // 更新脱敏预览
    });

    this.isShowResetRuleDialog = false;
  }

  handleHoverTagName(e, rItem: IRuleItem) {
    if (!this.tagPopoverInstance) {
      this.tagPopoverInstance = this.$bkPopover(e.target, {
        content: `<div class="rule-tag-popover">
                    <div class="tag-value">
                      <span>${this.$t('规则名称')}: </span>
                      <span>${rItem.rule_name || '-'}</span>
                    </div>
                    <div class="tag-value">
                      <span>${this.$t('匹配字段')}: </span>
                      <span>${rItem.match_fields?.join(', ') || '-'}</span>
                    </div>
                    <div class="tag-value">
                      <span>${this.$t('匹配正则')}: </span>
                      <span>${rItem.match_pattern || '-'}</span>
                    </div>
                    <div class="tag-value">
                      <span>${this.$t('脱敏算子')}: </span>
                      <span>${rItem.masking_rule || '-'}</span>
                    </div>
                  </div>`,
        arrow: true,
        placement: 'bottom',
        theme: 'light',
        interactive: true,
        onHidden: () => {
          this.tagPopoverInstance?.destroy();
          this.tagPopoverInstance = null;
        },
      });
      this.tagPopoverInstance.show(300);
    }
  }

  /** 同步或重新选择左边的按钮 */
  handleClickLeftBtn() {
    if (this.currentRuleState === 'delete') {
      this.isShowResetRuleDialog = true; // 重新选择弹窗显示
      this.isShowRuleChangeDialog = false; // 同步弹窗隐藏
      return;
    }
    this.handleCurrentSyncChange();
    this.isShowRuleChangeDialog = false;
  }

  /** 同步或重新选择右边的按钮 */
  handleClickRightBtn() {
    if (this.currentRuleState === 'delete') {
      // 直接同步
      this.handleCurrentSyncChange();
      this.isShowRuleChangeDialog = false;
      return;
    }
    this.isShowResetRuleDialog = true;
    this.isShowRuleChangeDialog = false;
  }

  /**
   * @desc: 同步改变当前字段的状态
   * @param {Object} syncField 同步的字段
   * @param {Number} syncIndex 同步的规则下标
   */
  handleCurrentSyncChange(syncField = {}, syncIndex = -1) {
    if (JSON.stringify(syncField) === '{}') syncField = this.currentOperateField;
    if (syncIndex === -1) syncIndex = this.currentOperateRuleIndex;

    this.tableValueChange(syncField as IFieldItem, async (fItem: IFieldItem) => {
      const currentRule = deepClone(fItem.rules[syncIndex]);

      if (currentRule.state === 'delete') {
        // 删除状态 直接删除当前规则
        fItem.rules.splice(syncIndex, 1);
        // 更新预览
        await this.updatePreview(fItem); // 更新脱敏预览
        return;
      }
      // 有相同ID的规则其他的规则也跟着一键同步
      this.handleAllSync(currentRule.rule_id);

      // !!TODO 下面是单条规则同步 现在是同步一条规则 其余的规则跟着同步
      // 拿new-rule里的数据更新
      // currentRule = {
      //   ...currentRule.new_rule,
      //   masking_rule: this.getMaskingRuleStr(currentRule.new_rule),
      //   rule_id: currentRule.rule_id, // rule_id不变
      //   new_rule: currentRule.new_rule,
      //   change_state: 'update',
      // };

      // 更新当前规则同步弹窗后的数据
      // fItem.rules[syncIndex] = currentRule;

      // 更新预览
      // await this.updatePreview(fItem); // 更新脱敏预览
    });
  }

  /**
   * @desc: 点击变更或删除同步状态时的弹窗
   * @param {IFieldItem} fieldItem 同步的字段数据
   * @param {IRuleItem} ruleItem 同步的规则
   * @param {Number} rIndex 同步的规则下标
   * @param {String} state 同步方式 删除还是变更
   */
  handleShowRuleChangeDialog(fieldItem: IFieldItem, ruleItem: IRuleItem, rIndex: number, state: string) {
    this.currentRuleState = state; // 当前同步状态
    this.currentOperateRule = ruleItem; // 当前同步规则
    this.currentOperateField = fieldItem; // 当前同步字段
    this.currentOperateRuleIndex = rIndex; // 当前同步规则下标
    this.defaultSelectRuleList = fieldItem.rules.map(item => item.rule_id);
    this.recommendRuleList = this.recommendRuleIDMap[fieldItem.field_name] ?? [];
    this.ruleDialogBoxValue = {
      // 脱敏规则同步展示的弹窗数据
      oldRule: {
        match_fields: ruleItem.match_fields?.join(', ') || '-',
        match_pattern: ruleItem.match_pattern || '',
        masking_rule: this.getMaskingRuleStr(ruleItem),
      },
      newRule: {
        match_fields: ruleItem.new_rule?.match_fields?.join(', ') || '-',
        match_pattern: ruleItem.new_rule?.match_pattern || '',
        masking_rule: this.getMaskingRuleStr(ruleItem.new_rule),
      },
    };
    this.isShowRuleChangeDialog = true;
  }

  // handleShowAllSyncDialog() {
  //   this.isShowAllSyncDialog = true;
  // }

  /**
   * @desc: 同步所有变更
   */
  /**
   * @desc: 同步所有变更
   * @param {number} syncID 同步规则ID列表
   */
  handleAllSync(syncID = -1) {
    if (!this.tableList.length || this.isAllSync) return;
    this.tableList.forEach(cItem => {
      cItem.fieldList.forEach(field => {
        const spliceIDList = [];
        field.rules.forEach((item, index) => {
          if (syncID >= 0) {
            // 有同步规则
            if (item.rule_id === syncID) {
              // 拿new-rule里的数据更新
              field.rules[index] = {
                ...item.new_rule,
                masking_rule: this.getMaskingRuleStr(item.new_rule),
                new_rule: item.new_rule,
                rule_id: item.rule_id, // rule_id不变
                change_state: 'update',
              };
            }
            return;
          }
          if (item.state === 'delete') {
            spliceIDList.push(item.rule_id);
            return;
          }
          if (item.state === 'update') {
            // 拿new-rule里的数据更新
            field.rules[index] = {
              ...item.new_rule,
              masking_rule: this.getMaskingRuleStr(item.new_rule),
              new_rule: item.new_rule,
              rule_id: item.rule_id, // rule_id不变
              change_state: 'update',
            };
          }
        });
        spliceIDList.forEach(item => {
          const index = field.rules.findIndex(rItem => rItem.rule_id === item);
          field.rules.splice(index, 1); // 删除状态 直接删除当前规则
        });
      });
    });
    this.tableShowList = deepClone(this.tableList);
    if (syncID === -1) this.isAllSync = true;
    // this.emitSyncRule();
    this.updatePreview();
  }

  /** 检索字段 */
  searchField() {
    const tableShowList = deepClone(this.tableList);
    this.tableShowList = tableShowList
      .map(fItem => ({
        ...fItem,
        fieldList: (fItem.fieldList as any).filter(item =>
          item.field_name.toString().toLowerCase().includes(this.searchStr.toLowerCase()),
        ),
      }))
      .filter(item => !!item.fieldList.length);
    this.emptyType = 'search-empty';
  }

  handleSearchChange(val) {
    if (val === '' && !this.tableLoading) {
      this.emptyType = 'empty';
      this.tableShowList = deepClone(this.tableList);
    }
  }

  renderHeaderRule(h) {
    return h(
      'div',
      {
        class: 'sync-render-header',
      },
      [
        h('span', this.$t('脱敏规则')),
        h('span', {
          class: 'bklog-icon bklog-brush',
          directives: [
            {
              name: 'bk-tooltips',
              value: this.$t('清空所有规则'),
            },
          ],
          on: {
            click: this.handleClearRule,
          },
        }),
        h('span', { class: ['bklog-icon bklog-double-arrow', { 'is-show-sync': this.isShowSyncBtn }] }),
        h(
          'span',
          {
            class: ['sync-btn', { 'is-show-sync': this.isShowSyncBtn }],
            on: {
              click: () => this.handleAllSync(),
            },
          },
          this.$t('同步所有变更'),
        ),
      ],
    );
  }

  renderHeaderPreview(h) {
    return h(
      'div',
      {
        class: 'sync-render-header',
      },
      [
        h('span', this.$t('脱敏预览')),
        h('span', {
          class: 'bklog-icon bklog-info-fill',
          directives: [
            {
              name: 'bk-tooltips',
              value: this.$t('脱敏预览会根据您的采样日志输出对应脱敏结果，多条采样会输出多条脱敏结果。'),
            },
          ],
        }),
      ],
    );
  }

  /**
   * @desc: 输入框失焦触发
   * @param {Boolean} isPreview 是否更新预览
   */
  async handleBlurConfigInput(jsonParseList = [], isPreview = true) {
    this.jsonParseList = jsonParseList;
    // 获取所有json字段相同字段的值 值为数组
    if (this.jsonParseList.length) {
      const flatJsonParseList = this.jsonParseList.map(item => {
        const { newObject } = getFlatObjValues(item);
        return newObject;
      });
      this.fieldOriginValueList = (flatJsonParseList as any).reduce((pre, cur) => {
        Object.entries(cur).forEach(([fieldKey, fieldVal]) => {
          if (!pre[fieldKey]) pre[fieldKey] = [];
          pre[fieldKey].push(fieldVal ?? '');
        });
        return pre;
      }, {});
    }
    if (isPreview) {
      const fieldConfigs = await this.matchMaskingRule();
      this.initMergeTableList(fieldConfigs, 'allInit');
    }
  }

  /**
   * @desc: 获取字段类型
   * @returns {Array}
   */
  async getFieldType() {
    try {
      const currentTime = Date.now();
      const startTime = Math.floor((currentTime - 15 * 60 * 1000) / 1000);
      const endTime = Math.floor(currentTime / 1000);
      const res = await $http.request('retrieve/getLogTableHead', {
        params: { index_set_id: this.collectData?.index_set_id },
        query: {
          start_time: startTime,
          end_time: endTime,
          is_realtime: 'True',
        },
      });
      return res.data.fields.reduce(
        (pre, cur) => {
          // 虚拟字段不用展示
          if (cur.field_type === '__virtual__') return pre;
          pre.fieldObj[`${cur.field_name}`] = {
            field_alias: cur.field_alias,
            field_type: cur.field_type,
          };
          pre.fieldList.push({
            field_name: cur.field_name,
            field_alias: cur.field_alias,
            field_type: cur.field_type,
            rules: [],
          });
          return pre;
        },
        {
          fieldList: [],
          fieldObj: {},
        },
      );
    } catch (err) {
      return {
        fieldList: [],
        fieldObj: {},
      };
    }
  }

  /**
   * @desc: 获取保存的脱敏字段
   * @returns {Array}
   */
  async getMaskingConfig() {
    try {
      const res = await $http.request(
        'masking/getMaskingConfig',
        {
          params: { index_set_id: this.collectData?.index_set_id },
        },
        { catchIsShowMessage: false },
      );
      return res.data.field_configs;
    } catch (err) {
      return [];
    }
  }

  /**
   * @desc: 一键生成规则
   */
  async handleCreateRule() {
    const fieldConfigs = await this.matchMaskingRule();
    this.initMergeTableList(fieldConfigs, 'merge');
  }

  /**
   * @desc: 清空所有规则
   */
  handleClearRule() {
    this.initMergeTableList([], 'allClear');
  }

  /**
   * @desc: 获取内置字段列表
   * @returns {Array<number>}
   */
  getBuiltInFields(): Array<number> {
    return this.collectData?.fields?.filter(item => item.is_built_in) || [];
  }

  /**
   * @desc: 获取初始化日志脱敏表格列表
   * @param {Array} maskingList 字段列表
   * @param {String} changeRuleState 规则根据什么情况改变
   * @param {String} isFirstInit 是否是第一次初始化
   * @returns {Array}
   */
  initTableList(maskingList = [], changeRuleState: TRuleChangeType = 'merge') {
    if (!maskingList.length) return [];
    try {
      const reduceInitList = [
        {
          field_class_islog: false,
          field_class: window.mainComponent.$t('内置字段'),
          fieldList: [],
        },
        {
          field_class_islog: false,
          field_class: window.mainComponent.$t('清洗字段'),
          fieldList: [],
        },
        {
          field_class_islog: true,
          field_class: window.mainComponent.$t('原始日志'),
          fieldList: [],
        },
      ];

      const initFieldList = maskingList.reduce((pre, cur) => {
        // 分类下标
        let preIndex = 1;
        if (this.builtInFields.some(item => item.field_name === cur.field_name)) {
          // 判断是否是内置字段 若是内置字段 更新需要更新的字段的下标
          preIndex = 0;
        } else if (cur.field_name === 'log' && this.fieldTypeObj[cur.field_name]?.field_type === 'text') {
          // 判断是否是原始日志 若是原始日志 更新需要更新的字段的下标
          preIndex = 2;
        }
        // 判断当前字段是否是原始日志字段
        cur.is_origin = preIndex === 2;
        // 字段更新分类
        cur.field_class = reduceInitList[preIndex].field_class;
        cur.field_alias = this.fieldTypeObj[cur.field_name]?.field_alias || '';
        cur.field_type = this.fieldTypeObj[cur.field_name]?.field_type || '';
        cur.rules.forEach((rItem: IRuleItem) => {
          // 获取脱敏规则tips弹窗字符串
          rItem.masking_rule = this.getMaskingRuleStr(rItem);
          // 更新状态 初始化为空字符串 旧的表格也需要缓存
          rItem.change_state = rItem.change_state ?? '';
          // 初始化都为false
          rItem.disabled = false;
          const isDeleteRule = rItem.state === 'delete' && rItem.change_state === '';
          // 给match接口中不生效的规则变灰色 并且不为状态删除的时候
          if (!isDeleteRule && !!this.recommendRuleIDMap[cur.field_name]) {
            rItem.disabled = !this.recommendRuleIDMap[cur.field_name].includes(rItem.rule_id);
          }
        });
        switch (changeRuleState) {
          case 'merge':
            break;
          case 'allInit':
            break;
          case 'allClear':
            cur.rules = []; // 全清除
            break;
        }

        // 更新分类的字段数组
        pre[preIndex].fieldList.push(cur);
        return pre;
      }, reduceInitList);

      return initFieldList.filter(item => item.fieldList.length);
    } catch (err) {
      return [];
    } finally {
    }
  }

  /**
   * @desc: 更新单个字段或所有字段的脱敏预览
   * @param {Object} fieldItem 当前字段数据
   */
  async updatePreview(fieldItem?: IFieldItem) {
    if (!this.previewSwitch) return; // 结果预览开关关闭 不更新预览
    try {
      this.isPreviewLoading = true;
      if (fieldItem) {
        // 更新单个字段
        this.previewLoadingField = fieldItem.field_name;
        const previewList = await this.getConfigPreview([fieldItem]);
        const fieldPreview = previewList[fieldItem.field_name];
        const preview = this.getFieldPreview(fieldItem.field_name, fieldPreview);
        this.tableValueChange(fieldItem, async (fItem: IFieldItem) => {
          fItem.preview = preview;
        });
      } else {
        const fieldList = this.tableList.reduce((pre, cur) => {
          pre.push(...cur.fieldList);
          return pre;
        }, []);
        const previewVal = await this.getConfigPreview(fieldList);
        this.updateAllFieldPreview(this.tableList, previewVal);
        this.updateAllFieldPreview(this.tableShowList, previewVal);
      }
    } catch (err) {
    } finally {
      this.previewLoadingField = '';
      this.isPreviewLoading = false;
    }
  }

  /**
   * @desc: 更新字段的脱敏预览
   * @param {Array} list 更新的表格
   * @param {Object} previewVal 预览对象
   */
  updateAllFieldPreview(list, previewVal): void {
    list.forEach(cItem => {
      cItem.fieldList.forEach((field: IFieldItem) => {
        const fieldPreview = previewVal[field.field_name];
        const preview = this.getFieldPreview(field.field_name, fieldPreview);
        field.preview = preview;
      });
    });
  }

  /**
   * @desc: 获取字段预览
   * @param {String} fieldName 字段名
   * @param {Array} previewResult 接口返回的预览值
   * @returns {Array}
   */
  getFieldPreview(fieldName = '', previewResult = []) {
    if (!previewResult.length) return [];
    if (!this.jsonParseList.length || !fieldName) return [];
    if (!this.fieldOriginValueList[fieldName]) return [];
    const previewList = [];
    const filterResult = previewResult.filter(item => item !== null);
    this.fieldOriginValueList[fieldName].forEach((item, index) => {
      const maskingValue = filterResult[index] ?? '';
      const origin = typeof item === 'object' ? JSON.stringify(item) : String(item);
      previewList[index] = {
        origin,
        afterMasking: maskingValue,
      };
    });
    return previewList;
  }

  /**
   * @desc: 接口获取脱敏预览
   * @param {Array} fieldList 字段列表
   * @returns {Object}
   */
  async getConfigPreview(fieldList = []) {
    if (!this.jsonParseList.length || !fieldList.length) return {};
    const fieldConfigs = fieldList
      .filter(item => {
        return item.rules.length && item.rules.some(rItem => !rItem.disabled);
      })
      .map(item => ({
        field_name: item.field_name,
        rules: item.rules
          .filter(fItem => !fItem.disabled)
          .map(rItem => {
            if (rItem.state === 'update' && rItem.change_state !== 'update') {
              // 更新同步后的预览 拿new_rule里的数据进行更新预览
              return {
                match_pattern: rItem.match_pattern,
                operator: rItem.operator,
                params: rItem.params,
              };
            }
            return { rule_id: rItem.rule_id };
          }),
      }));
    if (!fieldConfigs.length) return {};
    try {
      const res = await $http.request('masking/getConfigPreview', {
        data: {
          logs: this.jsonParseList,
          field_configs: fieldConfigs,
          text_fields: !this.isHiddenSyncNum
            ? this.tableList.find(item => item.field_class_islog)?.fieldList.map(item => item.field_name)
            : [],
        },
      });
      return res.data;
    } catch (err) {
      return {};
    }
  }

  /**
   * @desc: 获取日志查询生成的脱敏规则
   * @param {Boolean} isMerge 是否是合并 合并情况下 change_state改为true
   * @returns {Array}
   */
  async matchMaskingRule() {
    if (!this.jsonParseList.length) {
      return this.fieldTypeList.map(item => ({
        field_name: item.field_name,
        operatorRules: [],
        rules: [],
      }));
    }
    try {
      const res = await $http.request('masking/matchMaskingRule', {
        data: {
          space_uid: this.spaceUid,
          logs: this.jsonParseList,
          fields: this.fieldTypeList.map(item => item.field_name),
        },
      });
      return Object.entries(res.data).reduce((pre, [fieldsKey, fieldsVal]) => {
        const fieldsObj = {
          field_name: fieldsKey,
          operatorRules: fieldsVal,
          rules: [],
        };

        fieldsObj.operatorRules = (fieldsObj.operatorRules as any).map(item => ({
          ...item,
          // 获取脱敏规则tips弹窗字符串
          masking_rule: this.getMaskingRuleStr(item),
          // 更新状态 初始化为空字符串 旧的表格也需要缓存
          change_state: item.change_state ?? 'add',
        }));

        // 初始化生成推荐规则
        this.recommendRuleIDMap[fieldsKey] = (fieldsVal as any).map(item => item.rule_id);

        pre.push(fieldsObj);
        return pre;
      }, []);
    } catch (err) {
      return [];
    }
  }

  /**
   * @desc: 判断当前字符串是否是json格式并且有值
   * @param {String} str 字符串
   * @returns {Boolean}
   */
  isHaveValJSON(str: string): boolean {
    try {
      JSON.parse(str);
      return JSON.parse(str) && str !== '{}';
    } catch (error) {
      return false;
    }
  }

  /**
   * @desc: 获取表格的脱敏配置参数
   */
  getQueryConfigParams() {
    const fieldConfigs = this.tableList.reduce((pre, cur) => {
      const fieldList = (cur.fieldList as any)
        .filter(item => item.rules?.length)
        .map(item => ({
          field_name: item.field_name,
          rules: item.rules.map(item => {
            return {
              rule_id: item.rule_id,
              state: !!item.change_state ? item.change_state : 'normal',
            };
          }),
        }));
      pre.push(...fieldList);
      return pre;
    }, []);
    return {
      space_uid: this.spaceUid,
      field_configs: fieldConfigs,
      text_fields: !this.isHiddenSyncNum
        ? this.tableList.find(item => item.field_class_islog)?.fieldList.map(item => item.field_name)
        : [],
    };
  }

  /**
   * @desc: 获取脱敏规则字符串
   * @param {IRuleItem} item 脱敏规则参数
   * @returns {String} 返回脱敏规则字符串
   */
  getMaskingRuleStr(item: IRuleItem) {
    const endStr =
      item?.operator === 'text_replace'
        ? `${this.$t('替换为')} ${item?.params?.template_string}`
        : this.$t('保留前{0}位, 后{1}位', {
            0: item?.params?.preserve_head,
            1: item?.params?.preserve_tail,
          });
    return `${this.operatorMap[item?.operator]} | ${endStr}`;
  }

  handleOperation(type: string) {
    if (type === 'clear-filter') {
      this.searchStr = '';
      this.handleSearchChange('');
      return;
    }
    if (type === 'refresh') {
      return;
    }
  }

  handleClickAddRuleIcon(fieldItem: IFieldItem) {
    // 新增规则直接回填采样和字段
    this.addRuleFieldValue = {
      field: fieldItem.field_name,
      fieldLog: this.fieldOriginValueList[fieldItem.field_name]?.find((item: any) => Boolean(String(item))) ?? '',
    };
    this.currentOperateField = fieldItem; // 当前添加更多规则的字段
    this.defaultSelectRuleList = fieldItem.rules.map(item => item.rule_id);
    this.recommendRuleList = this.recommendRuleIDMap[fieldItem.field_name] ?? [];
    this.isShowRuleSideslider = true;
  }

  getMoveFillIcon(rules: Array<IRuleItem>) {
    if (rules?.length === 1) return '';
    return 'bk-icon icon-grag-fill';
  }

  htmlDecode(text) {
    // 1.首先动态创建一个容器标签元素，如DIV
    let temp = document.createElement('div');
    // 2.然后将要转换的字符串设置为这个元素的innerHTML(ie，火狐，google都支持)
    temp.innerHTML = xssFilter(text);
    // 3.最后返回这个元素的innerText(ie支持)或者textContent(火狐，google支持)，即得到经过HTML解码的字符串了。
    const output = temp.innerText || temp.textContent;
    temp = null;
    return output;
  }

  handleHoverRow(fieldName: string) {
    setTimeout(() => {
      this.hoverFieldName = fieldName;
    }, 50);
  }

  handleLeaveRow() {
    setTimeout(() => {
      this.hoverFieldName = '';
    }, 50);
  }

  render() {
    const fieldSlot = {
      default: ({ row }) => (
        <div class='field-info-box'>
          {this.isShowFieldClass && !!row.fieldList.length && <div class='type'>{row.field_class}</div>}
          <div class={`field-box ${!this.isShowFieldClass ? 'not-class-width' : ''}`}>
            {row.fieldList.map(item => (
              <div
                style={this.getFieldItemStyle(item)}
                class='field'
                onMouseenter={() => this.handleHoverRow(item.field_name)}
                onMouseleave={() => this.handleLeaveRow()}
              >
                <i
                  class={['field-type-icon', this.getFieldIcon(item.field_type) || 'bklog-icon bklog-unkown']}
                  v-bk-tooltips={{
                    content: fieldTypeMap[item.field_type]?.name,
                    disabled: !fieldTypeMap[item.field_type],
                  }}
                ></i>
                <span
                  class='title-overflow'
                  v-bk-overflow-tips={{ delay: 500 }}
                >
                  {item.field_name}
                </span>
                {item.field_alias && (
                  <span
                    class='nick-name title-overflow'
                    v-bk-overflow-tips={{ delay: 500 }}
                  >
                    {item.field_alias}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ),
    };

    const getMaskingRuleEndState = (fieldItem: IFieldItem, rItem: IRuleItem, rIndex: number) => {
      if (rItem.state === 'update' && !rItem.change_state) {
        return (
          <Tag
            ext-cls='sync-tag'
            theme='warning'
            type='filled'
            onClick={() => this.handleShowRuleChangeDialog(fieldItem, rItem, rIndex, 'update')}
          >
            {this.$t('已变更')}
          </Tag>
        );
      }
      if (rItem.state === 'delete') {
        return (
          <Tag
            ext-cls='sync-tag'
            theme='danger'
            type='filled'
            onClick={() => this.handleShowRuleChangeDialog(fieldItem, rItem, rIndex, 'delete')}
          >
            {this.$t('已删除')}
          </Tag>
        );
      }
      return undefined;
    };

    const getMaskingRuleAddIcon = (fieldItem: IFieldItem, index: number) => {
      if (fieldItem.rules.length === index + 1) {
        return (
          <div
            style={`visibility: ${this.hoverFieldName === fieldItem.field_name ? 'visible' : 'hidden'}`}
            class='add-rule-icon'
            onClick={() => this.handleClickAddRuleIcon(fieldItem)}
          >
            <i class='bk-icon left-icon icon-plus'></i>
          </div>
        );
      }
      return undefined;
    };

    const getRuleItemDom = (fieldItem: IFieldItem, rItem: IRuleItem, rIndex: number) => {
      return (
        <div class='tag-box'>
          <Tag
            class='title-overflow'
            ext-cls={`field-tag ${rItem?.disabled ? 'is-failed' : ''}`}
            icon={this.getMoveFillIcon(fieldItem.rules)}
            closable
            on-close={() => this.handleCloseRule(rIndex, fieldItem)}
          >
            <span
              class={['tag-name', { 'is-failed': JSON.stringify(fieldItem.preview) === '{}' }]}
              onMouseenter={e => this.handleHoverTagName(e, rItem)}
            >
              {rItem.rule_name}
            </span>
          </Tag>
          {rItem?.disabled && (
            <i
              class='bk-icon icon-info-circle-shape'
              v-bk-tooltips={{ content: this.$t('脱敏规则暂未匹配到有效日志，无法预览结果') }}
            ></i>
          )}
          {getMaskingRuleEndState(fieldItem, rItem, rIndex)}
          {getMaskingRuleAddIcon(fieldItem, rIndex)}
        </div>
      );
    };

    const maskingRuleSlot = {
      default: ({ row }) => (
        <div class='masking-rule-box'>
          {row.fieldList.map((item: IFieldItem) => (
            <div
              style={this.getFieldItemStyle(item)}
              class='rule'
              onMouseenter={() => this.handleHoverRow(item.field_name)}
              onMouseleave={() => this.handleLeaveRow()}
            >
              {this.getIsShowAddRuleBtn(item) ? (
                <div>
                  {item?.is_origin && (
                    <div
                      key='-1'
                      class='tag-box sync'
                    ></div>
                  )}
                  <VueDraggable
                    v-model={item.rules}
                    animation='150'
                    handle='.icon-grag-fill'
                    on-end={() => this.handleMoveEnd(item, item.rules)}
                  >
                    <transition-group>
                      {item.rules.map((rItem: IRuleItem, rIndex: number) => (
                        <div key={rIndex}>{getRuleItemDom(item, rItem, rIndex)}</div>
                      ))}
                    </transition-group>
                  </VueDraggable>
                </div>
              ) : (
                <div class='tag-box'>
                  <Button
                    text
                    onClick={() => this.handleClickAddRuleIcon(item)}
                  >
                    <i class='bk-icon icon-plus push'></i>
                    <span style='margin-left: 8px;'>{this.$t('添加规则')}</span>
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      ),
    };

    const getPreviewDom = (fieldItem: IFieldItem) => {
      const preview = fieldItem.preview;
      let rLength = fieldItem.rules.length;
      // 原始日志没有规则的时候，规则默认为1
      if (fieldItem.is_origin && !fieldItem.rules.length) rLength = 1;
      if (preview?.length) {
        return (
          <div class='result-box'>
            {preview.map((pItem, pIndex) => {
              if (pIndex <= rLength - 1) {
                return (
                  <div class='preview-result'>
                    <span
                      class='old title-overflow'
                      v-bk-overflow-tips={{ delay: 500 }}
                    >
                      {pItem.origin}
                    </span>
                    <i class='bk-icon icon-arrows-right'></i>
                    <span
                      class='result title-overflow'
                      v-bk-overflow-tips={{ delay: 500 }}
                    >
                      {pItem.afterMasking}
                    </span>
                    {getMorePreviewNum(preview, rLength, pIndex)}
                  </div>
                );
              }
            })}
          </div>
        );
      }
      return (
        <div class='result-box'>
          <div class='preview-result'>{'-'}</div>
        </div>
      );
    };

    const getSyncNumDom = (fieldItem: IFieldItem) => {
      if (fieldItem?.is_origin && !this.isHiddenSyncNum) {
        return (
          <div class='preview-result sync-num'>
            <i18n
              class='sync-i18n'
              path='已同步 {0} 个脱敏结果'
            >
              <span>{this.getSyncNum}</span>
            </i18n>
            <i
              class='bk-icon icon-info-circle-shape'
              v-bk-tooltips={{
                content: this.$t('该字段为原文字段，为防止脱敏规则遗漏，系统已帮您自动同步其他脱敏结果'),
                width: 260,
              }}
            ></i>
          </div>
        );
      }
    };

    const getMorePreviewNum = (previewList, rLength: number, pIndex: number) => {
      if (previewList.length < rLength) return undefined;
      const showNum = previewList.length - rLength;
      const showPreviewList = previewList.slice(rLength);
      if (showNum > 0 && pIndex === rLength - 1)
        return (
          <Popover
            ext-cls='preview-prop'
            tippy-options={{
              placement: 'top',
              theme: 'light',
            }}
            max-width='400'
          >
            <div class='preview-excess-num'>{`+${previewList.length - rLength}`}</div>
            <div
              class='preview'
              slot='content'
            >
              {showPreviewList.map(pItem => (
                <div class='preview-result'>
                  <span
                    class='old title-overflow'
                    v-bk-overflow-tips={{ placement: 'top' }}
                  >
                    {pItem.origin}
                  </span>
                  <i class='bk-icon icon-arrows-right'></i>
                  <span
                    class='result title-overflow'
                    v-bk-overflow-tips={{ placement: 'top' }}
                  >
                    {pItem.afterMasking}
                  </span>
                </div>
              ))}
            </div>
          </Popover>
        );
      return undefined;
    };

    const maskingPreviewSlot = {
      default: ({ row }) => (
        <div
          class='masking-preview-box'
          v-bkloading={{ isLoading: this.isPreviewLoading && !this.previewLoadingField }}
        >
          {row.fieldList.map(item => (
            <div
              style={this.getFieldItemStyle(item)}
              class='preview'
              v-bkloading={{ isLoading: this.isPreviewLoading && this.previewLoadingField === row.field_name }}
              onMouseenter={() => this.handleHoverRow(item.field_name)}
              onMouseleave={() => this.handleLeaveRow()}
            >
              {getSyncNumDom(item)}
              {getPreviewDom(item)}
            </div>
          ))}
        </div>
      ),
    };

    return (
      <div class='masking-field'>
        {/* 采样日志输入框 */}
        <MaskingFieldInput
          index-set-id={this.collectData?.index_set_id}
          is-index-set-masking={this.isIndexSetMasking}
          operate-type={this.operateType}
          onBlurInput={({ list, isPreview }) => this.handleBlurConfigInput(list, isPreview)}
          onCreateRule={this.handleCreateRule}
        />
        <div class='item-container'>
          <div class='item-title'>
            <div class='left-item'>
              <span class='title'>{this.$t('字段脱敏')}</span>
            </div>
            <div class='right'>
              <Input
                class='search-input'
                v-model={this.searchStr}
                behavior='simplicity'
                placeholder={this.$t('搜索字段')}
                right-icon='bk-icon icon-search'
                clearable
                onChange={this.handleSearchChange}
                onEnter={this.searchField}
              ></Input>
              <Switcher
                v-model={this.previewSwitch}
                theme='primary'
              ></Switcher>
              <span>{this.$t('结果预览')}</span>
            </div>
          </div>
          <Table
            ext-cls={`masking-field-table ${this.isShowFieldClass ? 'is-show-field-class' : ''}`}
            v-bkloading={{ isLoading: this.tableLoading }}
            data={this.tableShowList}
            size='small'
          >
            <TableColumn
              key={'column_name'}
              label={this.$t('字段信息')}
              scopedSlots={fieldSlot}
            ></TableColumn>

            <TableColumn
              key={'match_method'}
              render-header={this.renderHeaderRule}
              scopedSlots={maskingRuleSlot}
            ></TableColumn>

            {this.previewSwitch && (
              <TableColumn
                key={'match_content'}
                render-header={this.renderHeaderPreview}
                scopedSlots={maskingPreviewSlot}
              ></TableColumn>
            )}

            <div slot='empty'>
              <EmptyStatus
                emptyType={this.emptyType}
                showText={!this.isShowConfigFiledEmptyTips}
                onOperation={this.handleOperation}
              >
                {this.isShowConfigFiledEmptyTips && (
                  <span>{this.$t('未检测到字段信息，请确认采集项是否已配置索引')}</span>
                )}
              </EmptyStatus>
            </div>
          </Table>
        </div>

        <Sideslider
          width={640}
          ext-cls={`${this.isMarginRight && 'open-add-rule-sideslider'}`}
          is-show={this.isShowRuleSideslider}
          title={this.$t('选择脱敏规则')}
          quick-close
          transfer
          {...{
            on: {
              'update:isShow': () => (this.isShowRuleSideslider = false),
            },
          }}
        >
          <div
            style='padding: 20px 24px 66px;'
            slot='content'
          >
            <MaskingSelectRuleTable
              submit-box-style={this.sidesliderSubmitBoxStyle}
              add-rule-field-value={this.addRuleFieldValue}
              default-select-rule-list={this.defaultSelectRuleList}
              is-public-list={false}
              recommend-rule-list={this.recommendRuleList}
              on-new-rule-state={state => (this.isMarginRight = state)}
              onCancel={() => (this.isShowRuleSideslider = false)}
              onSubmit={selectList => this.handleSelectRule(selectList)}
            />
          </div>
        </Sideslider>

        <Dialog
          width='640'
          ext-cls='rule-change-dialog'
          v-model={this.isShowRuleChangeDialog}
          mask-close={false}
          show-footer={false}
          title={this.$t('规则变更确认')}
        >
          <div class='rule-change-dialog-container'>
            <span class='rule-text'>
              {this.currentRuleState === 'delete'
                ? this.$t('当前规则【{n}】已被删除，请确认是否需要更换为新规则或忽略变更', {
                    n: this.currentOperateRule.rule_name,
                  })
                : this.$t(
                    '当前规则【{n}】已进行了变更，同步该规则可能会导致命中结果变更，请确认是否需要同步该变更或忽略，也可重新选择规则',
                    { n: this.currentOperateRule.rule_name },
                  )}
            </span>
            <div class={`rule-change-container rule-${this.currentRuleState}`}>
              {Object.entries(this.ruleDialogBoxValue).map(([ruleKey, ruleValue], ruleIndex) => (
                <div class='rule-box'>
                  <div class='title'>{this.ruleDialogI18nMap[ruleKey]}</div>
                  <div class={`rule-item-row row-${this.currentRuleState}`}>
                    {this.currentRuleState === 'delete' && ruleIndex === 1 ? (
                      <div class='delete-item'>{this.$t('已删除')}</div>
                    ) : (
                      Object.entries(ruleValue)
                        .filter(fItem => !!fItem[1])
                        .map(([matchKey, matchValue]) => (
                          <div class='item'>
                            <span class='key'>{this.ruleDialogI18nMap[matchKey]} :</span>
                            <span
                              class='value title-overflow'
                              v-bk-overflow-tips={{ delay: 500 }}
                            >
                              {this.htmlDecode(matchValue)}
                            </span>
                          </div>
                        ))
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div class='rule-button'>
              <Button
                theme='primary'
                onClick={() => this.handleClickLeftBtn()}
              >
                {this.currentRuleState === 'delete' ? this.$t('重新选择') : this.$t('同步')}
              </Button>
              <Button
                theme='default'
                onClick={() => this.handleClickRightBtn()}
              >
                {this.currentRuleState === 'delete' ? this.$t('同步') : this.$t('重新选择')}
              </Button>
              <Button
                theme='default'
                onClick={() => (this.isShowRuleChangeDialog = false)}
              >
                {this.$t('忽略')}
              </Button>
            </div>
          </div>
        </Dialog>

        <Dialog
          width='640'
          v-model={this.isShowResetRuleDialog}
          header-position='left'
          mask-close={false}
          render-directive='if'
          title={this.$t('选择脱敏规则')}
          on-confirm={this.handleResetSelectRule}
        >
          <div>
            <MaskingSelectRuleTable
              ref='syncRuleTable'
              prop-pagination={{
                limit: 6,
                limitList: [6, 12, 20],
              }}
              default-select-rule-list={this.defaultSelectRuleList}
              is-public-list={false}
              is-show-submit-content={false}
              is-sync-select={this.isShowResetRuleDialog}
              recommend-rule-list={this.recommendRuleList}
              table-max-height={366}
            />
          </div>
        </Dialog>
      </div>
    );
  }
}
