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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import {
  Select,
  Option,
  OptionGroup,
  Tag,
  Tab,
  TabPanel,
  Popover,
  Form,
  FormItem,
  Input,
  Button,
  Checkbox,
} from 'bk-magic-vue';
import * as authorityMap from '../../../common/authority-map';
import $http from '../../../api';
import './select-index-set.scss';

interface IProps {}

type IndexSetType = 'single' | 'union';
type ActiveType = 'favorite' | 'history';

@Component
export default class QueryStatement extends tsc<IProps> {
  @Prop({ type: String, required: true }) indexId: string;
  @Prop({ type: Array, required: true }) indexSetList: Array<any>;
  @Prop({ type: Boolean, required: true }) basicLoading: boolean;
  @Ref('selectIndexBox') private readonly selectIndexBoxRef: HTMLElement;
  @Ref('tagBox') private readonly tagBoxRef: HTMLElement;
  @Ref('selectInput') private readonly selectInputRef: Select;
  @Ref('favoritePopover') private readonly favoritePopoverRef: Popover;
  @Ref('checkInputForm') private readonly checkInputFormRef: Form;

  /** 表示集合数据是否正在加载 */
  isCollectionLoading = false;

  /** 表示当前检索类型，可选值为 'single' 或 'union' */
  indexSearchType: IndexSetType = 'single';

  /** 表示单选收藏夹列表 */
  aloneFavorite = [];

  /** 表示多选收藏夹列表 */
  multipleFavorite = [];

  /** 表示单选历史记录列表 */
  aloneHistory = [];

  /** 表示多选历史记录列表 */
  multipleHistory = [];

  historyLoading = false;

  /** 当前过滤时候的ID */
  filterTagID = null;

  /** 单选时候的值 */
  selectAloneVal = null;

  /** 多选收藏选中的ID */
  multipleFavoriteSelectID = null;

  /** 多选历史记录选中的ID */
  multipleHistorySelectID = null;

  /** 多选时已选中的索引集列表 */
  selectTagCatchIDList = [];

  typeBtnSelectList = [
    {
      id: 'single',
      label: window.mainComponent.$t('单选'),
    },
    {
      id: 'union',
      label: window.mainComponent.$t('多选'),
    },
  ];

  tabPanels = [
    {
      name: 'history',
      icon: 'log-icon icon-lishijilu',
      label: window.mainComponent.$t('历史记录'),
    },
    {
      name: 'favorite',
      icon: 'log-icon icon-star-shape',
      label: window.mainComponent.$t('收藏'),
    },
  ];

  /** 当前活跃的采样日志下标 */
  activeTab: ActiveType = 'history';

  verifyData = {
    favoriteName: '',
  };

