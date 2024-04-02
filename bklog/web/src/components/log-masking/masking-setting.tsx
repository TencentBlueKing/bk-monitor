/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import { Component, Prop } from 'vue-property-decorator';
import { Alert, Button, Input, Table, TableColumn, Tag, Switcher, TableSettingContent, Dialog } from 'bk-magic-vue';

import MaskingAddRule from './masking-add-rule';
import './masking-setting.scss';
import $http from '../../api';
import EmptyStatus from '../empty-status/index.vue';
import { deepClone, utcFormatDate } from '../../common/util';
import i18n from '../../language/i18n';
import * as authorityMap from '../../common/authority-map';

interface IProps {
  isPublicList: boolean;
}

interface IEditAccessValue {
  accessNum: number;
  accessInfo: Array<any>;
}

const settingFields = [
  // 设置显示的字段
  {
    id: 'ruleName',
    label: i18n.t('规则名称'),
    disabled: true
  },
  {
    id: 'matchFields',
    label: i18n.t('匹配字段名')
    // disabled: true,
  },
  {
    id: 'matchPattern',
    label: i18n.t('匹配正则表达式')
  },
  {
    id: 'maskingRules',
    label: (i18n.t('label-脱敏算子') as String).replace('label-', '')
  },
  {
    id: 'accessNum',
    label: i18n.t('接入项')
  },
  {
    id: 'isActive',
    label: i18n.t('启/停')
  },
  {
    id: 'updatedBy',
    label: i18n.t('变更人')
  },
  {
    id: 'updatedAt',
    label: i18n.t('变更时间')
  }
];

@Component
export default class MaskingSetting extends tsc<IProps> {
  @Prop({ type: Boolean, default: true }) isPublicList: boolean;

  /** 规则搜索字符串 */
  searchStr = '';

  /** 表格加载状态 */
  tableLoading = false;

  /** 接入表格加载状态 */
  accessTableLoading = false;

  /** 是否显示接入对话框 */
  isShowAccessDialog = false;

  /** 是否显示停止或删除接入对话框 */
  isShowStopOrDeleteAccessDialog = false;

  /** 是否是删除规则 */
  isDeleteRule = false;

  /** 是否展示新建规则侧边栏 */
  isShowMaskingAddRule = false;

  /** 编辑ID */
  editRuleID = 0;

  /** 是否是编辑规则 */
  isEdit = false;

  /** 停用启用删除的规则id */
  changeRuleID = -1;

  emptyType = 'empty';

  /** 接入项表格列表 */
  stopOrStartAccessValue: IEditAccessValue = {
    accessNum: 0,
    accessInfo: [
      {
        scenario_id: '',
        /** 来源 */
        scenario_name: '',
        /** 接入文本 */
        ids: ''
      }
    ]
  };

  /** 编辑项的接入项表格列表 */
  editAccessValue: IEditAccessValue = {
    accessNum: 0,
    accessInfo: [
      {
        scenario_id: '',
        /** 来源 */
        scenario_name: '',
        /** 接入文本 */
        ids: ''
      }
    ]
  };

  operatorMap = {
    mask_shield: window.mainComponent.$t('掩码'),
    text_replace: window.mainComponent.$t('替换')
  };

  operatorFilters = [
    { text: window.mainComponent.$t('掩码'), value: 'mask_shield' },
    { text: window.mainComponent.$t('替换'), value: 'text_replace' }
  ];

  scenarioRouteMap = {
    log: 'collection-item',
    bkdata: 'bkdata-index-set-list',
    es: 'es-index-set-list',
    index_set: 'log-index-set-list',
    log_custom: 'custom-report'
  };

  tableSetting = {
    fields: settingFields,
    selectedFields: settingFields.slice(0, 6)
    // size: 'small',
  };

  updateSourceFilters = []; // 更变人过滤数组

