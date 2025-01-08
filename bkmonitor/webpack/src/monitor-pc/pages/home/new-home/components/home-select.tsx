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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { COMMON_ROUTE_LIST } from '../../../../router/router-config';
import { type ISearchListItem, type ISearchItem, type IRouteItem } from '../type';
import { highLightContent, ESearchType } from '../utils';

import './home-select.scss';

interface IHomeSelectProps {
  searchList?: ISearchListItem[];
  historyList?: ISearchListItem[];
}
const storageKey = 'bk_monitor_new_home_history';

@Component({
  name: 'HomeSelect',
})
export default class HomeSelect extends tsc<IHomeSelectProps> {
  @Ref('select') selectRef: HTMLDivElement;
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('textareaInput') textareaInputRef: HTMLDivElement;
  searchValue: string = '';
  searchType: string = '';
  showPopover: boolean = false;
  routeList: IRouteItem[] = [];
  /** 策略可跳转列表 */
  operatorList = [
    { name: this.$t('关联的告警'), key: 'strategy-alarm' },
    { name: this.$t('关联的屏蔽配置'), key: 'alarm-shield' },
  ];
  isLoading: boolean = false;
  /** 高亮选中的index, 第一个表示组的下标，第二个表示items的下标 */
  highlightedIndex: number[] = [-1, -1];
  /** 高亮选中的Item */
  highlightedItem: ISearchItem = {};

  highlightedValue: string = '';
  /** 历史搜索数据  */
  localHistoryList: ISearchListItem[] = [];
  /** 接口搜索结果列表 */
  searchList: ISearchListItem[] = [];
  /** 是否为input输入内容 */
  isInput: boolean = false;
  isEmpty: boolean = false;
  searchLenArr: number[] = [];

