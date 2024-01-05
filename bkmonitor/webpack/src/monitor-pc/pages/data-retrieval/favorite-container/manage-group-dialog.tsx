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

import VueJsonPretty from 'vue-json-pretty';
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import {
  bulkDeleteFavorite,
  bulkUpdateFavorite,
  createFavoriteGroup,
  destroyFavorite,
  listFavorite,
  listFavoriteGroup
} from '../../../../monitor-api/modules/model';
import { deepClone } from '../../../../monitor-common/utils/utils';

import 'vue-json-pretty/lib/styles.css';
import './manage-group-dialog.scss';

interface IProps {
  value?: boolean;
  favoriteSearchType: string;
}

interface IEvent {
  onSubmit: boolean;
}

interface IFavoriteItem {
  // 收藏元素
  id: number;
  created_user: string;
  update_time: string;
  update_user: string;
  name: string;
  group_id: number | string;
  group_name: string;
  visible_type: string;
  visible_option: any[];
  group_option: any[];
}

const settingFields = [
  // 设置显示的字段
  {
    id: 'name',
    label: window.i18n.t('收藏名'),
    disabled: true
  },
  {
    id: 'group_name',
    label: window.i18n.t('所属组'),
    disabled: true
  },
  {
    id: 'visible_type',
    label: window.i18n.t('可见范围')
  },
  {
    id: 'updated_by',
    label: window.i18n.t('最近更新人')
  },
  {
    id: 'updated_at',
    label: window.i18n.t('最近更新时间')
  }
];

