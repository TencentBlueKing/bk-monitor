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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CancelToken } from '../../monitor-api/index';
import { globalSearch } from '../../monitor-api/modules/search';

import './global-search-modal-new.scss';

interface IGlobalSearchModalProps {
  show: boolean;
}

interface IGlobalSearchModalEvent {
  onChange: (v: boolean, searchKey: string) => void;
}

const LIMIT_RECORD_COUNT = 8; // 搜索历史保存最新的前 X 条
const MODAF_CONTAINER_WIDTH = 720;

@Component
export default class GlobalSearchModal extends tsc<IGlobalSearchModalProps, IGlobalSearchModalEvent> {
  @Prop({ type: Boolean, default: true }) show: boolean;
  @Ref('input') inputRef: HTMLInputElement;

  searchVal = '';
  businessScope = ''; // 搜索空间范围
  curSearchSceneName = ''; // 当前搜索的场景
  curSelectScene = ''; // 当前搜索结果分类
  resizeObserver = null;
  dropdownShow = false;
  showDefaultResult = true; // 未搜索 默认展示导航
  isLoading = false; // 当前是否在搜索
  isSearchedQuery = true; // 当前输入关键字是否已经搜索过
  isPollRequest = true; // 允许本次搜索按场景顺序请求 为false则说明按场景搜索被中断
  isAllScene = true; // 全部场景是否勾选
  activeRange = 'BIZ'; // 当前搜索范围
  searchHistoryList = []; // 搜索历史列表
  selectSceneList = []; // 选中的搜索场景
  sceneViewList = [
    // 支持搜索的场景视图
    { id: 'nav', name: this.$t('导航') },
    { id: 'biz', name: this.$t('空间列表') },
    { id: 'host', name: this.$t('route-主机监控') },
    { id: 'kubernetes', name: 'Kubernetes' },
    { id: 'alert', name: this.$t('route-告警事件') },
    { id: 'action', name: this.$t('route-处理记录') },
    { id: 'strategy', name: this.$t('route-告警策略') },
    { id: 'uptimecheck', name: this.$t('route-综合拨测') },
    { id: 'dashboard', name: this.$t('route-仪表盘') },
    { id: 'apm', name: 'APM' }
  ];
  defaultNavList = [
    // 默认展示的导航列表
    { id: 'uptime-check', name: this.$t('route-综合拨测'), icon: 'icon-menu-uptime' },
    { id: 'k8s', name: 'Kubernetes', icon: 'icon-mc-mainboard' },
    { id: 'performance', name: this.$t('route-主机监控'), icon: 'icon-menu-performance' },
    { id: 'custom-scenes', name: this.$t('route-自定义场景'), icon: 'icon-mc-custom-scene' },
    { id: 'strategy-config', name: this.$t('route-告警策略'), icon: 'icon-mc-strategy' },
    { id: 'alarm-shield', name: this.$t('route-告警屏蔽'), icon: 'icon-menu-shield' },
    { id: 'alarm-group', name: this.$t('route-告警组'), icon: 'icon-menu-group' },
    { id: 'set-meal', name: this.$t('route-处理套餐'), icon: 'icon-chulitaocan' },
    { id: 'plugin-manager', name: this.$t('route-指标插件'), icon: 'icon-menu-plugin' },
    { id: 'export-import', name: this.$t('route-导入导出'), icon: 'icon-menu-export' },
    { id: 'collect-config', name: this.$t('route-数据采集'), icon: 'icon-menu-collect' },
    { id: 'custom-metric', name: this.$t('route-自定义指标'), icon: 'icon-menu-custom' },
    { id: 'custom-event', name: this.$t('route-自定义事件'), icon: 'icon-mc-custom-event' },
    { id: 'fta-integrated', name: this.$t('route-告警源'), icon: 'icon-menu-aler-source' },
    { id: 'apm-home', name: this.$t('route-应用监控'), icon: 'icon-mc-menu-apm' }
  ];
  searchResultList = [];
  modalPosition = {
    top: 0,
    left: 0
  };
  /** 搜索取消请求方法 */
  searchCancelFn = () => {};

  handleShowChange(v) {
    this.$emit('change', v, this.searchVal);
  }

  @Watch('show', { immediate: true })
  handleShow(v) {
    this.searchCancelFn();
    this.isPollRequest = v;
    this.isLoading = false;
    if (v) {
      this.$nextTick(() => document.addEventListener('click', this.handleClickOutSide, true));
    }
  }

