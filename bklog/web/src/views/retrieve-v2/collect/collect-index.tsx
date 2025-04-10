/* eslint-disable @typescript-eslint/naming-convention */
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

import { Component, Emit, Prop, PropSync, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { RetrieveUrlResolver } from '@/store/url-resolver';
import { Input, Popover, Radio, RadioGroup, Form, FormItem } from 'bk-magic-vue';
import { isEqual } from 'lodash';

import $http from '../../../api';
import { copyMessage, deepClone } from '../../../common/util';
import RetrieveHelper from '../../retrieve-helper';
import AddCollectDialog from './add-collect-dialog';
import CollectContainer from './collect-container';
import ManageGroupDialog from './manage-group-dialog';

import './collect-index.scss';

interface IProps {
  collectWidth: number;
  isShowCollect: boolean;
  visibleFields: Array<any>;
}

export interface IGroupItem {
  group_id: number;
  group_name: string;
  group_type?: visibleType;
  favorites?: IFavoriteItem[];
}

export interface IFavoriteItem {
  id: number;
  created_by: string;
  space_uid: number;
  index_set_id: number;
  name: string;
  group_id: number;
  visible_type: visibleType;
  params: object;
  is_active: boolean;
  is_actives?: boolean[];
  index_set_names?: string[];
  index_set_ids?: string[];
  display_fields: string[];
}

type visibleType = 'private' | 'public' | 'unknown';

@Component
export default class CollectIndex extends tsc<IProps> {
  @PropSync('width', { type: Number }) collectWidth: number;
  @PropSync('isShow', { type: Boolean }) isShowCollect: boolean;
  @PropSync('isRefresh', { type: Boolean }) isRefreshCollect: boolean;

  @Prop({ type: Array, default: () => [] }) visibleFields: Array<any>;

  collectMinWidth = 160; // 收藏最小栏宽度
  collectMaxWidth = 400; // 收藏栏最大宽度
  currentTreeBoxWidth = null; // 当前收藏容器的宽度
  currentScreenX = null;
  isChangingWidth = false; // 是否正在拖拽
  isShowManageDialog = false; // 是否展示管理弹窗
  isShowAddNewFavoriteDialog = false; // 是否展示编辑收藏弹窗
  collectLoading = false; // 分组容器loading
  searchVal = ''; // 搜索
  // groupName = ''; // 新增组
  privateGroupID = 0; // 私人组ID
  unknownGroupID = 0; // 公开组ID
  baseSortType = 'NAME_ASC'; // 排序参数
  sortType = 'NAME_ASC'; // 展示的排序参数
  editFavoriteID = -1; // 点击编辑时的收藏ID
  activeFavorite: IFavoriteItem = null;
  favoriteLoading = false;
  groupNameMap = {
    unknown: window.mainComponent.$t('未分组'),
    private: window.mainComponent.$t('个人收藏'),
  };
  verifyData = {
    groupName: '',
  };
  groupSortList = [
    // 排序展示列表
    {
      name: window.mainComponent.$t('按名称 {n} 排序', { n: 'A - Z' }),
      id: 'NAME_ASC',
    },
    {
      name: window.mainComponent.$t('按名称 {n} 排序', { n: 'Z - A' }),
      id: 'NAME_DESC',
    },
    {
      name: window.mainComponent.$t('按更新时间排序'),
      id: 'UPDATED_AT_DESC',
    },
  ];
  public rules = {
    groupName: [
      {
        validator: this.checkName,
        message: window.mainComponent.$t('{n}不规范, 包含特殊符号', { n: window.mainComponent.$t('组名') }),
        trigger: 'blur',
      },
      {
        validator: this.checkExistName,
        message: window.mainComponent.$t('组名重复'),
        trigger: 'blur',
      },
      {
        required: true,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.mainComponent.$t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
    ],
  };
  tippyOption = {
    trigger: 'click',
    interactive: true,
    theme: 'light',
  };

  // 收藏夹的二种类型选择
  currentCollectionType = 'origin';

  // 勾选是否查看当前索引集
  isShowCurrentIndexList = 'yes';

  // 是否隐藏收藏
  isHidden = false;

  @Ref('popoverGroup') popoverGroupRef: Popover;
  @Ref('popoverSort') popoverSortRef: Popover;
  @Ref('collectContainer') collectContainerRef: CollectContainer;
  @Ref('checkInputForm') private readonly checkInputFormRef: Form; // 移动到分组实例

  /** 是否搜索过滤 */
  get isSearchFilter() {
    return !!this.searchVal?.length;
  }

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get bkBizId() {
    return this.$store.state.bkBizId;
  }

  get activeFavoriteID() {
    return this.activeFavorite?.id || -1;
  }

  get indexSetId() {
    return `${this.$store.getters.indexId}`;
  }

  get favoriteList() {
    let data = this.$store.state.favoriteList ?? [];
    if (this.isShowCurrentIndexList === 'yes') {
      data = (this.$store.state.favoriteList ?? []).map(({ group_id, group_name, group_type, favorites }) => {
        return {
          group_id,
          group_name,
          group_type,
          favorites: favorites.filter(item => {
            // 当前索引集为联合索引
            if (this.isUnionSearch) {
              // 收藏为单个索引
              if (item.index_set_type === 'single') {
                return this.unionIndexList.includes(`${item.index_set_id}`);
              }
              // 收藏为联合索引
              return (item.index_set_ids ?? []).every(id => this.unionIndexList.includes(`${id}`));
            }
            // 当前索引集为单个索引
            if (item.index_set_type === 'single') {
              return `${item.index_set_id}` === this.indexSetId;
            } else {
              return (item.index_set_ids ?? []).some(id => this.indexSetId === `${id}`);
            }
          }),
        };
      });
    }

    const provideFavorite = data[0];
    const publicFavorite = data[data.length - 1];
    const sortFavoriteList = data.slice(1, data.length - 1).sort((a, b) => a.group_name.localeCompare(b.group_name));
    const sortAfterList = [provideFavorite, ...sortFavoriteList, publicFavorite];
    return sortAfterList.filter(item => item !== undefined);
  }

  get originFavoriteList() {
    return this.favoriteList.map(({ group_id, group_name, group_type, favorites }) => {
      return {
        group_id,
        group_name,
        group_type,
        favorites: favorites.filter(item => item.favorite_type !== 'chart'),
      };
    });
  }

  get chartFavoriteList() {
    return this.favoriteList.map(({ group_id, group_name, group_type, favorites }) => {
      return {
        group_id,
        group_name,
        group_type,
        favorites: favorites.filter(item => item.favorite_type === 'chart'),
      };
    });
  }

  get filterCollectList() {
    const mapFn = ({ group_id, group_name, group_type, favorites }) => {
      return {
        group_id,
        group_name,
        group_type,
        favorites: favorites.filter(
          fItem => fItem.created_by.includes(this.searchVal) || fItem.name.includes(this.searchVal),
        ),
      };
    };
    if (this.currentCollectionType === 'origin') {
      return this.originFavoriteList
        .map(mapFn)
        .filter(item => this.isShowCurrentIndexList !== 'yes' || item.favorites.length);
    }

    return this.chartFavoriteList
      .map(mapFn)
      .filter(item => this.isShowCurrentIndexList !== 'yes' || item.favorites.length);
  }

  get groupList() {
    return this.filterCollectList;
  }

  get originFavoriteCount() {
    return this.originFavoriteList.reduce((pre: number, cur) => ((pre += cur.favorites.length), pre), 0);
  }

  get chartFavoriteCount() {
    return this.chartFavoriteList.reduce((pre: number, cur) => ((pre += cur.favorites.length), pre), 0);
  }

  get allFavoriteNumber() {
    return this.favoriteList.reduce((pre: number, cur) => ((pre += cur.favorites.length), pre), 0);
  }

  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }

  get unionIndexList() {
    return this.$store.state.unionIndexList;
  }

  get indexSetList() {
    return this.$store.state.retrieve.indexSetList ?? [];
  }

  @Watch('isShowCollect')
  handleShowCollect(value) {
    if (value) {
      this.baseSortType = localStorage.getItem('favoriteSortType') || 'NAME_ASC';
      this.sortType = this.baseSortType;
      this.getFavoriteList();
    } else {
      this.activeFavorite = null;
      this.searchVal = '';
    }
  }
  @Watch('isRefreshCollect')
  handleRefreshList(val) {
    val && this.getFavoriteList();
    this.isRefreshCollect = false;
  }

  @Watch('bkBizId')
  watchIndexSetIDChange() {
    this.isShowCollect && this.getFavoriteList();
  }

  @Watch('activeFavorite', { deep: true })
  changeActiveFavorite(val) {
    RetrieveHelper.setFavoriteActive(val);
    this.updateActiveFavorite(val);
  }
  @Emit('is-refresh-favorite')
  handleUpdateActiveFavoriteData(value) {
    return value;
  }
  @Emit('update-active-favorite')
  updateActiveFavorite(value) {
    return value;
  }
  /** 获取收藏列表 */
  async getFavoriteList() {
    // 第一次显示收藏列表时因路由更变原因 在本页面第一次请求
    try {
      this.favoriteLoading = true;
      // 收藏列表更新时默认是展开的
      this.isHidden = false;
      await this.$store.dispatch('requestFavoriteList');
    } catch (err) {
      this.favoriteLoading = false;
    } finally {
      // 获取收藏列表后 若当前不是新检索 则判断当前收藏是否已删除 若删除则变为新检索
      if (this.activeFavoriteID !== -1) {
        let isFindCheckValue = false; // 是否从列表中找到匹配当前收藏的id
        for (const gItem of this.favoriteList) {
          const findFavorites = gItem.favorites.find(item => item.id === this.activeFavoriteID);
          if (!!findFavorites) {
            isFindCheckValue = true; // 找到 中断循环
            break;
          }
        }
        if (!isFindCheckValue) this.handleClickFavoriteItem(); // 未找到 清空当前收藏 变为新检索
      }
      this.favoriteLoading = false;
    }
  }

  setRouteParams() {
    const getRouteQueryParams = () => {
      const { ids, isUnionIndex, search_mode } = this.$store.state.indexItem;
      const unionList = this.$store.state.unionIndexList;
      const clusterParams = this.$store.state.clusterParams;
      const { start_time, end_time, addition, begin, size, ip_chooser, host_scopes, interval, sort_list } =
        this.$store.getters.retrieveParams;

      return {
        addition,
        start_time,
        end_time,
        begin,
        size,
        ip_chooser,
        host_scopes,
        interval,
        bk_biz_id: this.$store.state.bkBizId,
        search_mode,
        sort_list,
        ids,
        isUnionIndex,
        unionList,
        clusterParams,
      };
    };
    const routeParams = getRouteQueryParams();
    const { ids, isUnionIndex } = routeParams;
    const params = isUnionIndex
      ? { ...this.$route.params, indexId: undefined }
      : { ...this.$route.params, indexId: ids?.[0] ?? this.$route.params?.indexId };

    const query = { ...this.$route.query };
    const resolver = new RetrieveUrlResolver({
      ...routeParams,
      datePickerValue: this.$store.state.indexItem.datePickerValue,
    });

    Object.assign(query, resolver.resolveParamsToUrl());
    if (!isEqual(params, this.$route.params) || !isEqual(query, this.$route.query)) {
      this.$router.replace({
        params,
        query,
      });
    }
  }

  // 点击收藏列表的收藏
  handleClickFavoriteItem(value?) {
    if (!value) {
      this.activeFavorite = null;
      let clearSearchValueNum = this.$store.state.clearSearchValueNum;
      // 清空当前检索条件
      this.$store.commit('updateClearSearchValueNum', (clearSearchValueNum += 1));
      this.setRouteParams();
      return;
    }
    const cloneValue = deepClone(value);
    this.activeFavorite = deepClone(value);
    this.$store.commit('resetIndexsetItemParams');
    this.$store.commit('updateIndexId', cloneValue.index_set_id);
    this.$store.commit('updateIsSetDefaultTableColumn', false);
    const isUnionIndex = cloneValue.index_set_ids.length > 0;
    const keyword = cloneValue.params.keyword;
    const addition = cloneValue.params.addition ?? [];

    const ip_chooser = Object.assign({}, cloneValue.params.ip_chooser ?? {});
    if (isUnionIndex) {
      this.$store.commit(
        'updateUnionIndexList',
        cloneValue.index_set_ids.map(item => String(item)),
      );
    }
    if (JSON.stringify(ip_chooser) !== '{}') {
      addition.push({
        field: '_ip-select_',
        operator: '',
        value: [ip_chooser],
      });
    }
    const ids = isUnionIndex ? cloneValue.index_set_ids : [cloneValue.index_set_id];
    this.$store.commit('updateIndexItem', {
      keyword,
      addition,
      ip_chooser,
      index_set_id: cloneValue.index_set_id,
      ids,
      items: ids.map(id => this.indexSetList.find(item => item.index_set_id === `${id}`)),
      isUnionIndex,
      search_mode: cloneValue.search_mode,
    });

    this.$store.commit('updateChartParams', { ...cloneValue.params.chart_params, fromCollectionActiveTab: 'unused' });

    this.$store.dispatch('requestIndexSetFieldInfo').then(() => {
      this.$store.dispatch('requestIndexSetQuery');
    });

    this.setRouteParams();
  }

  /**
   * @desc: 切换索引
   * @param {Object} val 切换索引集的数据
   * @param {Object} params 检索传参数据
   * @param {Boolean} isFavoriteSearch 是否是收藏
   * @returns {*}
   */
  handleSelectIndex(val, isFavoriteSearch = false) {
    const { ids, selectIsUnionSearch } = val;
    // 关闭下拉框 判断是否是多选 如果是多选并且非缓存的则执行联合查询
    if (!isFavoriteSearch) {
      const favoriteIDs = this.activeFavorite.index_set_ids?.map(item => String(item)) ?? [];
      if (this.compareArrays(ids, favoriteIDs)) return;
      // this.resetFavoriteValue();
    }
    if (selectIsUnionSearch) {
      if (!this.compareArrays(ids, this.unionIndexList) || isFavoriteSearch) {
        this.$store.commit('updateUnionIndexList', ids ?? []);
      }
    } else {
      // 单选时弹窗关闭时 判断之前是否是多选 如果是多选 则直接检索
      if (this.isUnionSearch) {
      } else {
      }
      this.$store.commit('updateUnionIndexList', []);
    }
  }

  /** 检查两个数组否相等 */
  compareArrays(arr1, arr2) {
    let allElementsEqual = true;
    // 检查两个数组的长度是否相等
    if (arr1.length !== arr2.length) return false;
    // 对比两个数组的每个元素
    const sortedArr1 = [...arr1].sort();
    const sortedArr2 = [...arr2].sort();

    // 逐一比较排序后数组的元素
    for (let i = 0; i < sortedArr1.length; i++) {
      if (sortedArr1[i] !== sortedArr2[i]) {
        allElementsEqual = false; // 发现不匹配元素
        break;
      }
    }
    return allElementsEqual;
  }

  async handleUserOperate(obj) {
    const { type, value } = obj;
    switch (type) {
      case 'click-favorite': // 点击收藏
        this.handleClickFavoriteItem(value);
        break;
      case 'add-group': // 新增组
        await this.handleUpdateGroupName({ group_new_name: value });
        this.getFavoriteList();
        break;
      case 'reset-group-name': // 重命名
        await this.handleUpdateGroupName(value, false);
        this.getFavoriteList();
        break;
      case 'move-favorite': // 移动收藏
        const visible_type = value.group_id === this.privateGroupID ? 'private' : 'public';
        Object.assign(value, { visible_type });
        await this.handleUpdateFavorite(value);
        this.getFavoriteList();
        break;
      case 'remove-group': // 从组中移除收藏（移动至未分组）
        Object.assign(value, {
          visible_type: 'public',
          group_id: this.unknownGroupID,
        });
        await this.handleUpdateFavorite(value);
        this.getFavoriteList();
        break;
      case 'edit-favorite': // 编辑收藏
        this.editFavoriteID = value.id;
        this.isShowAddNewFavoriteDialog = true;
        break;
      case 'delete-favorite': // 删除收藏
        this.$bkInfo({
          subTitle: this.$t('当前收藏名为 {n}，确认是否删除？', { n: value.name }),
          type: 'warning',
          confirmFn: async () => {
            await this.deleteFavorite(value.id);
            this.getFavoriteList();
          },
        });
        break;
      case 'dismiss-group': // 解散分组
        this.$bkInfo({
          title: this.$t('当前分组名为 {n}，确认是否解散？', { n: value.group_name }),
          subTitle: `${this.$t('解散分组后，原分组内的收藏将移至未分组中。')}`,
          type: 'warning',
          confirmFn: async () => {
            await this.deleteGroup(value.group_id);
            this.getFavoriteList();
          },
        });
        break;
      case 'share':
      case 'new-link':
        {
          const params = { indexId: value.index_set_id };
          const resolver = new RetrieveUrlResolver({
            ...value.params,
            addition: value.params.addition,
            search_mode: value.search_mode,
            spaceUid: value.space_uid,
            unionList: value.index_set_ids.map((item: number) => String(item)),
            isUnionIndex: value.index_set_type === 'union',
          });

          const routeData = {
            name: 'retrieve',
            params,
            query: resolver.resolveParamsToUrl(),
          };

          let shareUrl = window.SITE_URL;
          if (!shareUrl.startsWith('/')) shareUrl = `/${shareUrl}`;
          if (!shareUrl.endsWith('/')) shareUrl += '/';

          shareUrl = `${window.location.origin + shareUrl}${this.$router.resolve(routeData).href}`;
          if (type === 'new-link') {
            window.open(shareUrl, '_blank');
          } else {
            console.log('routeData', `${shareUrl}`);
            copyMessage(shareUrl, this.$t('复制分享链接成功，通过链接，可直接查询对应收藏日志。'));
          }
        }
        break;
      case 'drag-move-end':
        // $http.request('favorite/groupUpdateOrder', {
        //   data: {
        //     space_uid: this.spaceUid,
        //     group_order: value,
        //   },
        // });
        break;
      case 'create-copy':
        {
          const { index_set_id, params, name, group_id, display_fields, visible_type, is_enable_display_fields } =
            value;
          const { host_scopes, addition, keyword, search_fields } = params;
          const data = {
            name: `${name} ${this.$t('副本')}`,
            group_id,
            display_fields,
            visible_type,
            host_scopes,
            addition,
            keyword,
            search_fields,
            is_enable_display_fields,
            index_set_id,
            space_uid: this.spaceUid,
          };
          if (this.isUnionSearch) {
            Object.assign(data, {
              index_set_ids: this.unionIndexList,
              index_set_type: 'union',
            });
          }
          $http.request('favorite/createFavorite', { data }).then(() => {
            this.showMessagePop(this.$t('创建成功'));
            this.getFavoriteList();
          });
        }
        break;
      default:
    }
  }
  checkName() {
    if (this.verifyData.groupName.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      this.verifyData.groupName.trim(),
    );
  }
  checkExistName() {
    return !this.groupList.some(item => item.group_name === this.verifyData.groupName);
  }
  /** 新增组 */
  handleClickGroupBtn(clickType: string) {
    if (clickType === 'add') {
      this.checkInputFormRef.validate().then(async () => {
        if (!this.verifyData.groupName.trim()) return;
        await this.handleUpdateGroupName({ group_new_name: this.verifyData.groupName });
        this.getFavoriteList();
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

  /** 排序 */
  handleClickSortBtn(clickType: string) {
    if (clickType === 'sort') {
      this.baseSortType = this.sortType;
      localStorage.setItem('favoriteSortType', this.sortType);
      this.getFavoriteList();
    } else {
      setTimeout(() => {
        this.sortType = this.baseSortType;
      }, 500);
    }
    this.popoverSortRef.hideHandler();
  }

  /** 新增或更新组名 */
  async handleUpdateGroupName(groupObj, isCreate = true) {
    const { group_id, group_new_name } = groupObj;
    const params = { group_id };
    const data = { name: group_new_name, space_uid: this.spaceUid };
    const requestStr = isCreate ? 'createGroup' : 'updateGroupName';
    await $http
      .request(`favorite/${requestStr}`, {
        params,
        data,
      })
      .then(() => {
        this.showMessagePop(this.$t('操作成功'));
      });
  }

  /** 解散分组 */
  async deleteGroup(group_id) {
    await $http
      .request('favorite/deleteGroup', {
        params: { group_id },
      })
      .then(() => {
        this.showMessagePop(this.$t('操作成功'));
      });
  }

  /** 删除收藏 */
  async deleteFavorite(favorite_id) {
    await $http
      .request('favorite/deleteFavorite', {
        params: { favorite_id },
      })
      .then(() => {
        this.showMessagePop(this.$t('删除成功'));
      });
  }

  showMessagePop(message, theme = 'success') {
    this.$bkMessage({
      message,
      theme,
    });
  }

  /** 更新收藏 */
  async handleUpdateFavorite(favoriteData) {
    const { params, name, group_id, display_fields, visible_type, id, index_set_id, index_set_ids, index_set_type } =
      favoriteData;
    const { ip_chooser, addition, keyword, search_fields } = params;
    const data = {
      name,
      group_id,
      display_fields,
      visible_type,
      ip_chooser,
      addition,
      keyword,
      search_fields,
      index_set_type,
    };
    if (index_set_type === 'union') {
      Object.assign(data, {
        index_set_ids,
      });
    } else {
      Object.assign(data, {
        index_set_id,
      });
    }
    await $http
      .request('favorite/updateFavorite', {
        params: { id },
        data,
      })
      .then(() => {
        this.showMessagePop(this.$t('操作成功'));
      });
  }
  handleGroupKeyDown(value: string, event) {
    if (event.code === 'Tab' && !!value) {
      this.handleUserOperate({
        type: 'add-group',
        value,
      });
      this.popoverGroupRef.hideHandler();
      setTimeout(() => {
        this.verifyData.groupName = '';
      }, 500);
    }
  }

  /** 控制页面布局宽度 */
  dragBegin(e) {
    this.isChangingWidth = true;
    this.currentTreeBoxWidth = this.collectWidth;
    this.currentScreenX = e.screenX;
    window.addEventListener('mousemove', this.dragMoving, { passive: true });
    window.addEventListener('mouseup', this.dragStop, { passive: true });
  }
  dragMoving(e) {
    const newTreeBoxWidth = this.currentTreeBoxWidth + e.screenX - this.currentScreenX;
    if (newTreeBoxWidth < this.collectMinWidth) {
      this.collectWidth = 240;
      this.isShowCollect = false;
      this.dragStop();
      localStorage.setItem('isAutoShowCollect', 'false');
    } else if (newTreeBoxWidth >= this.collectMaxWidth) {
      this.collectWidth = this.collectMaxWidth;
    } else {
      this.collectWidth = newTreeBoxWidth;
    }
  }
  dragStop() {
    this.isChangingWidth = false;
    this.currentTreeBoxWidth = null;
    this.currentScreenX = null;
    window.removeEventListener('mousemove', this.dragMoving);
    window.removeEventListener('mouseup', this.dragStop);
  }

  handleRadioGroup(val: string) {
    this.currentCollectionType = val;
  }

  handleCollapse() {
    this.isShowCollect = !this.isShowCollect;
  }
  // 折叠收藏夹文件全部收起或全部展开
  handleGroupIsHidden() {
    this.isHidden = !this.isHidden;
    this.collectContainerRef.handleGroupIsHidden(this.isHidden);
  }

  handleFavoriteSetttingClick() {
    this.isShowManageDialog = true;
  }
  render() {
    return (
      <div
        style={{
          width: this.isShowCollect ? `${this.collectWidth}px` : 0,
          display: this.isShowCollect ? 'block' : 'none',
        }}
        class='retrieve-collect-index'
      >
        <CollectContainer
          ref='collectContainer'
          activeFavoriteID={this.activeFavoriteID}
          collectLoading={this.collectLoading || this.favoriteLoading}
          dataList={this.filterCollectList}
          groupList={this.groupList}
          isSearchFilter={this.isSearchFilter}
          on-change={this.handleUserOperate}
        >
          <div class='search-container-new'>
            <div class='search-container-new-title'>
              <div>
                <span style={{ fontSize: '14px', color: '#313238' }}>收藏夹</span>
                <span class='search-container-new-title-num'>{this.allFavoriteNumber}</span>
              </div>
              <div
                style={{ fontSize: '16px', cursor: 'pointer' }}
                class='search-container-new-title-right'
              >
                <span
                  class='bklog-icon bklog-shezhi'
                  onClick={this.handleFavoriteSetttingClick}
                ></span>
                <span
                  class='bklog-icon bklog-collapse'
                  onClick={this.handleCollapse}
                ></span>
              </div>
            </div>
            <div class='search-box fl-jcsb'>
              <Input
                class='search-input'
                vModel={this.searchVal}
                behavior='normal'
                placeholder={this.$t('请输入')}
                right-icon='bk-icon icon-search'
              ></Input>
            </div>
            <div class='search-category'>
              <div class='selector-container'>
                {['origin', 'chart'].map(type => (
                  <span
                    key={type}
                    class={`option ${this.currentCollectionType === type ? 'selected' : ''}`}
                    onClick={() => this.handleRadioGroup(type)}
                  >
                    <span
                      style={{ marginRight: '4px' }}
                      class={`bklog-icon ${type === 'origin' ? 'bklog-table-2' : 'bklog-chart-2'}`}
                    ></span>
                    <span style={{ marginRight: '4px' }}>{type === 'origin' ? '原始日志' : '图表分析'}</span>
                    <span class='search-category-num'>
                      {type === 'origin' ? this.originFavoriteCount : this.chartFavoriteCount}
                    </span>
                  </span>
                ))}
              </div>
            </div>
            <div class='search-tool'>
              <span>
                <bk-checkbox
                  v-model={this.isShowCurrentIndexList}
                  false-value='no'
                  true-value='yes'
                >
                  仅查看当前索引集
                </bk-checkbox>
              </span>
              <div
                style={{ marginTop: '1px', cursor: 'pointer', marginLeft: '0px', width: '72px' }}
                class='fl-jcsb '
              >
                <Popover
                  ref='popoverGroup'
                  ext-cls='new-group-popover'
                  placement='bottom-start'
                  tippy-options={this.tippyOption}
                >
                  <span
                    style={{ fontSize: '16px' }}
                    class='bklog-icon bklog-xinjianwenjianjia'
                    v-bk-tooltips={this.$t('新建收藏分组')}
                  ></span>
                  <div slot='content'>
                    <Form
                      ref='checkInputForm'
                      style={{ width: '100%', padding: '0px 2px' }}
                      form-type='vertical'
                      {...{
                        props: {
                          model: this.verifyData,
                          rules: this.rules,
                        },
                      }}
                    >
                      <FormItem
                        icon-offset={34}
                        label='分组名称'
                        property='groupName'
                        required
                      >
                        <Input
                          style={{ marginTop: '4px' }}
                          vModel={this.verifyData.groupName}
                          placeholder={this.$t('请输入')}
                          clearable
                          onEnter={() => this.handleClickGroupBtn('add')}
                          onKeydown={this.handleGroupKeyDown}
                        ></Input>
                      </FormItem>
                    </Form>
                    <div class='operate-button'>
                      <span
                        class='operate-button-custom button-first'
                        onClick={() => this.handleClickGroupBtn('add')}
                      >
                        {this.$t('确定')}
                      </span>
                      <span
                        class='operate-button-custom button-second'
                        onClick={() => this.handleClickGroupBtn('cancel')}
                      >
                        {this.$t('取消')}
                      </span>
                    </div>
                  </div>
                </Popover>
                <span
                  style={{ fontSize: '16px' }}
                  class={`bklog-icon ${!this.isHidden ? 'bklog-zhankai-2' : 'bklog-shouqi'}`}
                  v-bk-tooltips={this.$t(`${!this.isHidden ? '全部收起' : '全部展开'}`)}
                  onClick={() => this.handleGroupIsHidden()}
                ></span>
                <Popover
                  ref='popoverSort'
                  ext-cls='sort-group-popover'
                  placement='bottom-start'
                  tippy-options={this.tippyOption}
                >
                  <div
                    class='icon-box'
                    v-bk-tooltips={this.$t('调整排序')}
                  >
                    <span
                      style={{ fontSize: '16px' }}
                      class='bklog-icon bklog-paixu'
                    ></span>
                  </div>
                  <div slot='content'>
                    <div style={{ padding: '0px 2px' }}>
                      <span style={{ fontSize: '14px', marginTop: '8px' }}>{this.$t('收藏名排序')}</span>
                      <RadioGroup
                        class='sort-group-container'
                        vModel={this.sortType}
                      >
                        {this.groupSortList.map(item => (
                          <Radio value={item.id}>{item.name}</Radio>
                        ))}
                      </RadioGroup>
                      <div class='operate-button'>
                        <span
                          class='operate-button-custom button-first'
                          onClick={() => this.handleClickSortBtn('sort')}
                        >
                          {this.$t('确定')}
                        </span>
                        <span
                          class='operate-button-custom button-second'
                          onClick={() => this.handleClickSortBtn('cancel')}
                        >
                          {this.$t('取消')}
                        </span>
                      </div>
                    </div>
                  </div>
                </Popover>
              </div>
            </div>
          </div>
          {/* <div
            class={`new-search ${this.activeFavoriteID === -1 && 'active'}`}
            onClick={() => this.handleClickFavoriteItem()}
          >
            <span class='bk-icon icon-enlarge-line'></span>
            <span>{this.$t('新检索')}</span>
          </div>*/}
          <div
            class={['drag-border', { 'drag-ing': this.isChangingWidth }]}
            onMousedown={this.dragBegin}
          ></div>
        </CollectContainer>
        <ManageGroupDialog
          vModel={this.isShowManageDialog}
          onSubmit={value => value && this.getFavoriteList()}
        />
        <AddCollectDialog
          vModel={this.isShowAddNewFavoriteDialog}
          activeFavoriteID={this.activeFavoriteID}
          favoriteID={this.editFavoriteID}
          favoriteList={this.favoriteList}
          visibleFields={this.visibleFields}
          on-change-favorite={async value => {
            await this.getFavoriteList();
            this.handleClickFavoriteItem(value);
          }}
        />
      </div>
    );
  }
}
