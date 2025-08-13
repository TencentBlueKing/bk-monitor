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

import {
  createFavorite,
  createFavoriteGroup,
  destroyFavorite,
  destroyFavoriteGroup,
  listByGroupFavorite,
  updateFavorite,
  updateFavoriteGroup,
} from 'monitor-api/modules/model';
import { deepClone } from 'monitor-common/utils';

import AddCollectDialog from './add-collect-dialog';
import FavoriteIndex from './collect-index';

import type { IFavList } from '../typings';

import './favorite-container.scss';

interface IEvent {
  onFavoriteListChange: (list: IFavList.favGroupList[]) => void;
  onSelectFavorite: (favorite: IFavList.favList) => void;
  onShowChange: (show: boolean) => void;
}

interface IProps {
  dataId?: string;
  favoriteSearchType: string;
  isShowFavorite: boolean;
}

@Component
export default class FavoriteContainer extends tsc<IProps, IEvent> {
  @Prop({ default: 'event' }) readonly favoriteSearchType!: string;
  @Prop({ default: true }) readonly isShowFavorite!: boolean;
  @Prop({ default: '' }) dataId: string;

  @Ref('favoriteIndex') favoriteIndexRef: FavoriteIndex;

  /** 是否是带有收藏id的初始化*/
  isHaveFavoriteInit = false;
  /** 收藏列表 */
  favoritesList: IFavList.favGroupList[] = [];
  favCheckedValue: IFavList.favList = null;
  /** 收藏查询中*/
  favoriteLoading = false;
  // 所有收藏的收藏名
  favStrList: string[];
  /** 是否展示新增收藏弹窗 */
  isShowAddFavoriteDialog = false;
  /** 编辑收藏弹窗时展示的收藏数据 */
  editFavoriteData: IFavList.favList = null;
  favoriteData = null;
  favoriteKeywordsData = null;

  get bizId(): string {
    return this.$store.getters.bizId;
  }

  created() {
    this.isHaveFavoriteInit = !!this.$route.query?.favorite_id;
  }

  @Watch('isShowFavorite')
  watchIsShowFavorite(val: boolean) {
    if (!val) this.favCheckedValue = null;
  }

  /**
   * @description: 获取收藏列表
   */
  async getListByGroupFavorite() {
    this.favoriteLoading = true;
    const order_type = localStorage.getItem('bk_monitor_favorite_sort_type') || 'asc'; // 获取收藏排序
    const param = { type: this.favoriteSearchType, order_type };
    await listByGroupFavorite(param)
      .then(res => {
        this.favoriteIndexRef && (this.favoriteIndexRef.emptyStatusType = 'empty');
        const provideFavorite = res[0];
        const publicFavorite = res[res.length - 1];
        const sortFavoriteList = res.slice(1, res.length - 1).sort((a, b) => a.name.localeCompare(b.name));
        const sortAfterList = [provideFavorite, ...sortFavoriteList, publicFavorite];
        this.favoritesList = this.setDisabledStatus(sortAfterList);
        this.favStrList = res.reduce((pre, cur) => {
          // 获取所有收藏的名字新增时判断是否重命名
          return pre.concat(cur.favorites.map(item => item.name));
        }, []);
        if (this.isHaveFavoriteInit) {
          // 判断是否是分享初始化
          const urlFavoriteID = this.$route.query.favorite_id;
          for (const gItem of res) {
            const favorite = gItem.favorites.find(item => String(item.id) === urlFavoriteID);
            if (favorite) {
              this.handleSelectFav(favorite);
              const { favorite_id, ...query } = this.$route.query;
              this.$router.replace({ query });
              break;
            }
          }
        }
      })
      .catch(err => {
        console.warn(err);
        this.favoriteIndexRef && (this.favoriteIndexRef.emptyStatusType = '500');
        this.favoritesList = [];
      })
      .finally(() => {
        // 获取收藏列表后 若当前不是新检索 则判断当前收藏是否已删除 若删除则变为新检索
        if (this.favCheckedValue !== null) {
          let isFindCheckValue = false; // 是否从列表中找到匹配当前收藏的id
          for (const gItem of this.favoritesList) {
            const findFavorites = gItem.favorites.find(item => item.id === this.favCheckedValue.id);
            if (findFavorites) {
              isFindCheckValue = true; // 找到 中断循环
              break;
            }
          }
          if (!isFindCheckValue) {
            // 未找到 清空当前收藏 变为新检索
            this.favCheckedValue = null;
            this.handleSelectFav(null);
          }
        }
        this.favoriteLoading = false;
        this.isHaveFavoriteInit = false;
      });

    this.$emit('favoriteListChange', this.favoritesList);
  }