  mounted() {
    if (localStorage.getItem('globalSearchHistory')) {
      this.searchHistoryList = JSON.parse(localStorage.getItem('globalSearchHistory'));
    }
    this.resizeObsever();
  }

  beforeDestroy() {
    this.resizeObserver.unobserve(document.body);
  }

  get bizId() {
    return this.$store.getters.bizId;
  }

  get curSpaceItem() {
    return this.$store.getters.bizList.find(set => +set.id === +this.bizId) || { text: '' };
  }
  get searchRangeMenu() {
    return [
      // 搜索范围列表
      { id: 'BIZ', name: `${this.$t('本空间')} (${this.curSpaceItem.type_name})` },
      { id: 'GLOBAL', name: this.$t('全部') }
    ];
  }
  /**
   * @desc 搜索范围
   */
  get activeRangeName() {
    return this.filterSearch(this.searchRangeMenu, this.activeRange, 'name');
  }

  get modalStyle() {
    const { top, left } = this.modalPosition;
    return {
      top: `${top}px`,
      left: `${left}px`
    };
  }

  /** 当前需要请求的搜索场景 其中【导航】分类是本地搜索*/
  get curRequestScenes() {
    // 除【导航】分类
    const list = this.sceneViewList.filter(scene => scene.id !== 'nav');
    return this.isAllScene ? list : list.filter(val => this.selectSceneList.includes(val.id));
  }

  activated() {
    this.inputRef.focus();
  }

  /** 监听页面大小变化 定位 Modal */
  resizeObsever() {
    this.resizeObserver = new ResizeObserver(() => {
      const navSearchElem = document.querySelector('.search-bar');
      const rect = navSearchElem?.getBoundingClientRect();
      const { x, y, width } = rect;
      const left = x + width - MODAF_CONTAINER_WIDTH;
      this.modalPosition.top = y;
      this.modalPosition.left = left < 0 ? 0 : left;
    });
    this.resizeObserver.observe(document.body);
  }

  /**
   * @desc 场景名称
   * @param { number } sceneId
   */
  getSceneName(sceneId) {
    if (sceneId === 'nav') {
      return this.$t('导航');
    }
    return this.filterSearch(this.sceneViewList, sceneId, 'name');
  }

  /**
   * @desc 数组搜索匹配项返回指定属性
   * @param { Array } arr 遍历的数组
   * @param { string } key 匹配关键字
   * @returns { string } 返回的属性值
   */
  filterSearch(arr, key, name) {
    const matchItem = arr.find(option => option.id === key);
    return matchItem ? matchItem[name] : '';
  }

  /**
   * @desc 改变搜索范围
   * @param { string } range
   */
  handleChangeSearchRange(range) {
    this.activeRange = range;
    if (this.searchVal?.trim?.().replace(/\t/g, '').length) this.handleSearch();
  }

  /** 当前如果是已全选 无法取消全选 */
  handleBeforeChangeSceneAll() {
    return !this.isAllScene;
  }

  /** 选择全部搜索场景 */
  handleChangeSceneAll(val: boolean) {
    if (val) this.selectSceneList = [];
    this.handleSearch();
  }

  /** 选择搜索的场景 */
  handleChangeSceneItem(val: string[]) {
    if (val.length === this.sceneViewList.length || !val.length) {
      this.isAllScene = true;
      this.selectSceneList = [];
    } else {
      this.isAllScene = false;
    }
    this.handleSearch();
  }

  /**
   * @desc 匹配颜色高亮
   * @param { Boolean } name
   */
  keywordscolorful(str, key, color) {
    // 将关键字中的特殊字符先转义
    const regKey = key.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
    const reg = new RegExp(`(${regKey})`, 'gi');
    if (str === key) {
      return `<span style='color:${color};'>${str}</span>`;
    }

    return str.replace(reg, `<span style='color:${color};'>${str.match(reg) ? str.match(reg)[0] : ''}</span>`);
  }

  /**
   * @desc 删除历史搜索
   */
  handleDeleteHistory() {
    this.searchHistoryList = [];
    localStorage.setItem('globalSearchHistory', JSON.stringify([]));
  }

