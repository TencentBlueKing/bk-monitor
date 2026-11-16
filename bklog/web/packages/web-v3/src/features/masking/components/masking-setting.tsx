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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { Alert as Alert, Tag as Tag } from 'tdesign-vue-next';

import { Switch as Switcher } from 'tdesign-vue-next';

import { MessagePlugin as TDesignMessage, Button as Button } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
import { asDictionary } from '@/shared/utils/typed-record';

import { Component, Prop, Watch } from 'vue-property-decorator';
import { toRaw } from 'vue';
import { Component as tsc } from 'vue-tsx-support';

import { Input, Table, Dialog, Popup, Checkbox, type PrimaryTableCol } from 'tdesign-vue-next';

import * as authorityMap from '../../../shared/lib/authority-map';
import i18n from '../../../platform/i18n/i18n';
import EmptyStatus from '../../../shared/ui/empty-status/index.vue';
import MaskingAddRule from './masking-add-rule';

import './masking-setting.scss';
import './masking-confirm-dialog.scss';
import { allocateOverlayZIndex, Z_INDEX_LAYERS } from '@/shared/global/overlay';
import useUtils from '@/shared/composables/use-utils';

interface MaskingRuleRow {
  id: number; ruleName: string; matchFields: string[]; matchPattern: string;
  accessNum: number | string; accessInfo: object[]; operator: string;
  params?: Record<string, number | string>; operatorParams?: Record<string, number | string>;
  isActive: boolean; isPublic: boolean; updatedBy?: string; updatedAt?: string;
}
interface IProps {
  isPublicList: boolean;
}

interface IEditAccessValue {
  accessNum: number;
  accessInfo: any[];
}

const settingFields = [
  // 设置显示的字段
  {
    id: 'ruleName',
    label: i18n.t('规则名称'),
    disabled: true,
  },
  {
    id: 'matchFields',
    label: i18n.t('匹配字段名'),
    // disabled: true,
  },
  {
    id: 'matchPattern',
    label: i18n.t('匹配正则表达式'),
  },
  {
    id: 'maskingRules',
    label: (i18n.t('label-脱敏算子') as string).replace('label-', ''),
  },
  {
    id: 'accessNum',
    label: i18n.t('接入项'),
  },
  {
    id: 'isActive',
    label: i18n.t('启/停'),
  },
  {
    id: 'updatedBy',
    label: i18n.t('变更人'),
  },
  {
    id: 'updatedAt',
    label: i18n.t('变更时间'),
  },
];

@Component
export default class MaskingSetting extends tsc<IProps> {
  @Prop({ type: Boolean, default: true }) isPublicList!: boolean;

  /** 规则搜索字符串 */
  searchStr = '';

  tableFilters: Record<string, string> = {};

  sortConfig: { sortBy: string; descending: boolean } | undefined = undefined;

  /** 表格加载状态 */
  tableLoading = false;

  /** 接入表格加载状态 */
  accessTableLoading = false;

  /** 是否显示接入对话框 */
  accessDialogZIndex: number = Z_INDEX_LAYERS.DIALOG;
  confirmDialogZIndex: number = Z_INDEX_LAYERS.DIALOG;

  @Watch('isShowAccessDialog')
  updateAccessDialogLayer(visible: boolean) {
    if (visible) this.accessDialogZIndex = allocateOverlayZIndex();
  }