  setDisabledStatus(favoritesList: IFavList.favGroupList[]) {
    const list = favoritesList;
    const routeName = this.$route.name;
    /** 新版事件检索暂不支持日志关键字，需要把日志关键字的收藏给禁用掉 */
    if (routeName === 'event-explore') {
      for (const favoriteGroup of list) {
        for (const favorite of favoriteGroup.favorites) {
          const data_source_label = favorite.config?.queryConfig?.data_source_label;
          const data_type_label = favorite.config?.queryConfig?.data_type_label;
          const eventType = `${data_source_label}_${data_type_label}`;
          if (eventType === 'bk_monitor_log') {
            favorite.disabled = true;
          } else {
            favorite.disabled = false;
          }
        }
      }
    }
    return list;
  }

  /** 收藏列表操作 */
  handleFavoriteOperate(operate: string, value?: IFavList.favList) {
    switch (operate) {
      case 'click-favorite': // 点击收藏行
        this.handleSelectFav(value);
        break;
      case 'add-group': // 新建分組
        createFavoriteGroup({
          type: this.favoriteSearchType,
          name: value,
        }).then(() => this.getListByGroupFavorite());
        break;
      case 'reset-group-name': // 重命名
        updateFavoriteGroup(value.group_id, {
          type: this.favoriteSearchType,
          name: value.group_new_name,
        }).then(() => this.getListByGroupFavorite());
        break;
      case 'move-favorite': // 移动收藏
      case 'remove-group': // 从组中移除收藏（移动至未分组）
        updateFavorite(value.id, {
          ...value,
          type: this.favoriteSearchType,
        }).then(() => this.getListByGroupFavorite());
        break;
      case 'edit-favorite': // 编辑收藏
        this.editFavoriteData = value;
        this.isShowAddFavoriteDialog = true;
        this.favoriteKeywordsData = value.config;
        this.favoriteData = value.config;
        break;
      case 'delete-favorite': // 删除收藏
        this.$bkInfo({
          subTitle: this.$t('当前收藏名为{name}是否删除?', { name: value.name }),
          type: 'warning',
          confirmFn: async () => {
            destroyFavorite(value.id, { type: this.favoriteSearchType }).then(() => this.getListByGroupFavorite());
          },
        });
        break;
      case 'dismiss-group': // 解散分组
        this.$bkInfo({
          title: this.$t('当前分组为{name}是否解散?', { name: value.name }),
          subTitle: `${this.$t('解散分组后，原分组内的收藏将移至未分组中。')}`,
          type: 'warning',
          confirmFn: async () => {
            destroyFavoriteGroup(value.id, { type: this.favoriteSearchType }).then(() => this.getListByGroupFavorite());
          },
        });
        break;
      case 'new-tab': {
        // 分享
        const href = `${location.origin}${location.pathname}?bizId=${this.bizId}#${this.$route.path}`;
        window.open(`${href}?favorite_id=${value.id}`, '_blank');
        break;
      }
      case 'drag-move-end': // 移动组
        // updateGroupOrderFavoriteGroup({
        //   bk_biz_id: this.bizId,
        //   type: this.favoriteSearchType,
        //   order: value
        // }).catch(err => console.warn(err));
        break;
      case 'create-copy':
        {
          const { group_id, name, id } = value;
          const copyName = `${name} ${this.$t('副本')}`;
          if (this.favStrList.includes(copyName)) {
            this.$bkMessage({
              message: this.$t('已存在该副本'),
              theme: 'warning',
            });
            return;
          }
          this.favoriteData = value.config;
          const copyBaseParams = { group_id, name: copyName, id };
          const submitValue = {
            value: copyBaseParams,
            hideCallback: () => {},
            isEdit: false,
          };
          this.handleSubmitFavorite(submitValue);
        }
        break;
      case 'request-query-history':
        this.getListByGroupFavorite();
        break;
      case 'new-search':
        this.handleSelectFav(null);
        break;
    }
  }