@Component
export default class GroupDialog extends tsc<IProps, IEvent> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ default: 'metric', type: String }) favoriteSearchType: string; // 分组类型
  searchValue = ''; // 搜索字段
  tableLoading = false;
  tableList: IFavoriteItem[] = []; // 表格数据;
  operateTableList: IFavoriteItem[] = []; // 用户操作操作缓存表格数据;
  submitTableList: IFavoriteItem[] = []; // 修改提交的表格数据;
  searchAfterList: IFavoriteItem[] = []; // 用于全选或者多选或搜索过滤后的表格数组;
  deleteTableIDList = []; // 删除收藏的表格ID
  selectFavoriteList = []; // 列的头部的选择框收藏ID列表
  groupList = []; // 组列表
  unPrivateList = []; // 无个人组的收藏列表
  privateList = []; // 个人组列表 只有个人的列表
  checkValue = 0; // 0为不选 1为半选 2为全选
  groupName = ''; // 输入框组名
  positionTop = 0;
  maxHeight = 300; // 表格最高高度
  isShowAddGroup = true; // 是否展示新增组
  isCannotValueChange = false; // 用于分组时不进行数据更新
  tippyOption = {
    trigger: 'click',
    interactive: true,
    theme: 'light'
  };
  cannotComparedData = [
    // 不进行对比的字段 （前端操作缓存自加的字段）
    'visible_option',
    'group_option',
    'group_option_private',
    'is_group_disabled',
    'visible_type',
    'isShowJsonKeywords',
    'config'
  ];
  sourceFilters = []; // 所属组数组
  updateSourceFilters = []; // 更变人过滤数组

  unPrivateOptionList = [
    // 非本人创建的收藏的可见范围数组
    { name: window.i18n.t('公开'), id: 'public' }
  ];
  allOptionList = [
    // 本人创建的收藏的可见范围数组
    { name: window.i18n.t('公开'), id: 'public' },
    { name: window.i18n.t('仅本人'), id: 'private' }
  ];

  tableSetting = {
    // table设置字段
    fields: settingFields,
    selectedFields: settingFields.slice(0, 3)
  };

  get selectCount() {
    // 当前选择的数据的数量
    return this.selectFavoriteList?.length;
  }

  get bizId(): string {
    return this.$store.getters.bizId;
  }

  get showFavoriteCount() {
    // 当前表格的收藏数量
    return this.searchAfterList.length;
  }

  @Watch('selectFavoriteList', { deep: true })
  watchSelectListLength(list) {
    // 监听选择数据的数量 改变全选的check状态 全选 半选 未选
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
    // 初始化表格高度
    const initTableHeight = Math.floor(document.body.clientHeight * 0.8) - 240;
    if (initTableHeight > this.maxHeight) this.maxHeight = initTableHeight;
    this.positionTop = Math.floor(document.body.clientHeight * 0.1);
  }

  async handleValueChange(value) {
    if (value) {
      // 管理弹窗开关
      await this.getGroupList();
      this.getFavoriteList();
    } else {
      this.tableList = [];
      this.operateTableList = [];
      this.searchAfterList = [];
      this.submitTableList = [];
      this.selectFavoriteList = [];
      this.groupList = [];
      this.updateSourceFilters = [];
      this.isShowAddGroup = true;
      this.deleteTableIDList = [];
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
      const index = this.selectFavoriteList.findIndex(item => item === row.id);
      this.selectFavoriteList.splice(index, 1);
    }
  }

  /** 搜索 */
  handleSearchFilter() {
    if (this.tableLoading) return;
    this.tableLoading = true;
    let searchList;
    if (this.searchValue !== '') {
      searchList = this.operateTableList.filter(item => item.name.includes(this.searchValue));
    } else {
      searchList = this.operateTableList;
    }
    setTimeout(() => {
      // 赋值搜索过后的列表
      this.searchAfterList = searchList;
      this.selectFavoriteList = [];
      this.tableLoading = false;
    }, 500);
  }

  handleInputSearchFavorite() {
    if (!this.searchValue) this.handleSearchFilter();
  }

  /** 全选操作 */
  handleSelectionChange(value) {
    this.selectFavoriteList = value ? this.searchAfterList.map(item => item.id) : [];
  }

  /** 多选移动至分组操作 */
  handleClickMoveGroup(value) {
    this.selectFavoriteList.forEach(item => {
      this.operateListChange({ id: item }, { group_id: String(value.group_id) });
    });
  }

  /** 获取收藏请求 */
  async getFavoriteList() {
    try {
      this.tableLoading = true;
      const res = await listFavorite({ type: this.favoriteSearchType });
      const updateSourceFiltersSet = new Set();
      const initList = res.map(item => {
        const isUserCreate = item.create_user === (window.user_name || window.username);
        const visible_option = isUserCreate ? this.allOptionList : this.unPrivateOptionList;
        // 初始化表格, 判断当前的收藏是否是个人创建 若不是个人则不显示个人组
        const is_group_disabled = item.group_id === 0;
        const visible_type = item.group_id === 0 ? 'private' : 'public';
        if (!updateSourceFiltersSet.has(item.update_user)) updateSourceFiltersSet.add(item.update_user);
        return {
          ...item,
          group_id: String(item.group_id),
          group_option: this.unPrivateList,
          group_option_private: this.privateList,
          visible_option,
          is_group_disabled,
          visible_type,
          isShowJsonKeywords: false
        };
      });
      this.updateSourceFilters = [...updateSourceFiltersSet].map(item => ({
        text: item,
        value: item
      }));
      this.tableList = res.map(item => ({ ...item, group_id: String(item.group_id) }));
      this.operateTableList = initList;
      this.searchAfterList = initList;
    } catch (error) {
    } finally {
      this.handleSearchFilter();
      this.tableLoading = false;
    }
  }

  /** 获取组列表 */
  async getGroupList() {
    try {
      const res = await listFavoriteGroup({ type: this.favoriteSearchType });
      this.groupList = res.map(item => ({
        group_id: item.id,
        group_name: item.name
      }));
      this.unPrivateList = this.groupList.slice(1); // 去除个人组的列表
      this.privateList = this.groupList.slice(0, 1); // 个人组列表
      this.sourceFilters = res.map(item => ({
        text: item.name,
        value: item.id
      }));
    } catch (error) {
      console.warn(error);
    }
  }

  /** 更改收藏名 */
  handleChangeFavoriteName(row, name) {
    this.operateListChange(row, { name });
  }

  /** 新增或更新组名 */
  async handleAddGroupName() {
    try {
      createFavoriteGroup({
        bk_biz_id: this.bizId,
        type: this.favoriteSearchType,
        name: this.groupName
      }).then(async () => {
        await this.getGroupList();
        this.operateTableList.forEach(item => {
          this.operateListChange({ id: item.id }, { group_option: this.unPrivateList });
        });
      });
    } catch (error) {
    } finally {
      this.groupName = '';
    }
  }

  /** 修改可选范围 */
  handleSelectVisible(row, nVal: string) {
    const group_id = nVal !== 'public' ? '0' : 'null';
    const { group_name } = this.groupList.find(item => `${item.group_id}` === `${group_id}`);
    this.operateListChange(row, {
      visible_type: nVal,
      is_group_disabled: nVal === 'private',
      group_name,
      group_id
    });
  }
  /** 单独修改组 */
  handleChangeGroup(row, group_id: string) {
    const visible_type = group_id === '0' ? 'private' : 'public';
    const is_group_disabled = visible_type === 'private';
    this.operateListChange(row, { visible_type, is_group_disabled });
  }
  /** 用户操作 */
  operateListChange(row, operateObj = {}) {
    if (this.isCannotValueChange) return;

    // 搜索展示用的列表和操作缓存的列表同时更新数据
    for (const listName of ['searchAfterList', 'operateTableList']) {
      const index = this[listName].findIndex(item => item.id === row.id);
      if (index >= 0) Object.assign(this[listName][index], row, operateObj);
      if (listName === 'operateTableList') this.submitDataCompared(row, index, operateObj);
    }
  }
  /** 提交数据对比 */
  submitDataCompared(row, operateIndex, operateObj) {
    const submitIndex = this.submitTableList.findIndex(item => item.id === row.id);
    if (submitIndex >= 0) {
      // 操作已添加到更新列表的值 然后进行数据对比
      Object.assign(this.submitTableList[submitIndex], row, operateObj);
      const comparedSubData = deepClone(this.submitTableList[submitIndex]);
      const cloneTableData = deepClone(this.tableList[operateIndex]);
      this.deleteSubmitData(comparedSubData, this.cannotComparedData); // 前端加的参数 不做对比
      this.deleteSubmitData(cloneTableData, this.cannotComparedData); // 前端加的参数 不做对比
      if (JSON.stringify(cloneTableData) === JSON.stringify(comparedSubData)) {
        this.submitTableList.splice(submitIndex, 1); // 判断数据是否相同 相同则删除提交更新里的值
      }
    } else {
      // 第一次操作相同的列 添加到提交更新列表
      const comparedData = deepClone(this.operateTableList[operateIndex]);
      const cloneTableData = deepClone(this.tableList[operateIndex]);
      this.deleteSubmitData(comparedData, this.cannotComparedData); // 前端加的参数 不做对比
      this.deleteSubmitData(cloneTableData, this.cannotComparedData); // 前端加的参数 不做对比
      // 判断操作过后的值和表格里的是否相同 不同则添加到提交更新列表
      if (JSON.stringify(comparedData) !== JSON.stringify(cloneTableData)) {
        this.submitTableList.push(comparedData);
      }
    }
  }
  /** 删除不做对比的参数 */
  deleteSubmitData(data: IFavoriteItem, list: string[]) {
    list.forEach(item => delete data[item]);
  }
  /** 获取展示时间 */
  getShowTime(timeStr: string) {
    return dayjs.tz(timeStr).format('YYYY-MM-DD HH:mm:ss');
  }
  /** 删除收藏 */
  handleDeleteFavorite(row) {
    this.$bkInfo({
      subTitle: this.$t('当前收藏名为{name}是否删除?', { name: row.name }),
      type: 'warning',
      confirmFn: () => {
        this.deleteTableIDList.push(row.id);
        // 删除收藏 把展示的表格, 操作表格, 提交表格, 以及基础表格统一删除
        for (const listName of ['searchAfterList', 'operateTableList', 'submitTableList', 'tableList']) {
          const index = this[listName].findIndex(item => item.id === row.id);
          if (index >= 0) this[listName].splice(index, 1);
        }
        // 当前选中选择删除
        const index = this.selectFavoriteList.findIndex(item => item === row.id);
        if (index >= 0) this.selectFavoriteList.splice(index, 1);
        destroyFavorite(row.id, { type: this.favoriteSearchType }).catch(err => console.warn(err));
      }
    });
  }
  /** 点击确定提交管理弹窗数据 */
  handleSubmitTableData() {
    this.tableLoading = true;
    Promise.all([this.batchDeleteFavorite(), this.batchUpdateFavorite()])
      .then(() => {
        this.handleValueChange(false);
        this.handleSubmitChange(true);
      })
      .finally(() => {
        this.tableLoading = false;
      });
  }

  // 删除接口
  async batchDeleteFavorite() {
    // 若没有删除则不请求
    if (!this.deleteTableIDList.length) return;
    try {
      const data = {
        bk_biz_id: this.bizId,
        type: this.favoriteSearchType,
        ids: this.deleteTableIDList
      };
      await bulkDeleteFavorite(data);
    } catch (error) {}
  }

  // 更新收藏接口
  async batchUpdateFavorite() {
    // 若没有更新收藏则不请求
    if (!this.submitTableList.length) return;
    try {
      const configs = this.submitTableList.map(item => ({
        id: item.id,
        name: item.name,
        group_id: item.group_id === null ? null : Number(item.group_id)
      }));
      const data = {
        bk_biz_id: this.bizId,
        type: this.favoriteSearchType,
        configs
      };
      await bulkUpdateFavorite(data);
    } catch (error) {}
  }

  /** 所属组和变更人分组操作 */
  sourceFilterMethod(value, row, column) {
    const { property } = column;
    this.isCannotValueChange = true;
    setTimeout(() => {
      // 因分组显示会导致数据更变 不改变数据
      this.isCannotValueChange = false;
    }, 500);
    return row[property] === String(value);
  }

  handleSettingChange({ fields, size }) {
    this.tableSetting.selectedFields = fields;
    this.tableSetting.size = size;
  }

  checkFields(field) {
    return this.tableSetting.selectedFields.some(item => item.id === field);
  }

  render() {
    const expandSlot = {
      default: ({ row }) => (
        <div class='expand-container'>
          <div class='expand-information'>
            <span>{this.$t('查询语句')}</span>
            {this.favoriteSearchType === 'metric' ? metricKeywordsSlot(row) : eventKeywordsSlot(row)}
          </div>
        </div>
      )
    };

    const metricKeywordsSlot = row => (
      <div class='view-box'>
        {row.isShowJsonKeywords ? (
          <div class='view-content'>
            <VueJsonPretty
              deep={5}
              data={row.config}
            ></VueJsonPretty>
          </div>
        ) : (
          <span
            class='string-json'
            onClick={() => (row.isShowJsonKeywords = true)}
          >
            {JSON.stringify(row.config)}
          </span>
        )}
      </div>
    );

    const eventKeywordsSlot = row => <span>{row.config?.queryConfig.query_string}</span>;

    const nameSlot = {
      default: ({ row }) => [
        <div class='group-container'>
          <bk-checkbox
            class='group-check-box'
            checked={this.getCheckedStatus(row)}
            on-change={status => this.handleRowCheckChange(row, status)}
          ></bk-checkbox>
          <div class='manage-input'>
            <bk-input
              vModel={row.name}
              onBlur={val => this.handleChangeFavoriteName(row, val)}
            ></bk-input>
          </div>
        </div>
      ]
    };

    const groupSlot = {
      default: ({ row }) => [
        <bk-select
          vModel={row.group_id}
          searchable
          clearable={false}
          disabled={row.is_group_disabled}
          ext-popover-cls='add-new-page-container'
          popover-min-width={200}
          on-change={id => this.handleChangeGroup(row, id)}
        >
          {row[row.visible_type === 'private' ? 'group_option_private' : 'group_option'].map(item => (
            <bk-option
              id={`${item.group_id}`}
              key={`${item.group_id}`}
              name={item.group_name}
            ></bk-option>
          ))}
          <div slot='extension'>
            {this.isShowAddGroup ? (
              <div
                class='select-add-new-group'
                onClick={() => (this.isShowAddGroup = false)}
              >
                <div>
                  <i class='bk-icon icon-plus-circle'></i>
                  {this.$t('新增')}
                </div>
              </div>
            ) : (
              <li class='add-new-page-input'>
                <bk-input
                  vModel={this.groupName}
                  maxlength={30}
                  behavior={'simplicity'}
                ></bk-input>
                <div class='operate-button'>
                  <span
                    class='bk-icon icon-check-line'
                    onClick={() => this.handleAddGroupName()}
                  ></span>
                  <span
                    class='bk-icon icon-close-line-2'
                    onClick={() => {
                      this.isShowAddGroup = true;
                      this.groupName = '';
                    }}
                  ></span>
                </div>
              </li>
            )}
          </div>
        </bk-select>
      ]
    };

    const visibleSlot = {
      default: ({ row }) => [
        <bk-select
          vModel={row.visible_type}
          on-selected={nVal => this.handleSelectVisible(row, nVal)}
          clearable={false}
        >
          {row.visible_option.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            ></bk-option>
          ))}
        </bk-select>
      ]
    };

    const switchSlot = {
      default: ({ row }) => [
        <div class='switcher-box'>
          <div
            class='delete'
            onClick={() => this.handleDeleteFavorite(row)}
          >
            <span class='bk-icon icon-delete'></span>
          </div>
        </div>
      ]
    };

    const renderHeader = () => (
      <bk-checkbox
        class='all-check-box'
        value={this.checkValue === 2}
        indeterminate={this.checkValue === 1}
        on-change={this.handleSelectionChange}
        disabled={this.searchAfterList.length === 0}
      ></bk-checkbox>
    );

    return (
      <bk-dialog
        value={this.value}
        title={this.$t('管理')}
        header-position='left'
        render-directive='if'
        mask-close={false}
        ext-cls='manage-group'
        width={750}
        position={{ top: this.positionTop }}
        confirm-fn={this.handleSubmitTableData}
        on-value-change={this.handleValueChange}
      >
        <div class={`top-operate ${!this.selectCount && 'is-not-select'}`}>
          <div class='favorite-size'>
            <i18n path='共{0}个收藏'>
              &nbsp;
              <span class='size-weight'>{this.showFavoriteCount}</span>
              &nbsp;
            </i18n>
          </div>
          <bk-input
            class='operate-input'
            rightIcon='bk-icon icon-search'
            vModel={this.searchValue}
            onEnter={this.handleSearchFilter}
            onKeyup={this.handleInputSearchFavorite}
            onRightIconClick={this.handleSearchFilter}
            placeholder={this.$t('输入')}
          />
        </div>
        {this.selectCount ? (
          <div class='table-top-operate'>
            <span>
              <i18n path='当前已选择{0}条数据'>
                <span class='operate-message'>{this.selectCount}</span>
              </i18n>
            </span>
            <bk-dropdown-menu trigger='click'>
              <div
                class='dropdown-trigger-text'
                slot='dropdown-trigger'
              >
                <span class='operate-click'>
                  ，&nbsp;{this.$t('移至分组')}
                  <span class='bk-icon icon-down-shape'></span>
                </span>
              </div>
              <div
                class='dropdown-list'
                slot='dropdown-content'
              >
                <ul class='search-li'>
                  {this.unPrivateList.map(item => (
                    <li onClick={() => this.handleClickMoveGroup(item)}>{item.group_name}</li>
                  ))}
                </ul>
              </div>
            </bk-dropdown-menu>
          </div>
        ) : undefined}
        <bk-table
          data={this.searchAfterList}
          size='small'
          header-border={true}
          border={true}
          max-height={this.maxHeight}
          empty-text={this.$t('查无数据')}
          v-bkloading={{ isLoading: this.tableLoading }}
          ext-cls={`${!this.selectCount && 'is-not-select'}`}
        >
          <bk-table-column
            width='64'
            type='expand'
            render-header={renderHeader}
            scopedSlots={expandSlot}
          ></bk-table-column>

          <bk-table-column
            label={this.$t('收藏名')}
            key={'column_name'}
            width='200'
            prop={'name'}
            class-name='group-input'
            label-class-name='group-title'
            scopedSlots={nameSlot}
          ></bk-table-column>

          {this.checkFields('group_name') ? (
            <bk-table-column
              label={this.$t('所属组')}
              min-width='112'
              key={'column_group_name'}
              prop={'group_id'}
              scopedSlots={groupSlot}
              label-class-name='group-title'
              class-name='group-select'
              filters={this.sourceFilters}
              filter-multiple={false}
              filter-method={this.sourceFilterMethod}
            ></bk-table-column>
          ) : undefined}

          {this.checkFields('visible_type') ? (
            <bk-table-column
              label={this.$t('可见范围')}
              min-width='112'
              key={'column_visible_type'}
              prop={'visible_type'}
              scopedSlots={visibleSlot}
              label-class-name='group-title'
              class-name='group-select'
            ></bk-table-column>
          ) : undefined}

          {this.checkFields('updated_by') ? (
            <bk-table-column
              label={this.$t('最近更新人')}
              prop={'update_user'}
              key={'column_update_by'}
              filters={this.updateSourceFilters}
              filter-multiple={false}
              filter-method={this.sourceFilterMethod}
            ></bk-table-column>
          ) : undefined}

          {this.checkFields('updated_at') ? (
            <bk-table-column
              label={this.$t('最近更新时间')}
              prop={'update_time'}
              key={'column_update_time'}
              scopedSlots={{
                default: ({ row }) => [<span>{this.getShowTime(row.update_time)}</span>]
              }}
            ></bk-table-column>
          ) : undefined}

          <bk-table-column
            class-name='group-input'
            width='1'
            label-class-name='group-title'
            key={'column_switch'}
            scopedSlots={switchSlot}
          ></bk-table-column>

          <bk-table-column type='setting'>
            <bk-table-setting-content
              fields={this.tableSetting.fields}
              size={this.tableSetting.size}
              selected={this.tableSetting.selectedFields}
              on-setting-change={this.handleSettingChange}
            ></bk-table-setting-content>
          </bk-table-column>
        </bk-table>
      </bk-dialog>
    );
  }
}
