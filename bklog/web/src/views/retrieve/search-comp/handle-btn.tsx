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

import { Button } from 'bk-magic-vue';
import { Component, Emit, Inject, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import $http from '../../../api';
import { deepEqual, Debounce } from '../../../common/util';

// import { deepClone } from '../../../components/monitor-echarts/utils';
import './handle-btn.scss';

const searchMap = {
  autoSearch: {
    changeBtnTips: window.mainComponent.$t('切换手动查询'),
    // 自动查询
    icon: 'bk-icon bklog-icon bklog-zanting',
    text: window.mainComponent.$t('自动查询'),
  },
  // 检索按钮
  search: {
    changeBtnTips: window.mainComponent.$t('切换自动查询'),
    // 查询
    icon: 'bk-icon bklog-icon bklog-bofang',
    text: window.mainComponent.$t('查询'),
  },
  searchIng: {
    changeBtnTips: '',
    // 查询中
    icon: 'loading',
    text: `${window.mainComponent.$t('查询中')}...`,
  },
};

@Component
export default class HandleBtn extends tsc<object> {
  @Inject('handleUserOperate') handleUserOperate;

  @Prop({ default: false, type: Boolean }) tableLoading: boolean;
  @Prop({ default: false, type: Boolean }) isAutoQuery: boolean; // 是否是自动检索
  @Prop({ required: true }) isSearchAllowed;
  @Prop({ required: true, type: Number }) activeFavoriteID: number; // 当前的收藏id
  @Prop({ required: true, type: Boolean }) isCanStorageFavorite: boolean; // 是否可以点击收藏
  @Prop({ required: true, type: Object }) retrieveParams; // 检索参数
  @Prop({ required: true, type: String }) indexId: string; // 索引集id
  @Prop({ required: true, type: Object }) activeFavorite; // 收藏参数
  @Prop({ required: true, type: Array }) visibleFields; // 显示字段
  @Prop({ required: true, type: Array }) indexSetList; // 索引集列表
  @Prop({ required: true, type: Boolean }) isSqlSearchType: boolean; // 当前是否是sql模式
  @Prop({ required: true, type: Array }) conditionList; // 条件列表
  @Prop({ required: true, type: Object }) catchIpChooser; // ip选择器的值

  favoriteUpdateLoading = false;

  get getSearchType() {
    // 获取搜索按钮状态
    if (this.tableLoading) return searchMap.searchIng;
    return searchMap[this.isAutoQuery ? 'autoSearch' : 'search'];
  }

  get isFavoriteNewSearch() {
    // 是否是新检索
    return this.activeFavoriteID === -1;
  }

  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get unionIndexItemList() {
    return this.$store.state.unionIndexItemList;
  }

  get isFavoriteUpdate() {
    // 判断当前收藏是否有参数更新
    if (this.tableLoading) return false;
    const { params: retrieveParams } = this.getRetrieveFavoriteData();
    const { params } = this.activeFavorite;
    const additions = params?.addition || [];
    const favAddition = additions.map((item) => ({
      ...item,
      value: this.getAdditionValue(item.value),
    }));
    const favoriteParams = {
      addition: favAddition,
      ip_chooser: params?.ip_chooser ?? {},
      keyword: params?.keyword ?? '*',
    };
    return !deepEqual(favoriteParams, retrieveParams, ['meta']);
  }

  get conditionListAddition() {
    // 获取添加条件里的值
    return this.conditionList
      .filter((item) => item.conditionType === 'filed' && item.value.length)
      .map((item) => ({
        field: item.id,
        operator: item.operator,
        value: this.getAdditionValue(item.value),
      }));
  }

  get isCanClickFavorite() {
    // 是否可点击收藏
    return (
      !this.isFavoriteUpdate ||
      this.favoriteUpdateLoading ||
      !this.isCanStorageFavorite ||
      this.tableLoading
    );
  }

  // 检索
  @Debounce(300)
  @Emit('retrieveLog')
  handleRetrieveLog() {}

  // 清空
  @Emit('clearCondition')
  handleClear() {
    return '*';
  }

  // 改检索类型
  handleChangeSearchType() {
    if (this.tableLoading) return;
    this.handleUserOperate('isAutoQuery', !this.isAutoQuery);
    localStorage.setItem('logAutoQuery', `${!this.isAutoQuery}`);
  }

  // 当前检索监听的收藏参数
  getRetrieveFavoriteData() {
    return {
      params: {
        addition: this.conditionListAddition,
        ip_chooser: this.catchIpChooser,
        keyword: this.retrieveParams.keyword,
      },
    };
  }

  // 点击查询
  handleQuery() {
    if (!this.tableLoading) {
      this.handleRetrieveLog();
    }
  }

  // 点击新建收藏
  handleClickFavorite() {
    // 如果点击过收藏，进行参数判断
    const displayFields = this.visibleFields.map((item) => item.field_name);
    const indexItem = this.indexSetList.find(
      (item) => item.index_set_id === String(this.indexId)
    );
    const {
      params: { addition, ip_chooser, keyword },
    } = this.getRetrieveFavoriteData();
    const favoriteData = {
      display_fields: displayFields,
      // 新建收藏参数
      index_set_id: this.indexId,
      index_set_ids:
        this.unionIndexItemList?.map((item) => item.index_set_id) || [],
      index_set_name: indexItem.index_set_name,
      index_set_names:
        this.unionIndexItemList?.map((item) => item.index_set_name) || [],
      is_enable_display_fields: false,
      name: '',
      params: {
        addition,
        ip_chooser,
        keyword: Boolean(keyword) ? keyword : '*',
        search_fields: [],
      },
      space_uid: this.spaceUid,
      visible_type: 'public',
    };
    this.handleUserOperate('addFavoriteData', favoriteData); // 新增收藏
    this.handleUserOperate('isShowAddNewCollectDialog', true); // 展示新增弹窗
  }

  // 更新参数更变后的收藏
  async handleUpdateFavorite() {
    try {
      this.favoriteUpdateLoading = true;
      const { display_fields, group_id, id, name, params, visible_type } =
        this.activeFavorite;
      const { search_fields: searchFields } = params;
      const {
        params: { addition, ip_chooser, keyword },
      } = this.getRetrieveFavoriteData();
      const fRes = await $http.request('favorite/getSearchFields', {
        data: { keyword },
      });
      const searchFilterList = fRes.data
        .filter((v) => searchFields.includes(v.name))
        .map((item) => item.name);
      const data = {
        addition,
        display_fields,
        group_id,
        ip_chooser,
        keyword,
        name,
        search_fields: searchFilterList,
        visible_type,
      };
      if (!data.search_fields.length)
        this.handleUserOperate('isSqlSearchType', true);
      const res = await $http.request('favorite/updateFavorite', {
        data,
        params: { id },
      });
      if (res.result) {
        this.$bkMessage({
          message: this.$t('更新成功'),
          theme: 'success',
        });
        if (this.isAutoQuery && this.isSqlSearchType) {
          this.handleUserOperate('isAfterRequestFavoriteList', true);
        }
      }
    } finally {
      this.handleUserOperate('getFavoriteList', null, true);
      this.favoriteUpdateLoading = false;
    }
  }
  /** 获取过滤条件中的值 如果是字符串就变成数组 */
  getAdditionValue(value: Array<string> | string) {
    return Array.isArray(value) ? value : value.split(',');
  }

  render() {
    return (
      // 查询收藏清空按钮
      <div class="retrieve-button-group">
        {this.tableLoading ? (
          <div class="loading-box">
            <div
              class="loading"
              v-bkloading={{ isLoading: true, mode: 'spin', theme: 'primary' }}
            ></div>
          </div>
        ) : (
          <Button
            class="query-btn"
            icon={this.getSearchType.icon}
            onClick={this.handleChangeSearchType}
            v-bk-tooltips={{ content: this.getSearchType.changeBtnTips }}
          ></Button>
        )}

        <Button
          class={{ loading: this.tableLoading, 'query-search': true }}
          data-test-id="dataQuery_button_filterSearch"
          onClick={this.handleQuery}
          theme="primary"
          v-cursor={{ active: (this.isSearchAllowed as boolean) === false }}
        >
          {this.getSearchType.text}
        </Button>
        <div class="favorite-btn-container">
          <Button
            data-test-id="dataQuery_button_collection"
            disabled={!this.isCanStorageFavorite}
            ext-cls="favorite-btn"
            onClick={this.handleClickFavorite}
            v-show={this.isFavoriteNewSearch}
          >
            <span class="favorite-btn-text">
              <span class="icon bk-icon icon-star"></span>
              <span>
                {(this.$t('button-收藏') as string).replace('button-', '')}
              </span>
            </span>
          </Button>
          <span
            class="catching-ball"
            v-show={!this.isFavoriteNewSearch && this.isFavoriteUpdate}
          ></span>
          <Button
            disabled={this.isCanClickFavorite}
            ext-cls="favorite-btn"
            onClick={this.handleUpdateFavorite}
            v-show={!this.isFavoriteNewSearch}
          >
            <span
              v-bk-tooltips={{
                content: this.$t('当前收藏有更新，点击保存当前修改'),
                disabled: !this.isFavoriteUpdate,
              }}
            >
              <span class="favorite-btn-text">
                <span
                  class={[
                    'icon',
                    !this.isFavoriteUpdate
                      ? 'bklog-icon bklog-lc-star-shape'
                      : 'bk-icon icon-save',
                  ]}
                ></span>
                <span>
                  {!this.isFavoriteUpdate ? this.$t('已收藏') : this.$t('保存')}
                </span>
              </span>
            </span>
          </Button>
        </div>
        <span v-bk-tooltips={{ content: this.$t('清空'), delay: 200 }}>
          <div class="clear-params-btn" onClick={() => this.handleClear()}>
            <Button data-test-id="dataQuery_button_phrasesClear"></Button>
            <span class="bklog-icon bklog-brush"></span>
          </div>
        </span>
      </div>
    );
  }
}