  rules = {
    favoriteName: [
      {
        validator: this.checkFavoriteName,
        message: window.mainComponent.$t('已有同名收藏'),
        trigger: 'blur',
      },
      {
        required: true,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
    ],
  };

  tippyOptions = {
    trigger: 'click',
    interactive: true,
    theme: 'light',
    placement: 'left-start',
    arrow: true,
  };

  get authorityMap() {
    return authorityMap;
  }

  /** 单选时候的索引集 */
  get selectedItem() {
    return (
      this.indexSetList.find(item => item.index_set_id === this.indexId) || {}
    );
  }

  /** 多选的选中的索引集值 */
  get selectedItemList() {
    return this.indexSetList.filter(item => this.selectTagCatchIDList.includes(item.index_set_id));
  }


  get spaceUid() {
    return this.$store.state.spaceUid;
  }

  get showFavoriteList() {
    return this.isAloneType ? this.aloneFavorite : this.multipleFavorite;
  }

  get historyListNum() {
    return this.isAloneType
      ? this.aloneHistory.length
      : this.multipleHistory.length;
  }

  /** 列表渲染 */
  get renderOptionList() {
    const list = [
      { name: '', children: [] },
      { name: this.$t('无数据'), children: [] },
    ];
    const haveDataFavoriteList = [];
    const haveDataList = [];
    const notDataList = [];
    this.indexSetList.forEach((item) => {
      const tagIDList = item.tags?.map(tag => tag.tag_id) || [];
      item.tagSearchName = item.tags?.map(tag => tag.name).join(',') || [];
      if (this.filterTagID) {
        const isFilterTagItem = tagIDList.includes(this.filterTagID);
        if (!isFilterTagItem) return;
      }

      if (tagIDList.includes(4)) {
        // 无数据索引集
        notDataList.push(item);
      } else if (item.is_favorite) {
        // 有数据的收藏索引集
        haveDataFavoriteList.push(item);
      } else {
        // 有数据的其他索引集
        haveDataList.push(item);
      }
    });
    list[0].children = [...haveDataFavoriteList, ...haveDataList];
    list[1].children = notDataList;
    // 添加全选选项
    if (this.filterTagID && list[0].children.length && !this.isAloneType) {
      list[0].children.unshift({
        index_set_id: '-1',
        tagSearchName: '',
        indexName: this.$t('全选'),
        lightenName: '',
        tagAllID: this.filterTagID,
        tags: [],
      });
    }
    if (!notDataList.length) {
      list[1].name = '';
    }
    return list;
  }

  /** 获取可选的标签过滤列表 */
  get labelSelectList() {
    const labelMap = new Map();
    const favoriteList = [];
    this.indexSetList.forEach((item) => {
      item.tags?.forEach((tag) => {
        if (!labelMap.has(tag.tag_id)) labelMap.set(tag.tag_id, tag);
      });
      // 所有的收藏索引集
      if (item.is_favorite) {
        item.name = item.index_set_name;
        favoriteList.push(item);
      }
    });
    // 单选收藏列表
    this.aloneFavorite = favoriteList;
    return [...labelMap.values()];
  }

  /** 获取分组的高度样式 */
  get groupListStyle() {
    const isUnion = this.selectedItemList.length && !this.isAloneType;
    return {
      height: isUnion ? '214px' : '314px',
      marginTop: isUnion ? '0' : '46px',
    };
  }

  /** 当前是否是单选 */
  get isAloneType() {
    return this.indexSearchType === 'single';
  }

  /** 全选是否展示 */
  get getIsAllCheck() {
    return this.havValRenderIDSetList.every(item => this.selectTagCatchIDList.includes(item));
  }

  /** 当前标签过滤后的有数据的索引集ID列表 */
  get havValRenderIDSetList() {
    return this.renderOptionList[0].children
      .filter(item => !item.tagAllID)
      .map(item => item.index_set_id);
  }

  get unionIndexList() {
    return this.$store.state.unionIndexList;
  }

  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }

  get isOverSelect() {
    return this.selectTagCatchIDList.length >= 10;
  }

  @Watch('unionIndexList', { immediate: true, deep: true })
  initUnionList(val) {
    this.indexSearchType = !!val.length ? 'union' : 'single';
    this.selectTagCatchIDList = !!val.length ? val : [this.indexId];
  }

  @Emit('selected')
  emitSelected() {
    return {
      ids: this.isAloneType ? this.selectAloneVal : this.selectTagCatchIDList,
      selectIsUnionSearch: !this.isAloneType,
    };
  }

  /** 判断当前索引集是否有权限 */
  isHaveAuthority(item) {
    if (item.tagAllID) return true;
    return (
      item.permission && item.permission[this.authorityMap.SEARCH_LOG_AUTH]
    );
  }

  /** 选中索引集 */
  handleSelectIndex(val) {
    if (this.isAloneType) {
      this.selectAloneVal = [val[1]]; // 单选赋值
      this.handleCloseSelectPopover();
    } else {
      this.selectTagCatchIDList = val.filter(item => item !== '-1');
      this.multipleFavoriteSelectID = null;
      this.multipleHistorySelectID = null;
    }
  }

  /** 选中全选时的数据过滤 */
  handelClickIndexSet(item) {
    if (item.index_set_id === '-1') {
      const allIn = this.havValRenderIDSetList.every(item => this.selectTagCatchIDList.includes(item));
      if (!allIn) {
        // 当前未全选中  则把过滤后的标签索引集id全放到缓存的id列表
        this.selectTagCatchIDList = [
          ...new Set([
            ...this.selectTagCatchIDList,
            ...this.havValRenderIDSetList,
          ]),
        ].slice(0, 10); // 最多选10条数据
      } else {
        // 全选选中 清空 已有的过滤后的标签索引集id
        this.selectTagCatchIDList = this.selectTagCatchIDList
          .filter(item => !this.havValRenderIDSetList.includes(item))
          .slice(0, 10); // 最多选10条数据
      }
    }
  }