  @Watch('isShowStopOrDeleteAccessDialog')
  updateConfirmDialogLayer(visible: boolean) {
    if (visible) this.confirmDialogZIndex = allocateOverlayZIndex();
  }

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
        ids: '',
      },
    ],
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
        ids: '',
      },
    ],
  };

  operatorMap = asDictionary({
    mask_shield: window.mainComponent.$t('掩码'),
    text_replace: window.mainComponent.$t('替换'),
  });

  operatorFilters = [
    { text: window.mainComponent.$t('全部'), value: '' },
    { text: window.mainComponent.$t('掩码'), value: 'mask_shield' },
    { text: window.mainComponent.$t('替换'), value: 'text_replace' },
  ];

  scenarioRouteMap = asDictionary({
    log: 'collection-item',
    bkdata: 'bkdata-index-set-list',
    es: 'es-index-set-list',
    index_set: 'log-index-set-list',
    log_custom: 'custom-report',
  });

  tableSetting = {
    fields: settingFields,
    selectedFields: settingFields.slice(0, 6),
    // size: 'small',
  };

  updateSourceFilters: (({ text: unknown; value: unknown; }))[] = []; // 更变人过滤数组

  /** 规则表格列表 */
  tableList: MaskingRuleRow[] = [
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
        replace_mark: '*',
      },
      /** 开关状态 */
      isActive: true,
      isPublic: false,
    },
  ];

  tableShowList: MaskingRuleRow[] = [];

  tableSearchList: MaskingRuleRow[] = [];

  tableStrList: ((string))[] = [];

  /** 分页信息 */
  pagination = {
    /** 当前页数 */
    current: 1,
    /** 总数 */
    count: 0,
    /** 每页显示数量 */
    limit: 10,
    /** 每页显示数量列表 */
    limitList: [10, 20, 50, 100],
  };

  /** 是否有脱敏权限 */
  isAllowed = false;

  enTableWidth = {
    ruleName: '166',
    matchFields: '240',
    maskingRules: '240',
    matchPattern: '280',
    accessNum: '125',
    isActive: '95',
    operate: '100',
  };

  cnTableWidth = {
    ruleName: '166',
    matchFields: '240',
    maskingRules: '240',
    matchPattern: '280',
    accessNum: '95',
    isActive: '75',
    operate: '100',
  };

  get spaceUid() {
    return useApplicationStore().spaceUid;
  }

  get getTableWidth() {
    return useApplicationStore().isEnLanguage ? this.enTableWidth : this.cnTableWidth;
  }

  get authorityData() {
    return this.isPublicList
      ? {
          action_ids: [authorityMap.MANAGE_GLOBAL_DESENSITIZE_RULE],
        }
      : {
          action_ids: [authorityMap.MANAGE_DESENSITIZE_RULE],
          resources: [
            {
              type: 'space',
              id: this.spaceUid,
            },
          ],
        };
  }

  @Watch('$route.query.spaceUid', { immediate: true })
  handleSpaceUidChange() {
    this.initTableList();
  }

  async initTableList() {
    try {
      if (!this.spaceUid) {
        this.tableList = [];
        this.tableSearchList = [];
        this.tableShowList = [];
        this.tableStrList = [];
        this.updateSourceFilters = [];
        this.changePagination({ current: 1, count: 0 });
        this.emptyType = 'empty';
        this.isAllowed = false;
        TDesignMessage.warning(this.$t('请先选择业务'));
        return;
      }
      this.tableLoading = true;
      const params = { space_uid: this.spaceUid, rule_type: this.isPublicList ? 'public' : 'all' }; // 非全局列表 传业务id
      const authorityRes = await useApplicationStore().checkAndGetData(this.authorityData);
      this.isAllowed = authorityRes.isAllowed;
      const res = await ServicesInstance.masking.getMaskingRuleList({
        params,
      });
      const updateSourceFiltersSet = new Set();
      const { formatResponseListTimeZoneString } = useUtils();
      this.tableList = formatResponseListTimeZoneString(res.data, {}, ['updated_at'])
        .map(item => {
          if (!updateSourceFiltersSet.has(item.updated_by)) {
            updateSourceFiltersSet.add(item.updated_by);
          }
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
            updatedAt: item.updated_at,
          };
        })
        .sort((_a, b) => (b.isPublic ? 1 : -1));
      this.tableStrList = this.tableList.map(item => item.ruleName);
      this.searchStr = '';
      this.tableFilters = {};
      this.sortConfig = undefined;
      this.tableSearchList = structuredClone(toRaw(this.tableList));
      this.tableShowList = this.tableSearchList.slice(0, this.pagination.limit);
      this.changePagination({
        current: 1,
        count: this.tableSearchList.length,
      });

      this.updateSourceFilters = [...updateSourceFiltersSet].map(item => ({
        text: item,
        value: item,
      }));
      this.emptyType = 'empty';
    } catch {
      this.emptyType = '500';
    } finally {
      this.tableLoading = false;
    }
  }

  changePagination(pagination = {}) {
    Object.assign(this.pagination, pagination);
  }

  handleClickAccess(row: { accessInfo: any[]; }) {
    this.stopOrStartAccessValue.accessInfo = row.accessInfo;
    this.isShowAccessDialog = true;
  }

  /**
   * @desc: 编辑规则
   * @param {Any} row
   */
  handleEditRule(row: { id: number; accessNum: any; accessInfo: any; }) {
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.editRuleID = row.id;
    this.isEdit = true;
    this.editAccessValue = {
      accessNum: row.accessNum,
      accessInfo: row.accessInfo,
    };
    this.isShowMaskingAddRule = true;
  }

  /**
   * @desc: 删除规则
   * @param {Any} row
   */
  async handleDeleteRule(row: { id: number; accessNum: any; accessInfo: any; }) {
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.isDeleteRule = true;
    this.changeRuleID = row.id;
    this.stopOrStartAccessValue = {
      accessNum: row.accessNum,
      accessInfo: row.accessInfo,
    };
    if (row.accessNum) {
      // 当前是启用状态  并且接入项不为0的时候  执行展示删除弹窗
      this.isShowStopOrDeleteAccessDialog = true;
    } else {
      // 接入项为0 直接删除
      const res = await ServicesInstance.masking.deleteRule({
        params: { rule_id: this.changeRuleID },
      });
      if (res.result) {
        this.initTableList();
      }
    }
  }

  /**
   * @desc: 点击停启规则开关
   * @param {Any} row
   */
  async handleChangeRuleSwitch(row: MaskingRuleRow) {
    if (this.isDisabledClick(row)) {
      return;
    }
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
        accessInfo: row.accessInfo,
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
          TDesignMessage("success", { content: this.$t('操作成功') });
        }
      }
      return;
    }
    const res = await this.requestStopOrStartRule(row.id, 'start');
    if (res.result) {
      this.handleChangeTableListValue(row.id, tItem => (tItem.isActive = true));
      TDesignMessage("success", { content: this.$t('操作成功') });
    }
  }

  handleChangeTableListValue(
    changeTableID: number,
    callback: (any) => void,
    list = [this.tableSearchList, this.tableList],
  ) {
    for (const lItem of list) {
      for (const item of lItem) {
        if (item.id === changeTableID) {
          callback(item);
        }
      }
    }
  }
  /**
   * @desc: 停删规则弹窗确认按钮
   * @param {Any} row
   */
  async handleStopOrDeleteRule() {
    try {
      if (this.isDeleteRule) {
        const res = await ServicesInstance.masking.deleteRule({
          params: { rule_id: this.changeRuleID },
        });
        if (res.result) {
          this.initTableList();
        }
      } else {
        const res = await this.requestStopOrStartRule(this.changeRuleID, 'stop');
        if (res.result) {
          this.initTableList();
        }
      }
    } finally {
      this.isShowStopOrDeleteAccessDialog = false;
    }
  }

  isDisabledClick(row: { isPublic: any; }) {
    return !this.isPublicList && row.isPublic;
  }

  /**
   * @desc: 接入项跳转
   * @param {Any} row
   */
  handleJumpAccess(row: { ids: Iterable<unknown>|null|undefined; scenario_id: string|number; }) {
    const setList = new Set(row.ids);
    const idList = [...setList].join(',');
    const { href } = this.$router.resolve({
      name: this.scenarioRouteMap[row.scenario_id],
      query: {
        ids: encodeURIComponent(idList),
        spaceUid: this.spaceUid,
      },
    });
    window.open(href, '_blank', 'noopener,noreferrer');
  }

  handleCreateRule() {
    if (!this.isAllowed) {
      this.getOptionApplyData();
      return;
    }
    this.isShowMaskingAddRule = true;
    this.isEdit = false;
  }

  handleSearchChange(val: string) {
    if (val === '' && !this.tableLoading) {
      this.searchRule();
      this.emptyType = 'empty';
    }
  }

  searchRule() {
    this.tableSearchList = this.tableList.filter(item =>
      item.ruleName.toString().toLowerCase().includes(this.searchStr.toLowerCase())
      && (!this.tableFilters.operator || item.operator === this.tableFilters.operator)
      && (!this.tableFilters.updatedBy || item.updatedBy === this.tableFilters.updatedBy),
    );
    if (this.sortConfig?.sortBy === 'accessNum') {
      const direction = this.sortConfig.descending ? -1 : 1;
      this.tableSearchList.sort((a, b) => direction * (Number(a.accessNum) - Number(b.accessNum)));
    }
    this.pageLimitChange(this.pagination.limit);
    this.emptyType = 'search-empty';
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

  async requestStopOrStartRule(ruleID: number, status: string) {
    const requestStr = status === 'start' ? 'startDesensitize' : 'stopDesensitize';
    return await ServicesInstance.masking[requestStr]({
      params: { rule_id: ruleID },
    });
  }

  handleOperation(type: string) {
    if (type === 'clear-filter') {
      this.searchStr = '';
      this.tableFilters = {};
      this.handleSearchChange('');
      return;
    }

    if (type === 'refresh') {
      this.initTableList();
      return;
    }
  }

  /** 申请权限 */
  async getOptionApplyData() {
    try {
      const res = await useApplicationStore().getApplyData(this.authorityData);
      useApplicationStore().updateState({ authDialogData: res.data });
    } catch (err) {
      console.warn(err);
    }
  }

  render() {
    const ruleNameSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <div class='rule-name-box'>
          <span
            class='title-overflow'
            v-log-overflow-tips
          >
            {row.ruleName}
          </span>
          {row.isPublic && !this.isPublicList && <span class='tag global'>{this.$t('全局')}</span>}
        </div>
      ),
    };

    /** 匹配字段名插槽 */
    const matchFieldNameSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <div
          class='title-overflow'
          v-log-overflow-tips={{
            content: row.matchFields.join(' , '),
          }}
        >
          {row.matchFields.length ? (
            row.matchFields.map((item: string|number|symbol|undefined) => <Tag key={item} variant='light' data-v2-display='tag'>{item}</Tag>)
          ) : (
            <span style='padding-left: 10px;'>{'-'}</span>
          )}
        </div>
      ),
    };

    const matchExpressionSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <div
          class='title-overflow'
          v-log-overflow-tips
        >
          <span>{row.matchPattern || '-'}</span>
        </div>
      ),
    };

    const maskingRuleSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <div
          class='title-overflow'
          v-log-overflow-tips
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
                1: row?.params?.preserve_tail,
              })}
            </span>
          )}
        </div>
      ),
    };

    /** 接入项插槽 */
    const accessItemSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <Button

          theme='primary'
          onClick={() => this.handleClickAccess(row)} variant={(true) ? 'text' : ('base')}
        >
          {row.accessNum}
        </Button>
      ),
    };

    const switcherSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <div
          v-cursor={{ active: !this.isAllowed }}
        >
          <Switcher
            value={row.isActive}
            disabled={this.isDisabledClick(row)}
            beforeChange={async () => {
              await this.handleChangeRuleSwitch(row);
              return false;
            }}
            size='small'

          />
        </div>
      ),
    };

    const operatorSlot = {
      default: ({ row }: { row: MaskingRuleRow }) => (
        <div class='operator-slot'>
          <Button
            v-cursor={{ active: !this.isAllowed }}
            disabled={this.isDisabledClick(row)}

            theme='primary'
            onClick={() => this.handleEditRule(row)} variant={(true) ? 'text' : ('base')}
          >
            {this.$t('编辑')}
          </Button>
          <Button
            v-cursor={{ active: !this.isAllowed }}
            disabled={this.isDisabledClick(row)}

            theme='primary'
            onClick={() => this.handleDeleteRule(row)} variant={(true) ? 'text' : ('base')}
          >
            {this.$t('删除')}
          </Button>
        </div>
      ),
    };

    const columns: PrimaryTableCol[] = [
      { colKey: 'ruleName', title: this.$t('规则名称'), width: this.getTableWidth.ruleName,
        cell: (_h, scope) => ruleNameSlot.default({ row: scope.row as MaskingRuleRow }) },
      { colKey: 'matchFields', title: this.$t('匹配字段名'), width: this.getTableWidth.matchFields,
        cell: (_h, scope) => matchFieldNameSlot.default({ row: scope.row as MaskingRuleRow }) },
      { colKey: 'matchPattern', title: this.$t('匹配正则表达式'), width: this.getTableWidth.matchPattern,
        cell: (_h, scope) => matchExpressionSlot.default({ row: scope.row as MaskingRuleRow }) },
      { colKey: 'operator', title: (this.$t('label-脱敏算子') as string).replace('label-', ''),
        width: this.getTableWidth.maskingRules,
        filter: { type: 'single', list: this.operatorFilters.map(item => ({ label: item.text, value: item.value })) },
        cell: (_h, scope) => maskingRuleSlot.default({ row: scope.row as MaskingRuleRow }) },
      { colKey: 'accessNum', title: this.$t('接入项'), width: this.getTableWidth.accessNum,
        align: 'center', sorter: true,
        cell: (_h, scope) => accessItemSlot.default({ row: scope.row as MaskingRuleRow }) },
      { colKey: 'updatedBy', title: this.$t('变更人'), width: 120,
        filter: { type: 'single', list: [{ label: this.$t('全部'), value: '' }, ...this.updateSourceFilters.map(item => ({ label: String(item.text), value: String(item.value) }))] },
        cell: (_h, { row }) => <span class='overflow-tips' v-log-overflow-tips>{row.updatedBy}</span> },
      { colKey: 'updatedAt', title: this.$t('变更时间'), width: 180,
        cell: (_h, { row }) => <span class='overflow-tips' v-log-overflow-tips>{row.updatedAt}</span> },
      { colKey: 'isActive', title: this.$t('启/停'), width: this.getTableWidth.isActive,
        align: 'center', cell: (_h, scope) => switcherSlot.default({ row: scope.row as MaskingRuleRow }) },
      { colKey: 'operate', title: this.$t('操作'), width: this.getTableWidth.operate,
        cell: (_h, scope) => operatorSlot.default({ row: scope.row as MaskingRuleRow }) },
    ];
    const visibleColumns = columns.filter(column => column.colKey === 'operate'
      || this.tableSetting.selectedFields.some(field => (field.id === 'maskingRules' ? 'operator' : field.id) === column.colKey));
    visibleColumns.push({
      colKey: 'setting',
      width: 40,
      title: () => (
        <Popup trigger='click' placement='bottom-right' v-slots={{
          content: () => (
            <div class='masking-column-config'>
              <div class='masking-column-config-title'>{this.$t('字段显示设置')}</div>
              {settingFields.map(field => (
                <Checkbox
                  key={field.id}
                  checked={this.tableSetting.selectedFields.some(item => item.id === field.id)}
                  disabled={field.disabled}
                  onChange={checked => {
                    this.tableSetting.selectedFields = settingFields.filter(item => item.disabled
                      || (item.id === field.id ? checked : this.tableSetting.selectedFields.some(selected => selected.id === item.id)));
                  }}
                >
                  {field.label}
                </Checkbox>
              ))}
            </div>
          ),
        }}>
          <button type='button' class='masking-column-trigger' aria-label={this.$t('字段显示设置')}>
            <i class='bk-icon icon-cog-shape' />
          </button>
        </Popup>
      ),
      cell: () => null,
    });

    const accessTableSlot = () => (
      <Table
        rowKey='scenario_id'
        hideSortTips={true}
        stripe={true}
        class='masking-access-table'
        size='small'
        loading={this.accessTableLoading}
        data={this.stopOrStartAccessValue.accessInfo}
        onDataChange={data => { this.stopOrStartAccessValue.accessInfo = data; }}
        columns={[
          { colKey: 'scenario_name', title: this.$t('日志来源') },
          { colKey: 'ids', title: this.$t('接入项'), width: 125, align: 'center',
            sorter: (a, b) => a.ids.length - b.ids.length,
            cell: (_h, { row }) => (
              <Button size='small' theme='primary' onClick={() => this.handleJumpAccess(row as { ids: string[]; scenario_id: string })} variant='text'>
                {row.ids.length}
              </Button>
            ) },
        ]}
      />
    );

    return (
      <div class='masking-table-container'>
        <Alert
          class='top-alert'
          message={this.$t(
            '脱敏规则会应用到本业务全部索引集。为保证脱敏规则效力，配置规则后，需针对计算平台索引集、第三方ES索引集进行手动校准指定，校准后索引集恢复可用状态。',
          )}
          theme={'info'}
          closeBtn={true} data-v2-display='alert'
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
            placeholder={this.$t('搜索 规则名称')}
            rightIcon='bk-icon icon-search'
            onChange={this.handleSearchChange}
            onEnter={this.searchRule}
          />
        </div>

        <Table
          rowKey='id'
          v-slots={{
            empty: () => (
              <div>
                <EmptyStatus
                  emptyType={this.emptyType}
                  onOperation={this.handleOperation}
                />
              </div>
            ),
          }}
          v-loading={{ loading: this.tableLoading }}
          data={this.tableShowList}
          columns={visibleColumns}
          tableLayout='fixed'
          filterRow={() => null}
          sort={this.sortConfig}
          onSortChange={sort => {
            this.sortConfig = Array.isArray(sort) ? sort[0] : sort;
            this.searchRule();
          }}
          filterValue={this.tableFilters}
          onFilterChange={filters => {
            this.tableFilters = filters;
            this.searchRule();
          }}
          pagination={{
            current: this.pagination.current,
            total: this.pagination.count,
            pageSize: this.pagination.limit,
            pageSizeOptions: this.pagination.limitList,
          }}
          disableDataPage={true}
          size='small'
          onPageChange={({ current, pageSize }) => {
            if (pageSize !== this.pagination.limit) this.pageLimitChange(pageSize);
            else this.pageChange(current);
          }}
        />

        <Dialog
          width={480}
          visible={this.isShowAccessDialog}
          onClose={() => (this.isShowAccessDialog = false)}
          zIndex={this.accessDialogZIndex}
          destroyOnClose
          footer={false}
          header={this.$t('接入项详情')}
        >
          {accessTableSlot()}
        </Dialog>

        <Dialog
          width={400}
          dialogClassName='masking-rule-confirm-dialog'
          header={false}
          visible={this.isShowStopOrDeleteAccessDialog}
          onClose={() => (this.isShowStopOrDeleteAccessDialog = false)}
          zIndex={this.confirmDialogZIndex}
          destroyOnClose
          footer={false}
        >
          <div class='delete-dialog-container'>
            <span class='delete-title'>
              {this.$t('确认{n}该规则？', { n: this.isDeleteRule ? this.$t('删除') : this.$t('停用') })}
            </span>
            <span class='delete-text'>
              {this.$t('当前脱敏规则被应用{n}次，如停用/删除，将无法选用该规则，请确认是否{v}。', {
                v: this.isDeleteRule ? this.$t('删除') : this.$t('停用'),
                n: this.stopOrStartAccessValue.accessNum,
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
          editAccessValue={this.editAccessValue}
          isEdit={this.isEdit}
          isPublicRule={this.isPublicList}
          ruleID={this.editRuleID}
          tableStrList={this.tableStrList}
          onSubmitRule={(value: object) => value && this.initTableList()}
        />
      </div>
    );
  }
}
