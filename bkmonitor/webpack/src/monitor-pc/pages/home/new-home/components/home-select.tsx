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

import debounceDecorator from 'monitor-common/utils/debounce-decorator';

import { COMMON_ROUTE_LIST } from '../../../../router/router-config';
import { highLightContent, ESearchType, ESearchPopoverType } from '../utils';

import type { ISearchListItem, ISearchItem, IRouteItem, IDataItem } from '../type';

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
  @Ref('textareaInput') textareaInputRef: HTMLDivElement;
  searchValue = '';
  searchType = '';
  showPopover = false;
  routeList: IRouteItem[] = [];
  /** 策略可跳转列表 */
  operatorList = [
    { name: this.$t('关联的告警'), key: 'strategy-alarm' },
    { name: this.$t('关联的屏蔽配置'), key: 'alarm-shield' },
  ];
  isLoading = false;
  /** 高亮选中的index, 第一个表示组的下标，第二个表示items的下标 */
  highlightedIndex: number[] = [-1, -1];
  /** 高亮选中的Item */
  highlightedItem: ISearchItem = {};
  /** 历史搜索数据  */
  localHistoryList: ISearchListItem[] = [];
  /** 接口搜索结果列表 */
  searchList: ISearchListItem[] = [];
  /** 是否为input输入内容 */
  isInput = false;
  isEmpty = false;
  searchLenArr: number[] = [];
  isComposing = false;
  currentAbortController: IDataItem = null;
  /** 窗口宽度 */
  windowWidth = 0;

  /** 处理数据 */
  flattenRoute(tree: IRouteItem[]) {
    const result = [];
    const traverse = node => {
      if (!node) return;
      result.push(node);
      if (node.children && node.children.length > 0) {
        node.children.map(child => traverse(child));
      }
    };
    tree.map(rootNode => traverse(rootNode));
    return result;
  }
  /** 符合搜索内容的路由列表 */
  get searchRouteList() {
    return (this.routeList || []).filter(item => item.name.indexOf(this.searchValue) !== -1);
  }
  /** 是否展示搜索结果 */
  get isSearchResult() {
    return !!this.searchValue && this.isInput;
  }

  get currentListKey() {
    return this.isSearchResult ? ESearchPopoverType.searchList : ESearchPopoverType.localHistoryList;
  }
  get computedWidth() {
    return this.windowWidth < 2560 ? 920 : 1080;
  }

  mounted() {
    this.autoResize();
    this.updateWidth();
    this.routeList = this.flattenRoute(COMMON_ROUTE_LIST).filter(item => item.icon);
    document.addEventListener('click', this.handleClickOutside);
    window.addEventListener('resize', this.updateWidth);
  }
  beforeDestroy() {
    document.removeEventListener('click', this.handleClickOutside);
    window.removeEventListener('resize', this.updateWidth);
  }
  /** 窗口变化时更新宽度值 */
  updateWidth() {
    this.windowWidth = window.innerWidth;
  }
  /** 点击收起下拉框 */
  handleClickOutside(event: Event) {
    if (this.showPopover && this.selectRef && !this.selectRef.contains(event.target)) {
      this.showPopover = false;
    }
  }
  /** 后台eventStream数据处理 Start */
  /** 解析后台返回的eventStream */
  @debounceDecorator(500)
  async fetchEventStream(url: string) {
    // 如果已经存在一个请求，取消请求
    if (this.currentAbortController) {
      this.currentAbortController.abort();
    }
    this.currentAbortController = new AbortController();
    const { signal } = this.currentAbortController;

    this.searchList = [];
    this.highlightedIndex = [-1, -1];
    this.highlightedItem = null;
    this.isLoading = true;
    try {
      const response = await fetch(url, { signal });
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const eventString = buffer.substring(0, boundary);
          buffer = buffer.substring(boundary + 2);
          this.processEvent(eventString);
          boundary = buffer.indexOf('\n\n');
        }
      }
    } catch (error) {
      this.isLoading = false;
      this.searchList = [];
      console.error('Error fetching event stream:', error);
    } finally {
      this.isLoading = false;
    }
  }
  /** 特殊处理alert_id */
  extractAlertId(str: string) {
    const regex = /"alert_id":(.*?),/;
    const match = str.match(regex);
    if (match?.[1]) {
      return match[1].trim();
    }
    return null;
  }
  // 从给定的事件字符串中提取数据，如果事件字符串以"data:"开头，则截取并解析其中的JSON数据，否则返回null
  extractDataFromEventString(eventString: string) {
    if (eventString.startsWith('data:')) {
      const eventData = eventString.slice(5).trim();
      const pattern = /"alert_id":\s*[^,]+,/;
      const outputString = eventData.replace(pattern, `"alert_id": "${this.extractAlertId(eventData)}",`);
      return JSON.parse(outputString);
    }
    return null;
  }

  // 根据传入的已解析数据（parsedData）来更新搜索列表（searchList）
  // 如果已解析数据的类型在搜索列表中已存在，则过滤掉原列表中同类型的数据，然后将新数据加入列表
  // 如果不存在，则直接将新数据添加到搜索列表末尾，并返回更新后的搜索列表
  updateSearchList(searchList: ISearchListItem[], parsedData: ISearchListItem) {
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
      this.searchList = [];
      console.error('Error parsing event string:', error);
    }
  }
  /** 后台eventStream数据处理 End */

  /** 获取搜索结果 */
  getSearchList() {
    this.isLoading = true;
    this.fetchEventStream(`${location.origin}/rest/v2/overview/search/?query=${this.searchValue}`);
  }
  /* 显示弹出层 */
  handleMousedown() {
    this.showPopover = true;
    this.localHistoryList = JSON.parse(localStorage.getItem(storageKey)) || [];
  }
  /** 关联的屏蔽策略/关联的告警  */
  handleOperator(e: Event, item: ISearchItem, key: string) {
    e.stopPropagation();
    this.handleSearchJumpPage(item, key);
  }

  /**
   * 渲染查询结果Item
   * @param item - 当前渲染的查询结果Item。
   * @param type - 当前渲染的查询结果Item的类型，类型包含可见 ESearchType
   * @param parentInd - 当前渲染的查询结果Item的父级下标。
   * @param ind - 当前渲染的查询结果Item的下标。
   */
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
              <span
                key={operator.key}
                class='item-operator-item'
                onClick={e => this.handleOperator(e, item, operator.key)}
              >
                {operator.name}
              </span>
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
        onClick={e => this.handleClickHistoryItem(e, item)}
      >
        <i class='icon-monitor icon-lishijilu item-icon'></i>
        <span class='history-item-name'>{item.name}</span>
      </div>
    );
  }
  /** 点击选中历史搜索Item */
  handleClickHistoryItem(e: Event, item: ISearchItem) {
    e.stopPropagation();
    this.isInput = true;
    this.searchValue = item.name;
    this.handleGetSearchData();
    this.textareaInputRef.focus();
  }
  /** 获取搜索结果 */
  handleGetSearchData() {
    this.searchValue && this.getSearchList();
  }
  /** 跳转到具体的功能 */
  handleGoRoute(item: IRouteItem) {
    this.showPopover = false;
    this.searchValue && this.setLocalHistory(this.searchValue);
    window.open(location.href.replace(location.hash, item.href));
  }
  /** 相关功能Render */
  renderRouterList() {
    /** 根据当前bizId区分是要展示新版的k8s还是旧版的k8s, 当isEnableK8sV2为true时，不展示旧版 */
    const filterKey = this.$store.getters.isEnableK8sV2 ? 'k8s' : 'k8s-new';
    return (
      <div class='secondary-list'>
        <span class='new-home-select-item-title'>
          {this.$t('相关功能')} ( {this.searchRouteList.length} )
        </span>
        <div class='new-home-select-router-list'>
          {(this.searchRouteList || [])
            .filter(item => item.id !== filterKey)
            .map(item => (
              <span
                key={item.id}
                class='new-home-select-router-item'
                onClick={() => this.handleGoRoute(item)}
              >
                <i class={`${item?.icon} router-item-icon`} />
                <span class='item-txt'>{item?.name}</span>
              </span>
            ))}
        </div>
      </div>
    );
  }
  /** 设置历史搜索 */
  setLocalHistory(value: string) {
    try {
      const listStr = localStorage.getItem(storageKey);
      const obj = { name: value };
      const list = listStr ? JSON.parse(listStr) : [];
      const resultList = list.filter(item => item.name !== value);

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
    this.handleSearchJumpPage(item, type);
  }
  /** 渲染历史搜索列表 */
  renderHistoryList() {
    return this.localHistoryList.map((item, ind) => this.renderHistoryItem(item, ind));
  }
  /** 相关功能/文档渲染 */
  renderRouteAndWord() {
    if (this.searchValue && this.searchRouteList.length > 0) {
      return (
        <div>
          <div class='new-home-select-divider' />
          {this.renderRouterList()}
        </div>
      );
    }
  }
  /** 渲染搜索列表 */
  renderGroupList() {
    return this.searchList.map((item, ind) => {
      const data = highLightContent(this.searchValue, item.items, ['name']);
      return (
        <div key={item.name}>
          <span class='new-home-select-item-title'>
            {item.name} ( {item.items.length} )
          </span>
          {data.map((child, key) => this.renderGroupItem(child, item.type, ind, key))}
        </div>
      );
    });
  }

  /** 清空输入 */
  clearInput(e: Event) {
    e.stopPropagation();
    this.searchList = [];
    this.handleResetData();
    this.textareaInputRef.style.height = '52px';
  }
  /** 重置相关的数据 */
  handleResetData() {
    this.isInput = false;
    this.searchValue = '';
    this.highlightedIndex = [-1, -1];
    this.highlightedItem = null;
  }
  /** 溢出动态展示输入框高度 */
  autoResize(event?: Event) {
    !this.isComposing && this.handleGetSearchData();
    this.isInput = !!event?.target?.value;
    this.textareaInputRef.style.height = 'auto';
    this.textareaInputRef.style.height = `${this.textareaInputRef.scrollHeight}px`;
  }
  /** 清空历史 */
  clearHistory() {
    localStorage.setItem(storageKey, JSON.stringify([]));
    this.localHistoryList = [];
    this.handleResetData();
  }
  /** 获取选中当前高亮的搜索项 */
  getSearchHightItem(key: string = ESearchPopoverType.searchList) {
    if (this[key].length === 0) {
      this.highlightedItem = null;
      return;
    }
    if (key === ESearchPopoverType.searchList) {
      this.highlightedItem = this[key][this.highlightedIndex[0]].items[this.highlightedIndex[1]];
      this.highlightedItem.type = this[key][this.highlightedIndex[0]].type;
      return;
    }
    this.highlightedItem = this[key][this.highlightedIndex[1]];
    this.searchValue = this[key][this.highlightedIndex[1]].name;
  }

  /** 键盘向上切换选中设置当前的index */
  setHighlightIndexUp(key: string = ESearchPopoverType.searchList) {
    if (this[key].length === 0) {
      return;
    }
    if (key === ESearchPopoverType.searchList) {
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
  setHighlightIndexDown(key: string = ESearchPopoverType.searchList) {
    if (this[key].length === 0) {
      return;
    }
    if (key === ESearchPopoverType.searchList) {
      this.keyWordUpOrDown('down');
      return;
    }
    this.highlightedIndex[1] = (this.highlightedIndex[1] + 1) % this[key].length;
  }
  /** 键盘向上切换选中 */
  handleHighlightUp() {
    this.setHighlightIndexUp(this.currentListKey);
    this.getSearchHightItem(this.currentListKey);
  }
  /** 键盘向下切换选中 */
  handleHighlightDown() {
    this.setHighlightIndexDown(this.currentListKey);
    this.getSearchHightItem(this.currentListKey);
  }

  /** 键盘操作 */
  handleKeydown(event: KeyboardEvent) {
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
        /** 如果是搜索结果，回车则是跳转 */
        if (this.isSearchResult) {
          this.highlightedItem && this.handleSearchJumpPage(this.highlightedItem, this.highlightedItem.type);
          return;
        }
        this.isInput = true;
        /** 如果是历史搜索页面回车则搜索 */
        this.handleGetSearchData();
        break;
      default:
        return;
    }
  }
  /** 跳转到具体的页面 */
  handleSearchJumpPage(item: ISearchItem, type: string) {
    /** 回车跳转了则存入到历史搜索中 */
    if (this.searchValue) {
      this.setLocalHistory(this.searchValue);
    }
    const baseParams = { bizId: item.bk_biz_id };
    const k8sV2EnableList = this.$store.getters.k8sV2EnableList;
    /** 是否需要跳转到新版的k8s */
    const isNewK8sV2List = k8sV2EnableList.some(id => (id === 0 ? true : +id === +item.bk_biz_id));
    const routeOptions = {
      /** 告警 */
      alert: {
        name: 'event-center',
        query: { alertId: String(item.alert_id) },
        extraParams: { specEvent: 1 },
      },
      /** 告警策略 */
      strategy: {
        name: 'strategy-config',
        query: { filters: JSON.stringify([{ key: 'strategy_id', value: [item.strategy_id] }]) },
      },
      /** Trace */
      trace: {
        name: 'trace-retrieval',
        query: {
          app_name: item.app_name,
          search_type: 'accurate',
          search_id: 'traceID',
          trace_id: item.trace_id,
        },
      },
      /** APM应用 */
      apm_application: {
        name: 'apm-home',
        query: { app_name: item.app_name },
      },
      /** 主机 */
      host: {
        name: 'performance-detail',
        params: { id: item.bk_host_id },
      },
      /** 关联的告警 */
      'strategy-alarm': {
        name: 'event-center',
        query: { queryString: `策略ID : ${item.strategy_id}` },
      },
      /** 关联的屏蔽策略 */
      'alarm-shield': {
        name: 'alarm-shield',
        query: { queryString: JSON.stringify([{ key: 'strategy_id', value: [item.strategy_id] }]) },
      },
      /** bcs */
      bcs_cluster: {
        name: isNewK8sV2List ? 'k8s-new' : 'k8s',
        query: isNewK8sV2List
          ? {
              sceneId: 'kubernetes',
              cluster: item.bcs_cluster_id,
              scene: 'performance',
              activeTab: 'list',
            }
          : {
              'filter-bcs_cluster_id': item.bcs_cluster_id,
              sceneId: 'kubernetes',
              sceneType: 'detail',
              dashboardId: 'cluster',
            },
      },
    };

    const option = routeOptions[type];
    if (!option) return;

    const routeData = this.$router.resolve(option);
    const extraParams = option.extraParams ? `&${new URLSearchParams(option.extraParams).toString()}` : '';
    const baseUrl = `${location.origin}/?${new URLSearchParams(baseParams).toString()}${extraParams}`;
    window.open(`${baseUrl}${routeData.href}`, '_blank');
  }
  handleCompositionend() {
    this.isComposing = false;
  }
  handleCompositionstart() {
    this.isComposing = true;
  }
  handleBlur() {
    this.showPopover = false;
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
              onClick={this.clearHistory}
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
              class='empty-clear-btn'
              onClick={this.clearInput}
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
            <div
              class='loading-view mt30'
              v-bkloading={{ isLoading: this.isLoading, size: 'small' }}
            ></div>
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
          style={{ width: `${this.computedWidth}px` }}
          class='new-home-select-input'
        >
          <span class='new-home-select-icon'></span>
          <textarea
            ref='textareaInput'
            class='home-select-input'
            v-model={this.searchValue}
            placeholder={this.$tc('请输入 IP / Trace ID / 容器集群 / 告警ID / 策略名 进行搜索')}
            rows={1}
            spellcheck={false}
            onCompositionend={this.handleCompositionend}
            onCompositionstart={this.handleCompositionstart}
            onFocus={this.handleMousedown}
            onInput={this.autoResize}
            onKeydown={this.handleKeydown}
          ></textarea>
          {this.searchValue && (
            <span
              class='icon-monitor clear-btn icon-mc-close-fill'
              onClick={this.clearInput}
            />
          )}
          {this.showPopover && (
            <div class='new-home-select-popover'>
              {this.isSearchResult ? this.renderSearchView() : this.renderHistoryView()}
            </div>
          )}
        </div>
      </div>
    );
  }
}
