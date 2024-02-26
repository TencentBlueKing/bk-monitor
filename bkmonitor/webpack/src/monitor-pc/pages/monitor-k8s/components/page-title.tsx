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
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Debounce, random } from 'monitor-common/utils/utils';
// import ListMenu from './list-menu';
import { throttle } from 'throttle-debounce';

import { BookMarkMode, COMMON_TAB_LIST, CommonTabType, IMenuItem, ISearchItem, ITabItem, SearchType } from '../typings';

import './page-title.scss';

const SMALL_SCREEN = 1440;
interface IPageTitleProps {
  // tab列表
  tabList?: ITabItem[];
  // active tab
  activeTab?: CommonTabType | string;
  // 是否显示搜索
  showSearch?: boolean;
  bookMarkMode?: BookMarkMode;
  // 是否显示过滤
  showFilter?: boolean;
  // 是否显示详情
  showInfo?: boolean;
  // 是否显示列表
  showListPanel?: boolean;
  filterActive?: boolean;
  searchData?: ISearchItem[];
  searchValue?: ISearchItem[] | string[];
  // 是否显示左侧栏设置
  showSelectPanel?: boolean;
  selectPanelActive?: boolean;
  listPanelActive?: boolean;
  // info active
  infoActive?: boolean;
  // 概览与列表选项（概览选项不可点击且置灰）
  disableOverview?: boolean;
  filterCount?: number;
  needAddViewBtn?: boolean;
}
interface IPageTitleEvent {
  onTabChange: ITabItem;
  onSearchClick: boolean;
  onFilterChange: boolean;
  onInfoChange: boolean;
  onSearchChange: (a: SearchType, b: ISearchItem[]) => void;
  onSelectPanelChange: boolean;
  onListPanelChange: boolean;
  onAddTab: void;
}
@Component
export default class PageTitle extends tsc<IPageTitleProps, IPageTitleEvent> {
  // 只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  @Prop({ default: () => COMMON_TAB_LIST }) tabList: ITabItem[];
  @Prop({ required: true }) activeTab: CommonTabType | string;
  @Prop({ default: true, type: Boolean }) showSearch: boolean;
  @Prop({ default: true, type: Boolean }) showFilter: boolean;
  @Prop({ default: true, type: Boolean }) showInfo: boolean;
  @Prop({ default: true, type: Boolean }) showSelectPanel: boolean;
  @Prop({ default: false, type: Boolean }) showListPanel: boolean;
  @Prop({ default: false, type: Boolean }) selectPanelActive: boolean;
  @Prop({ default: false, type: Boolean }) filterActive: boolean;
  @Prop({ default: false, type: Boolean }) infoActive: boolean;
  @Prop({ default: false, type: Boolean }) listPanelActive: boolean;
  @Prop({ default: false, type: Boolean }) disableOverview: boolean;
  @Prop({ default: 'auto', type: String }) bookMarkMode: BookMarkMode;
  @Prop({ default: () => [], type: Array }) searchData: ISearchItem[];
  @Prop({ default: () => [], type: Array }) searchValue: ISearchItem[] | string[];
  @Prop({ default: 0, type: Number }) filterCount: number;
  @Prop({ default: false, type: Boolean }) needAddViewBtn: boolean;
  @Ref() searchSelect: any;
  @Ref() inputSearchRef: any;
  @Ref() inputSearchMenuRef: any;
  @Ref() listSearchSelect: any;
  searchActive = false;
  isRefreshRandomKey = random(6);
  searchKeyword = '';
  isSmallScreen = false;
  insideSearchSelect = false;
  throttledResize: Function = () => {};

  // 是否是key-value模式搜索
  get isKeyValueSearch() {
    return this.searchData.some(item => item.children);
  }
  created() {
    this.throttledResize = throttle(300, false, this.handleResize);
  }

  mounted() {
    if (document.body.clientWidth >= SMALL_SCREEN) {
      this.searchActive = true;
    }
    this.handleResize();
    window.addEventListener('resize', this.throttledResize as any);
  }

  destroyed() {
    window.removeEventListener('resize', this.throttledResize as any);
  }

  @Emit('tabChange')
  handleTabChange(v: CommonTabType): ITabItem {
    const item = this.tabList.find(item => item.id === v);
    return item;
  }