  /**
   * @desc 改变搜索范围
   */
  getResultItemText(item) {
    let innerHtml = '';
    const titleStr = item.title;
    if (item.is_collected) {
      // 汇聚结果 匹配数字高亮
      const count = titleStr.replace(/[^0-9]/gi, '');
      innerHtml = this.keywordscolorful(item.title, count, '#EA3636');
    } else {
      // 单条结果 匹配搜索值高亮
      innerHtml = this.keywordscolorful(item.title, this.searchVal, '#3a84ff');
    }

    return (
      <span
        class='result-text'
        title={item.title}
        domPropsInnerHTML={innerHtml}
      ></span>
    );
  }

  /**
   * @desc 保存为历史搜索
   * @param { string } val
   */
  setSearchHistory(val) {
    const index = this.searchHistoryList.indexOf(val);
    if (index > -1) {
      // 去重
      this.searchHistoryList.unshift(this.searchHistoryList.splice(index, 1)[0]);
    } else {
      this.searchHistoryList.unshift(val);
    }
    if (this.searchHistoryList.length > LIMIT_RECORD_COUNT) {
      this.searchHistoryList.pop();
    }
    localStorage.setItem('globalSearchHistory', JSON.stringify(this.searchHistoryList));
  }

  /**
   * @desc 默认导航跳转
   * @param { Object } nav 跳转的导航
   */
  handleDefaultNavView(nav) {
    this.$router.push({ name: nav.id });
    this.handleShowChange(false);
  }

  /**
   * @desc 历史搜索
   * @param { String } str 搜索关键字
   */
  handleRecoedSearch(str) {
    this.searchVal = str;
    this.handleSearch();
  }

  /**
   * @desc 默认导航搜索
   * @param { String } queryStr 搜索关键字
   */
  queryNavMenu(queryStr) {
    const result = this.defaultNavList.filter(item => String(item.name).toUpperCase().includes(queryStr.toUpperCase()));
    if (result.length) {
      const resArr = result.map(item => ({
        bk_biz_id: '',
        bk_biz_name: '',
        is_allowed: true,
        title: item.name,
        view: item.id,
        view_args: {},
        is_collected: false
      }));
      this.searchResultList.push({
        scene: 'nav',
        results: resArr
      });
    }
  }

  /**
   * @desc enter确认搜索
   */
  async handleSearch() {
    if (this.searchVal?.trim?.().replace(/\t/g, '').length < 1) {
      this.showDefaultResult = true;
      return;
    }

    const queryStr = this.searchVal.trim?.().replace(/\t/g, '');
    this.showDefaultResult = false;
    this.isSearchedQuery = true;
    this.curSelectScene = '';
    this.searchCancelFn();
    if (this.isLoading) {
      this.isPollRequest = false;
    }
    this.setSearchHistory(queryStr);
    this.searchResultList.splice(0, this.searchResultList.length);

    // 导航搜索
    if (this.selectSceneList.includes('nav') || this.isAllScene) {
      this.queryNavMenu(queryStr);
    }
    this.loopRequest(queryStr);

    setTimeout(() => {
      if (!this.isPollRequest && this.show) {
        this.isPollRequest = true;
        this.loopRequest(queryStr);
      }
    }, 100);
  }

  /**
   * @desc 循环请求
   * @param { string } queryStr 搜索关键字
   */
  async loopRequest(queryStr) {
    for (const [index, item] of this.curRequestScenes.entries()) {
      if (!this.isPollRequest) break;
      await this.requestSceneView(item, queryStr, index);
    }
  }

  /**
   * @desc 搜索场景
   * @param { string } scene 场景
   * @param { string } str 搜索关键字
   * @param { number } index 请求顺序索引
   */
  async requestSceneView(scene, str, index) {
    try {
      this.isLoading = true;
      this.curSearchSceneName = scene.name;
      const params = {
        bk_biz_id: this.bizId,
        scope: this.activeRange,
        scene: scene.id,
        query: str
      };
      await globalSearch(params, {
        cancelToken: new CancelToken(c => (this.searchCancelFn = c))
      }).then(res => {
        this.searchResultList.push(...res);
      });
    } catch (err) {
      console.warn(err);
    } finally {
      // 所有场景已请求 关闭loading
      this.isLoading = index < this.curRequestScenes.length - 1;
    }
  }

  /** 选中结果分类 */
  handleSelectCategory(scene: string) {
    this.curSelectScene = scene;
    document.getElementById(`${scene}__key__`)?.scrollIntoView?.();
  }

