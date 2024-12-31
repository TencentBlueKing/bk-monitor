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
import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctionShortcut } from 'monitor-api/modules/overview';
import draggable from 'vuedraggable';

import { GLOAB_FEATURE_LIST, type IRouteConfigItem } from '../../../../router/router-config';
import emptyImageSrc from '../../../../static/images/png/empty.png';
import aiWhaleSrc from '../../../../static/images/png/new-page/aiWhale.png';
import dashboardSrc from '../../../../static/images/png/new-page/dashboard.png';
import retrievalSrc from '../../../../static/images/png/new-page/retrieval.png';
import serviceSrc from '../../../../static/images/png/new-page/service.png';
import { EFunctionNameType } from '../utils';
import HeaderSettingModal from './header-setting-modal';

import './my-favorites.scss';
interface RecentItems {
  function: string;
  items: Item[];
  name: string;
  icon?: string;
}

interface Item {
  bk_biz_id: number;
  bk_biz_name: string;
  name?: string;
  url?: string;
}

// const STORE_USER_MENU_KEY = 'USER_STORE_MENU_KEY';
const srcObj = {
  dashboard: dashboardSrc,
  retrieval: retrievalSrc,
  apm_service: serviceSrc,
};

// 模块名称映射
const modeNameMap = {
  仪表盘: 'dashboard',
  检索: 'retrieval',
  服务: 'apm_service',
  服务拨测: '-',
  主机监控: '-',
  容器服务: '-',
};

@Component({
  name: 'MyFavorites',
  components: {
    draggable,
  },
})
export default class MyFavorites extends tsc<object> {
  isRecentView = true; // 状态，用于切换视图
  userStoreRoutes = []; // 用户存储的路由
  selectedCategories = ['dashboard']; // 用户选择的类别
  inputValue = ''; // 输入框的值
  isActive = false; // 输入框状态
  showModal = false; // 控制模态框显示
  localVarList = [
    { name: '仪表盘' },
    { name: '服务' },
    // { name: '检索' },
    // { name: '服务拨测' },
    // { name: '主机监控' },
    // { name: '容器服务' },
  ];

  categoriesHasTwoRows = false; // 是否两行布局

  showPlaceholder = true; // 是否展示AI小鲸 placeHolder

  placeholderText = window.i18n.tc('有问题就问 AI 小鲸'); // AI小鲸 placeHolder内容

  recentItems: RecentItems[] = []; // 最近使用列表
  favoriteItems: RecentItems[] = []; // 收藏列表

  @Watch('selectedCategories')
  handleSelect(v) {
    console.log('v', v);
    this.updateFunctionShortcut();
  }

  // 计算布局策略
  get rowClass() {
    // 三种布局方式
    const strategies = {
      1: 'row-1',
      2: 'row-2',
      4: 'row-2',
      3: 'row-3',
      5: 'row-3',
      6: 'row-3',
    };
    this.categoriesHasTwoRows = this.selectedCategories.length > 3;
    return strategies[this.selectedCategories.length] || '';
  }

  // 获取被选中的变量名
  get selectedNames() {
    return this.localVarList.map(item => modeNameMap[item.name]);
  }

  // 根据当前视图状态获取要显示的项目
  get itemsToDisplay() {
    const items = this.isRecentView ? this.recentItems : this.favoriteItems;
    return items
      .filter(item => this.selectedCategories.includes(item.function))
      .sort((a, b) => {
        const orderA = this.orderMap[a.function] !== undefined ? this.orderMap[a.function] : Number.POSITIVE_INFINITY;
        const orderB = this.orderMap[b.function] !== undefined ? this.orderMap[b.function] : Number.POSITIVE_INFINITY;
        return orderA - orderB;
      });
  }

  get orderMap() {
    return this.selectedNames.reduce((acc, category, index) => {
      acc[category] = index;
      return acc;
    }, {});
  }

  async created() {
    await this.updateFunctionShortcut();
  }

  async updateFunctionShortcut() {
    // TODO 分页
    const data = await getFunctionShortcut({
      type: this.isRecentView ? 'recent' : 'favorite',
      functions: this.selectedCategories,
      limit: 10,
    });
    console.log('data', data);
    if (this.isRecentView) {
      this.recentItems = data;
    } else {
      this.favoriteItems = data;
    }
  }

  // 切换视图状态
  toggleView(viewType: 'favorite' | 'recent'): void {
    this.isRecentView = viewType === 'recent';
  }

  // 显示或隐藏头部设置模态框
  handleHeaderSettingShowChange(visible: boolean) {
    this.showModal = visible;
  }

  // 获取用户存储菜单
  // getUserStoreMenu() {
  //   const storeRoute = localStorage.getItem(STORE_USER_MENU_KEY);
  //   if (!storeRoute) return null;
  //   try {
  //     return JSON.parse(storeRoute);
  //   } catch {
  //     return null;
  //   }
  // }