  /** 规则表格列表 */
  tableList = [
    {
      /** ID */
      id: 1,
      /** 名称 */
      ruleName: '',
      /** 字段名称 */
      matchFields: [],
      /** 表达式 */
      matchPattern: '',
      /** 接入文本 */
      accessNum: '0',
      accessInfo: [],
      operator: 'text_replace',
      operatorParams: {
        preserve_head: 0,
        preserve_tail: 0,
        replace_mark: '*'
      },
      /** 开关状态 */
      isActive: true,
      isPublic: false
    }
  ];

  tableShowList = [];

  tableSearchList = [];

  tableStrList = [];

  /** 分页信息 */
  pagination = {
    /** 当前页数 */
    current: 1,
    /** 总数 */
    count: 0,
    /** 每页显示数量 */
    limit: 10,
    /** 每页显示数量列表 */
    limitList: [10, 20, 50, 100]
  };

  /** 是否有脱敏权限 */
  isAllowed = false;

  enTableWidth = {
    ruleName: '166',
    matchFields: '240',
    maskingRules: '210',
    accessNum: '125',
    isActive: '95',
    operate: '80'
  };

  cnTableWidth = {
    ruleName: '166',
    matchFields: '240',
    maskingRules: '210',
    accessNum: '95',
    isActive: '75',
    operate: '68'
  };

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get getTableWidth() {
    return this.$store.getters.isEnLanguage ? this.enTableWidth : this.cnTableWidth;
  }

  get authorityData() {
    return this.isPublicList
      ? {
          action_ids: [authorityMap.MANAGE_GLOBAL_DESENSITIZE_RULE]
        }
      : {
          action_ids: [authorityMap.MANAGE_DESENSITIZE_RULE],
          resources: [
            {
              type: 'space',
              id: this.spaceUid
            }
          ]
        };
  }

  created() {
    this.initTableList();
  }

  async initTableList() {
    try {
      this.tableLoading = true;
      const params = { space_uid: this.spaceUid, rule_type: this.isPublicList ? 'public' : 'all' }; // 非全局列表 传业务id
      const authorityRes = await this.$store.dispatch('checkAndGetData', this.authorityData);
      this.isAllowed = authorityRes.isAllowed;
      const res = await $http.request('masking/getMaskingRuleList', {
        params
      });
      const updateSourceFiltersSet = new Set();
      this.tableList = res.data
        .map(item => {
          if (!updateSourceFiltersSet.has(item.updated_by)) updateSourceFiltersSet.add(item.updated_by);
          return {
            id: item.id,
            ruleName: item.rule_name,
            matchFields: item.match_fields,
            matchPattern: item.match_pattern,
            accessNum: item.access_num,
            accessInfo: item.access_info,
            operator: item.operator,
            params: item.params,
            isActive: item.is_active,
            isPublic: item.is_public,
            updatedBy: item.updated_by,
            updatedAt: item.updated_at
          };
        })
        .sort((a, b) => (b.isPublic ? 1 : -1));
      this.tableStrList = this.tableList.map(item => item.ruleName);
      this.tableSearchList = deepClone(this.tableList);
      this.tableShowList = this.tableSearchList.slice(0, this.pagination.limit);
      this.changePagination({
        current: 1,
        count: this.tableSearchList.length
      });

      this.updateSourceFilters = [...updateSourceFiltersSet].map(item => ({
        text: item,
        value: item
      }));
      this.emptyType = 'empty';
    } catch (err) {
      this.emptyType = '500';
    } finally {
      this.tableLoading = false;
    }
  }

  changePagination(pagination = {}) {
    Object.assign(this.pagination, pagination);
  }

  handleClickAccess(row) {
    this.stopOrStartAccessValue.accessInfo = row.accessInfo;
    this.isShowAccessDialog = true;
  }

  /**
   * @desc: 编辑规则
   * @param {Any} row
   */
  handleEditRule(row) {
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.editRuleID = row.id;
    this.isEdit = true;
    this.editAccessValue = {
      accessNum: row.accessNum,
      accessInfo: row.accessInfo
    };
    this.isShowMaskingAddRule = true;
  }

