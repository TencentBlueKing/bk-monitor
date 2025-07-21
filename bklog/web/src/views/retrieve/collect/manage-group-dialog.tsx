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

import {
  Dialog,
  Switcher,
  Option,
  Table,
  TableColumn,
  Checkbox,
  Input,
  Select,
  TableSettingContent,
  DropdownMenu,
  Tag,
} from 'bk-magic-vue';
import jsCookie from 'js-cookie';
import { Component, Emit, Watch, Model } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import $http from '../../../api';
import { deepClone, random, utcFormatDate } from '../../../common/util';
import EmptyStatus from '../../../components/empty-status/index.vue';
import FingerSelectColumn from '../result-table-panel/log-clustering/components/finger-select-column.vue';

import ManageInput from './component/manage-input';
import './manage-group-dialog.scss';

interface IProps {
  value?: boolean;
}

interface IFavoriteItem {
  id: number;
  created_by: string;
  space_uid: number;
  index_set_id: number;
  name: string;
  group_id: number;
  group_name: string;
  keyword: string;
  index_set_name: string;
  search_fields: string[];
  is_active: boolean;
  visible_type: string;
  display_fields: string[];
  is_enable_display_fields: boolean;
  search_fields_select_list?: any[];
  visible_option: any[];
  search_mode: string;
  group_option: any[];
  params: Record<string, any>;
}

const settingFields = [
  // 设置显示的字段
  {
    disabled: true,
    id: 'name',
    label: window.mainComponent.$t('收藏名'),
  },
  {
    disabled: true,
    id: 'group_name',
    label: window.mainComponent.$t('所属组'),
  },
  {
    id: 'visible_type',
    label: window.mainComponent.$t('可见范围'),
  },
  {
    id: 'display_fields',
    label: window.mainComponent.$t('表单模式'),
  },
  {
    id: 'is_show_switch',
    label: window.mainComponent.$t('显示字段'),
  },
  {
    id: 'updated_by',
    label: window.mainComponent.$t('变更人'),
  },
  {
    id: 'updated_at',
    label: window.mainComponent.$t('变更时间'),
  },
];

@Component
export default class GroupDialog extends tsc<IProps> {
  @Model('change', { default: false, type: Boolean }) value: IProps['value'];
  searchValue = ''; // 搜索字段
  tableLoading = false;
  isShowDeleteDialog = false;
  tableList: IFavoriteItem[] = []; // 表格数据;
  operateTableList: IFavoriteItem[] = []; // 用户操作操作缓存表格数据;
  submitTableList: IFavoriteItem[] = []; // 修改提交的表格数据;
  searchAfterList: IFavoriteItem[] = []; // 用于全选或者多选或搜索过滤后的表格数组;
  deleteTableIDList = []; // 删除收藏的表格ID
  tableDialog = false;
  selectFavoriteList = []; // 列的头部的选择框收藏ID列表
  groupList = []; // 组列表
  unPrivateList = []; // 无个人收藏的收藏列表
  privateList = []; // 个人收藏列表 只有个人的列表
  checkValue = 0; // 0为不选 1为半选 2为全选
  groupName = ''; // 输入框组名
  unknownGroupID = 0;
  privateGroupID = 0;
  positionTop = 0;
  isCannotValueChange = false; // 用于分组时不进行数据更新
  maxHeight = 300;
  emptyType = 'empty';
  tippyOption = {
    interactive: true,
    theme: 'light',
    trigger: 'click',
  };
  isShowAddGroup = true;
  cannotComparedData = [
    // 不进行对比的字段 （前端操作缓存自加的字段）
    'search_fields_select_list',
    'visible_option',
    'group_option',
    'group_option_private',
    'is_group_disabled',
  ];
  groupNameMap = {
    private: window.mainComponent.$t('个人收藏'),
    unknown: window.mainComponent.$t('未分组'),
  };
  sourceFilters = []; // 所属组数组
  updateSourceFilters = []; // 更变人过滤数组

  tableKey = random(10);

  unPrivateOptionList = [
    // 非本人创建的收藏的可见范围数组
    { id: 'public', name: window.mainComponent.$t('公开') },
  ];
  allOptionList = [
    // 本人创建的收藏的可见范围数组
    { id: 'public', name: window.mainComponent.$t('公开') },
    { id: 'private', name: window.mainComponent.$t('私有') },
  ];

