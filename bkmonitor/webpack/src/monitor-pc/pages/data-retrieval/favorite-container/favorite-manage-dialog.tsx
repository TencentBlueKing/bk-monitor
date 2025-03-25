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
import { createFavoriteGroup } from 'monitor-api/modules/model';
import { deepClone } from 'monitor-common/utils';
import MonitorDialog from 'monitor-ui/monitor-dialog';

import type { IFavList } from '../typings';

import './favorite-manage-dialog.scss';
interface FavoriteManageDialogProps {
  show: boolean;
  favoriteType: string;
  favoriteList: IFavList.favGroupList[];
}

interface FavoriteManageDialogEvents {
  onShowChange(show: boolean): void;
  onOperateChange(operate: string, value?: any): void;
}

@Component
export default class FavoriteManageDialog extends tsc<FavoriteManageDialogProps, FavoriteManageDialogEvents> {
  @Prop({ default: false }) show: boolean;
  @Prop({ default: 'event' }) favoriteType: string;
  @Prop({ default: () => [] }) favoriteList: IFavList.favGroupList[];

  @Ref('addGroupPopover') addGroupPopoverRef;
  @Ref('checkInputForm') checkInputFormRef;

  /** 所有的分组和收藏 */
  localFavoriteList: IFavList.favGroupList[] = [];
  /** 分组查询关键字 */
  groupSearchValue = '';
  /** 全部收藏 */
  allGroupList: IFavList.favList[] = [];
  /** 未分组 */
  noGroupList: IFavList.favList[] = [];
  /** 个人收藏 */
  privateFavorite: IFavList.favList[] = [];
  /** 其余分组 */
  otherGroupList: IFavList.favGroupList[] = [];
  /** 当前选择的分组 */
  curSelectGroup: number | string = 'all';
  /** 搜索结束后展示的组列表 */
  searchResultGroupList: IFavList.favGroupList[] = [];
  /** 当前选择分组的收藏列表 */
  curSelectGroupFavorites: IFavList.favList[] = [];
  /** 筛选后展示的收藏列表 */
  searchResultFavorites: IFavList.favList[] = [];
  /** 收藏查询关键字 */
  favoriteSearchValue = '';
  /** 已勾选的收藏列表 */
  selectFavoriteList: IFavList.favList[] = [];
  /** 当前点击的行 */
  curClickRow = null;
  /** 当前hover的行 */
  curHoverRowIndex = -1;

  addGroupData = {
    name: '',
  };