  /**
   * @desc: 删除规则
   * @param {Any} row
   */
  async handleDeleteRule(row) {
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.isDeleteRule = true;
    this.changeRuleID = row.id;
    this.stopOrStartAccessValue = {
      accessNum: row.accessNum,
      accessInfo: row.accessInfo
    };
    if (row.accessNum) {
      // 当前是启用状态  并且接入项不为0的时候  执行展示删除弹窗
      this.isShowStopOrDeleteAccessDialog = true;
    } else {
      // 接入项为0 直接删除
      const res = await $http.request('masking/deleteRule', {
        params: { rule_id: this.changeRuleID }
      });
      if (res.result) this.initTableList();
    }
  }

  /**
   * @desc: 点击停启规则开关
   * @param {Any} row
   */
  async handleChangeRuleSwitch(row) {
    if (this.isDisabledClick(row)) return;
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.changeRuleID = row.id;
    if (row.isActive) {
      // 当前是启用状态
      this.isDeleteRule = false;
      this.stopOrStartAccessValue = {
        accessNum: row.accessNum,
        accessInfo: row.accessInfo
      };
      if (row.accessNum) {
        // 当前是启用状态  并且接入项不为0的时候  执行展示删除弹窗
        this.isShowStopOrDeleteAccessDialog = true;
      } else {
        // 接入项为0 直接停用
        const res = await this.requestStopOrStartRule(row.id, 'stop');
        // 这里如果直接请求新的接口会 后端会返回不同
        if (res.result) {
          this.handleChangeTableListValue(row.id, tItem => (tItem.isActive = false));
          this.$bkMessage({
            message: this.$t('操作成功'),
            theme: 'success'
          });
        }
      }
      return;
    }
    const res = await this.requestStopOrStartRule(row.id, 'start');
    if (res.result) {
      this.handleChangeTableListValue(row.id, tItem => (tItem.isActive = true));
      this.$bkMessage({
        message: this.$t('操作成功'),
        theme: 'success'
      });
    }
  }
  handleChangeTableListValue(changeTableID: number, callback: Function, list = [this.tableSearchList, this.tableList]) {
    list.forEach(lItem => {
      lItem.forEach(item => {
        if (item.id === changeTableID) {
          callback(item);
        }
      });
    });
  }
  /**
   * @desc: 停删规则弹窗确认按钮
   * @param {Any} row
   */
  async handleStopOrDeleteRule() {
    try {
      if (this.isDeleteRule) {
        const res = await $http.request('masking/deleteRule', {
          params: { rule_id: this.changeRuleID }
        });
        if (res.result) this.initTableList();
      } else {
        const res = await this.requestStopOrStartRule(this.changeRuleID, 'stop');
        if (res.result) this.initTableList();
      }
    } catch (error) {
    } finally {
      this.isShowStopOrDeleteAccessDialog = false;
    }
  }

  getShowRowStyle(row: any) {
    return { background: (row.rowIndex + 1) % 2 === 0 ? '#F5F7FA' : '#FFF' };
  }

  isDisabledClick(row) {
    return !this.isPublicList && row.isPublic;
  }

  /**
   * @desc: 接入项跳转
   * @param {Any} row
   */
  handleJumpAccess(row) {
    const setList = new Set(row.ids);
    const idList = [...setList].join(',');
    const { href } = this.$router.resolve({
      name: this.scenarioRouteMap[row.scenario_id],
      query: {
        ids: encodeURIComponent(idList),
        spaceUid: this.spaceUid
      }
    });
    window.open(href, '_blank');
  }

  handleCreateRule() {
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.isShowMaskingAddRule = true;
    this.isEdit = false;
  }

  handleSearchChange(val) {
    if (val === '' && !this.tableLoading) {
      this.emptyType = 'empty';
      this.tableSearchList = deepClone(this.tableList);
      this.pageLimitChange(10);
    }
  }

