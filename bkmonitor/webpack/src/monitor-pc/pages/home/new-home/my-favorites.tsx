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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import draggable from 'vuedraggable';

import { GLOAB_FEATURE_LIST, type IRouteConfigItem } from '../../../router/router-config';
import HeaderSettingModal from './header-setting-modal';

import './my-favorites.scss';
interface RecentItems {
  category: string;
  items: Item[];
  icon?: string;
}

interface Item {
  id: number;
  name: string;
  description: string;
  icon: string;
}

// const STORE_USER_MENU_KEY = 'USER_STORE_MENU_KEY';

const recentItems: RecentItems[] = [
  {
    category: '仪表盘',
    icon: 'icon-monitor icon-menu-chart',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '检索',
    icon: 'icon-monitor icon-mc-menu-apm ',

    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '服务',
    icon: 'icon-monitor icon-menu-collect',

    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '服务拨测',
    icon: '',

    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '主机监控',
    icon: 'icon-monitor icon-menu-performance',

    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '容器服务',
    icon: 'icon-monitor icon-shujuku',

    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
];

const favoriteItems: RecentItems[] = [
  {
    category: '检索',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '♥' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '服务',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '♥' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '主机监控',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '♥' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '♥' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '♥' },
    ],
  },
  {
    category: '容器服务',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '♥' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '♥' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '♥' },
    ],
  },
  {
    category: '服务拨测',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '📄' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '📄' },
    ],
  },
  {
    category: '仪表盘',
    items: [
      { id: 1, name: '[BlueKing]BCS Cluster Autoscaler', description: 'Description 1', icon: '♥' },
      { id: 2, name: '业务使用细节 update', description: 'Description 2', icon: '♥' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '♥' },
      { id: 3, name: 'Item 3', description: 'Description 3', icon: '♥' },
    ],
  },
];

@Component({
  name: 'MyFavorites',
  components: {
    draggable,
  },
})
export default class MyFavorites extends tsc<object> {
  isRecentView = true; // 状态，用于切换视图
  userStoreRoutes = []; // 用户存储的路由
  selectedCategories = ['仪表盘', '服务']; // 用户选择的类别
  inputValue = ''; // 输入框的值
  isActive = false; // 输入框状态
  showModal = false; // 控制模态框显示
  localVarList = [
    { id: 1, name: '仪表盘', checked: true, disabled: false },
    { id: 2, name: '检索', checked: true, disabled: false },
    { id: 3, name: '服务', checked: true, disabled: false },
    { id: 4, name: '服务拨测', checked: true, disabled: false },
    { id: 5, name: '主机监控', checked: true, disabled: false },
    { id: 6, name: '容器服务', checked: true, disabled: false },
  ];

  // 获取被选中的本地变量名
  get selectedLocalNames() {
    return this.localVarList.filter(item => item.checked).map(item => item.name);
  }

  // 根据当前视图状态获取要显示的项目
  get itemsToDisplay() {
    const items = this.isRecentView ? recentItems : favoriteItems;
    return items.filter(item => this.selectedCategories.includes(item.category));
  }

  // 计算布局策略
  get rowClass() {
    const strategies = {
      1: 'row-1',
      2: 'row-2',
      4: 'row-2',
      3: 'row-3',
      5: 'row-3',
      6: 'row-3',
    };
    return strategies[this.selectedCategories.length] || '';
  }

  // 切换视图状态
  toggleView(viewType: 'favorite' | 'recent'): void {
    this.isRecentView = viewType === 'recent';
  }

  // 处理列选择变化
  handleCheckColChange(item) {
    console.log(item, this.selectedLocalNames);
  }

  // 拖动结束事件
  onDragEnd(event) {
    console.log('Drag ended:', event);
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
        offset='-1, 2'
        placement='bottom-start'
        theme='light strategy-setting'
        trigger='click'
      >
        <div class='customize'>
          <i class='input-right-icon bk-icon bk-icon icon-search' />
          <span>{this.$t('自定义')}</span>
        </div>
        <div
          class='common-tool-popover'
          slot='content'
        >
          <div class='tool-popover-title'>
            {this.$t('展示模块')}
            <span class='route-count'>{this.selectedCategories.length}/6</span>
          </div>

          <ul class='tool-popover-content'>
            <bk-checkbox-group v-model={this.selectedCategories}>
              <draggable
                class='draggable-container'
                v-model={this.localVarList}
              >
                {this.localVarList.map(item => (
                  <li
                    key={item.id}
                    class='tool-popover-content-item'
                  >
                    <bk-checkbox
                      disabled={item.disabled}
                      value={item.name}
                      on-change={() => this.handleCheckColChange(item)}
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
              <span
                class={[!this.isRecentView ? 'active ' : '', 'recent-title']}
                onClick={() => this.toggleView('favorite')}
              >
                {this.$t('我的收藏')}
              </span>
            </div>
            {this.getCustomize()}
          </div>
          {/* 最近/收藏列表 */}
          <div
            class={[
              'recent-content',
              this.rowClass,
              [4, 5, 6].includes(this.selectedCategories.length) ? 'has-line' : '',
            ]}
          >
            {this.itemsToDisplay.map(section => (
              <div
                key={section.category}
                class='category'
              >
                <div class='sub-head'>
                  <div>
                    <i class={['bk-icon bk-icon icon-search', section.icon]} />
                    <span class='recent-subtitle'>{section.category}</span>
                  </div>
                  {/* <span class='more'>更多</span> */}
                </div>
                <ul class='recent-list'>
                  {section.items.map(item => (
                    <li
                      key={item.id}
                      class='recent-item'
                    >
                      <div class='detail'>
                        {!this.isRecentView && <i class='icon-mc-collect icon-monitor favorite' />}
                        <span class='tag'>
                          <span>哈</span>
                        </span>
                        <span>{item.name}</span>
                      </div>
                      <span class='desc'>王者荣耀</span>
                    </li>
                  ))}
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
              <i class='input-right-icon bk-icon bk-icon icon-search' />
              <span>{this.$t('自定义')}</span>
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
          <div class='quick-list'>
            <ul class='quick-items'>
              {this.userStoreRoutes
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
                ))}
              {/* AI 小鲸 */}
              <div class='ai-whale'>
                <div class='input'>
                  <bk-input
                    ext-cls={`${this.selectedCategories.length > 3 ? 'ext-ccls' : 'ext-cls'} ${this.isActive ? 'ai-active' : ''}`}
                    v-model={this.inputValue}
                    maxlength='255'
                    placeholder='有问题就问小鲸'
                    right-icon="'icon-monitor icon-search'"
                    rows={this.isActive ? 3 : 1}
                    type='textarea'
                    onBlur={() => (this.isActive = false)}
                    onInput={() => (this.isActive = true)}
                  />
                </div>
              </div>
            </ul>
          </div>
        </div>
      </div>
    );
  }
}