  @Emit('searchCick')
  handleSearch() {
    this.searchActive = !this.searchActive;
    this.handleFocusSearch();
    return this.searchActive;
  }
  @Emit('filterChange')
  handleFileter() {
    return !this.filterActive;
  }
  @Emit('infoChange')
  handleInfo() {
    return !this.infoActive;
  }
  handleSearchChange(v: ISearchItem[] | string[]) {
    this.$emit('searchChange', !this.isKeyValueSearch ? 'list' : 'key-value', v);
  }
  @Emit('selectPanelChange')
  handleSelectPanelActive() {
    return !this.selectPanelActive;
  }
  @Emit('listPanelChange')
  handleListPanelActive(v: boolean) {
    return v;
  }
  @Watch('tabList', { immediate: true })
  handleTabListChange() {
    this.isRefreshRandomKey = random(6);
  }
  /**
   * @description: 搜索框失去焦点后检查是否缩进搜索框
   * @param {*}
   * @return {*}
   */
  handleSearchBlur() {
    setTimeout(() => {
      this.searchActive =
        this.searchValue.length > 0 ||
        (this.$refs.searchSelect as any)?.input.value.length > 0 ||
        (this.$refs.searchSelect as any)?.input.focus;
      try {
        !this.searchSelect?.input.focus && this.searchSelect.handleKeyEnter({ preventDefault: () => {} });
      } catch (error) {
        console.log(error);
      }
    }, 100);
  }
  handleSearchToggle() {
    setTimeout(() => {
      this.searchActive = this.searchValue.length > 0 || (this.listSearchSelect as any).focus;
    }, 100);
  }
  @Debounce(300)
  handleSearchInputChange(val: string) {
    this.searchKeyword = val;
  }
  handleSearchMenuSelect(val: IMenuItem) {
    this.$emit('searchChange', 'list', [val]);
  }
  handleSearchMenuHidden() {
    this.searchActive = !!this.searchKeyword?.length;
  }

  handleResize() {
    this.isSmallScreen = document.body.clientWidth < SMALL_SCREEN;
  }

  @Emit('addTab')
  handleAddTab() {}

  /** 自动聚焦搜索框 此处包含了三种搜索框 */
  handleFocusSearch() {
    setTimeout(() => {
      if (this.bookMarkMode === 'auto') {
        if (this.isKeyValueSearch) {
          this.searchSelect?.$refs?.input?.click?.();
        } else {
          const popEl = this.listSearchSelect?.$refs?.selectDropdown.$el;
          const triggerEl = popEl.querySelector('.bk-tooltip-ref');
          triggerEl.click();
        }
      } else {
        this.inputSearchRef?.focus?.();
        setTimeout(() => {
          this.inputSearchMenuRef?.handleClick();
          this.inputSearchRef?.focus?.();
        }, 300);
      }
    }, 100);
  }

  // 概览/列表

  getOverviewOrList(isOverview = true) {
    return (
      <span class='overview-list-options'>
        <span
          class={['overview', { active: this.disableOverview ? false : isOverview }, { disable: this.disableOverview }]}
          v-bk-tooltips={{ content: this.$t('概览'), delay: 200, boundary: 'window', disabled: !this.isSmallScreen }}
          onClick={() => !this.disableOverview && this.handleListPanelActive(false)}
        >
          <i class='icon-monitor icon-mc-overview option-icon'></i>
          {!this.isSmallScreen ? <span class='option-text'>{this.$t('概览')}</span> : undefined}
        </span>
        <span
          class={['list', { active: !isOverview || this.disableOverview }]}
          v-bk-tooltips={{ content: this.$t('列表'), delay: 200, boundary: 'window', disabled: !this.isSmallScreen }}
          onClick={() => this.handleListPanelActive(true)}
        >
          <i class='icon-monitor icon-mc-list option-icon'></i>
          {!this.isSmallScreen ? <span class='option-text'>{this.$t('列表')}</span> : undefined}
        </span>
      </span>
    );
  }