  toggleSelect(val: boolean) {
    if (val) {
      // 打开索引集下拉框 初始化单选的数据
      this.selectAloneVal = [this.indexId];
      if (this.isUnionSearch) {
        this.indexSearchType = 'union';
        this.selectTagCatchIDList = this.unionIndexList;
      } else {
        this.indexSearchType = 'single';
        this.selectTagCatchIDList = [this.indexId];
      }
      this.getMultipleFavoriteList();
      this.getIndexSetHistoryList(this.indexSearchType);
    } else {
      if (!this.selectTagCatchIDList.length) {
        this.indexSearchType = 'single';
      }
      this.aloneHistory = [];
      this.multipleHistory = [];
      this.emitSelected();
    }
  }

  handleCloseSelectPopover() {
    this.selectInputRef.close();
  }

  /** 获取checkbox的布尔值 */
  getCheckedVal(indexSetID: string) {
    if (indexSetID === '-1') return this.getIsAllCheck;
    return this.selectedItemList
      .map(item => item.index_set_id)
      .includes(indexSetID);
  }

  // 申请索引集的搜索权限
  async applySearchAccess(item) {
    (this.$el as any).click(); // 手动关闭下拉
    try {
      this.$emit('update:basicLoading', true);
      const res = await this.$store.dispatch('getApplyData', {
        action_ids: [authorityMap.SEARCH_LOG_AUTH],
        resources: [
          {
            type: 'indices',
            id: item.index_set_id,
          },
        ],
      });
      window.open(res.data.apply_url);
    } catch (err) {
      console.warn(err);
    } finally {
      this.$emit('update:basicLoading', false);
    }
  }

  /** 单选情况下的收藏 */
  async handleCollection(item, e?) {
    e?.stopPropagation();
    if (this.isCollectionLoading) return;

    try {
      this.isCollectionLoading = true;
      const url = `/indexSet/${item.is_favorite ? 'cancelMark' : 'mark'}`;

      await $http
        .request(url, {
          params: {
            index_set_id: item.index_set_id,
          },
        })
        .then(() => {
          this.$emit('updateIndexSetList');
        });
    } finally {
      this.isCollectionLoading = false;
    }
  }

  /** 已选tag中的删除事件 */
  handleCloseSelectTag(item) {
    this.selectTagCatchIDList = this.selectTagCatchIDList.filter(
      catchVal => catchVal !== item.index_set_id,
    );
    this.multipleFavoriteSelectID = null;
  }

  /** 切换多选或者单选 */
  handleClickSetType(type: IndexSetType) {
    this.indexSearchType = type;
    this.multipleHistorySelectID = null;
    this.getIndexSetHistoryList(type);

    if (type === 'single') {
      this.selectTagCatchIDList = [this.indexId];
    } else {
      this.selectTagCatchIDList = [];
    }
  }

  /** 切换收藏或历史 */
  handleTabChange(val: ActiveType) {
    this.activeTab = val;
    this.multipleFavoriteSelectID = null;
    this.multipleHistorySelectID = null;
  }

  /** 点击收藏 */
  handleClickFavorite(item) {
    if (this.isAloneType) {
      this.handleSelectIndex(String(item.index_set_id));
      this.handleCloseSelectPopover();
      this.multipleFavoriteSelectID = null;
    } else {
      this.multipleFavoriteSelectID = item.id;
      this.selectTagCatchIDList = item.index_set_ids.map(item => String(item),
      );
    }
  }

  /** 取消收藏 */
  handleCancelFavorite(item, e?) {
    e?.stopPropagation();
    if (this.isAloneType) {
      this.handleCollection(item);
    } else {
      this.handleMultipleCollection(item);
    }
  }

  /** 删除历史记录 */
  async handleDeleteHistory(item, e?, isDeleteAll = false) {
    e.stopPropagation();
    try {
      await $http
        .request('unionSearch/unionDeleteHistory', {
          data: {
            space_uid: this.spaceUid,
            index_set_type: this.indexSearchType,
            history_id: item?.id,
            is_delete_all: isDeleteAll,
          },
        })
        .then(() => {
          this.getIndexSetHistoryList(this.indexSearchType, true);
        });
    } catch {}
  }

  /** 点击历史记录 */
  handleClickHistory(item) {
    this.multipleHistorySelectID = item.id;
    this.selectTagCatchIDList = item.index_set_ids.map(item => String(item));
  }

  /** 多选情况下的取消收藏 */
  async handleMultipleCollection(item) {
    if (this.isCollectionLoading) return;

    try {
      this.isCollectionLoading = true;

      await $http
        .request('unionSearch/unionDeleteFavorite', {
          params: {
            favorite_union_id: item.id,
          },
        })
        .then(() => {
          this.getMultipleFavoriteList();
        });
    } finally {
      this.isCollectionLoading = false;
    }
  }

