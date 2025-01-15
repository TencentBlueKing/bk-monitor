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
import { Component, Mixins, Watch } from 'vue-property-decorator';

import aiWhaleStore from '../../../../store/modules/ai-whale';
// import AiBlueking, { MessageStatus, RoleType } from '@blueking/ai-blueking/vue2';
import { getFunctionShortcut } from 'monitor-api/modules/overview';
import draggable from 'vuedraggable';

import UserConfigMixin from '../../../../mixins/userStoreConfig';
import { GLOAB_FEATURE_LIST, type IRouteConfigItem } from '../../../../router/router-config';
import emptyImageSrc from '../../../../static/images/png/empty.png';

import type { IRecentList } from '../type';
// import aiWhaleSrc from '../../../../static/images/png/new-page/aiWhale.png';
import { RECENT_FAVORITE_STORE_KEY } from '../utils';
import AiWhaleInput from './ai-whale-input';
import HeaderSettingModal from './header-setting-modal';
import RecentFavoritesList from './recent-favorites-list';

import './recent-favorites-tab.scss';

// 模块名称映射
const modeNameMap = {
  [window.i18n.tc('仪表盘')]: 'dashboard',
  [window.i18n.tc('服务')]: 'apm_service',
  [window.i18n.tc('日志检索')]: 'log_retrieve',
  [window.i18n.tc('服务拨测')]: '-',
  [window.i18n.tc('主机监控')]: '-',
  [window.i18n.tc('容器服务')]: '-',
};

interface Category {
  name: string;
}

@Component({
  name: 'RecentFavoritesTab',
  components: {
    draggable,
  },
})
export default class RecentFavoritesTab extends Mixins(UserConfigMixin) {
  isRecentView = true; // 状态，用于切换视图
  userStoreRoutes = []; // 用户存储的路由
  selectedCategories = ['dashboard']; // 用户选择的类别
  showModal = false; // 控制模态框显示
  categoriesConfig: Category[] = [
    { name: '仪表盘' },
    { name: '服务' },
    { name: '日志检索' },
    // { name: '服务拨测' },
    // { name: '主机监控' },
    // { name: '容器服务' },
  ];

  loadingRecentList = true; // 最近列表loading
  loadingQuickList = true; // 快捷入口loading

  recentItems: IRecentList[] = []; // 最近使用列表
  favoriteItems: IRecentList[] = []; // 收藏列表

  // 展示AI小鲸输入框
  get enableAiAssistant() {
    return aiWhaleStore.enableAiAssistant;
  }

  // 是否两行布局
  get categoriesHasTwoRows() {
    return this.selectedCategories.length > 3;
  }

  @Watch('selectedCategories')
  handleSelect() {
    this.onCategoriesOrderChanged();
    this.updateFunctionShortcut();
  }

  @Watch('categoriesConfig')
  onCategoriesOrderChanged() {
    this.setStoreSelectedCategories();
  }

  // 获取被选中的变量名
  get selectedNames() {
    return this.categoriesConfig.map(item => modeNameMap[item.name]);
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
    try {
      const [selected, selectList] =
        (await this.handleGetUserConfig<[string[], []]>(RECENT_FAVORITE_STORE_KEY, {
          reject403: true,
        })) || [];
      this.selectedCategories = selected || this.selectedCategories;
      this.categoriesConfig = this.categoriesConfig.reduce((accumulator: Category[], category: Category) => {
        if (!accumulator.some(item => item.name === category.name)) {
          accumulator.push(category);
        }
        return accumulator;
      }, selectList || []);
      await this.updateFunctionShortcut();
    } catch (error) {
      console.log('error', error);
    }
  }

  // 设置存储的最近使用模块并同步到用户配置
  setStoreSelectedCategories() {
    this.handleSetUserConfig(
      RECENT_FAVORITE_STORE_KEY,
      JSON.stringify([this.selectedCategories, this.categoriesConfig])
    );
  }

  async updateFunctionShortcut() {
    // TODO 分页
    this.loadingRecentList = true;
    try {
      const data = await getFunctionShortcut({
        type: this.isRecentView ? 'recent' : 'favorite',
        functions: this.selectedCategories,
      });
      if (this.isRecentView) {
        this.recentItems = data;
      } else {
        this.favoriteItems = data;
      }
    } catch (error) {
      console.log('error', error);
    } finally {
      this.loadingRecentList = false;
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

  // 处理导航到存储路由
  handleGoStoreRoute(item: IRouteConfigItem) {
    const globalSetting = GLOAB_FEATURE_LIST.find(set => set.id === item.id);
    if (globalSetting) {
      this.handleHeaderSettingShowChange(false);
      (this.$refs.NavTools as any).handleSet(globalSetting);
    } else if (this.$route.name !== item.id) {
      this.handleHeaderSettingShowChange(false);
      const route = item.usePath ? { path: item.path } : { name: item.id };
      const newUrl = this.$router.resolve({
        ...route,
        query: { ...item.query },
      }).href;

      // 在新标签页中打开这个 URL
      window.open(newUrl, '_blank');
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
              {this.selectedCategories.length}/{this.categoriesConfig.length}
            </span>
          </div>

          <ul class='tool-popover-content'>
            <bk-checkbox-group v-model={this.selectedCategories}>
              <draggable
                class='draggable-container'
                v-model={this.categoriesConfig}
              >
                {this.categoriesConfig.map(item => (
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

  // 触发 AI 小鲸，针对回车做处理
  handleKeyDown(event) {
    if (event.key !== 'Enter') return;
    // 阻止默认行为，即在没有按下 Shift 或 Ctrl 时不插入换行符
    if (event.shiftKey || event.ctrlKey) return;
    event.preventDefault();
    // 打开小鲸聊天框
    aiWhaleStore.setShowAIBlueking(true);
    aiWhaleStore.handleAiBluekingSend({
      content: event.target.innerText,
    });
    event.target.innerText = '';
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
          {
            <RecentFavoritesList
              class={{ 'loading-element': this.loadingRecentList, 'has-two-row': this.categoriesHasTwoRows }}
              v-bkloading={{ isLoading: this.loadingRecentList, zIndex: 10 }}
              hasTwoRows={this.categoriesHasTwoRows}
              isRecentView={this.isRecentView}
              itemsToDisplay={this.itemsToDisplay}
              selectedCategories={this.selectedCategories}
            />
          }
        </div>
        {/* 快捷入口 */}
        <div class='quick-access'>
          <div class='quick-head'>
            <div class='quick-title'>{this.$t('快捷入口')}</div>
            <div
              class='customize'
              onClick={() => (this.showModal = true)}
            >
              <i class='icon-monitor icon-menu-setting' />
              <span>{this.$t('自定义')}</span>
            </div>
          </div>
          <div
            class='quick-list'
            v-bkloading={{ isLoading: this.loadingQuickList, zIndex: 10 }}
          >
            <ul class={{ 'quick-items': true, 'no-ai-whale': !this.enableAiAssistant }}>
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
          {this.enableAiAssistant && (
            <AiWhaleInput
              categoriesHasTwoRows={this.categoriesHasTwoRows}
              onKeyDown={this.handleKeyDown}
            />
          )}
        </div>
        {/* 快捷入口模态框 */}
        <HeaderSettingModal
          show={this.showModal}
          onChange={this.handleHeaderSettingShowChange}
          onConfirm={() => (this.showModal = false)}
          onStoreRoutesChange={v => {
            this.loadingQuickList = true;
            this.$nextTick(() => {
              this.userStoreRoutes = v;
              this.loadingQuickList = false;
            });
          }}
        />
      </div>
    );
  }
}