  tableSetting = {
    fields: settingFields,
    selectedFields: settingFields.slice(0, 5),
    size: 'small',
  };

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get getUserName() {
    // 当前用户名称
    return this.$store.state.userMeta?.username || '';
  }

  get selectCount() {
    // 当前选择的数据的数量
    return this.selectFavoriteList.length;
  }

  get showFavoriteCount() {
    return this.searchAfterList.length;
  }

  get getGroupLabelWidth() {
    return this.$store.state.isEnLanguage ? 140 : 115;
  }

  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }

  @Watch('selectFavoriteList', { deep: true })
  watchSelectListLength(list) {
    // 监听选择数据的数量 改变全选的check状态
    if (!list.length) {
      this.checkValue = 0;
      return;
    }
    if (list.length === this.searchAfterList.length) {
      this.checkValue = 2;
      return;
    }
    this.checkValue = 1;
  }

  @Emit('change') // 展示或者隐藏弹窗
  handleShowChange(value = false) {
    return value;
  }

  @Emit('submit') // 更新成功
  handleSubmitChange(value = false) {
    return value;
  }

  mounted() {
    const initTableHeight = Math.floor(document.body.clientHeight * 0.8) - 240;
    this.maxHeight =
      initTableHeight > this.maxHeight ? initTableHeight : this.maxHeight;
    this.positionTop = Math.floor(document.body.clientHeight * 0.1);
  }

  async handleValueChange(value) {
    if (value) {
      // 展开
      await this.getGroupList();
      this.getFavoriteList();
    } else {
      // 关闭
      this.tableList = [];
      this.operateTableList = [];
      this.submitTableList = [];
      this.selectFavoriteList = [];
      this.groupList = [];
      this.updateSourceFilters = [];
      this.searchAfterList = [];
      this.handleShowChange();
      this.handleSubmitChange(true);
    }
  }

  /** 多选是否选中 */
  getCheckedStatus(row) {
    return this.selectFavoriteList.includes(row.id);
  }
  /** 多选操作 */
  handleRowCheckChange(row, status) {
    if (status) {
      this.selectFavoriteList.push(row.id);
    } else {
      const index = this.selectFavoriteList.findIndex(
        (item) => item === row.id
      );
      this.selectFavoriteList.splice(index, 1);
    }
  }
  /** 搜索 */
  handleSearchFilter() {
    if (this.tableLoading) return;
    this.tableLoading = true;
    let searchList;
    if (this.searchValue !== '') {
      searchList = this.operateTableList.filter((item) =>
        item.name.includes(this.searchValue)
      );
      this.emptyType = 'search-empty';
    } else {
      searchList = this.operateTableList;
      this.emptyType = 'empty';
    }
    setTimeout(() => {
      this.tableLoading = false;
      // 赋值搜索过后的列表
      this.searchAfterList = searchList;
      this.selectFavoriteList = [];
    }, 500);
  }
  handleOperation(type) {
    if (type === 'clear-filter') {
      this.searchValue = '';
      this.handleSearchFilter();
      return;
    }

    if (type === 'refresh') {
      this.emptyType = 'empty';
      this.getFavoriteList();
      return;
    }
  }
  handleInputSearchFavorite() {
    if (this.searchValue === '') this.handleSearchFilter();
  }
  /** 全选操作 */
  handleSelectionChange(value) {
    this.selectFavoriteList = value
      ? this.searchAfterList.map((item) => item.id)
      : [];
  }
  /** 多选移动至分组操作 */
  handleClickMoveGroup(value) {
    this.selectFavoriteList.forEach((item) => {
      this.operateListChange(
        { id: item },
        { group_id: value.group_id, is_group_disabled: false }
      );
    });
  }
  /** 获取字段下拉框列表请求 */
  async getSearchFieldsList(keyword: string) {
    return await $http.request('favorite/getSearchFields', {
      data: { keyword },
    });
  }
  /** 获取收藏请求 */
  async getFavoriteList() {
    try {
      this.tableLoading = true;
      const res = await $http.request('favorite/getFavoriteList', {
        query: {
          order_type: 'NAME_ASC',
          space_uid: this.spaceUid,
        },
      });
      const updateSourceFiltersSet = new Set();
      const localLanguage = jsCookie.get('blueking_language') || 'zh-cn';
      const initList = res.data.map((item) => {
        const visible_option =
          item.created_by === this.getUserName
            ? this.allOptionList
            : this.unPrivateOptionList;
        const search_fields_select_list = item.search_fields.map((item) => ({
          chName: item,
          name:
            localLanguage === 'en'
              ? item.replace(/^全文检索(\(\d\))?$/, (item, p1) => {
                  return `${this.$t('全文检索')}${!!p1 ? p1 : ''}`;
                })
              : item,
        })); // 初始化表单字段

        const is_group_disabled = item.visible_type === 'private';
        if (!updateSourceFiltersSet.has(item.updated_by))
          updateSourceFiltersSet.add(item.updated_by);
        return {
          ...item,
          group_option: this.unPrivateList,
          group_option_private: this.privateList,
          is_group_disabled,
          search_fields_select_list,
          visible_option,
        };
      });
      this.updateSourceFilters = [...updateSourceFiltersSet].map((item) => ({
        text: item,
        value: item,
      }));
      this.tableList = res.data;
      this.operateTableList = initList;
      this.searchAfterList = initList;
    } catch (error) {
      this.emptyType = '500';
    } finally {
      this.tableLoading = false;
      this.handleSearchFilter();
    }
  }
  /** 获取组列表 */
  async getGroupList(isAddGroup = false) {
    try {
      const res = await $http.request('favorite/getGroupList', {
        query: {
          space_uid: this.spaceUid,
        },
      });
      this.groupList = res.data.map((item) => ({
        group_id: item.id,
        group_name: this.groupNameMap[item.group_type] ?? item.name,
        group_type: item.group_type,
      }));
      this.unPrivateList = this.groupList.slice(1); // 去除个人收藏的列表
      this.privateList = this.groupList.slice(0, 1); // 个人收藏列表
      this.sourceFilters = res.data.map((item) => ({
        text: this.groupNameMap[item.group_type] ?? item.name,
        value: item.name,
      }));
      this.unknownGroupID = this.groupList[this.groupList.length - 1]?.group_id;
      this.privateGroupID = this.groupList[0]?.group_id;
    } catch (error) {
      console.warn(error);
    } finally {
      if (isAddGroup) {
        // 如果是新增组 则刷新操作表格的组列表
        this.operateTableList = this.operateTableList.map((item) => ({
          ...item,
          group_option: this.unPrivateList,
          group_option_private: this.privateList,
        }));
        this.handleSearchFilter();
      }
    }
  }
  /** 显示字段选择操作 */
  handleChangeSearchList(row, nVal: string[]) {
    this.operateListChange(row, { search_fields: nVal });
  }
  /** 更改收藏名 */
  handleChangeFavoriteName(row, name) {
    this.operateListChange(row, { name });
  }
  /** 是否同时显示字段操作 */
  handleSwitchChange(row, value) {
    this.operateListChange(row, { is_enable_display_fields: value });
  }
  /** 新增或更新组名 */
  async handleAddGroupName() {
    const data = { name: this.groupName, space_uid: this.spaceUid };
    try {
      const res = await $http.request('favorite/createGroup', { data });
      if (res.result) {
        this.$bkMessage({
          message: this.$t('新建成功'),
          theme: 'success',
        });
        this.getGroupList(true);
      }
    } catch (error) {
    } finally {
      this.isShowAddGroup = true;
      this.groupName = '';
    }
  }
  /** 获取显示字段下拉框列表 */
  async handleClickFieldsList(row, status: boolean) {
    if (status) {
      try {
        const res = await this.getSearchFieldsList(row.keyword);
        const list = res.data.map((item) => ({
          ...item,
          chName: item.name,
          name: item.is_full_text_field
            ? `${this.$t('全文检索')}${!!item.repeat_count ? `(${item.repeat_count})` : ''}`
            : item.name,
        }));
        this.operateListChange(row, { search_fields_select_list: list });
      } catch (error) {
        console.warn(error);
      }
    }
  }
  /** 修改可选范围 */
  handleSelectVisible(row, nVal: string) {
    const group_id =
      nVal !== 'public' ? this.privateGroupID : this.unknownGroupID;
    const group_name = this.groupList.find(
      (item) => item.group_id === group_id
    ).group_name;
    this.operateListChange(row, {
      group_id,
      group_name,
      is_group_disabled: nVal === 'private',
      visible_type: nVal,
    });
  }
  /** 单独修改组 */
  handleChangeGroup(row) {
    const visible_type =
      row.group_id === this.privateGroupID ? 'private' : 'public';
    const groupName = this.groupList.find(
      (item) => item.group_id === row.group_id
    ).group_name;
    this.operateListChange(row, { group_name: groupName, visible_type });
  }
  /** 用户操作 */
  operateListChange(row, operateObj = {}) {
    if (this.isCannotValueChange) return;

    // 搜索展示用的列表和操作缓存的列表同时更新数据
    for (const listName of ['searchAfterList', 'operateTableList']) {
      const index = this[listName].findIndex((item) => item.id === row.id);
      if (index >= 0) Object.assign(this[listName][index], row, operateObj);
      if (listName === 'operateTableList')
        this.submitDataCompared(row, index, operateObj);
    }
  }
  /** 提交数据对比 */
  submitDataCompared(row, operateIndex, operateObj) {
    const submitIndex = this.submitTableList.findIndex(
      (item) => item.id === row.id
    );
    if (submitIndex >= 0) {
      // 操作已添加到更新列表的值 进行数据对比
      Object.assign(this.submitTableList[submitIndex], row, operateObj);
      const comparedSubData = deepClone(this.submitTableList[submitIndex]);
      this.deleteSubmitData(comparedSubData, this.cannotComparedData); // 前端加的参数 不做对比
      const tableData = this.tableList[operateIndex];
      if (JSON.stringify(tableData) === JSON.stringify(comparedSubData)) {
        this.submitTableList.splice(submitIndex, 1); // 判断数据是否相同 相同则删除提交更新里的值
      }
    } else {
      // 第一次操作相同的列 添加到提交更新列表
      const comparedData = deepClone(this.operateTableList[operateIndex]);
      this.deleteSubmitData(comparedData, this.cannotComparedData); // 前端加的参数 不做对比
      const tableData = this.tableList[operateIndex];
      // 判断操作过后的值和表格里的是否相同 不同则添加到提交更新列表
      if (JSON.stringify(comparedData) !== JSON.stringify(tableData)) {
        this.submitTableList.push(comparedData);
      }
    }
  }
  /** 删除不做对比的参数 */
  deleteSubmitData(data: object, list: string[]) {
    list.forEach((item) => delete data[item]);
  }

  handleDeleteFavorite(row) {
    this.$bkInfo({
      confirmFn: () => {
        this.deleteTableIDList.push(row.id);
        // 删除收藏 把展示的表格, 操作表格, 提交表格, 以及基础表格统一删除
        for (const listName of [
          'searchAfterList',
          'operateTableList',
          'submitTableList',
          'tableList',
        ]) {
          const index = this[listName].findIndex((item) => item.id === row.id);
          if (index >= 0) this[listName].splice(index, 1);
        }
        // 当前选中选择删除
        const index = this.selectFavoriteList.findIndex(
          (item) => item === row.id
        );
        if (index >= 0) this.selectFavoriteList.splice(index, 1);
        $http.request('favorite/deleteFavorite', {
          params: { favorite_id: row.id },
        });
      },
      subTitle: this.$t('当前收藏名为 {n}，确认是否删除？', { n: row.name }),
      type: 'warning',
    });
  }
  /** 点击确定提交管理弹窗数据 */
  handleSubmitTableData() {
    this.tableLoading = true;
    Promise.all([this.batchDeleteFavorite(), this.batchUpdateFavorite()])
      .then(() => {
        this.handleShowChange();
      })
      .finally(() => {
        this.tableLoading = false;
      });
  }

  async batchDeleteFavorite() {
    // 删除接口
    // 若没有删除则不请求
    if (!this.deleteTableIDList.length) return;
    try {
      await $http.request('favorite/batchFavoriteDelete', {
        data: {
          id_list: this.deleteTableIDList,
        },
      });
    } catch (error) {}
  }

  async batchUpdateFavorite() {
    // 更新收藏接口
    // 若没有更新收藏则不请求
    if (!this.submitTableList.length) return;
    const params = this.submitTableList.map((item) => ({
      addition: item.params.addition,
      display_fields: item.display_fields,
      group_id: item.group_id,
      id: item.id,
      // host_scopes: item.params.host_scopes,
      ip_chooser: item.params.ip_chooser,
      is_enable_display_fields: item.is_enable_display_fields,
      keyword: item.keyword,
      name: item.name,
      search_fields: item.search_fields,
      search_mode: item.search_mode,
      visible_type: item.visible_type,
    }));
    try {
      await $http.request('favorite/batchFavoriteUpdate', {
        data: {
          params,
        },
      });
    } catch (error) {}
  }
  /** 所属组和变更人分组操作 */
  sourceFilterMethod(value, row, column) {
    const property = column.property;
    this.isCannotValueChange = true;
    setTimeout(() => {
      // 因为操作组会导致数据更变 即不改变数据
      this.isCannotValueChange = false;
    }, 500);
    return row[property] === value;
  }

  handleSettingChange({ fields, size }) {
    this.tableSetting.selectedFields = fields;
    this.tableSetting.size = size;
  }

  checkFields(field) {
    return this.tableSetting.selectedFields.some((item) => item.id === field);
  }

  getGroupName(row) {
    if (row.group_id === this.unknownGroupID) return this.groupNameMap.unknown;
    return row.group_name;
  }

  renderHeader(h) {
    return h(FingerSelectColumn, {
      class: {
        'header-checkbox': true,
      },
      on: {
        change: this.handleSelectionChange,
      },
      props: {
        disabled: !this.searchAfterList.length,
        value: this.checkValue,
      },
    });
  }

  renderHeaderTable(h) {
    return h(
      'div',
      {
        class: 'render-header',
      },
      [
        h(
          'span',
          {
            class: 'header-tips',
            directives: [
              {
                name: 'bk-tooltips',
                value: {
                  content: this.$t(
                    '该功能指从查询语句中获取相应的字段，当勾选对应的字段时，将以表单的填写方式显示给收藏的使用者。（字段说明：没有字段时，为全文检索；重复的字段增加显示序号(N) ，默认不勾选任何字段)'
                  ),
                  width: 400,
                },
              },
            ],
          },
          this.$t('表单模式')
        ),
      ]
    );
  }

  renderHeaderFields(h) {
    return h(
      'div',
      {
        class: 'render-header',
      },
      [
        h(
          'span',
          {
            class: 'header-tips',
            directives: [
              {
                name: 'bk-tooltips',
                value: {
                  content: this.$t(
                    '当打开时，使用该收藏将同时显示如下字段，不影响用户字段显示设置。'
                  ),
                  width: 400,
                },
              },
            ],
          },
          this.$t('显示字段')
        ),
      ]
    );
  }

  render() {
    const indexSetName = (row) => {
      const { index_set_name: indexSetName, index_set_names: indexSetNames } =
        row;
      return !this.isUnionSearch
        ? indexSetName
        : indexSetNames?.map((item) => <Tag>{item}</Tag>) || '';
    };
    const expandSlot = {
      default: ({ row }) => (
        <div class="expand-container">
          <div class="expand-information">
            <span>{this.$t('索引集')}</span>
            <span>{indexSetName(row)}</span>
            <span>{row.index_set_name}</span>
          </div>
          <div class="expand-information">
            <span>{this.$t('查询语句')}</span>
            <span>{row.keyword}</span>
          </div>
          <div class="expand-information">
            <span>{this.$t('查询显示字段')}:</span>
            {row.display_fields.map((item) => (
              <Tag>{item}</Tag>
            ))}
          </div>
        </div>
      ),
    };
    const nameSlot = {
      default: ({ row }) => [
        <div class="group-container">
          <Checkbox
            checked={this.getCheckedStatus(row)}
            class="group-check-box"
            on-change={(status) => this.handleRowCheckChange(row, status)}
          ></Checkbox>
          <ManageInput
            favorite-data={row}
            on-change={(val) => this.handleChangeFavoriteName(row, val)}
          ></ManageInput>
        </div>,
      ],
    };
    const groupSlot = {
      default: ({ row }) => [
        <Select
          clearable={false}
          disabled={row.is_group_disabled}
          ext-popover-cls="add-new-page-container"
          on-change={() => this.handleChangeGroup(row)}
          popover-min-width={200}
          searchable
          vModel={row.group_id}
        >
          <div slot="trigger">
            <span
              class="overflow-tips"
              style="padding: 0 10px;"
              v-bk-overflow-tips
            >
              {this.getGroupName(row)}
            </span>
          </div>
          {row[
            row.visible_type === 'private'
              ? 'group_option_private'
              : 'group_option'
          ].map((item) => (
            <Option
              id={item.group_id}
              key={item.group_id}
              name={item.group_name}
            ></Option>
          ))}
          <div slot="extension">
            {this.isShowAddGroup ? (
              <div
                class="select-add-new-group"
                onClick={() => (this.isShowAddGroup = false)}
              >
                <div>
                  <i class="bk-icon icon-plus-circle"></i>
                  {this.$t('新增')}
                </div>
              </div>
            ) : (
              <li class="add-new-page-input">
                <Input
                  behavior={'simplicity'}
                  maxlength={30}
                  vModel={this.groupName}
                ></Input>
                <div class="operate-button">
                  <span
                    class="bk-icon icon-check-line"
                    onClick={() => this.handleAddGroupName()}
                  ></span>
                  <span
                    class="bk-icon icon-close-line-2"
                    onClick={() => {
                      this.isShowAddGroup = true;
                      this.groupName = '';
                    }}
                  ></span>
                </div>
              </li>
            )}
          </div>
        </Select>,
      ],
    };
    const visibleSlot = {
      default: ({ row }) => [
        <Select
          clearable={false}
          on-selected={(nVal) => this.handleSelectVisible(row, nVal)}
          vModel={row.visible_type}
        >
          {row.visible_option.map((item) => (
            <Option id={item.id} key={item.id} name={item.name}></Option>
          ))}
        </Select>,
      ],
    };
    const selectTagSlot = {
      default: ({ row }) => [
        <Select
          clearable={false}
          display-tag
          multiple
          on-change={(nVal) => this.handleChangeSearchList(row, nVal)}
          on-toggle={(status) => this.handleClickFieldsList(row, status)}
          placeholder={this.$t('未设置')}
          searchable
          vModel={row.search_fields}
        >
          {row.search_fields_select_list.map((item) => (
            <Option id={item.chName} key={item.name} name={item.name}></Option>
          ))}
        </Select>,
      ],
    };
    const switchSlot = {
      default: ({ row }) => [
        <div class="switch-container">
          <Switcher
            on-change={(value) => this.handleSwitchChange(row, value)}
            theme="primary"
            vModel={row.is_enable_display_fields}
          ></Switcher>
        </div>,
      ],
    };
    const deleteSlot = {
      default: ({ row }) => [
        <div class="switcher-box">
          <div class="delete" onClick={() => this.handleDeleteFavorite(row)}>
            <span class="bk-icon icon-delete"></span>
          </div>
        </div>,
      ],
    };
    return (
      <Dialog
        confirm-fn={this.handleSubmitTableData}
        ext-cls="manage-group"
        header-position="left"
        on-value-change={this.handleValueChange}
        position={{ top: this.positionTop }}
        render-directive="if"
        title={this.$t('管理')}
        value={this.value}
        width={960}
      >
        <div class={`top-operate ${!this.selectCount && 'is-not-select'}`}>
          <div class="favorite-size">
            <i18n path="共 {0} 个收藏">
              <span class="size-weight">{this.showFavoriteCount}</span>
            </i18n>
          </div>
          <Input
            class="operate-input"
            on-enter={this.handleSearchFilter}
            on-right-icon-click={this.handleSearchFilter}
            onKeyup={this.handleInputSearchFavorite}
            right-icon="bk-icon icon-search"
            vModel={this.searchValue}
          ></Input>
        </div>
        {this.selectCount ? (
          <div class="table-top-operate">
            <span>
              <i18n path="当前已选择 {0} 条数据">
                <span class="operate-message">{this.selectCount}</span>
              </i18n>
            </span>
            <DropdownMenu trigger="click">
              <div class="dropdown-trigger-text" slot="dropdown-trigger">
                <span class="operate-click">
                  ，&nbsp;{this.$t('移至分组')}
                  <span class="bk-icon icon-down-shape"></span>
                </span>
              </div>
              <div class="dropdown-list" slot="dropdown-content">
                <ul class="search-li">
                  {this.unPrivateList.map((item) => (
                    <li onClick={() => this.handleClickMoveGroup(item)}>
                      {item.group_name}
                    </li>
                  ))}
                </ul>
              </div>
            </DropdownMenu>
          </div>
        ) : undefined}
        <Table
          border={true}
          data={this.searchAfterList}
          empty-text={this.$t('暂无数据')}
          ext-cls={`${!this.selectCount && 'is-not-select'}`}
          header-border={true}
          max-height={this.maxHeight}
          render-directive="if"
          size="small"
          v-bkloading={{ isLoading: this.tableLoading }}
        >
          <TableColumn
            render-header={this.renderHeader}
            scopedSlots={expandSlot}
            type="expand"
            width="64"
          ></TableColumn>

          <TableColumn
            class-name="group-input"
            key={'column_name'}
            label={this.$t('收藏名')}
            label-class-name="group-title"
            prop={'name'}
            render-header={this.$renderHeader}
            scopedSlots={nameSlot}
            width="160"
          ></TableColumn>

          {this.checkFields('group_name') ? (
            <TableColumn
              class-name="group-select"
              filter-method={this.sourceFilterMethod}
              filter-multiple={false}
              filters={this.sourceFilters}
              key={'column_group_name'}
              label={this.$t('所属组')}
              label-class-name="group-title"
              prop={'group_name'}
              render-header={this.$renderHeader}
              scopedSlots={groupSlot}
              width={this.getGroupLabelWidth}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('visible_type') ? (
            <TableColumn
              class-name="group-select"
              key={'column_visible_type'}
              label={this.$t('可见范围')}
              label-class-name="group-title"
              prop={'visible_type'}
              render-header={this.$renderHeader}
              scopedSlots={visibleSlot}
              width="112"
            ></TableColumn>
          ) : undefined}

          {this.checkFields('display_fields') ? (
            <TableColumn
              class-name="group-select"
              key={'column_search_fields'}
              label={this.$t('表单模式')}
              label-class-name="group-title"
              prop={'search_fields'}
              render-header={this.renderHeaderTable}
              scopedSlots={selectTagSlot}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('updated_by') ? (
            <TableColumn
              filter-method={this.sourceFilterMethod}
              filter-multiple={false}
              filters={this.updateSourceFilters}
              key={'column_update_by'}
              label={this.$t('变更人')}
              prop={'updated_by'}
              render-header={this.$renderHeader}
              scopedSlots={{
                default: ({ row }) => [
                  <span class="overflow-tips" v-bk-overflow-tips>
                    {row.updated_by}
                  </span>,
                ],
              }}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('updated_at') ? (
            <TableColumn
              key={'column_update_time'}
              label={this.$t('变更时间')}
              prop={'updated_at'}
              render-header={this.$renderHeader}
              scopedSlots={{
                default: ({ row }) => [
                  <span class="overflow-tips" v-bk-overflow-tips>
                    {utcFormatDate(row.updated_at)}
                  </span>,
                ],
              }}
            ></TableColumn>
          ) : undefined}

          {this.checkFields('is_show_switch') ? (
            <TableColumn
              class-name="group-input"
              key={'column_switch'}
              label={this.$t('显示字段')}
              label-class-name="group-title"
              max-width="120"
              render-header={this.renderHeaderFields}
              scopedSlots={switchSlot}
            ></TableColumn>
          ) : undefined}

          <TableColumn
            key={'column_delete'}
            scopedSlots={deleteSlot}
            width="0"
          ></TableColumn>

          <TableColumn type="setting">
            <TableSettingContent
              fields={this.tableSetting.fields}
              key={`${this.tableKey}__settings`}
              on-setting-change={this.handleSettingChange}
              selected={this.tableSetting.selectedFields}
              size={this.tableSetting.size}
              v-en-style="width: 510px;"
            ></TableSettingContent>
          </TableColumn>

          <div slot="empty">
            <EmptyStatus
              emptyType={this.emptyType}
              onOperation={this.handleOperation}
            />
          </div>
        </Table>
      </Dialog>
    );
  }
}
