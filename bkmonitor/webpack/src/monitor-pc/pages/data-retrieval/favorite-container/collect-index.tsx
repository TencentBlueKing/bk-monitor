/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Debounce, deepClone } from 'monitor-common/utils';

import CollectContainer from './collect-container';
import SharedDialog from './component/shared-dialog';
import FavoriteManageDialog from './favorite-manage-dialog';
// import ManageGroupDialog from './manage-group-dialog';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { FavoriteIndexType, IFavList } from '../typings';

import './collect-index.scss';

const VIEW_DATA_ID_KEY = 'bk_monitor_favorite_view_data_id';

@Component
export default class CollectIndex extends tsc<FavoriteIndexType.IProps, FavoriteIndexType.IEvent> {
  @Prop({ default: () => [], type: Array }) favoritesList: IFavList.favGroupList[]; // 收藏列表
  @Prop({ default: () => ({}), type: Object }) favCheckedValue: IFavList.favList; // 当前点击的收藏
  @Prop({ default: false, type: Boolean }) isShowFavorite: boolean; // 是否展开收藏列表
  @Prop({ default: false, type: Boolean }) favoriteLoading: boolean; // 请求中
  @Prop({ default: 'metric', type: String }) favoriteSearchType: string; // 当前页收藏类型
  @Prop({ default: '' }) dataId: string; // 数据id

  @Ref('checkInputForm') checkInputFormRef: any;
  @Ref('popoverGroup') popoverGroupRef: any;
  @Ref('popoverSort') popoverSortRef: any;
  @Ref('collectContainer') collectContainerRef: CollectContainer;
  isShowManageDialog = false; // 是否展示管理弹窗
  isShowSharedDialog = false;
  isSearchFilter = false; // 是否搜索过滤
  isShowAddNewFavoriteDialog = false; // 是否展示编辑收藏弹窗
  searchVal = ''; // 搜索
  allExpand = true; // 是否全部展开
  // groupName = ''; // 新增或编辑组名
  verifyData = {
    groupName: '',
  };
  sharedConfig = null as IFavList.favList;
  baseSortType = 'asc'; // 排序参数
  sortType = 'asc'; // 展示的排序参数
  groupSortList = [
    // 排序展示列表
    {
      name: window.i18n.t('按名称 A - Z 排序'),
      id: 'asc',
    },
    {
      name: window.i18n.t('按名称 Z - A 排序'),
      id: 'desc',
    },
    {
      name: window.i18n.t('按更新时间排序'),
      id: 'update',
    },
  ];
  public rules = {
    groupName: [
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
  tippyOption = {
    trigger: 'click',
    interactive: true,
    theme: 'light',
  };
  groupList: IFavList.groupList[] = []; // 分组列表
  filterCollectList: IFavList.favGroupList[] = []; // 搜索的收藏列表
  emptyStatusType: EmptyStatusType = 'empty';
  /** 是否仅查看数据Id */
  isViewDataId = JSON.parse(localStorage.getItem(VIEW_DATA_ID_KEY) || 'true');

  get isNewSearch() {
    return this.favCheckedValue === null;
  }

  get allFavoriteNumber() {
    return this.favoritesList.reduce((pre: number, cur) => pre + cur.favorites.length, 0);
  }

  @Watch('isShowFavorite', { immediate: true })
  async handleShowCollect(value: boolean) {
    if (value) {
      this.baseSortType = localStorage.getItem('bk_monitor_favorite_sort_type') || 'asc';
      this.sortType = localStorage.getItem('bk_monitor_favorite_sort_type') || 'asc';
      this.handleEmitOperateChange('request-query-history');
    } else {
      this.filterCollectList = [];
      this.searchVal = '';
    }
  }

  @Watch('favoritesList', { deep: true }) // 收藏列表有操作 重新请求
  operateChangeFavoriteList() {
    this.handleSearchFavorite(); // 更新收藏列表
    this.initGroupList(); // 更新组列表
  }

  @Watch('dataId')
  watchDataIdChange() {
    this.handleSearchFavorite();
  }

  @Emit('operateChange')
  handleEmitOperateChange(operate: string, value?: any) {
    return { operate, value };
  }

  checkName() {
    if (this.verifyData.groupName.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.verifyData.groupName.trim()
    );
  }

  checkExistName() {
    return !this.groupList.some(item => item.group_name === this.verifyData.groupName);
  }

  handleGroupKeyDown(value: string, event) {
    if (event.code === 'Tab' && !!value) {
      this.handleEmitOperateChange('add-group', value);
      this.popoverGroupRef.hideHandler();
      this.verifyData.groupName = '';
    }
  }

  /** 用户收藏操作 */
  handleUserOperate(obj) {
    if (obj.type === 'business-copy') {
      this.isShowSharedDialog = true;
      this.sharedConfig = obj.value;
      return;
    }
    this.handleEmitOperateChange(obj.type, obj.value);
  }

  /** 初始化组列表 */
  initGroupList() {
    this.groupList = this.favoritesList.map(item => ({
      group_name: item.name,
      group_id: item.id,
    }));
  }

  /** 新增组 */
  async handleClickGroupBtn(clickType: string) {
    if (clickType === 'add') {
      this.checkInputFormRef.validate().then(async () => {
        this.handleEmitOperateChange('add-group', this.verifyData.groupName);
        this.popoverGroupRef.hideHandler();
        setTimeout(() => {
          this.verifyData.groupName = '';
        }, 500);
      });
    }
    if (clickType === 'cancel') {
      this.popoverGroupRef.hideHandler();
      this.checkInputFormRef.clearError();
    }
  }

  /** 收藏排序 */
  handleClickSortBtn(clickType: string) {
    if (clickType === 'sort') {
      this.baseSortType = this.sortType;
      localStorage.setItem('bk_monitor_favorite_sort_type', this.sortType);
      this.handleEmitOperateChange('request-query-history');
    } else {
      setTimeout(() => {
        this.sortType = this.baseSortType;
      }, 500);
    }
    this.popoverSortRef.hideHandler();
  }

  /** 收藏搜索 */
  @Debounce(100)
  handleSearchFavorite() {
    if (this.emptyStatusType !== '500') this.emptyStatusType = this.searchVal ? 'search-empty' : 'empty';
    let showFavList = deepClone(this.favoritesList);
    // 当前只有未分组和个人收藏时 判断未分组是否有数据 如果没有 则不展示未分组
    if (showFavList.length === 2 && !showFavList[1].favorites.length) {
      showFavList = [showFavList[0]];
    }
    if (this.favoriteSearchType === 'event' && this.isViewDataId) {
      showFavList = showFavList.map(item => {
        const favorites = item.favorites.filter(
          favorite => favorite.config.queryConfig?.result_table_id === this.dataId
        );
        item.favorites = favorites;
        return item;
      });
    }
    if (this.searchVal === '') {
      this.filterCollectList = showFavList;
      this.isSearchFilter = false;
      return;
    }
    this.isSearchFilter = true;
    this.filterCollectList = showFavList
      .map(item => ({
        ...item,
        favorites: item.favorites.filter(
          fItem => fItem.create_user.includes(this.searchVal) || fItem.name.includes(this.searchVal)
        ),
      }))
      .filter(item => item.favorites.length);
  }

  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchVal = '';
      this.handleSearchFavorite();
      return;
    }
    if (type === 'refresh') {
      this.$emit('getFavoritesList');
      return;
    }
  }