  /** 收藏该组合 */
  async handleClickFavoritePopoverBtn(type: string) {
    if (type === 'add') {
      this.checkInputFormRef.validate().then(
        async () => {
          await $http
            .request('unionSearch/unionCreateFavorite', {
              data: {
                space_uid: this.spaceUid,
                name: this.verifyData.favoriteName,
                index_set_ids: this.selectTagCatchIDList,
              },
            })
            .then((res) => {
              this.verifyData.favoriteName = '';
              this.favoritePopoverRef.hideHandler();
              this.getMultipleFavoriteList();
              this.multipleFavoriteSelectID = res.data.id;
            });
        },
        () => {},
      );
    } else {
      this.favoritePopoverRef.hideHandler();
    }
  }

  /** 获取多选时候的列表 */
  async getMultipleFavoriteList() {
    await $http
      .request('unionSearch/unionFavoriteList', {
        params: {
          space_uid: this.spaceUid,
        },
      })
      .then((res) => {
        this.multipleFavorite = res.data;
      });
  }

  scrollLeft() {
    this.tagBoxRef.scrollLeft -= 560;
  }

  scrollRight() {
    this.tagBoxRef.scrollLeft += 560;
  }

  /** 点击标签过滤 */
  handleClickTag(tagID: number) {
    this.filterTagID = this.filterTagID === tagID ? null : tagID;
  }

  /** 多选时索引集禁用判断 */
  getDisabled(indexID: string) {
    return this.isOverSelect && !this.selectTagCatchIDList.includes(indexID);
  }

  /** 获取当前活跃的收藏 */
  favoriteActive(item) {
    return this.isAloneType
      ? String(item.index_set_id) === this.selectedItem.index_set_id
      : item.id === this.multipleFavoriteSelectID;
  }

  /**
   * @desc: 获取历史记录
   * @param {IndexSetType} queryType 历史记录类型
   * @param {Boolean} isForceRequest 是否强制请求
   */
  async getIndexSetHistoryList(
    queryType: IndexSetType = 'single',
    isForceRequest = false,
  ) {
    // 判断当前历史记录数组是否需要请求
    const isShouldQuery =      queryType === 'single'
      ? !!this.aloneHistory.length
      : !!this.multipleHistory.length;
    // 判断是否需要更新历史记录
    if ((!isForceRequest && isShouldQuery) || this.historyLoading) return;

    this.historyLoading = true;
    await $http
      .request('unionSearch/unionHistoryList', {
        data: {
          space_uid: this.spaceUid,
          index_set_type: queryType,
        },
      })
      .then((res) => {
        if (queryType === 'single') {
          this.aloneHistory = res.data;
        } else {
          this.multipleHistory = res.data;
        }
      })
      .finally(() => {
        this.historyLoading = false;
      });
  }

  /** 检查收藏名 */
  checkFavoriteName() {
    return !this.multipleFavorite.some(
      item => item.name === this.verifyData.favoriteName.trim(),
    );
  }

  getOptionName(item) {
    return `${item.indexName}${item.lightenName}${item.tagSearchName ? `(${item.tagSearchName})` : ''}`;
  }