  searchRule() {
    this.tableSearchList = this.tableList.filter(item =>
      item.ruleName.toString().toLowerCase().includes(this.searchStr.toLowerCase())
    );
    this.pageLimitChange(10);
    this.emptyType = 'search-empty';
  }

  pageChange(newPage: number) {
    const { limit } = this.pagination;
    const startIndex = (newPage - 1) * limit;
    const endIndex = newPage * limit;
    this.tableShowList = this.tableSearchList.slice(startIndex, endIndex);
    this.changePagination({
      current: newPage
    });
  }

  pageLimitChange(limit: number) {
    this.tableShowList = this.tableSearchList.slice(0, limit);
    this.changePagination({
      limit,
      current: 1,
      count: this.tableSearchList.length
    });
  }

  async requestStopOrStartRule(ruleID: number, status: string) {
    const requestStr = status === 'start' ? 'startDesensitize' : 'stopDesensitize';
    return await $http.request(`masking/${requestStr}`, {
      params: { rule_id: ruleID }
    });
  }

  handleOperation(type) {
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

  operatorFilterMethod(value, row, column) {
    const property = column.property;
    return row[property] === value;
  }

  handleSettingChange({ fields, size }) {
    this.tableSetting.selectedFields = fields;
    this.tableSetting.size = size;
  }

  checkFields(field) {
    return this.tableSetting.selectedFields.some(item => item.id === field);
  }

  /** 所属组和变更人分组操作 */
  sourceFilterMethod(value, row, column) {
    const property = column.property;
    return row[property] === value;
  }

  /** 申请权限 */
  async getOptionApplyData() {
    try {
      const res = await this.$store.dispatch('getApplyData', this.authorityData);
      this.$store.commit('updateAuthDialogData', res.data);
    } catch (err) {
      console.warn(err);
    }
  }

  render() {
    const ruleNameSlot = {
      default: ({ row }) => (
        <div class='rule-name-box'>
          <span
            class='title-overflow'
            v-bk-overflow-tips
          >
            {row.ruleName}
          </span>
          {row.isPublic && !this.isPublicList && <span class='tag global'>{this.$t('全局')}</span>}
        </div>
      )
    };

    /** 匹配字段名插槽 */
    const matchFieldNameSlot = {
      default: ({ row }) => (
        <div
          class='title-overflow'
          v-bk-overflow-tips={{
            content: row.matchFields.join(' , ')
          }}
        >
          {row.matchFields.length ? (
            row.matchFields.map(item => <Tag>{item}</Tag>)
          ) : (
            <span style='padding-left: 10px;'>{'-'}</span>
          )}
        </div>
      )
    };

    const matchExpressionSlot = {
      default: ({ row }) => (
        <div
          class='title-overflow'
          v-bk-overflow-tips
        >
          <span>{row.matchPattern || '-'}</span>
        </div>
      )
    };

    const maskingRuleSlot = {
      default: ({ row }) => (
        <div
          class='title-overflow'
          v-bk-overflow-tips
        >
          <span>{`${this.operatorMap[row.operator]} | `}</span>
          {row.operator === 'text_replace' ? (
            <span>
              {' '}
              {this.$t('替换为')} {row.params.template_string}
            </span>
          ) : (
            <span>
              {' '}
              {this.$t('保留前{0}位, 后{1}位', {
                0: row?.params?.preserve_head,
                1: row?.params?.preserve_tail
              })}
            </span>
          )}
        </div>
      )
    };

    /** 接入项插槽 */
    const accessItemSlot = {
      default: ({ row }) => (
        <Button
          text
          onClick={() => this.handleClickAccess(row)}
        >
          {row.accessNum}
        </Button>
      )
    };

    const switcherSlot = {
      default: ({ row }) => (
        <div
          v-cursor={{ active: !this.isAllowed }}
          onClick={() => this.handleChangeRuleSwitch(row)}
        >
          <Switcher
            size='small'
            v-model={row.isActive}
            disabled={this.isDisabledClick(row)}
            pre-check={() => false}
            theme='primary'
          />
        </div>
      )
    };

    const operatorSlot = {
      default: ({ row }) => (
        <div class='operator-slot'>
          <Button
            text
            v-cursor={{ active: !this.isAllowed }}
            disabled={this.isDisabledClick(row)}
            onClick={() => this.handleEditRule(row)}
          >
            {this.$t('编辑')}
          </Button>
          <Button
            text
            v-cursor={{ active: !this.isAllowed }}
            disabled={this.isDisabledClick(row)}
            onClick={() => this.handleDeleteRule(row)}
          >
            {this.$t('删除')}
          </Button>
        </div>
      )
    };

    const accessTableSlot = () => (
      <Table
        data={this.stopOrStartAccessValue.accessInfo}
        v-bkloading={{ isLoading: this.accessTableLoading }}
        border={false}
        outer-border={false}
        header-border={false}
        row-border={false}
        col-border={false}
        ext-cls='access-table'
        row-style={this.getShowRowStyle}
      >
        <TableColumn
          label={this.$t('日志来源')}
          key={'scenario_name'}
          prop={'scenario_name'}
        ></TableColumn>

        <TableColumn
          sortable
          label={this.$t('接入项')}
          width='125'
          key={'ids'}
          prop={'ids'}
          align='center'
          scopedSlots={{
            default: ({ row }) => (
              <Button
                text
                onClick={() => this.handleJumpAccess(row)}
              >
                {row.ids.length}
              </Button>
            )
          }}
        ></TableColumn>
      </Table>
    );

    return (
      <div class='masking-table-container'>
        <Alert
          class='top-alert'
          type='info'
          title={this.$t(
            '脱敏规则会应用到本业务全部索引集。为保证脱敏规则效力，配置规则后，需针对计算平台索引集、第三方ES索引集进行手动校准指定，校准后索引集恢复可用状态。'
          )}
          closable
        />

        <div class='search-box'>
          <Button
            v-cursor={{ active: !this.isAllowed }}
            theme='primary'
            onClick={this.handleCreateRule}
          >
            {this.$t('新建规则')}
          </Button>
          <Input
            v-model={this.searchStr}
            right-icon='bk-icon icon-search'
            placeholder={this.$t('请输入脱敏规则')}
            onEnter={this.searchRule}
            onChange={this.handleSearchChange}
          />
        </div>

        <Table
          data={this.tableShowList}
          size='small'
          render-directive='if'
          pagination={this.pagination}
          v-bkloading={{ isLoading: this.tableLoading }}
          on-page-change={this.pageChange}
          on-page-limit-change={this.pageLimitChange}
        >
          <TableColumn
            label={this.$t('规则名称')}
            width={this.getTableWidth.ruleName}
            key={'ruleName'}
            render-header={this.$renderHeader}
            scopedSlots={ruleNameSlot}
          ></TableColumn>

          {this.checkFields('matchFields') ? (
            <TableColumn
              label={this.$t('匹配字段名')}
              width={this.getTableWidth.matchFields}
              key={'matchFields'}
              render-header={this.$renderHeader}
              scopedSlots={matchFieldNameSlot}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('matchPattern') ? (
            <TableColumn
              label={this.$t('匹配正则表达式')}
              key={'matchPattern'}
              scopedSlots={matchExpressionSlot}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('maskingRules') ? (
            <TableColumn
              label={(this.$t('label-脱敏算子') as String).replace('label-', '')}
              width={this.getTableWidth.maskingRules}
              key={'maskingRules'}
              prop='operator'
              render-header={this.$renderHeader}
              filters={this.operatorFilters}
              filter-method={this.operatorFilterMethod}
              filter-multiple={false}
              scopedSlots={maskingRuleSlot}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('accessNum') ? (
            <TableColumn
              label={this.$t('接入项')}
              width={this.getTableWidth.accessNum}
              render-header={this.$renderHeader}
              align='center'
              key={'accessNum'}
              prop='accessNum'
              sortable
              scopedSlots={accessItemSlot}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('updatedBy') ? (
            <TableColumn
              label={this.$t('变更人')}
              render-header={this.$renderHeader}
              prop={'updatedBy'}
              key={'updatedBy'}
              scopedSlots={{
                default: ({ row }) => [
                  <span
                    class='overflow-tips'
                    v-bk-overflow-tips
                  >
                    {row.updatedBy}
                  </span>
                ]
              }}
              filters={this.updateSourceFilters}
              filter-multiple={false}
              filter-method={this.sourceFilterMethod}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('updatedAt') ? (
            <TableColumn
              label={this.$t('变更时间')}
              render-header={this.$renderHeader}
              prop={'updatedAt'}
              key={'updatedAt'}
              scopedSlots={{
                default: ({ row }) => [
                  <span
                    class='overflow-tips'
                    v-bk-overflow-tips
                  >
                    {utcFormatDate(row.updatedAt)}
                  </span>
                ]
              }}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('isActive') ? (
            <TableColumn
              label={this.$t('启/停')}
              width={this.getTableWidth.isActive}
              key={'isActive'}
              align='center'
              scopedSlots={switcherSlot}
            ></TableColumn>
          ) : undefined}

          <TableColumn
            label={this.$t('操作')}
            width={this.getTableWidth.operate}
            key={'operate'}
            scopedSlots={operatorSlot}
          ></TableColumn>

          <TableColumn type='setting'>
            <TableSettingContent
              v-en-style='width: 580px;'
              // key={`${this.tableKey}__settings`}
              fields={this.tableSetting.fields}
              selected={this.tableSetting.selectedFields}
              on-setting-change={this.handleSettingChange}
            ></TableSettingContent>
          </TableColumn>

          <div slot='empty'>
            <EmptyStatus
              emptyType={this.emptyType}
              onOperation={this.handleOperation}
            />
          </div>
        </Table>

        <Dialog
          v-model={this.isShowAccessDialog}
          title={this.$t('接入项详情')}
          width='480'
          render-directive='if'
          header-position='left'
          show-footer={false}
        >
          {accessTableSlot()}
        </Dialog>

        <Dialog
          v-model={this.isShowStopOrDeleteAccessDialog}
          width='400'
          render-directive='if'
          show-footer={false}
        >
          <div class='delete-dialog-container'>
            <span class='delete-title'>
              {this.$t('确认{n}该规则？', { n: this.isDeleteRule ? this.$t('删除') : this.$t('停用') })}
            </span>
            <span class='delete-text'>
              {this.$t('当前脱敏规则被应用{n}次，如停用/删除，将无法选用该规则，请确认是否{v}。', {
                v: this.isDeleteRule ? this.$t('删除') : this.$t('停用'),
                n: this.stopOrStartAccessValue.accessNum
              })}
            </span>
            {accessTableSlot()}
            <div class='delete-button'>
              <Button
                theme='danger'
                onClick={() => this.handleStopOrDeleteRule()}
              >
                {this.isDeleteRule ? this.$t('删除') : this.$t('停用')}
              </Button>
              <Button
                theme='default'
                onClick={() => (this.isShowStopOrDeleteAccessDialog = false)}
              >
                {this.$t('取消')}
              </Button>
            </div>
          </div>
        </Dialog>

        <MaskingAddRule
          v-model={this.isShowMaskingAddRule}
          is-public-rule={this.isPublicList}
          ruleID={this.editRuleID}
          is-edit={this.isEdit}
          table-str-list={this.tableStrList}
          edit-access-value={this.editAccessValue}
          on-submit-rule={(value: object) => value && this.initTableList()}
        />
      </div>
    );
  }
}