  /** 处理数据 */
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
    return (this.routeList || []).filter(item => item.name.indexOf(this.highlightedValue) !== -1);
  }
  /** 是否展示搜索结果 */
  get isSearchResult() {
    return this.isInput && this.searchValue;
  }

  get currentListKey() {
    return this.isSearchResult ? 'searchList' : 'localHistoryList';
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
  /** 解析后台返回的eventStream */
  async fetchEventStream(url: string) {
    this.searchList = [];
    try {
      const response = await fetch(url);
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // 解码新数据并添加到缓冲区
        buffer += decoder.decode(value, { stream: true });

        // 处理缓冲区中的完整事件
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const eventString = buffer.substring(0, boundary);
          buffer = buffer.substring(boundary + 2);
          this.processEvent(eventString);
          boundary = buffer.indexOf('\n\n');
        }
      }
    } catch (error) {
      console.error('Error fetching event stream:', error);
    }
  }
  // 从给定的事件字符串中提取数据，如果事件字符串以"data:"开头，则截取并解析其中的JSON数据，否则返回null
  extractDataFromEventString(eventString) {
    if (eventString.startsWith('data:')) {
      const eventData = eventString.slice(5).trim();
      return JSON.parse(eventData);
    }
    return null;
  }

  // 根据传入的已解析数据（parsedData）来更新搜索列表（searchList）
  // 如果已解析数据的类型在搜索列表中已存在，则过滤掉原列表中同类型的数据，然后将新数据加入列表
  // 如果不存在，则直接将新数据添加到搜索列表末尾，并返回更新后的搜索列表
  updateSearchList(searchList, parsedData) {
    const index = searchList.findIndex(item => item.type === parsedData.type);
    if (index !== -1) {
      const data = searchList.filter(item => item.type !== parsedData.type);
      return [...data, parsedData];
    }
    return [...searchList, parsedData];
  }
  /** 处理后台返回的数据 */
  processEvent(eventString: string) {
    try {
      // 事件字符串中是否包含'end'来设置this.isLoading的值，若不包含'end'则设为true，表示正在加载，反之设为false
      this.isLoading = eventString.indexOf('end') < 0;
      // 提取事件字符串中的数据
      const parsedData = this.extractDataFromEventString(eventString);
      if (parsedData) {
        this.searchLenArr = [];
        // 如果提取到了有效数据，更新搜索列表
        this.searchList = this.updateSearchList(this.searchList, parsedData);
        this.searchList.map(item => this.searchLenArr.push(item.items.length));
        /** 默认选中第一个，直接回车的话就按照第一个跳转 */
        this.highlightedIndex = [0, 0];
        this.getSearchHightItem();
      }
    } catch (error) {
      this.isLoading = false;
      console.error('Error parsing event string:', error);
    }
  }

  /** 获取搜索结果 */
  getSearchList() {
    this.isLoading = true;
    this.fetchEventStream(`${location.origin}/rest/v2/overview/search/?query=${this.searchValue}`);
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
    this.localHistoryList = JSON.parse(localStorage.getItem(storageKey)) || [];
  }
  /** 关联的屏蔽策略/关联的告警  */
  handleOperator(e, item: ISearchItem, key: string) {
    e.stopPropagation();
    this.handleSearchJumpPage(item, key);
  }

  /** 渲染查询结果Item */
  renderGroupItem(item: ISearchItem, type: string, parentInd: number, ind: number) {
    const isHost = type === ESearchType.host;
    const isStrategy = type === ESearchType.strategy;
    return (
      <div
        class={[
          'new-home-select-group-item',
          {
            active: this.highlightedIndex[0] === parentInd && this.highlightedIndex[1] === ind,
          },
        ]}
        onClick={() => this.handleItemClick(item, type)}
      >
        {isHost && <span class='ip-tag'>{item.bk_cloud_id}:</span>}
        <span class='item-label'>
          <span domPropsInnerHTML={item.nameSearch}></span>
          {isHost && <span class='ip-sub'>（{item.bk_host_name}）</span>}
        </span>
        {isStrategy && (
          <span class='item-operator'>
            {this.operatorList.map(operator => (
              <label
                key={operator.key}
                class='item-operator-item'
                on-click={e => this.handleOperator(e, item, operator.key)}
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
  renderHistoryItem(item: ISearchItem, ind: number) {
    return (
      <div
        class={[
          'new-home-select-history-item',
          {
            active: this.highlightedIndex[1] === ind,
          },
        ]}
        onClick={() => this.handleSearchJumpPage(item, item.type)}
      >
        <i class='icon-monitor icon-lishijilu item-icon'></i>
        <span class='history-item-name'>{item.name}</span>
      </div>
    );
  }
  /** 跳转到具体的功能 */
  handleGoRoute(item) {
    this.showPopover = false;
    window.open(location.href.replace(location.hash, item.href));
  }
  /** 相关功能Render */
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
  /** 设置历史搜索 */
  setLocalHistory(item: ISearchItem, type: string) {
    try {
      const listStr = localStorage.getItem(storageKey);
      const obj = {
        ...item,
        type,
      };
      const list = listStr ? JSON.parse(listStr) : [];
      const resultList = list.filter(item => item.name !== obj.name);

      if (resultList.length >= 50) {
        resultList.splice(resultList.length - 1, resultList.length - 50);
      }

      resultList.unshift(obj);
      localStorage.setItem(storageKey, JSON.stringify(resultList));
    } catch (err) {
      console.log(err);
    }
  }
  /** 选中搜索结果 */
  handleItemClick(item: ISearchItem, type: string) {
    this.searchType = type;
    this.showPopover = false;
    this.highlightedItem = item;
    this.setLocalHistory(item, type);
    this.handleSearchJumpPage(item, type);
  }
  /** 渲染历史搜索列表 */
  renderHistoryList() {
    return this.localHistoryList.map((item, ind) => this.renderHistoryItem(item, ind));
  }
  /** 相关功能/文档渲染 */
  renderRouteAndWord() {
    if (this.searchValue && this.searchRouteList.length > 0) {
      return [<div class='new-home-select-divider'></div>, this.renderRouterList()];
    }
  }
  /** 渲染搜索列表 */
  renderGroupList() {
    return this.searchList.map((item, ind) => {
      const data = highLightContent(this.highlightedValue, item.items, ['name']);
      return (
        <div>
          <span class='new-home-select-item-title'>
            {item.name}（{item.items.length}）
          </span>
          {data.map((child, key) => this.renderGroupItem(child, item.type, ind, key))}
        </div>
      );
    });
  }

  /** 清空输入 */
  clearInput(e: MouseEvent) {
    e.stopPropagation();
    this.searchValue = '';
    this.searchList = [];
    this.isInput = false;
    this.highlightedIndex = [-1, -1];
    this.highlightedItem = null;
  }
  /** 溢出动态展示输入框高度 */
  autoResize(event) {
    this.isInput = !!event?.target?.value;
    this.highlightedValue = event?.target?.value;
    this.textareaInputRef.style.height = 'auto';
    this.textareaInputRef.style.height = `${this.textareaInputRef.scrollHeight}px`;
  }
  /** 清空历史 */
  clearHistory() {
    localStorage.setItem(storageKey, JSON.stringify([]));
    this.localHistoryList = [];
  }
  /** 获取选中当前高亮的搜索项 */
  getSearchHightItem(key = 'searchList') {
    if (this[key].length === 0) {
      this.highlightedItem = null;
      return;
    }
    if (key === 'searchList') {
      this.highlightedItem = this[key][this.highlightedIndex[0]].items[this.highlightedIndex[1]];
      this.highlightedItem.type = this[key][this.highlightedIndex[0]].type;
      return;
    }
    this.highlightedItem = this[key][this.highlightedIndex[1]];
  }
  // 键盘上下切换的时候更新选中的内容
  updateSelectedItem() {
    this.getSearchHightItem(this.currentListKey);
    this.searchValue = this.highlightedItem.name;
  }

  /** 键盘向上切换选中设置当前的index */
  setHighlightIndexUp(key = 'searchList') {
    if (this[key].length === 0) {
      return;
    }
    if (key === 'searchList') {
      this.keyWordUpOrDown('up');
      return;
    }
    this.highlightedIndex[1] = (this.highlightedIndex[1] - 1 + this[key].length) % this[key].length;
  }
  /** 键盘上下键操作 */
  keyWordUpOrDown(type: string) {
    const len = this.searchLenArr.length;
    let parentId = this.highlightedIndex[0];
    let ind = this.highlightedIndex[1];
    /** 向上 */
    if (type === 'up') {
      ind -= 1;
      if (ind < 0) {
        parentId -= 1;
        ind = this.searchLenArr[parentId] - 1;
      }
      if (parentId < 0) {
        parentId = len - 1;
        ind = this.searchLenArr[parentId] - 1;
      }
    }
    /** 向下 */
    if (type === 'down') {
      ind += 1;
      if (ind > this.searchLenArr[parentId] - 1) {
        parentId += 1;
        ind = 0;
      }
      if (parentId > len - 1) {
        parentId = 0;
        ind = 0;
      }
    }
    this.highlightedIndex = [parentId, ind];
  }
  /** 键盘向上切换选中设置当前的index */
  setHighlightIndexDown(key = 'searchList') {
    if (this[key].length === 0) {
      return;
    }
    if (key === 'searchList') {
      this.keyWordUpOrDown('down');
      return;
    }
    this.highlightedIndex[1] = (this.highlightedIndex[1] + 1) % this[key].length;
  }
  /** 键盘向上切换选中 */
  handleHighlightUp() {
    this.setHighlightIndexUp(this.currentListKey);
    this.updateSelectedItem();
  }
  /** 键盘向下切换选中 */
  handleHighlightDown() {
    this.setHighlightIndexDown(this.currentListKey);
    this.updateSelectedItem();
  }

  /** 键盘操作 */
  handleKeydown(event) {
    switch (event.key) {
      case 'ArrowUp':
        this.handleHighlightUp();
        break;
      case 'ArrowDown':
        this.handleHighlightDown();
        break;
      /** 回车跳转 */
      case 'Enter':
        event.preventDefault();
        /** 如果是搜索结果还需要存入到历史搜索中 */
        if (this.isSearchResult) {
          this.highlightedItem && this.setLocalHistory(this.highlightedItem, this.highlightedItem.type);
        }
        this.highlightedItem && this.handleSearchJumpPage(this.highlightedItem, this.highlightedItem.type);
        break;
      default:
        const keyword = [' ', 'Backspace'];
        const combinedRegex = /^[0-9a-zA-Z]$/;
        /** 只有在输入数字/字母，空格、删除键的时候才调搜索接口 */
        if (combinedRegex.test(event.key) || keyword.includes(event.key)) {
          this.isInput = true;
          setTimeout(() => {
            this.searchValue && this.getSearchList();
          }, 5);
        }
        return;
    }
  }
  /** 跳转到具体的页面 */
  handleSearchJumpPage(item: ISearchItem, type: string) {
    let baseUrl = `${location.origin}/?bizId=${item.bk_biz_id}#/`;
    let url = '';

    switch (type) {
      /** 告警 */
      case 'alert':
        baseUrl = `${location.origin}/?bizId=${item.bk_biz_id}&specEvent=1#/`;
        url = `event-center?alertId=${item.alert_id}`;
        break;
      /** 告警策略 */
      case 'strategy':
        const filter = encodeURIComponent(JSON.stringify([{ key: 'strategy_id', value: [item.strategy_id] }]));
        url = `strategy-config?filters=${filter}`;
        break;
      /** Trace */
      case 'trace':
        url = `trace/home?app_name=${item.app_name}&search_type=accurate&search_id=traceID&trace_id=${item.trace_id}`;
        break;
      /** APM应用 */
      case 'apm_application':
        url = `apm/home?app_name=${encodeURIComponent(item.app_name)}`;
        break;
      /** 主机 */
      case 'host':
        url = `performance/detail/${item.bk_host_id}`;
        break;
      /** 关联的告警 */
      case 'strategy-alarm':
        url = `event-center?queryString=${encodeURIComponent(`策略ID : ${item.strategy_id}`)}`;
        break;
      /** 关联的屏蔽配置 */
      case 'alarm-shield':
        const query = JSON.stringify([{ key: 'strategy_id', value: [item.strategy_id] }]);
        url = `alarm-shield?queryString=${encodeURIComponent(query)}`;
        break;
      default:
        console.warn(`Unknown type: ${type}`);
        return;
    }
    window.open(`${baseUrl}${url}`, '_self');
  }
  /** 渲染历史搜索View */
  renderHistoryView() {
    if (this.localHistoryList.length > 0) {
      return (
        <div class='new-home-select-popover-content'>
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
          <div class='item-list is-history'>{this.renderHistoryList()}</div>
        </div>
      );
    }
    return (
      <bk-exception
        class='select-empty'
        scene='part'
        type='search-empty'
      >
        <span>{this.$t('请输入关键词进行搜索')}</span>
      </bk-exception>
    );
  }
  /** 渲染搜索结果View */
  renderSearchView() {
    if (!this.isLoading && this.searchList.length === 0) {
      return (
        <bk-exception
          class='select-empty'
          scene='part'
          type='search-empty'
        >
          <span>
            {this.$t('当前输入条件无匹配结果，请清空后重新输入')}
            <label
              class='clear-btn'
              on-click={e => this.clearInput(e)}
            >
              {this.$t('清空搜索')}
            </label>
          </span>
        </bk-exception>
      );
    }
    return (
      <div class='new-home-select-popover-content'>
        <div class='item-list'>
          {this.renderGroupList()}
          {this.isLoading && (
            <div class='loading-view mt30'>
              <i class='icon-monitor icon-loading1'></i>
              {this.$t('当前正在加载 采集任务')}
            </div>
          )}
          {this.renderRouteAndWord()}
        </div>
      </div>
    );
  }

  render() {
    return (
      <div class='new-home-select'>
        <div
          ref='select'
          class='new-home-select-input'
        >
          <span class='new-home-select-icon'></span>
          <textarea
            ref='textareaInput'
            class='home-select-input'
            v-model={this.searchValue}
            placeholder={this.$t('请输入 IP / traceId / 容器集群 / 告警ID / 策略名 进行搜索')}
            rows={1}
            clearable
            onFocus={this.handleMousedown}
            onInput={this.autoResize}
            onKeydown={this.handleKeydown}
          ></textarea>
          {this.searchValue && (
            <span
              class='icon-monitor clear-btn icon-mc-close-fill'
              onClick={e => this.clearInput(e)}
            ></span>
          )}
        </div>
        {this.showPopover && (
          <div
            ref='wrap'
            class='new-home-select-popover'
          >
            {this.isSearchResult ? this.renderSearchView() : this.renderHistoryView()}
          </div>
        )}
      </div>
    );
  }
}