  render() {
    const tabItemTpl = (_, id) => {
      const item = this.tabList.find(item => item.id === id);
      return (
        <span
          class={['tab-item-name', { active: id === this.activeTab }]}
          key={item.id}
        >
          <span class='tab-label-text'>{item.name}</span>
          {item.show_panel_count && (
            <span class={`tab-item-count ${this.activeTab === item.id ? 'item-active' : ''}`}>{item.panel_count}</span>
          )}
        </span>
      );
    };

    return (
      <div class='page-title'>
        <div class='page-header'>
          <div class='page-header-name'>{this.$slots.title || this.$t('容器监控')}</div>
          <div class='page-header-tools'>{this.$slots.tools}</div>
        </div>
        <div class='page-filters'>
          <div
            class='page-filters-tab'
            style={{ width: `calc(100% - ${this.searchActive ? '360px' : '130px'})` }}
          >
            {!this.readonly && this.tabList.length ? (
              <bk-tab
                key={this.isRefreshRandomKey}
                type='unborder-card'
                active={this.activeTab}
                {...{ on: { 'update:active': this.handleTabChange } }}
              >
                {this.tabList.map(item => (
                  <bk-tab-panel
                    class='tab-item'
                    name={item.id}
                    label={item.name}
                    key={item.id}
                    render-label={tabItemTpl}
                  />
                ))}
                <div slot='setting'>{this.$slots.tabSetting}</div>
                {this.needAddViewBtn && (
                  <span
                    slot='add'
                    class='add-btn-wrap'
                    onClick={this.handleAddTab}
                  >
                    <i class='icon-monitor icon-mc-add'></i>
                  </span>
                )}
              </bk-tab>
            ) : undefined}
          </div>
          <div class='page-filters-tools'>
            {this.$slots.filter}
            {
              this.showSearch &&
                this.searchActive &&
                (this.bookMarkMode === 'auto'
                  ? [
                      this.isKeyValueSearch ? (
                        <bk-search-select
                          ref='searchSelect'
                          class='filter-search'
                          data={this.searchData}
                          values={this.searchValue}
                          show-condition={false}
                          on-input-click-outside={this.handleSearchBlur}
                          on-change={this.handleSearchChange}
                        />
                      ) : (
                        <span
                          onMouseenter={() => (this.insideSearchSelect = true)}
                          onMouseleave={() => (this.insideSearchSelect = false)}
                          class='page-filters-select'
                        >
                          <bk-select
                            value={this.searchValue}
                            ref='listSearchSelect'
                            class='filter-search'
                            searchable={true}
                            multiple={true}
                            display-tag={true}
                            show-select-all={true}
                            behavior='simplicity'
                            popoverOptions={{
                              onHidden: this.handleSearchToggle
                            }}
                            on-change={this.handleSearchChange}
                          >
                            {this.searchData.map(item => (
                              <bk-option
                                key={item.id}
                                id={item.id}
                                name={item.name}
                              ></bk-option>
                            ))}
                          </bk-select>
                          {(!this.insideSearchSelect || !this.searchValue.length) && (
                            <i class='bk-icon icon-search'></i>
                          )}
                        </span>
                      )
                    ]
                  : undefined)
              // <ListMenu
              //   list={this.searchData}
              //   keyword={this.searchKeyword}
              //   ref="inputSearchMenuRef"
              //   onHidden={this.handleSearchMenuHidden}
              //   onMenuSelect={this.handleSearchMenuSelect}>
              //   <div class="filter-search-wrap">
              //     <bk-input class="filter-search"
              //       ref="inputSearchRef"
              //       // right-icon="bk-icon icon-search"
              //       behavior="simplicity"
              //       value={this.searchKeyword}
              //       onChange={this.handleSearchInputChange} />
              //     <i class="icon-monitor icon-dingwei1 search-icon"></i>
              //   </div>
              // </ListMenu>)
            }
            {this.showSearch && !this.searchActive && (
              <i
                class={[
                  `tool-icon ${this.searchActive ? 'icon-active' : ''}`,
                  this.bookMarkMode === 'auto' ? 'bk-icon icon-search' : 'icon-monitor'
                ]}
                onMouseenter={this.handleSearch}
              />
            )}
            {!window.__BK_WEWEB_DATA__?.lockTimeRange && this.showFilter && (
              <span
                class='filter-tool-wrap'
                v-bk-tooltips={{ content: this.$t('筛选'), delay: 200, boundary: 'window' }}
              >
                {!!this.filterCount && <span class='filter-badge'>{this.filterCount}</span>}
                <i
                  class={`icon-monitor icon-filter tool-icon ${this.filterActive ? 'icon-active' : ''}`}
                  onClick={this.handleFileter}
                />
              </span>
            )}
            {this.showSelectPanel && (
              <i
                class={`icon-monitor icon-mc-tree tool-icon ${this.selectPanelActive ? 'icon-active' : ''}`}
                v-bk-tooltips={{ content: this.$t('列表'), delay: 200, boundary: 'window' }}
                onClick={this.handleSelectPanelActive}
              />
            )}
            {this.showInfo && (
              <i
                v-bk-tooltips={{ content: this.$t('详情'), delay: 200, boundary: 'window' }}
                class={`icon-monitor icon-mc-detail tool-icon ${this.infoActive ? 'icon-active' : ''}`}
                onClick={this.handleInfo}
              />
            )}
            {this.showListPanel && this.getOverviewOrList(!this.listPanelActive)}
          </div>
        </div>
      </div>
    );
  }
}