  render() {
    const labelFilter = () => {
      return (
        <div class="label-filter" v-en-class="en-label-btn">
          <div class="select-type-btn">
            {this.typeBtnSelectList.map(item => (
              <div
                class={{ active: this.indexSearchType === item.id }}
                onClick={() => this.handleClickSetType(item.id as IndexSetType)}
              >
                {item.label}
              </div>
            ))}
          </div>
          <div class="label-tag-container">
            <div class="tag-box" ref="tagBox">
              {this.labelSelectList.map(item => (
                <div>
                  <span
                    class={[
                      'tag-item',
                      {
                        'tag-select': this.filterTagID === item.tag_id,
                      },
                    ]}
                    onClick={() => this.handleClickTag(item.tag_id)}
                  >
                    {item.name}
                  </span>
                </div>
              ))}
            </div>
            <div onClick={this.scrollLeft} class="move-icon left-icon">
              <i class="bk-icon icon-angle-left-line"></i>
            </div>
            <div onClick={this.scrollRight} class="move-icon right-icon">
              <i class="bk-icon icon-angle-right-line"></i>
            </div>
          </div>
        </div>
      );
    };
    const favoriteListDom = () => {
      return (
        <ul class="favorite-list">
          {this.showFavoriteList.map(item => (
            <li
              class={[
                'favorite-item',
                {
                  active: this.favoriteActive(item),
                },
              ]}
              onClick={() => this.handleClickFavorite(item)}
            >
              <span class="name title-overflow">{item.name}</span>
              <span
                class="cancel"
                onClick={e => this.handleCancelFavorite(item, e)}
              >
                {this.$t('取消收藏')}
              </span>
            </li>
          ))}
        </ul>
      );
    };
    const historyListDom = () => {
      return (
        <div class="history">
          {!!this.historyListNum && (
            <div class="top-clear">
              <span>{`${this.historyListNum}/10`}</span>
              <span
                class="clear-btn"
                onClick={e => this.handleDeleteHistory(null, e, true)}
              >
                <i class="log-icon icon-brush"></i>
                <span>{this.$t('清空')}</span>
              </span>
            </div>
          )}
          {this.isAloneType ? (
            <ul
              class="history-alone-list"
              v-bkloading={{ isLoading: this.historyLoading }}
            >
              {this.aloneHistory.map(item => (
                <li
                  class={[
                    'history-alone-item',
                    {
                      active: this.favoriteActive(item),
                    },
                  ]}
                  onClick={() => this.handleClickFavorite(item)}
                >
                  <span class="name title-overflow">{item.index_set_name}</span>
                  <i
                    class="bk-icon icon-close-circle-shape"
                    onClick={e => this.handleDeleteHistory(item, e)}
                  ></i>
                </li>
              ))}
            </ul>
          ) : (
            <ul
              class="history-multiple-list"
              v-bkloading={{ isLoading: this.historyLoading }}
            >
              {this.multipleHistory.map(item => (
                <li
                  class={[
                    'history-multiple-item',
                    {
                      active: this.multipleHistorySelectID === item.id,
                    },
                  ]}
                  onClick={() => this.handleClickHistory(item)}
                >
                  <div class="tag-box">
                    {item.index_set_names?.map(setName => (
                      <Tag>{setName}</Tag>
                    ))}
                  </div>
                  <i
                    class="bk-icon icon-close-circle-shape"
                    onClick={e => this.handleDeleteHistory(item, e)}
                  ></i>
                </li>
              ))}
            </ul>
          )}
        </div>
      );
    };
    const favoriteAndHistory = () => {
      return (
        <div class="favorite-and-history">
          <Tab
            type="unborder-card"
            active={this.activeTab}
            on-tab-change={this.handleTabChange}
          >
            {this.tabPanels.map((panel, index) => (
              <TabPanel {...{ props: panel }} key={index}>
                <div slot="label" class="top-label">
                  <i class={panel.icon}></i>
                  <span class="panel-name">{panel.label}</span>
                </div>
              </TabPanel>
            ))}
            {this.activeTab === 'favorite'
              ? favoriteListDom()
              : historyListDom()}
          </Tab>
        </div>
      );
    };
    const selectIndexContainer = () => (
      <div
        v-show={!!this.selectedItemList.length && !this.isAloneType}
        class="select-index-container"
        ref="selectIndexBox"
      >
        <div class="title">
          <div class="index-select">
            <i18n style="color: #979BA5;" path="已选择{0}个索引集">
              {this.selectedItemList.length}
            </i18n>
            {this.isOverSelect && (
              <span class="over-select">{this.$t('每次最多可选择10项')}</span>
            )}
          </div>
          <Popover
            ref="favoritePopover"
            tippy-options={{
              ...this.tippyOptions,
              appendTo: () => this.selectIndexBoxRef,
            }}
            placement="bottom-start"
            ext-cls="new-favorite-popover"
            disabled={!!this.multipleFavoriteSelectID}
          >
            <span class="favorite-btn">
              <i
                class={[
                  !!this.multipleFavoriteSelectID
                    ? 'log-icon icon-star-shape'
                    : 'log-icon bk-icon icon-star',
                ]}
              ></i>
              <span>{this.$t('收藏该组合')}</span>
            </span>
            <div slot="content">
              <Form
                labelWidth={0}
                style={{ width: '100%' }}
                ref="checkInputForm"
                {...{
                  props: {
                    model: this.verifyData,
                    rules: this.rules,
                  },
                }}
              >
                <FormItem property="favoriteName">
                  <span style="color: #63656E;">{this.$t('收藏名称')}</span>
                  <Input
                    clearable
                    vModel={this.verifyData.favoriteName}
                    onEnter={() => this.handleClickFavoritePopoverBtn('add')}
                  ></Input>
                </FormItem>
              </Form>
              <div class="operate-button">
                <Button
                  text
                  onClick={() => this.handleClickFavoritePopoverBtn('add')}
                >
                  {this.$t('确认收藏')}
                </Button>
                <Button
                  text
                  onClick={() => this.handleClickFavoritePopoverBtn('cancel')}
                >
                  {this.$t('取消')}
                </Button>
              </div>
            </div>
          </Popover>
        </div>
        <div class="index-tag-box">
          {this.selectedItemList.map(item => (
            <Tag
              closable
              style="background: #FAFBFD;"
              type="stroke"
              onClose={() => this.handleCloseSelectTag(item)}
            >
              {item.indexName}
            </Tag>
          ))}
        </div>
      </div>
    );
    const indexHandDom = (item) => {
      return this.isAloneType ? (
        <span
          class={[
            item.is_favorite
              ? 'log-icon icon-star-shape'
              : 'log-icon bk-icon icon-star',
          ]}
          onClick={e => this.handleCollection(item, e)}
        ></span>
      ) : (
        <Checkbox
          disabled={this.getDisabled(item.index_set_id)}
          checked={this.getCheckedVal(item.index_set_id)}
        ></Checkbox>
      );
    };
    const selectGroupDom = () => {
      return (
        <div class="group-list" style={this.groupListStyle}>
          {this.renderOptionList.map(group => (
            <OptionGroup
              show-count={false}
              name={group.name}
              id={(group as any).id}
              scopedSlots={{
                'group-name': () => {
                  return group.name && group.children.length ? (
                    <div class="group-title">
                      <span>{group.name}</span>
                      <span>{group.children[0].no_data_check_time}</span>
                    </div>
                  ) : undefined;
                },
              }}
            >
              {group.children.map(item => (
                <Option
                  class="custom-no-padding-option"
                  id={String(item.index_set_id)}
                  name={this.getOptionName(item)}
                  disabled={this.getDisabled(item.index_set_id)}
                >
                  {this.isHaveAuthority(item) ? (
                    <div
                      class="authority"
                      style="padding: 9px 10px;"
                      onClick={() => this.handelClickIndexSet(item)}
                    >
                      <span class="index-info">
                        {indexHandDom(item)}
                        <span class="index-name" v-bk-overflow-tips>
                          {item.indexName}
                        </span>
                        <span class="lighten-name" v-bk-overflow-tips>
                          {item.lightenName}
                        </span>
                      </span>
                      <div class="index-tags">
                        {item.tags.map((tag, tIndex) => {
                          if (tag.tag_id === 4) return undefined; // 无数据 不显示
                          return tIndex < 2 ? (
                            <span class={['tag-card', `tag-card-${tag.color}`]}>
                              {tag.name}
                            </span>
                          ) : undefined;
                        })}
                      </div>
                    </div>
                  ) : (
                    <div
                      class="option-slot-container no-authority"
                      onClick={e => e.stopPropagation()}
                    >
                      <span class="text">
                        {item.indexName + item.lightenName}
                      </span>
                      <span
                        class="apply-text"
                        onClick={() => this.applySearchAccess(item)}
                      >
                        {this.$t('申请权限')}
                      </span>
                    </div>
                  )}
                </Option>
              ))}
            </OptionGroup>
          ))}
        </div>
      );
    };
    const triggerSlot = () => {
      if (this.isAloneType) {
        return (
          <div
            class="bk-select-name"
            v-bk-overflow-tips={{ placement: 'right' }}
          >
            <span>{this.selectedItem.indexName}</span>
            <span style="color: #979ba5;">{this.selectedItem.lightenName}</span>
          </div>
        );
      }
    };
    return (
      <Select
        searchable
        multiple={true}
        display-tag={!this.isAloneType}
        ext-popover-cls="retrieve-index-select-popover"
        class="retrieve-index-select"
        data-test-id="dataQuery_div_indexSetSelect"
        ref="selectInput"
        clearable={false}
        v-model={this.selectTagCatchIDList}
        popover-min-width={600}
        popover-options={{ boundary: 'window' }}
        scroll-height={400}
        onSelected={this.handleSelectIndex}
        onToggle={this.toggleSelect}
        scopedSlots={{
          trigger: () => triggerSlot(),
        }}
      >
        {labelFilter()}
        {favoriteAndHistory()}
        {selectIndexContainer()}
        {selectGroupDom()}
      </Select>
    );
  }
}