  handleCollapseAll() {
    this.collectContainerRef?.handleExpandAll(!this.allExpand);
    this.allExpand = !this.allExpand;
  }

  @Emit('close')
  handleClose() {}

  handleIsViewDataIdChange(check: boolean) {
    this.isViewDataId = check;
    this.handleSearchFavorite();
    localStorage.setItem(VIEW_DATA_ID_KEY, String(check));
  }

  favoriteManageDialogChange(show: boolean) {
    this.isShowManageDialog = show;
  }

  render() {
    return (
      <div class='retrieve-collect-index-comp'>
        <CollectContainer
          ref='collectContainer'
          collectLoading={this.favoriteLoading}
          dataList={this.filterCollectList}
          emptyStatusType={this.emptyStatusType}
          favCheckedValue={this.favCheckedValue}
          groupList={this.groupList}
          isSearchFilter={this.isSearchFilter}
          onChange={this.handleUserOperate}
          onHandleOperation={this.handleEmptyOperation}
        >
          <div class='search-container'>
            <div class='fl-jcsb'>
              <span class='search-title fl-jcsb'>
                <span
                  class='icon-monitor icon-gongneng-shouqi'
                  v-bk-tooltips={{ content: this.$t('收起收藏夹') }}
                  onClick={this.handleClose}
                />
                {this.$t('收藏夹')}
                <span class='favorite-number'>{this.allFavoriteNumber}</span>
              </span>
              <div class='tools'>
                <span
                  class='icon-monitor icon-shezhi1'
                  v-bk-tooltips={{ content: this.$t('收藏管理') }}
                  onClick={() => (this.isShowManageDialog = true)}
                />
              </div>
            </div>
            <bk-input
              class='search-input'
              vModel={this.searchVal}
              native-attributes={{
                spellcheck: false,
              }}
              placeholder={this.$t('搜索收藏名')}
              right-icon='bk-icon icon-search'
              onEnter={this.handleSearchFavorite}
              onInput={this.handleSearchFavorite}
              onRightIconClick={this.handleSearchFavorite}
            />
            <div class='data-tool-btn fl-jcsb'>
              {this.favoriteSearchType === 'event' && (
                <bk-checkbox
                  class='view-data'
                  value={this.isViewDataId}
                  onChange={this.handleIsViewDataIdChange}
                >
                  {this.$t('仅查看当前数据 ID')}
                </bk-checkbox>
              )}
              <div class='tools-btn'>
                <bk-popover
                  ref='popoverGroup'
                  ext-cls='new-group-popover'
                  placement='bottom-start'
                  tippy-options={this.tippyOption}
                >
                  <i
                    class='icon-monitor icon-xinjianwenjianjia tool-icon'
                    v-bk-tooltips={{ content: this.$t('新建收藏分组') }}
                  />
                  <div slot='content'>
                    <bk-form
                      ref='checkInputForm'
                      style={{ width: '100%' }}
                      labelWidth={0}
                      {...{
                        props: {
                          model: this.verifyData,
                          rules: this.rules,
                        },
                      }}
                    >
                      <bk-form-item property='groupName'>
                        <bk-input
                          vModel={this.verifyData.groupName}
                          placeholder={this.$t('输入组名,30个字符')}
                          clearable
                          onEnter={() => this.handleClickGroupBtn('add')}
                          onKeydown={this.handleGroupKeyDown}
                        />
                      </bk-form-item>
                    </bk-form>
                    <div class='operate-button'>
                      <bk-button
                        text
                        onClick={() => this.handleClickGroupBtn('add')}
                      >
                        {this.$t('确定')}
                      </bk-button>
                      <span onClick={() => this.handleClickGroupBtn('cancel')}>{this.$t('取消')}</span>
                    </div>
                  </div>
                </bk-popover>
                <i
                  class={['icon-monitor ml12', this.allExpand ? 'icon-zhankai-2' : 'icon-shouqi3']}
                  v-bk-tooltips={{ content: this.$t(this.allExpand ? '全部收起' : '全部展开') }}
                  onClick={this.handleCollapseAll}
                />
                <bk-popover
                  ref='popoverSort'
                  class='ml12'
                  ext-cls='sort-group-popover'
                  placement='bottom-start'
                  tippy-options={this.tippyOption}
                >
                  <span
                    class='icon-monitor icon-paixu1'
                    v-bk-tooltips={{ content: this.$t('调整排序') }}
                  />
                  <div slot='content'>
                    <span style={{ fontSize: '14px', marginTop: '8px' }}>{this.$t('收藏排序')}</span>
                    <bk-radio-group
                      class='sort-group-container'
                      vModel={this.sortType}
                    >
                      {this.groupSortList.map(item => (
                        <bk-radio
                          key={item.id}
                          value={item.id}
                        >
                          {item.name}
                        </bk-radio>
                      ))}
                    </bk-radio-group>
                    <div class='operate-button'>
                      <bk-button
                        theme='primary'
                        onClick={() => this.handleClickSortBtn('sort')}
                      >
                        {this.$t('确定')}
                      </bk-button>
                      <bk-button onClick={() => this.handleClickSortBtn('cancel')}>{this.$t('取消')}</bk-button>
                    </div>
                  </div>
                </bk-popover>
              </div>
            </div>
          </div>
          <div
            class={['new-search', { active: this.isNewSearch }]}
            onClick={() => this.handleEmitOperateChange('new-search', undefined)}
          >
            <span class='icon-monitor icon-xinjiansuo' />
            <span>{this.$t('新检索')}</span>
          </div>
        </CollectContainer>
        {/* <ManageGroupDialog
          v-model={this.isShowManageDialog}
          favoriteSearchType={this.favoriteSearchType}
          onSubmit={(value: boolean) => value && this.handleEmitOperateChange('request-query-history')}
        /> */}
        <FavoriteManageDialog
          favoriteList={this.favoritesList}
          favoriteType={this.favoriteSearchType}
          show={this.isShowManageDialog}
          onOperateChange={this.handleEmitOperateChange}
          onShowChange={this.favoriteManageDialogChange}
        />
        <SharedDialog
          v-model={this.isShowSharedDialog}
          favoriteConfig={this.sharedConfig}
          favoriteSearchType={this.favoriteSearchType}
        />
      </div>
    );
  }
}