  rules = {
    name: [
      {
        validator: this.checkName,
        message: window.i18n.t('组名不规范, 包含了特殊符号.'),
        trigger: 'blur',
      },
      {
        validator: this.checkExistName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur',
      },
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.i18n.t('注意：最大值为30个字符'),
        trigger: 'blur',
      },
    ],
  };

  get tableFilters() {
    const names = {};
    const ids = {};
    const groups = {};
    for (const item of this.searchResultFavorites) {
      if (!names[item.update_user]) {
        names[item.update_user] = item.update_user;
      }
      if (this.favoriteType === 'event' && !ids[item.config.queryConfig.result_table_id]) {
        ids[item.config.queryConfig.result_table_id] = item.config.queryConfig.result_table_id;
      }
      if (!groups[item.group_id as number]) {
        groups[item.group_id as number] = item.group_id;
      }
    }
    return {
      names: Object.keys(names).map(key => ({ text: key, value: names[key] })),
      ids: Object.keys(ids).map(key => ({ text: key, value: ids[key] })),
      groups: Object.keys(groups).map(key => {
        const text = this.localFavoriteList.find(item => item.id === groups[key])?.name;
        return { text, value: groups[key] };
      }),
    };
  }

  @Watch('favoriteList')
  watchFavoriteListChange(val: IFavList.favGroupList[]) {
    this.splitFavoriteList(val);
    this.handleSelectGroupChange(this.curSelectGroup);
  }

  @Watch('show')
  watchShowChange(val: boolean) {
    if (val) {
      this.splitFavoriteList(this.favoriteList);
      this.handleSelectGroupChange(this.curSelectGroup);
    } else {
      this.groupSearchValue = '';
      this.favoriteSearchValue = '';
      this.curSelectGroup = 'all';
    }
  }

  /** 对收藏组进行拆解 */
  splitFavoriteList(val: IFavList.favGroupList[]) {
    this.privateFavorite = [];
    this.otherGroupList = [];
    this.allGroupList = [];
    this.noGroupList = [];
    this.localFavoriteList = deepClone(val);
    for (const group of this.localFavoriteList) {
      if (group.id === 0) {
        this.privateFavorite = group.favorites || [];
      } else if (group.id === null) {
        this.noGroupList = group.favorites || [];
      } else {
        this.otherGroupList.push(group);
      }
      this.allGroupList = this.allGroupList.concat(group.favorites || []);
    }
  }

  @Emit('showChange')
  handleShowChange(show = false) {
    return show;
  }

  /** 切换分组，获取收藏列表 */
  handleSelectGroupChange(id: number | string) {
    this.curSelectGroup = id;
    this.selectFavoriteList = [];
    switch (id) {
      case 'all':
        this.curSelectGroupFavorites = this.allGroupList;
        break;
      case 'noGroup':
        this.curSelectGroupFavorites = this.noGroupList;
        break;
      case 'private':
        this.curSelectGroupFavorites = this.privateFavorite;
        break;
      default:
        this.curSelectGroupFavorites = this.otherGroupList.find(item => item.id === id)?.favorites || [];
    }
    this.handleFavoriteSearch();
  }

  /** 收藏列表搜索 */
  handleFavoriteSearch() {
    this.searchResultFavorites = this.curSelectGroupFavorites.filter(favorite =>
      favorite.name.includes(this.favoriteSearchValue)
    );
  }

  /** 组搜索 */
  handleGroupSearch() {
    this.searchResultGroupList = this.otherGroupList.filter(group => group.name.includes(this.groupSearchValue));
  }

  checkName() {
    if (this.addGroupData.name.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.addGroupData.name.trim()
    );
  }

  checkExistName() {
    return !this.localFavoriteList.some(item => item.name === this.addGroupData.name);
  }

  /** 添加分组 */
  handleAddGroupConfirm() {
    this.checkInputFormRef.validate().then(async () => {
      await createFavoriteGroup({
        type: this.favoriteType,
        name: this.addGroupData.name,
      });
      this.handleAddGroupPopoverHidden();
      this.$emit('operateChange', 'request-query-history');
    });
  }

  /** 隐藏添加分组popover */
  handleAddGroupPopoverHidden() {
    this.addGroupData.name = '';
    this.checkInputFormRef?.clearError();
    this.addGroupPopoverRef?.hideHandler();
  }

  /** 表格行点击触发 */
  handleRowClick(row) {
    this.curClickRow = row;
  }

  /** 添加行类名 */
  getRowClassName({ row, rowIndex }) {
    const styles = [];
    if (row.id === this.curClickRow?.id) styles.push('row-click');
    if (rowIndex === this.curHoverRowIndex) styles.push('row-hover');
    return styles.join(' ');
  }

  /** 自定义收藏名称展示 */
  favoriteNameScopedSlots({ row }) {
    if (!row.edit)
      return (
        <div class='edit-cell'>
          <span class='text name'>{row.name}</span>
          <i class='icon-monitor icon-bianji' />
        </div>
      );
  }

  /** 自定义所属组展示 */
  groupScopedSlots({ row }) {
    if (!row.edit)
      return (
        <div class='edit-cell'>
          <span class='text'>{this.tableFilters.groups.find(item => item.value === row.group_id)?.text}</span>
          <i class='icon-monitor icon-bianji' />
        </div>
      );
  }

  handleDeleteFavorite(row) {
    this.$emit('operateChange', 'delete-favorite', row);
  }

  renderEventColumns() {
    return [
      <bk-table-column
        key='result_table_id'
        filter-method={(value, row) => row.config.queryConfig.result_table_id === value}
        filters={this.tableFilters.ids}
        formatter={row => row.config.queryConfig.result_table_id}
        label={this.$t('数据ID')}
        prop='result_table_id'
        filter-multiple
      />,
    ];
  }

  render() {
    return (
      <MonitorDialog
        class='favorite-group-dialog'
        fullScreen={true}
        needFooter={false}
        needHeader={false}
        value={this.show}
        onChange={this.handleShowChange}
      >
        <div class='favorite-group-dialog-header'>
          {this.$t('收藏管理')}
          <i
            class='bk-icon icon-close close-icon'
            onClick={() => this.handleShowChange(false)}
          />
        </div>
        <div class='favorite-group-dialog-content'>
          <div class='favorite-group-filter'>
            <div class='group-type-container'>
              <div
                class={['group-item', { active: this.curSelectGroup === 'all' }]}
                onClick={() => {
                  this.handleSelectGroupChange('all');
                }}
              >
                <i class='icon-monitor icon-all' />
                <span class='group-name'>{this.$t('全部收藏')}</span>
                <span class='favorite-count'>{this.allGroupList.length}</span>
              </div>
              <div
                class={['group-item', { active: this.curSelectGroup === 'noGroup' }]}
                onClick={() => {
                  this.handleSelectGroupChange('noGroup');
                }}
              >
                <i class='icon-monitor icon-mc-file-close' />
                <span class='group-name'>{this.$t('未分组')}</span>
                <span class='favorite-count'>{this.noGroupList.length}</span>
              </div>
              <div
                class={['group-item', { active: this.curSelectGroup === 'private' }]}
                onClick={() => {
                  this.handleSelectGroupChange('private');
                }}
              >
                <i class='icon-monitor icon-file-personal' />
                <span class='group-name'>{this.$t('个人收藏')}</span>
                <span class='favorite-count'>{this.privateFavorite.length}</span>
              </div>
            </div>
            <div class='search-input-container'>
              <bk-popover
                ref='addGroupPopover'
                ext-cls='new-add-group-popover'
                tippy-options={{
                  trigger: 'click',
                  interactive: true,
                  theme: 'light',
                }}
                placement='bottom-start'
              >
                <div class='add-group-btn'>
                  <i class='icon-monitor icon-a-1jiahao' />
                </div>
                <div slot='content'>
                  <bk-form
                    ref='checkInputForm'
                    style={{ width: '100%' }}
                    form-type='vertical'
                    {...{
                      props: {
                        model: this.addGroupData,
                        rules: this.rules,
                      },
                    }}
                  >
                    <bk-form-item
                      label={this.$tc('分组名称')}
                      property='name'
                      required
                    >
                      <bk-input
                        vModel={this.addGroupData.name}
                        placeholder={this.$t('输入组名,30个字符')}
                        clearable
                      />
                    </bk-form-item>
                  </bk-form>
                  <div class='operate-button'>
                    <bk-button
                      size='small'
                      theme='primary'
                      onClick={this.handleAddGroupConfirm}
                    >
                      {this.$t('确定')}
                    </bk-button>
                    <bk-button
                      size='small'
                      onClick={this.handleAddGroupPopoverHidden}
                    >
                      {this.$t('取消')}
                    </bk-button>
                  </div>
                </div>
              </bk-popover>

              <bk-input
                class='search-input'
                v-model={this.groupSearchValue}
                allow-emoji={false}
                right-icon='bk-icon icon-search'
                clearable
                show-clear-only-hover
                onInput={this.handleGroupSearch}
                onRightIconClick={this.handleGroupSearch}
              />
            </div>
            <div class='group-list'>
              {this.otherGroupList.map(group => (
                <div
                  key={group.id}
                  class={['group-item', { active: this.curSelectGroup === group.id }]}
                  onClick={() => {
                    this.handleSelectGroupChange(group.id);
                  }}
                >
                  <i class='icon-monitor icon-mc-file-close' />
                  <span class='group-name'>{group.name}</span>
                  <span class='favorite-count'>{group.favorites.length}</span>
                </div>
              ))}
            </div>
          </div>
          <div class='favorite-table-container'>
            <div class='table-header-operation'>
              <bk-button disabled={this.selectFavoriteList.length === 0}>
                {this.$t('批量操作')} <i class='icon-monitor icon-arrow-down' />
              </bk-button>
              <bk-input
                class='favorite-search-input'
                v-model={this.favoriteSearchValue}
                allow-emoji={false}
                right-icon='bk-icon icon-search'
                clearable
                show-clear-only-hover
                onInput={this.handleFavoriteSearch}
                onRightIconClick={this.handleFavoriteSearch}
              />
            </div>
            <div class='table-content'>
              <bk-table
                data={this.searchResultFavorites}
                max-height={525}
                row-class-name={this.getRowClassName}
                on-row-click={row => (this.curClickRow = row)}
                on-row-mouse-enter={index => (this.curHoverRowIndex = index)}
                on-row-mouse-leave={() => (this.curHoverRowIndex = -1)}
              >
                <bk-table-column
                  width='45'
                  type='selection'
                />
                <bk-table-column
                  scopedSlots={{
                    default: this.favoriteNameScopedSlots,
                  }}
                  label={this.$t('收藏名称')}
                  prop='name'
                />
                <bk-table-column
                  scopedSlots={{
                    default: this.groupScopedSlots,
                  }}
                  filter-method={(value, row) => row.group_id === value}
                  filters={this.tableFilters.groups}
                  label={this.$t('所属组')}
                  prop='group_id'
                  filter-multiple
                />
                {this.favoriteType === 'event' && this.renderEventColumns()}
                <bk-table-column
                  filter-method={(value, row, column) => row[column.property] === value}
                  filters={this.tableFilters.names}
                  label={this.$t('变更人')}
                  prop='update_user'
                  filter-multiple
                />
                <bk-table-column
                  formatter={row => dayjs(row.update_time).format('YYYY-MM-DD HH:mm:ss')}
                  label={this.$t('变更时间')}
                  prop='update_time'
                  sortable
                />
                <bk-table-column
                  width='80'
                  scopedSlots={{
                    default: ({ row }) => (
                      <span
                        class='del-btn'
                        onClick={() => this.handleDeleteFavorite(row)}
                      >
                        {this.$t('删除')}
                      </span>
                    ),
                  }}
                  label={this.$t('操作')}
                  prop='operation'
                />
              </bk-table>
            </div>
          </div>
          <div class='favorite-detail-container' />
        </div>
      </MonitorDialog>
    );
  }
}
