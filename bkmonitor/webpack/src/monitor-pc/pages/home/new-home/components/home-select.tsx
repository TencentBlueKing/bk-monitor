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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import debounceDecorator from 'monitor-common/utils/debounce-decorator';
import bus from 'monitor-common/utils/event-bus';
import { getCmdShortcutKey } from 'monitor-common/utils/navigator';
import { random } from 'monitor-common/utils/utils';
import { SPACE_TYPE_MAP } from 'monitor-pc/common/constant';

import { COMMON_ROUTE_LIST } from '../../../../router/router-config';
import reportLogStore from '../../../../store/modules/report-log';
import { ESearchPopoverType, ESearchType, flattenRoute, highLightContent } from '../utils';

import type { IDataItem, IRouteItem, ISearchItem, ISearchListItem } from '../type';

import './home-select.scss';

interface IHomeSelectEvent {
  onChange: (v: boolean, searchKey: string) => void;
}

interface IHomeSelectProps {
  isBarToolShow?: boolean;
  show?: boolean;
}
const storageKey = 'bk_monitor_new_home_history';
/** 输入框展示的最小列数 */
const MIN_ROW = 1;
/** 输入框展示的最大列数 */
const MAX_ROW = 8;

@Component({
  name: 'HomeSelect',
})
export default class HomeSelect extends tsc<IHomeSelectProps, IHomeSelectEvent> {
  /** 是否为展示在顶部导航栏的状态 */
  @Prop({ default: false, type: Boolean }) isBarToolShow: boolean;
  /** 是否需要展示，配合着外部组件的交互 */
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Ref('select') selectRef: HTMLDivElement;
  @Ref('textareaInput') textareaInputRef: HTMLDivElement;
  searchValue = '';
  searchType = '';
  showPopover = false;
  routeList: IRouteItem[] = [];
  /** 策略/集群可跳转列表 */
  operatorList = {
    strategy: [
      { name: this.$t('关联的告警'), key: 'strategy-alarm' },
      { name: this.$t('关联的屏蔽配置'), key: 'alarm-shield' },
    ],
    bcs_cluster: [{ name: this.$t('集群管理'), key: 'bsc-detail' }],
    host: [{ name: this.$t('主机管理'), key: 'host-detail' }],
  };
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
  textareaRow = MIN_ROW;
  showKeywordEle = false;

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
    return this.isBarToolShow ? 720 : this.windowWidth < 2560 ? 920 : 1080;
  }
  /** 获取业务类型列表 */
  get spaceTypeIdList() {
    const spaceTypeMap: Record<string, any> = {};
    for (const item of this.$store.getters.bizList) {
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    }
    return Object.keys(spaceTypeMap).map(key => ({
      id: key,
      name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
      styles: SPACE_TYPE_MAP[key]?.light || {},
      list: this.$store.getters.bizList.filter(item => item.space_type_id === key).map(item => item.bk_biz_id),
    }));
  }

  mounted() {
    this.autoResize();
    this.updateWidth();
    this.routeList = flattenRoute(COMMON_ROUTE_LIST).filter(item => item.icon);
    document.addEventListener('click', this.handleClickOutside);
    window.addEventListener('blur', this.handleHiddenPopover);
    window.addEventListener('resize', this.updateWidth);
    bus.$on('handle-keyup-nav', this.handleKeyupNav);
  }
  beforeDestroy() {
    document.removeEventListener('click', this.handleClickOutside);
    window.removeEventListener('resize', this.updateWidth);
    window.removeEventListener('blur', this.handleHiddenPopover);
    bus.$off('handle-keyup-nav', this.handleKeyupNav);
  }
  /** 按下'/'，搜索框自动聚焦 */
  handleKeyupNav(e: KeyboardEvent) {
    e.preventDefault();
    this.showKeywordEle = false;
    this.showPopover = true;
    this.handleInputFocus();
  }
  /** 隐藏/展示发生变化的时候的changeHandle */
  handleShowChange(v) {
    this.$emit('change', v, this.searchValue);
  }
  /** 窗口变化时更新宽度值 */
  updateWidth() {
    this.windowWidth = window.innerWidth;
  }
  /** 点击收起下拉框 */
  handleClickOutside(event: Event) {
    if (this.showPopover && this.selectRef && !this.selectRef.contains(event.target)) {
      this.showPopover = false;
      this.textareaRow = MIN_ROW;
      this.handleShowChange(false);
    }
    this.showKeywordEle = !this.showPopover && !this.searchValue;
  }
  handleHiddenPopover() {
    this.handleShowChange(false);
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
      const traceparent = `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`;
      const response = await fetch(url, {
        method: 'GET',
        signal,
        headers: {
          traceparent,
        },
      });
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
    this.fetchEventStream(`${location.origin}/rest/v2/overview/search/?query=${encodeURIComponent(this.searchValue)}`);
  }
  /* 显示弹出层 */
  handleMousedown() {
    if (this.textareaInputRef.autofocus) {
      // 初始化自动聚焦时，不打开搜索历史
      this.textareaInputRef.attributes.removeNamedItem('autofocus');
    } else {
      this.showPopover = true;
    }
    this.textareaRow = this.limitRows();
    this.localHistoryList = JSON.parse(localStorage.getItem(storageKey))?.slice(0, 10) || [];
  }
  /** 关联的屏蔽策略/关联的告警  */
  handleOperator(e: Event, item: ISearchItem, key: string, parentIndex: number) {
    e.stopPropagation();
    this.handleSearchJumpPage(item, key, parentIndex);
  }

  /**
   * 渲染查询结果Item
   * @param item - 当前渲染的查询结果Item。
   * @param type - 当前渲染的查询结果Item的类型，类型包含可见 ESearchType
   * @param parentInd - 当前渲染的查询结果Item的父级下标。
   * @param ind - 当前渲染的查询结果Item的下标。
   */
  renderGroupItem(item: ISearchItem, type: string, parentInd: number, ind: number) {
    const hasOperatorKeys = [ESearchType.strategy, ESearchType.bcs_cluster, ESearchType.host];
    const isHost = type === ESearchType.host;
    const isBcsCluster = type === ESearchType.bcs_cluster;
    return (
      <div
        class={[
          'new-home-select-group-item',
          {
            active: this.highlightedIndex[0] === parentInd && this.highlightedIndex[1] === ind,
          },
        ]}
        onClick={() => this.handleItemClick(item, type, parentInd)}
      >
        {isHost && <span class='ip-tag'>{item.bk_cloud_id}:</span>}
        <span class='item-label'>
          <span domPropsInnerHTML={item.nameSearch} />
          {isHost && <span class='ip-sub'>（{item.bk_host_name}）</span>}
          {isBcsCluster && <span class='ip-sub'>（{item.bcs_cluster_id}）</span>}
          {isHost && item.compare_hosts.length > 0 && (
            <span class='host-compare'>
              <span class='host-compare-num'>
                +<b>{item.compare_hosts.length}</b> {this.$t('台')}
              </span>
              {this.$t('主机对比')}
            </span>
          )}
        </span>
        {(item.compare_hosts || []).length === 0 && hasOperatorKeys.includes(type) && (
          <span class='item-operator'>
            {this.operatorList[type].map(operator => (
              <span
                key={operator.key}
                class='item-operator-item'
                onClick={e => this.handleOperator(e, item, operator.key, parentInd)}
              >
                {operator.name}
              </span>
            ))}
          </span>
        )}
        <span class='item-business'>{item.bk_biz_name}</span>
        {this.spaceTypeIdList.length > 0 &&
          this.spaceTypeIdList?.map?.(
            tag =>
              tag.list.includes(item.bk_biz_id) && (
                <span
                  key={tag.id}
                  class='list-item-tag'
                >
                  {tag.name}
                </span>
              )
          )}
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
        <i class='icon-monitor icon-History item-icon' />
        <span class='history-item-name'>{item.name}</span>
        <div
          class='icon-delete-wrap'
          onClick={e => this.handleDeleteHistoryItem(e, item)}
        >
          <i class='icon-monitor icon-mc-delete-line' />
        </div>
      </div>
    );
  }
  /** 点击选中历史搜索Item */
  handleClickHistoryItem(e: Event, item: ISearchItem) {
    e.stopPropagation();
    this.isInput = true;
    this.searchValue = item.name;
    this.textareaRow = this.limitRows();
    this.handleGetSearchData();
    this.handleInputFocus();
  }
  /** 删除历史搜索Item */
  handleDeleteHistoryItem(e: Event, item: ISearchItem) {
    e.stopPropagation();
    if (item.name === this.searchValue) {
      this.searchValue = '';
    }
    this.highlightedItem = null;
    this.highlightedIndex = [-1, -1];
    this.localHistoryList = this.localHistoryList.filter(history => history.name !== item.name);
    localStorage.setItem(storageKey, JSON.stringify(this.localHistoryList));
    if (!this.localHistoryList.length) {
      this.isInput = false;
      this.handleInputFocus();
    }
  }
  /** 初始化输入框是否要自动聚焦 */
  handleInputFocus() {
    this.textareaInputRef.focus();
  }
  /** 获取搜索结果 */
  handleGetSearchData() {
    this.isLoading = true;
    this.searchValue && this.getSearchList();
  }
  /** 跳转到具体的功能 */
  handleGoRoute(item: IRouteItem) {
    this.showPopover = false;
    this.searchValue && this.setLocalHistory(this.searchValue);
    window.open(location.href.replace(location.hash, item.href));
    this.handleShowChange(false);
  }
  /** 相关功能Render */
  renderRouterList() {
    /** 根据当前bizId区分是要展示新版的k8s还是旧版的k8s, 当isEnableK8sV2为true时，不展示旧版 */
    const filterKey = this.$store.getters.isEnableK8sV2 ? 'k8s' : 'k8s-new';
    return (
      <div class='secondary-list'>
        <span class='new-home-select-item-title'>
          {this.$t('相关功能')}（{this.searchRouteList.length}）
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
  handleItemClick(item: ISearchItem, type: string, parentIndex: number) {
    this.searchType = type;
    this.showPopover = false;
    this.highlightedItem = item;
    this.handleSearchJumpPage(item, type, parentIndex);
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
            {item.name}（{item.items.length}）
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
    this.textareaRow = this.limitRows();
    this.handleInputFocus();
  }
  /** 重置相关的数据 */
  handleResetData() {
    this.isInput = false;
    this.searchValue = '';
    this.highlightedIndex = [-1, -1];
    this.highlightedItem = null;
  }
  /** 弹性布局适应输入长度变化的实现 --- start */

  /** 溢出动态展示输入框高度 */
  calculateRows() {
    const styles = window.getComputedStyle(this.textareaInputRef);
    const width = Number.parseInt(styles.width, 10);
    const fontSize = Number.parseInt(styles.fontSize, 10);
    // 计算每行能容纳的字符数
    const charsPerLine = Math.floor(width / fontSize);
    // 获取文本内容
    const text = this.searchValue || '';
    if (text.includes('\n')) {
      // 有换行符的情况
      const lines = text.split('\n');
      let totalLines = 0;
      lines.map(line => {
        /** 连续有多个换行符的话，则默认每一个为一行 */
        totalLines += Math.ceil((line.length === 0 ? charsPerLine : line.length) / charsPerLine);
      });
      return totalLines;
    }
    // 无换行符的情况
    return Math.ceil(text.length / charsPerLine);
  }
  /** 根据设置的最大最小值，计算出最终要展示的row值 */
  limitRows() {
    const calculatedRows = this.calculateRows();
    return Math.min(Math.max(calculatedRows, MIN_ROW), MAX_ROW);
  }
  autoResize(event?: Event) {
    !this.isComposing && setTimeout(this.handleGetSearchData, 500);
    this.isInput = !!event?.target?.value;
    this.textareaRow = this.limitRows();
    // 初始化搜索框自动聚焦后，输入搜索内容后打开下拉框
    if (!this.isBarToolShow && !this.showPopover && this.searchValue.trim()) {
      this.showPopover = true;
    }
    // 输入内容后未选择，手动删空了输入内容需要取消history高亮
    if (!this.isInput && this.highlightedItem?.name) {
      this.highlightedIndex = [-1, -1];
      this.highlightedItem = null;
    }
  }
  /** 弹性布局适应输入长度变化的实现 --- end */
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
    event.stopPropagation(); // window会监听'/'按键 自动聚焦输入框
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
  handleSearchJumpPage(item: ISearchItem, type: string, parentIndex: number) {
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
        query: item.compare_hosts?.length > 0 ? { compares: JSON.stringify({ targets: item.compare_hosts }) } : {},
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
      /** 跳转到其他系统的话，则配置isOtherWeb为true */
      /** 集群管理跳转到bcs */
      'bsc-detail': {
        isOtherWeb: true,
        url: `${window.bk_bcs_url}bcs/projects/${item.project_name}/clusters?clusterId=${item.bcs_cluster_id}&active=info`,
      },
      /** 主机管理跳转到cmdb */
      'host-detail': {
        isOtherWeb: true,
        url: `${window.bk_cc_url}#/business/${item.bk_biz_id}/index/host/${item.bk_host_id}`,
      },
    };

    this.handleShowChange(false);
    const option = routeOptions[type];
    const groupName = this.searchList[parentIndex]?.name || this.searchList[this.highlightedIndex[0]]?.name || '其他';
    /** 如果不在指定的url跳转对象里，item中存在url字段的话，则默认使用该字段的url链接打开新页面 */
    if (!option) {
      item.url && window.open(item.url, '_blank');
      reportLogStore.reportHomeSearchLog({
        type: 'others',
        name: groupName,
      });
      return;
    }
    /** 是否调整到其他系统 */
    if (option.isOtherWeb) {
      window.open(option.url, '_blank');
      reportLogStore.reportHomeSearchLog({
        type: 'others',
        name: groupName,
      });
      return;
    }
    reportLogStore.reportHomeSearchLog({
      type,
      name: groupName,
    });
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
  handleClick() {
    // 初始化搜索框自动聚焦后，再次点击了搜索框，打开下拉框
    if (!this.isBarToolShow && !this.showPopover && !this.searchValue.trim()) {
      this.showPopover = true;
    }
  }
  /** 渲染历史搜索View */
  renderHistoryView() {
    if (this.localHistoryList.length > 0) {
      return (
        <div class='new-home-select-popover-content'>
          <div class='item-list-title'>
            <span>
              {this.$t('搜索历史')}（{this.localHistoryList.length}）
            </span>
            <span
              class='item-list-clear'
              onClick={this.clearHistory}
            >
              <i class='icon-monitor icon-a-Clearqingkong history-clear-icon' />
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
            {this.$t('检索结果为空，请重新输入关键词')}
            <label
              class='empty-clear-btn'
              onClick={this.clearInput}
            >
              {this.$t('清空检索')}
            </label>
          </span>
        </bk-exception>
      );
    }
    return (
      <div class='new-home-select-popover-content'>
        <div class='item-list'>
          {this.isLoading ? (
            <div class='skeleton-loading'>
              {Array(6)
                .fill(null)
                .map((_, index) => (
                  <div
                    key={index}
                    class='skeleton-element'
                  />
                ))}
            </div>
          ) : (
            this.renderGroupList()
          )}
          {this.renderRouteAndWord()}
        </div>
      </div>
    );
  }

  render() {
    return (
      <div class={['new-home-select', { 'home-select-bar-tool': this.isBarToolShow }]}>
        <div
          ref='select'
          style={{ width: `${this.computedWidth}px` }}
          class='new-home-select-input'
        >
          {!this.isBarToolShow && <span class='icon-monitor new-home-select-icon icon-mc-search' />}
          <textarea
            ref='textareaInput'
            class={['home-select-input', { 'is-hidden': this.textareaRow === 1 }]}
            v-model={this.searchValue}
            autofocus={!this.isBarToolShow}
            placeholder={this.$tc('请输入 IP / Trace ID / 容器集群 / 告警ID / 策略名 进行搜索')}
            rows={this.textareaRow}
            spellcheck={false}
            onClick={this.handleClick}
            onCompositionend={this.handleCompositionend}
            onCompositionstart={this.handleCompositionstart}
            onFocus={this.handleMousedown}
            onInput={this.autoResize}
            onKeydown={this.handleKeydown}
          />
          {this.isBarToolShow && <span class='bk-icon icon-search' />}
          {this.searchValue && (
            <span
              class='icon-monitor clear-btn icon-mc-close-fill'
              onClick={this.clearInput}
            />
          )}
          {!this.isBarToolShow && this.showKeywordEle && (
            <div class='search-keyboard'>
              {this.$tc('快捷键')} {getCmdShortcutKey()} + /
            </div>
          )}
          {(this.isBarToolShow || this.showPopover) && (
            <div class='new-home-select-popover'>
              {this.isSearchResult ? this.renderSearchView() : this.renderHistoryView()}
            </div>
          )}
        </div>
      </div>
    );
  }
}