  /**
   * 当前选择的收藏项
   * @param data 收藏数据
   * @returns 收藏的数据
   */
  @Emit('selectFavorite')
  handleSelectFav(data?: IFavList.favList) {
    this.favCheckedValue = data;
    return data || null;
  }

  /** 弹窗dialog新增或编辑收藏 */
  async handleSubmitFavorite({ value, hideCallback, isEdit, tips = '' }) {
    const type = this.favoriteSearchType === 'event' ? 'event' : 'metric';
    const { group_id, name, id } = value;
    // 若是当前是编辑收藏, 且非更新收藏config的情况下 不改变config
    const data = {
      bk_biz_id: this.bizId,
      group_id,
      name,
      type,
      config: this.favoriteData,
    };
    if (!isEdit) {
      // 新增收藏
      const res = await createFavorite(data);
      hideCallback();
      this.handleShowChange(true);
      this.editFavoriteData = null;
      await this.getListByGroupFavorite();
      this.handleSelectFav(res); // 更新点击的收藏
    } else {
      // 编辑或替换收藏
      updateFavorite(id, data)
        .then(res => {
          hideCallback();
          if (tips) {
            this.$bkMessage({
              theme: 'success',
              message: tips,
            });
          }
          this.handleSelectFav(res); // 更新点击的收藏
        })
        .finally(() => {
          this.editFavoriteData = null;
          this.getListByGroupFavorite();
        });
    }
  }

  @Emit('showChange')
  handleShowChange(isShow: boolean) {
    return isShow;
  }

  /**
   * 收藏操作
   * @param data 收藏数据
   */
  async handleFavorite(data, isEdit = false, tips = '') {
    if (isEdit) {
      this.favoriteData = data.config;
      this.editFavoriteData = deepClone(this.favCheckedValue);
      await this.handleSubmitFavorite({
        value: data,
        hideCallback: () => {},
        isEdit: true,
        tips,
      });
    } else {
      this.isShowAddFavoriteDialog = true;
      this.favoriteData = data;
      this.favoriteKeywordsData = data;
    }
  }

  render() {
    return (
      <div class='favorite-container-comp'>
        <FavoriteIndex
          ref='favoriteIndex'
          dataId={this.dataId}
          favCheckedValue={this.favCheckedValue}
          favoriteLoading={this.favoriteLoading}
          favoriteSearchType={this.favoriteSearchType}
          favoritesList={this.favoritesList}
          isShowFavorite={this.isShowFavorite}
          onClose={() => this.handleShowChange(false)}
          onGetFavoritesList={this.getListByGroupFavorite}
          onOperateChange={({ operate, value }) => this.handleFavoriteOperate(operate, value)}
        />

        <AddCollectDialog
          v-model={this.isShowAddFavoriteDialog}
          editFavoriteData={this.editFavoriteData}
          favoriteSearchType={this.favoriteSearchType}
          favStrList={this.favStrList}
          keyword={this.favoriteKeywordsData}
          onCancel={() => {
            this.editFavoriteData = null;
          }}
          onSubmit={value => this.handleSubmitFavorite(value)}
        />
      </div>
    );
  }
}