  /**
   * @desc 跳转对应视图页面
   */
  handleViewToScene(data, scene) {
    // bk_biz_id=0(搜索结果过多提示优化查询条件)
    if (!data?.view) return;

    const { view, view_args: viewArgs } = data;
    const params =
      viewArgs.params &&
      Object.keys(viewArgs.params).reduce((result, key) => {
        // eslint-disable-next-line no-param-reassign
        result[key] = String(viewArgs.params[key]);
        return result;
      }, {});
    if (scene === 'host' && data.temp_share_url) {
      window.open(data.temp_share_url, '_blank');
      return;
    }
    if (scene === 'apm') {
      // APM是微前端嵌套模块需特殊处理
      const routerNamePath = view.replace('-', '/', 'gm');
      let queryStr =
        viewArgs.query &&
        Object.keys(viewArgs.query).reduce((result, key) => {
          // eslint-disable-next-line no-param-reassign
          result += `${key}=${String(viewArgs.query[key])}&`;
          return result;
        }, '');
      queryStr = queryStr.substring(0, queryStr.length - 1);
      const newHref = `${location.origin}${location.pathname}?bizId=${data.bk_biz_id}#/${routerNamePath}?${queryStr}`;
      location.href = newHref;
    } else if (this.activeRange === 'GLOBAL' || data.bk_biz_id !== this.bizId) {
      // 夸平台需要切换业务
      const targetRoute = this.$router.resolve({
        name: view,
        params,
        query: viewArgs.query
      });
      location.href = `${location.origin}${location.pathname}?bizId=${data.bk_biz_id}${targetRoute.href}`;
    } else {
      this.$router.push({
        name: view,
        params,
        query: viewArgs.query
      });
      if (this.$route.name === view) location.reload();
    }
    this.handleShowChange(false);
  }

  /**
   * @description: 处理自动收起
   * @param {*} evt
   */
  handleClickOutSide(evt: Event) {
    const targetEl = evt.target as HTMLBaseElement;
    if (this.$el.contains(targetEl)) return;
    this.handleShowChange(false);
  }

