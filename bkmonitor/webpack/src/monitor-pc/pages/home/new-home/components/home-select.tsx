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
import { Component, Ref, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { COMMON_ROUTE_LIST } from '../../../../router/router-config';
import { type ISearchListItem, type ISearchItem } from '../type';
import { highLightContent, ESearchType } from '../utils';

import './home-select.scss';
interface IHomeSelectProps {
  searchList: ISearchListItem[];
  historyList: ISearchListItem[];
}

@Component({
  name: 'HomeSelect',
})
export default class HomeSelect extends tsc<IHomeSelectProps> {
  /** 接口搜索结果列表 */
  @Prop({ default: () => [], type: Array }) searchList: ISearchListItem[];
  /** 历史搜索列表 */
  @Prop({ default: () => [], type: Array }) historyList: ISearchListItem[];

  @Ref('select') selectRef: HTMLDivElement;
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('textareaInput') textareaInputRef: HTMLDivElement;

  searchValue = '';
  searchType = '';
  showPopover = false;
  routeList = [];
  /* 弹出实例 */
  popInstance = null;
  currentValue: ISearchItem = {};
  showHostView = false;
  operatorList = [
    { name: this.$t('关联的告警'), key: 'alarm' },
    { name: this.$t('关联的屏蔽策略'), key: 'strategy' },
  ];
  isLoading = false;
  flattenRoute(tree) {
    let result = [];
    const traverse = node => {
      if (!node) return;
      result.push(node);
      if (node.children && node.children.length > 0) {
        node.children.forEach(child => traverse(child));
      }
    };
    tree.forEach(rootNode => traverse(rootNode));
    return result;
  }
  /** 符合搜索内容的路由列表 */
  get searchRouteList() {
    return (this.routeList || []).filter(item => item.name.indexOf(this.searchValue) !== -1);
  }
  /** 点击收起下拉框 */
  handleClickOutside(event) {
    if (
      this.showPopover &&
      this.wrapRef &&
      !this.wrapRef.contains(event.target) &&
      this.selectRef &&
      !this.selectRef.contains(event.target)
    ) {
      this.showPopover = false;
    }
  }
  mounted() {
    this.autoResize();
    this.routeList = this.flattenRoute(COMMON_ROUTE_LIST).filter(item => item.icon);
    document.addEventListener('click', this.handleClickOutside);
  }
  beforeDestroy() {
    document.removeEventListener('click', this.handleClickOutside);
  }
  /* 显示弹出层 */
  handleMousedown() {
    this.showPopover = true;
  }
  /** 关联的屏蔽策略/关联的告警  */
  handleOperator(item: ISearchItem, key: string) {
    console.log(item, key);
  }

  /** 渲染查询结果Item */
  renderGroupItem(item: ISearchItem, type: string) {
    const isHost = type === ESearchType.host;
    const isStrategy = type === ESearchType.strategy;
    return (
      <div
        class='new-home-select-group-item'
        onClick={() => this.handleItemClick(item, type)}
      >
        {isHost && <span class='ip-tag'>0:</span>}
        <span class='item-label'>
          <span domPropsInnerHTML={item.nameSearch}></span>
          {isHost && <span class='ip-sub'>{item.bk_host_name}</span>}
        </span>
        {isStrategy && (
          <span class='item-operator'>
            {this.operatorList.map(operator => (
              <label
                key={operator.key}
                class='item-operator-item'
                on-click={() => this.handleOperator(item, operator.key)}
              >
                {operator.name}
              </label>
            ))}
          </span>
        )}
        <span class='item-business'>{item.bk_biz_name}</span>
      </div>
    );
  }
  /** 渲染历史搜索Item */
  renderHistoryItem(item) {
    return (
      <div
        class='new-home-select-history-item'
        onClick={() => this.handleItemClick(item, 'history')}
      >
        <i class='icon-monitor icon-lishijilu item-icon'></i>
        {item.name}
      </div>
    );
  }
  /** 跳转到具体的功能 */
  handleGoRoute(item) {
    this.showPopover = false;
    window.open(location.href.replace(location.hash, item.href));
  }
  renderRouterList() {
    return (
      <div class='secondary-list'>
        <span class='new-home-select-item-title'>
          {this.$t('相关功能')}（{this.searchRouteList.length}）
        </span>
        <div class='new-home-select-router-list'>
          {this.searchRouteList.map(item => (
            <span
              class='new-home-select-router-item'
              on-click={() => this.handleGoRoute(item)}
            >
              <i class={`${item?.icon} router-item-icon`}></i>
              <span class='item-txt'>{item?.name}</span>
            </span>
          ))}
        </div>
      </div>
    );
  }
  handleItemClick(item: ISearchItem, type: string) {
    this.searchType = type;
    this.showPopover = false;
    this.currentValue = item;
    this.searchValue = item.name;
  }
  /** 渲染历史搜索列表 */
  renderHistoryList() {
    return this.historyList.map(item => this.renderHistoryItem(item));
  }

  renderRouteAndWord() {
    if (this.searchValue && this.searchRouteList.length > 0) {
      return [<div class='new-home-select-divider'></div>, this.renderRouterList()];
    }
  }
  /** 渲染历史搜索列表 */
  renderGroupList() {
    return this.searchList.map(item => {
      const data = highLightContent(this.searchValue, item.items, ['name']);
      return (
        <div>
          <span class='new-home-select-item-title'>
            {item.name}（{item.items.length}）
          </span>
          {data.map(child => this.renderGroupItem(child, item.type))}
        </div>
      );
    });
  }
  handleBlur() {
    this.showHostView = true;
  }
  handleFocus() {
    this.showHostView = false;
  }
  handleInputFocus() {
    this.handleFocus();
    this.textareaInputRef.focus();
  }
  clearSearchValue() {
    this.searchValue = '';
  }
  /** 溢出动态展示输入框高度 */
  autoResize() {
    this.textareaInputRef.style.height = 'auto';
    this.textareaInputRef.style.height = `${this.textareaInputRef.scrollHeight}px`;
  }
  /** 清空历史 */
  clearHistory() {}

  render() {
    return (
      <div class='new-home-select'>
        <div
          ref='select'
          class='new-home-select-input'
          onMousedown={this.handleMousedown}
        >
          <span class='new-home-select-icon'></span>
          {/* ip类型选中后的特殊展示处理 */}
          {this.showHostView && this.searchType === ESearchType.host && (
            <span
              class='host-show-view'
              on-click={this.handleInputFocus}
            >
              <span class='ip-tag'>0:</span>
              <span class='item-label'>{this.currentValue.name}</span>
              <span class='ip-sub'>{this.currentValue.bk_host_name}</span>
            </span>
          )}
          <textarea
            ref='textareaInput'
            class='home-select-input'
            v-model={this.searchValue}
            placeholder={this.$t('请输入 IP / traceId / 容器集群 / 告警ID / 策略名 进行搜索')}
            rows={1}
            type='textarea'
            clearable
            on-enter={() => console.log('111')}
            onBlur={this.handleBlur}
            onFocus={this.handleFocus}
            onInput={this.autoResize}
          ></textarea>
        </div>
        {this.showPopover && (
          <div
            ref='wrap'
            class='new-home-select-popover'
          >
            {this.searchList.length > 0 ? (
              <div class='new-home-select-popover-content'>
                {!this.searchValue && this.historyList.length > 0 && (
                  <div class='item-list-title'>
                    <span>{this.$t('历史搜索')}</span>
                    <span
                      class='item-list-clear'
                      on-click={this.clearHistory}
                    >
                      <i class='icon-monitor icon-mc-clear'></i>
                      {this.$t('清空历史')}
                    </span>
                  </div>
                )}
                <div class='item-list'>
                  {!this.searchValue && this.historyList.length > 0 && this.renderHistoryList()}
                  {this.renderGroupList()}
                  {this.renderRouteAndWord()}
                </div>
                {this.isLoading && (
                  <div class='loading-view'>
                    <i class='icon-monitor icon-loading1'></i>
                    {this.$t('当前正在加载 采集任务')}
                  </div>
                )}
              </div>
            ) : (
              <bk-exception
                class='select-empty'
                scene='part'
                type='search-empty'
              >
                {this.searchValue ? (
                  <span>
                    {this.$t('当前输入条件无匹配结果，请清空后重新输入')}
                    <label
                      class='clear-btn'
                      on-click={this.clearSearchValue}
                    >
                      {this.$t('清空搜索')}
                    </label>
                  </span>
                ) : (
                  <span>{this.$t('请输入关键词进行搜索')}</span>
                )}
              </bk-exception>
            )}
          </div>
        )}
      </div>
    );
  }
}