  // 设置用户存储菜单
  // setUserStoreMenu(newMenu: Record<string, { name: string } | { path: string }>) {
  //   const storeMenu = this.getUserStoreMenu() || {};
  //   localStorage.setItem(
  //     STORE_USER_MENU_KEY,
  //     JSON.stringify({
  //       ...storeMenu,
  //       ...newMenu,
  //     })
  //   );
  // }

  // 处理导航到存储路由
  handleGoStoreRoute(item: IRouteConfigItem) {
    const globalSetting = GLOAB_FEATURE_LIST.find(set => set.id === item.id);
    if (globalSetting) {
      this.handleHeaderSettingShowChange(false);
      (this.$refs.NavTools as any).handleSet(globalSetting);
    } else if (this.$route.name !== item.id) {
      this.handleHeaderSettingShowChange(false);
      const route = item.usePath ? { path: item.path } : { name: item.id };
      this.$router.push({ ...route, query: { ...item.query } });
    }
  }

  // 自定义设置组件
  getCustomize() {
    return (
      <bk-popover
        width='240'
        ext-cls='myself-popover'
        tippy-options={{
          arrow: false,
          trigger: 'click',
        }}
        animation='slide-toggle'
        offset='1, 4'
        placement='bottom-start'
        theme='light strategy-setting'
        trigger='click'
      >
        <div class='customize'>
          <i class='icon-monitor icon-menu-setting' />
          <span>{this.$t('自定义')}</span>
        </div>
        <div
          class='common-tool-popover'
          slot='content'
        >
          <div class='tool-popover-title'>
            {this.$t('展示模块')}
            <span class='route-count'>
              {this.selectedCategories.length}/{this.localVarList.length}
            </span>
          </div>

          <ul class='tool-popover-content'>
            <bk-checkbox-group v-model={this.selectedCategories}>
              <draggable
                class='draggable-container'
                v-model={this.localVarList}
              >
                {this.localVarList.map(item => (
                  <li
                    key={item.name}
                    class='tool-popover-content-item'
                  >
                    <bk-checkbox
                      disabled={
                        this.selectedCategories.length === 1 && this.selectedCategories.includes(modeNameMap[item.name])
                      }
                      value={modeNameMap[item.name]}
                    >
                      <span>{item.name}</span>
                    </bk-checkbox>
                    <i class='icon-monitor icon-mc-tuozhuai' />
                  </li>
                ))}
              </draggable>
            </bk-checkbox-group>
          </ul>
        </div>
      </bk-popover>
    );
  }

  // AI 小鲸 start
  expandTextarea(event) {
    this.showPlaceholder = false;
    event.target.style.maxHeight = '96px';
    event.target.style.overflowY = 'auto';
    event.target.style.whiteSpace = 'normal';
    this.focusDiv();
  }
  shrinkTextarea(event) {
    if (this.categoriesHasTwoRows) return;
    const content = event.target.innerText.trim();
    this.showPlaceholder = content === '' || content === this.placeholderText;
    if (content === '') {
      event.target.innerText = this.inputValue;
    }
    event.target.style.maxHeight = '32px';
    event.target.style.overflow = 'hidden';
    event.target.style.whiteSpace = 'nowrap';
  }
  handleInput(event) {
    const content = event.target.innerText.trim();
    this.showPlaceholder = content === '';
    if (content === this.inputValue) {
      event.target.innerText = '';
    }
  }
  handleKeyDown(event) {
    if (event.key === 'Enter') {
      if (!event.shiftKey && !event.ctrlKey) {
        // 阻止默认行为，即在没有按下 Shift 或 Ctrl 时不插入换行符
        event.preventDefault();
        // TODO 触发 AI 功能
      } else {
        // 在按下 Shift+Enter 或 Ctrl+Enter 时插入换行符
        // document.execCommand('insertLineBreak');
        // 插入换行并移动光标
        // this.insertLineBreakAndMoveCursor();
        // event.preventDefault();
      }
    }
  }

  // 插入回车符
  insertLineBreakAndMoveCursor() {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    const range = selection.getRangeAt(0);
    range.deleteContents();

    // 创建一个换行元素
    const br = document.createElement('br');

    // 插入换行符
    range.insertNode(br);

    // 移动光标到换行符之后
    range.setStartAfter(br);
    range.setEndAfter(br);
    selection.removeAllRanges();
    selection.addRange(range);

    this.ensureCursorVisible(br);
  }