  render() {
    return (
      <div
        class='global-search-modal'
        style={this.modalStyle}
      >
        <div class='global-search-wrap'>
          <div class='search-input'>
            <bk-input
              ref='input'
              v-model={this.searchVal}
              placeholder={this.$t('请输入关键词搜索')}
              clearable={!this.isLoading}
              right-icon={`${!this.isLoading ? 'bk-icon icon-search' : ''}`}
              on-change={() => {
                this.isSearchedQuery = false;
              }}
              on-enter={() => this.handleSearch()}
              on-clear={() => this.handleSearch()}
            ></bk-input>
            {this.isLoading && (
              <bk-spin
                size='mini'
                theme='info'
              />
            )}
          </div>
        </div>
        <div class='search-result-content'>
          <div class='result-content'>
            {/* 历史搜索 */}
            {this.showDefaultResult && this.searchHistoryList.length ? (
              <div class='search-history'>
                <div class='title'>
                  <span class='text'>{this.$t('历史搜索')}</span>
                  <span
                    class='bk-icon icon-delete'
                    onClick={() => this.handleDeleteHistory()}
                  ></span>
                </div>
                <div class='history-list'>
                  {this.searchHistoryList.map(item => (
                    <span
                      class='search-tag'
                      title={item}
                      onClick={() => {
                        this.handleRecoedSearch(item);
                      }}
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              ''
            )}
            {/* 无搜索历史默认提示 */}
            {this.showDefaultResult && !this.searchHistoryList.length ? (
              <div class='search-default-empty'>
                <div class='search-empty'>
                  <bk-exception
                    class='search-empty-item'
                    type='search-empty'
                    scene='part'
                  >
                    <div class='empty-text'>{this.$t('输入关键词进行搜索')}</div>
                  </bk-exception>
                </div>
              </div>
            ) : (
              ''
            )}
            {/* 搜索结果列表 */}
            {!this.showDefaultResult && this.searchResultList.length ? (
              <div class='search-result-main'>
                {/* 超过一项分类出现分类tag 用于快速定位 */}
                {this.searchResultList.length > 1 && (
                  <div class='scene-bar'>
                    {this.searchResultList.map(item => (
                      <div
                        class={['scene-tag', { active: item.scene === this.curSelectScene }]}
                        onClick={() => this.handleSelectCategory(item.scene)}
                      >
                        <span>{this.getSceneName(item.scene)}</span>
                        <span>({item.results.length})</span>
                      </div>
                    ))}
                  </div>
                )}
                <div
                  class='scene-result-list'
                  style={`height:${this.searchResultList.length > 1 ? 'calc(100% - 43px)' : '100%'}`}
                >
                  {this.searchResultList.map(list => (
                    <div
                      id={`${list.scene}__key__`}
                      class='main-content'
                    >
                      <div class='title'>
                        <span class='text'>{this.getSceneName(list.scene)}</span>
                        <span class='count'>({list.results.length})</span>
                      </div>
                      <div class='list-item'>
                        {list.results.map(val => (
                          <div
                            class={['val-item', { 'not-allow': !val.is_allowed }]}
                            onClick={() => this.handleViewToScene(val, list.scene)}
                          >
                            {!val.is_allowed && <span class='bk-icon icon-lock-shape'></span>}
                            {this.getResultItemText(val)}
                            {val.bk_biz_id && (
                              <span class='biz-name'>{`${this.$t('业务:')}[${val.bk_biz_id}]${val.bk_biz_name}`}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              ''
            )}
            {/* 搜索Loading */}
            {this.isLoading && (
              <div class='loading-bar'>
                <div class='bar-content'>
                  <span class='loading-text-default'>
                    <bk-spin
                      theme='info'
                      size='mini'
                    ></bk-spin>
                    {`${this.$t('加载中...')}`}
                  </span>
                  <span class='laoding-text-module'>{this.curSearchSceneName}</span>
                </div>
              </div>
            )}
            {/* 搜素结果为空 */}
            {!this.showDefaultResult && !this.searchResultList.length && !this.isLoading && (
              <div class='search-empty'>
                <bk-exception
                  class='search-empty-item'
                  type='search-empty'
                  scene='part'
                >
                  <div class='empty-text'>
                    {this.activeRange === 'BIZ' ? this.$t('当前空间下无结果，尝试') : this.$t('全站搜索无结果')}
                  </div>
                  {this.activeRange === 'BIZ' && (
                    <div
                      class='empty-btn'
                      onClick={() => this.handleChangeSearchRange('GLOBAL')}
                    >
                      {this.$t('全站搜索')}
                    </div>
                  )}
                </bk-exception>
              </div>
            )}
          </div>
          <div class='search-nav'>
            {/* 空间范围 */}
            <div class='search-range'>
              <div class='title'>
                <span class='text'>{this.$t('空间范围')}</span>
              </div>
              <bk-radio-group
                class='range-radio'
                v-model={this.activeRange}
                onChange={this.handleChangeSearchRange}
              >
                {this.searchRangeMenu.map(item => (
                  <bk-radio
                    key={item.id}
                    value={item.id}
                    class={`${item.id === 'BIZ' ? 'biz-radio' : ''}`}
                  >
                    {item.id === 'BIZ' ? (
                      <div class='range-biz'>
                        <div
                          class='range-biz-item'
                          v-bk-overflow-tips
                        >
                          {item.name}
                        </div>
                        <div
                          class='range-biz-item'
                          style='color: #ddd'
                          v-bk-overflow-tips
                        >
                          {this.curSpaceItem.text}(
                          {this.curSpaceItem.space_type_id === 'bkcc'
                            ? `#${this.curSpaceItem.bk_biz_id}`
                            : this.curSpaceItem.space_id}
                          )
                        </div>
                      </div>
                    ) : (
                      item.name
                    )}
                  </bk-radio>
                ))}
              </bk-radio-group>
            </div>
            {/* 内容范围 */}
            <div class='search-scene'>
              <div class='title'>
                <span class='text'>{this.$t('内容范围')}</span>
              </div>
              <bk-checkbox
                class='scene-item all-scene'
                v-model={this.isAllScene}
                before-change={this.handleBeforeChangeSceneAll}
                onChange={this.handleChangeSceneAll}
              >
                {this.$t('全部')}
              </bk-checkbox>
              <bk-checkbox-group
                class='scene-list'
                v-model={this.selectSceneList}
                onChange={this.handleChangeSceneItem}
              >
                {this.sceneViewList.map(scene => (
                  <bk-checkbox
                    key={scene.id}
                    value={scene.id}
                    class='scene-item'
                  >
                    {scene.name}
                  </bk-checkbox>
                ))}
              </bk-checkbox-group>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
