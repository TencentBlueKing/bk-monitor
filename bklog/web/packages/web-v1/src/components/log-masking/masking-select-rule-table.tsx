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

import { Component, Model, Emit, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Table, TableColumn, Input, Button, Checkbox } from 'bk-magic-vue';

import $http from '../../api';
import * as authorityMap from '../../common/authority-map';
import fingerSelectColumn from '../../views/retrieve/result-table-panel/log-clustering/components/finger-select-column.vue';
import EmptyStatus from '../empty-status/index.vue';
import MaskingAddRule from './masking-add-rule';

import './masking-select-rule-table.scss';

interface IProps {
  value: boolean;
}

interface IAddRuleFieldValue {
  field: string;
  fieldLog: string;
}

@Component
export default class MaskingSelectRuleTable extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ type: Number, default: Number.NaN }) tableMaxHeight: number;
  @Prop({ type: Object, default: () => ({}) }) submitBoxStyle: object;
  @Prop({ type: Boolean, default: true }) isShowSubmitContent: boolean;
  @Prop({ type: Boolean, default: false }) isSyncSelect: boolean;
  @Prop({ type: Array, default: () => [] }) defaultSelectRuleList: number[];
  @Prop({ type: Array, default: () => [] }) recommendRuleList: number[];
  @Prop({ type: Object, default: () => ({}) }) propPagination: object;
  @Prop({ type: Boolean, default: true }) isPublicList: boolean;
  @Prop({
    type: Object,
    default: () => ({
      field: '',
      fieldLog: '',
    }),
  })
  addRuleFieldValue: IAddRuleFieldValue;
  @Ref('orderTips') orderTipsRef: HTMLElement;

  searchStr = '';
  selectList = [];
  checkValue = 0; // 0 , 1 , 2分别表示未选  半选  全选

  syncSelectRuleID = -1;

  pagination = {
    /** 当前页数 */
    current: 1,
    /** 总数 */
    count: 0,
    /** 每页显示数量 */
    limit: 10,
    small: true,
    limitList: [10, 20, 50, 100],
  };

  operatorMap = {
    mask_shield: window.mainComponent.$t('掩码'),
    text_replace: window.mainComponent.$t('替换'),
  };

  emptyType = 'empty';

  tableList = [];

  tableShowList = [];

  tableSearchList = [];

  tableStrList = [];

  tableLoading = false;

  isShowMaskingAddRule = false;

  isAllowed = false;

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get authorityData() {
    return {
      action_ids: [authorityMap.MANAGE_DESENSITIZE_RULE],
      resources: [
        {
          type: 'space',
          id: this.spaceUid,
        },
      ],
    };
  }

  @Watch('selectList.length')
  watchSelectList(newLength) {
    this.changeCheckValue(newLength);
  }

  @Emit('change')
  hiddenSlider() {
    return false;
  }

  @Watch('isShowMaskingAddRule')
  watchIsShowMaskingAddRule(value: boolean) {
    this.emitNewRuleSidesliderState(value);
  }

  @Watch('isSyncSelect')
  async watchSyncSelect(val: boolean) {
    if (val) {
      Object.assign(this.pagination, this.propPagination);
      await this.initTableList();
    }
  }

  @Emit('new-rule-state')
  emitNewRuleSidesliderState(value: boolean) {
    return value;
  }

  @Emit('submit')
  submitSelectRule() {
    this.syncSelectRuleID = -1;
    return this.tableList.filter(item => this.selectList.includes(item.id));
  }

  @Emit('cancel')
  cancelSelectRule() {}

  async created() {
    Object.assign(this.pagination, this.propPagination);
    await this.initTableList();
  }

  getSyncSelectRule() {
    return this.tableList.find(item => this.syncSelectRuleID === item.id);
  }

  async handleAddNewRule() {
    if (!this.isAllowed) {
      try {
        const res = await this.$store.dispatch('getApplyData', this.authorityData);
        this.$store.commit('updateState', { 'authDialogData': res.data});
      } catch (err) {
        console.warn(err);
      }
      return;
    }
    this.isShowMaskingAddRule = true;
  }

  handleSelectItem(state, ruleID) {
    if (this.isSyncSelect) {
      this.syncSelectRuleID = state ? ruleID : -1;
      return;
    }
    if (state) {
      this.selectList.push(ruleID);
    } else {
      const index = this.selectList.indexOf(ruleID);
      this.selectList.splice(index, 1);
    }
  }

  handleSelectAllItem(val: boolean) {
    this.selectList = val ? this.tableShowList.map(item => item.id) : [];
  }

  /**
   * @desc: 获取脱敏规则字符串
   * @param {IRuleItem} item 脱敏规则参数
   * @returns {String} 返回脱敏规则字符串
   */
  getMaskingRuleStr(item) {
    const endStr =
      item?.operator === 'text_replace'
        ? `${this.$t('替换为')} ${item?.params?.template_string}`
        : this.$t('保留前{0}位, 后{1}位', {
            0: item?.params?.preserve_head,
            1: item?.params?.preserve_tail,
          });
    return `${this.operatorMap[item?.operator]} | ${endStr}`;
  }

  async initTableList(newRuleId = -1) {
    try {
      this.tableLoading = true;
      let params = {}; // 如果要获取全局列表 params为空 不传业务id
      params = { space_uid: this.spaceUid, rule_type: 'all' }; // 非全局列表 传业务id
      const authorityRes = await this.$store.dispatch('checkAndGetData', this.authorityData);
      this.isAllowed = authorityRes.isAllowed;
      const res = await $http.request('masking/getMaskingRuleList', {
        params,
      });
      const selectList: any[] = [];
      const otherList: any[] = [];
      const activeRule = res.data.filter(item => item.is_active);
      for (const item of activeRule) {
        // 给推荐规则排序
        this.recommendRuleList.includes(item.id) ? selectList.push(item) : otherList.push(item);
      }
      // 全局规则优先排序
      otherList.sort((_a, b) => (b.is_public ? 1 : -1));

      // 给当前选中了的规则排序到前面
      if (this.defaultSelectRuleList.length) {
        otherList.sort((_a, b) => (this.defaultSelectRuleList.includes(b.id) || b.is_public ? 1 : -1));
      }

      // 新增规则 把新的规则变绿
      if (newRuleId >= 0) {
        otherList.sort((_a, b) => (newRuleId === b.id ? 1 : -1));
        otherList[0].is_add = true;
        !this.isSyncSelect && this.defaultSelectRuleList.push(otherList[0].id);
      }

      this.selectList = this.defaultSelectRuleList;
      // 判断当前是否是同步重新选择列表，将展示不同的顺序
      this.tableList = selectList.concat(otherList);
      if (this.isSyncSelect) {
        // 如果是重选或同步的列表 直接去除掉之前选中过的规则
        this.tableList = this.tableList.filter(tItem => !this.defaultSelectRuleList.includes(tItem.id));
      }
      this.tableStrList = this.tableList.map(item => item.rule_name);
      this.tableSearchList = structuredClone(this.tableList);
      this.tableShowList = this.tableSearchList.slice(0, this.pagination.limit);
      this.changePagination({
        current: 1,
        count: this.tableSearchList.length,
      });
      this.emptyType = 'empty';
      this.searchStr = '';
    } catch {
      this.emptyType = '500';
    } finally {
      this.tableLoading = false;
    }
  }

  renderHeaderCheckBox(h) {
    return h(fingerSelectColumn, {
      props: {
        value: this.checkValue,
        disabled: this.isSyncSelect,
      },
      on: {
        change: this.handleSelectAllItem,
      },
    });
  }

  getCheckBoxDisable(ruleID: number) {
    if (!this.isSyncSelect) {
      return false;
    }
    // 当前是同步重新选择选择列表 旧的规则禁用
    if (this.defaultSelectRuleList.includes(ruleID)) {
      return true;
    }
    // 当前未选同步规则 或者选中同步规则 取消禁用
    if (this.syncSelectRuleID === -1 || this.syncSelectRuleID === ruleID) {
      return false;
    }
    // 已选同步规则 单选禁用其他规则
    return true;
  }

  getItemChecked(ruleID) {
    return this.selectList.includes(ruleID);
  }

  searchRule() {
    this.tableSearchList = this.tableList.filter(item =>
      item.rule_name.toString().toLowerCase().includes(this.searchStr.toLowerCase()),
    );
    this.pageLimitChange(this.pagination.limit);
    this.selectList = this.tableSearchList.filter(v => this.selectList.includes(v.id)).map(item => item.id);
    this.changeCheckValue(this.selectList.length);
    this.emptyType = 'search-empty';
  }

  handleSearchChange(val) {
    if (val === '' && !this.tableLoading) {
      this.emptyType = 'empty';
      this.tableSearchList = structuredClone(this.tableList);
      this.pageLimitChange(this.pagination.limit);
      this.changeCheckValue(this.selectList.length);
    }
  }

  handleOperation(type: string) {
    if (type === 'clear-filter') {
      this.searchStr = '';
      this.handleSearchChange('');
      return;
    }

    if (type === 'refresh') {
      this.initTableList();
      return;
    }
  }

  changeCheckValue(newLength) {
    // 单选时直接显示未选
    if (this.isSyncSelect) {
      return 0;
    }
    // 根据手动选择列表长度来判断全选框显示 全选 半选 不选
    if (!newLength) {
      this.checkValue = 0;
      return;
    }
    if (newLength && newLength !== this.tableShowList.length) {
      this.checkValue = 1;
    } else {
      this.checkValue = 2;
    }
  }

  pageChange(newPage: number) {
    const { limit } = this.pagination;
    const startIndex = (newPage - 1) * limit;
    const endIndex = newPage * limit;
    this.tableShowList = this.tableSearchList.slice(startIndex, endIndex);
    this.changePagination({
      current: newPage,
    });
  }

  pageLimitChange(limit: number) {
    this.tableShowList = this.tableSearchList.slice(0, limit);
    this.changePagination({
      limit,
      current: 1,
      count: this.tableSearchList.length,
    });
  }

  changePagination(pagination = {}) {
    Object.assign(this.pagination, pagination);
  }

  getMatchMethodStr(row) {
    if (row.match_fields.length && row.match_pattern) {
      return this.$t('字段+正则匹配');
    }
    if (row.match_fields.length) {
      return this.$t('字段匹配');
    }
    return this.$t('正则匹配');
  }

  getMatchContentStr(row) {
    if (row.match_fields.length && row.match_pattern) {
      return `${row.match_fields.join(', ')} ${this.$t('且')} ${row.match_pattern}`;
    }
    if (row.match_fields.length) {
      return row.match_fields.join(', ');
    }
    return row.match_pattern;
  }

  getShowRowStyle(rowObj: any) {
    if (rowObj.row.is_add) {
      return { background: '#F2FFF4' };
    }
    return { background: this.recommendRuleList.includes(rowObj.row.id) ? '#F0F5FF' : '#FFF' };
  }

  render() {
    const ruleNameSlot = {
      default: ({ row }) => (
        <div class='rule-name-box'>
          <span
            class='title-overflow'
            v-bk-overflow-tips
          >
            {row.rule_name}
          </span>
          {row.is_public && <span class='tag global'>{this.$t('全局')}</span>}
          {row.is_add && <span class='tag new'>{'New'}</span>}
        </div>
      ),
    };

    const matchingMethodSlot = {
      default: ({ row }) => (
        <div class='rule-name-box'>
          <span
            class='title-overflow'
            v-bk-overflow-tips
          >
            {this.getMatchMethodStr(row)}
          </span>
        </div>
      ),
    };

    const matchingContentSlot = {
      default: ({ row }) => (
        <div class='rule-name-box'>
          <span
            class='title-overflow'
            v-bk-overflow-tips
          >
            {this.getMatchContentStr(row)}
          </span>
        </div>
      ),
    };

    const maskingRulesSlot = {
      default: ({ row }) => (
        <div class='rule-name-box'>
          <span
            class='title-overflow'
            v-bk-overflow-tips
          >
            {this.getMaskingRuleStr(row)}
          </span>
        </div>
      ),
    };

    const checkBoxSlot = {
      default: ({ row }) => (
        <Checkbox
          checked={this.getItemChecked(row.id)}
          disabled={this.getCheckBoxDisable(row.id)}
          onChange={(val: boolean) => this.handleSelectItem(val, row.id)}
        />
      ),
    };
    return (
      <div class='masking-select-rule-table'>
        <div class='input-box'>
          <Button
            class='new-rule-btn'
            v-cursor={{ active: !this.isAllowed }}
            theme='primary'
            outline
            onClick={() => this.handleAddNewRule()}
          >
            <i class='bk-icon icon-plus push' />
            {this.$t('新建规则')}
          </Button>
          <div class='right-box'>
            <Input
              class='search-input'
              v-model={this.searchStr}
              right-icon='bk-icon icon-search'
              onChange={this.handleSearchChange}
              onEnter={this.searchRule}
            />
            <Button
              class='refresh-btn'
              v-bk-tooltips={this.$t('刷新')}
              onClick={() => this.initTableList()}
            >
              <i class='icon bk-icon icon-right-turn-line' />
            </Button>
          </div>
        </div>

        <Table
          row-style={this.getShowRowStyle}
          v-bkloading={{ isLoading: this.tableLoading }}
          data={this.tableShowList}
          header-border={false}
          max-height={this.tableMaxHeight}
          outer-border={false}
          pagination={this.pagination}
          render-directive='if'
          size='small'
          on-page-change={this.pageChange}
          on-page-limit-change={this.pageLimitChange}
        >
          <TableColumn
            width='50'
            render-header={this.renderHeaderCheckBox}
            scopedSlots={checkBoxSlot}
          />

          <TableColumn
            key={'rule_name'}
            label={this.$t('规则名称')}
            scopedSlots={ruleNameSlot}
          />

          <TableColumn
            key={'match_method'}
            label={this.$t('匹配方式')}
            scopedSlots={matchingMethodSlot}
          />

          <TableColumn
            key={'match_content'}
            label={this.$t('匹配内容')}
            scopedSlots={matchingContentSlot}
          />

          <TableColumn
            key={'masking_result'}
            label={this.$t('脱敏算子')}
            scopedSlots={maskingRulesSlot}
          />

          <div slot='empty'>
            <EmptyStatus
              emptyType={this.emptyType}
              onOperation={this.handleOperation}
            />
          </div>
        </Table>

        {this.isShowSubmitContent && (
          <div
            style={{ ...this.submitBoxStyle }}
            class='submit-content'
          >
            <Button
              theme='primary'
              onClick={() => this.submitSelectRule()}
            >
              {this.$t('确定')}
            </Button>
            <Button
              theme='default'
              onClick={() => this.cancelSelectRule()}
            >
              {this.$t('取消')}
            </Button>
          </div>
        )}

        <MaskingAddRule
          v-model={this.isShowMaskingAddRule}
          add-rule-field-value={this.addRuleFieldValue}
          is-public-rule={this.isPublicList}
          table-str-list={this.tableStrList}
          on-submit-rule={(value: any) => value && this.initTableList(value.id)}
        />
      </div>
    );
  }
}