  // 光标切换至可视区域
  ensureCursorVisible(node) {
    // 使用 scrollIntoView 方法确保节点可见
    if (node && typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // 点击placeholder
  focusDiv() {
    // 使用 this.$refs 访问可编辑的 div
    const editableDiv = this.$refs.editableDiv;
    editableDiv.focus();

    // 确保光标在内容的末尾
    const range = document.createRange();
    range.selectNodeContents(editableDiv);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  // AI 小鲸 end

  // 最近使用列表
  listItem({ item, title = '', tag = '' }) {
    if (!item) return;
    return (
      <li
        key={item.id}
        class='recent-item'
      >
        <div class='detail'>
          {!this.isRecentView && <i class='icon-mc-collect icon-monitor favorite' />}
          {tag && (
            <span class='tag'>
              <span>{tag}</span>
            </span>
          )}
          <span>{title}</span>
        </div>
        <span class='desc'>{item.bk_biz_name}</span>
      </li>
    );
  }

  // 根据模块类型，获取对应参数
  getListItemParams(type, item) {
    const typeHandlers = {
      dashboard: {
        item,
        id: item.dashboard_uid,
        title: item.dashboard_title,
      },
      apm_service: {
        item,
        id: item.application_id,
        title: `${item.app_name}/${item.service_name}`,
      },
      // TODO 为其他模块类型添加相关处理
      retrieval: {
        item,
        title: item.dashboard_title,
        // tag: '',
      },
      default: {},
    };

    return typeHandlers[type];
  }

  render() {
    return (
      <div class='recent-and-quick-access'>
        {/* 最近/收藏 */}
        <div class='recent-use'>
          <div class='recent-head'>
            {/* tab按钮 */}
            <div class='tab-buttons'>
              <span
                class={[this.isRecentView ? 'active ' : '', 'recent-title']}
                onClick={() => this.toggleView('recent')}
              >
                {this.$t('最近使用')}
              </span>
              {/* <span
                class={[!this.isRecentView ? 'active ' : '', 'recent-title']}
                onClick={() => this.toggleView('favorite')}
              >
                {this.$t('我的收藏')}
              </span> */}
            </div>
            {this.getCustomize()}
          </div>
          {/* 最近/收藏列表 */}
          <div class={['recent-content', this.rowClass, this.categoriesHasTwoRows ? 'has-line' : '']}>
            {this.itemsToDisplay.map(shortcut => (
              <div
                key={shortcut.function}
                class='category'
              >
                <div class='sub-head'>
                  <div>
                    {srcObj[shortcut.function] ? (
                      <div class='img'>
                        <img
                          alt=''
                          src={srcObj[shortcut.function]}
                        />
                      </div>
                    ) : (
                      <i class={['bk-icon bk-icon icon-search', shortcut.icon]} />
                    )}
                    <span class='recent-subtitle'>{EFunctionNameType[shortcut.function]}</span>
                  </div>
                  {/* <span class='more'>更多</span> */}
                </div>
                <ul class='recent-list'>
                  {shortcut.items.length ? (
                    shortcut.items.map(item => this.listItem(this.getListItemParams(shortcut.function, item)))
                  ) : (
                    <div class='recent-list-empty'>
                      {' '}
                      <div class='empty-img'>
                        <img
                          alt=''
                          src={emptyImageSrc}
                        />
                      </div>
                      {this.$t('暂无告警事件')}
                    </div>
                  )}
                </ul>
              </div>
            ))}
          </div>
        </div>
        {/* 快捷入口 */}
        <div class='quick-access'>
          <div class='quick-head'>
            <div class='quick-title'>{this.$t('快捷入口')}</div>
            {/* {this.getCustomize('quick-access')} */}
            <div
              class='customize'
              onClick={() => (this.showModal = true)}
              // onClick={() => (this.exampleSetting1.primary.visible = true)}
            >
              <i class='icon-monitor icon-menu-setting' />
              <span>{this.$t('自定义')}</span>
            </div>
          </div>
          <div class='quick-list'>
            <ul class='quick-items'>
              {this.userStoreRoutes.length ? (
                this.userStoreRoutes
                  ?.filter(item => item.id)
                  .map(item => (
                    <li
                      key={item.id}
                      class='quick-item'
                      onClick={() => this.handleGoStoreRoute(item)}
                    >
                      <i class={`${item.icon} list-item-icon`} />
                      <span>{this.$t(item.name.startsWith('route-') ? item.name : `route-${item.name}`)}</span>
                    </li>
                  ))
              ) : (
                <div class='quick-items-empty'>
                  {' '}
                  <div class='empty-img'>
                    <img
                      alt=''
                      src={emptyImageSrc}
                    />
                  </div>
                  {this.$t('暂无快捷入口')}
                </div>
              )}
            </ul>
          </div>
          {/* AI 小鲸 */}
          <div class={`${this.categoriesHasTwoRows ? 'max-height' : ''} ai-whale`}>
            <div class='editable-div-wrapper'>
              <div
                ref='editableDiv'
                class={{
                  'editable-div': true,
                  animated: !this.categoriesHasTwoRows,
                  'placeholder-visible': this.showPlaceholder,
                }}
                contenteditable={true}
                tabindex={0}
                onBlur={this.shrinkTextarea}
                onFocus={this.expandTextarea}
                onInput={this.handleInput}
                onKeydown={this.handleKeyDown}
              >
                {this.inputValue}
                {this.showPlaceholder && <span class='placeholder'>{this.placeholderText}</span>}
              </div>
              <img
                class='icon'
                alt='icon'
                src={aiWhaleSrc}
              />
            </div>
          </div>
        </div>
        <HeaderSettingModal
          show={this.showModal}
          onChange={this.handleHeaderSettingShowChange}
          onConfirm={() => (this.showModal = false)}
          onStoreRoutesChange={v => {
            this.userStoreRoutes = v;
          }}
        />
      </div>
    );
  }
}
