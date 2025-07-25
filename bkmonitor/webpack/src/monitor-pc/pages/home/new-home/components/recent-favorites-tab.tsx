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

import bus from 'monitor-common/utils/event-bus';
import draggable from 'vuedraggable';

import UserConfigMixin from '../../../../mixins/userStoreConfig';
import { HANDLE_MENU_CHANGE } from '../../../../pages/nav-tools';
import { type IRouteConfigItem, GLOBAL_FEATURE_LIST } from '../../../../router/router-config';
import aiWhaleStore from '../../../../store/modules/ai-whale';
import { RECENT_FAVORITE_LIST_KEY } from '../utils';
import QuickAccess from './quick-access';
import RecentFavoritesList from './recent-favorites-list';

import './recent-favorites-tab.scss';

// 模块名称映射
const modeNameMap = {
  仪表盘: 'dashboard',
  服务: 'apm_service',
  日志检索: 'log_retrieve',
  服务拨测: '-',
  主机监控: '-',
  容器服务: '-',
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
  selectedCategories = ['dashboard', 'log_retrieve']; // 用户选择的类别
  categoriesConfig: Category[] = [
    { name: '仪表盘' },
    { name: '服务' },
    { name: '日志检索' },
    // { name: '服务拨测' },
    // { name: '主机监控' },
    // { name: '容器服务' },
  ];

  // 展示AI小鲸输入框
  get enableAiAssistant() {
    return aiWhaleStore.enableAiAssistant;
  }

  // 是否两行布局
  get categoriesHasTwoRows() {
    return this.selectedCategories.length > 3;
  }

  @Watch('categoriesConfig')
  onCategoriesOrderChanged() {
    this.setStoreSelectedCategories();
  }

  // 获取被选中的变量名
  get selectedNames() {
    return this.categoriesConfig.map(item => modeNameMap[item.name]);
  }

  get loading() {
    return aiWhaleStore.loading;
  }

  // 初始化最近使用的数据
  async initRecentUseData() {
    try {
      const [selected, selectList] =
        (await this.handleGetUserConfig<[string[], []]>(RECENT_FAVORITE_LIST_KEY, {
          reject403: true,
        })) || [];
      this.selectedCategories = selected?.slice?.() || this.selectedCategories.slice();
      this.categoriesConfig = this.categoriesConfig
        .reduce((accumulator: Category[], category: Category) => {
          if (!accumulator.some(item => item.name === category.name)) {
            accumulator.push(category);
          }
          return accumulator;
        }, selectList || [])
        .slice();
    } catch {}
  }

  async created() {
    try {
      await this.initRecentUseData();
    } catch (error) {
      console.log('error', error);
    }
  }

  // 设置存储的最近使用模块并同步到用户配置
  setStoreSelectedCategories() {
    this.handleSetUserConfig(
      RECENT_FAVORITE_LIST_KEY,
      JSON.stringify([this.selectedCategories, this.categoriesConfig])
    );
  }

  // 切换视图状态
  toggleView(viewType: 'favorite' | 'recent'): void {
    this.isRecentView = viewType === 'recent';
  }

  // 处理导航到存储路由
  handleGoStoreRoute(item: IRouteConfigItem) {
    const globalSetting = GLOBAL_FEATURE_LIST.find(set => set.id === item.id);
    if (globalSetting) {
      bus.$emit(HANDLE_MENU_CHANGE, item);
    } else if (this.$route.name !== item.id) {
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
          trigger: 'click',
        }}
        arrow={false}
        offset='1, 1'
        placement='bottom-start'
        theme='light common-monitor'
      >
        <div class='customize'>
          <i class='icon-monitor icon-customize' />
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
            <bk-checkbox-group
              v-model={this.selectedCategories}
              onChange={this.onCategoriesOrderChanged}
            >
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
                      <span>{this.$tc(item.name)}</span>
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
    // if (this.loading) {
    //   event.preventDefault();
    //   return;
    // }
    // 获取实际输入内容（考虑换行符情况）
    const hasContent = event.target.innerText.replace(/[\n\r]/g, '').trim().length > 0;

    if (!hasContent) {
      event.preventDefault();
      return;
    }
    event.preventDefault();
    // 打开小鲸聊天框
    aiWhaleStore.sendMessage(event.target.innerText);
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
              hasTwoRows={this.categoriesHasTwoRows}
              isRecentView={this.isRecentView}
              selectedCategories={this.selectedCategories}
              selectedNames={this.selectedNames}
            />
          }
        </div>
        {/* 快捷入口 */}
        <QuickAccess
          categoriesHasTwoRows={this.categoriesHasTwoRows}
          enableAiAssistant={this.enableAiAssistant}
          onHandleGoStoreRoute={this.handleGoStoreRoute}
          onHandleKeyDown={this.handleKeyDown}
        />
      </div>
    );
  }
}
