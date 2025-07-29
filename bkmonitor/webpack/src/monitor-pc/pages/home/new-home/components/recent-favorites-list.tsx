import { Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctionShortcut } from 'monitor-api/modules/overview';
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
import Component from 'vue-class-component';

import emptyImageSrc from '../../../../static/images/png/empty.png';
import dashboardSrc from '../../../../static/images/png/new-page/dashboard.png';
import retrievalSrc from '../../../../static/images/png/new-page/retrieval.png';
import serviceSrc from '../../../../static/images/png/new-page/service.png';
import reportLogStore from '../../../../store/modules/report-log';
import { EFunctionNameType } from '../utils';

import type { IRecentList } from '../type';

import './recent-favorites-list.scss';

interface IRecentFavoritesListProps {
  hasTwoRows: boolean;
  isRecentView: boolean;
  itemsToDisplay?: IRecentList[];
  selectedCategories: string[];
  selectedNames: string[];
}

const categoryIcons = {
  dashboard: dashboardSrc,
  log_retrieve: retrievalSrc,
  apm_service: serviceSrc,
};

// 三种布局方式
const layoutClassesByLength = {
  1: 'single-col',
  2: 'double-col',
  3: 'triple-col',
  4: 'double-col',
  5: 'triple-col',
  6: 'triple-col',
};
@Component({
  name: 'RecentFavoritesList',
})
export default class RecentFavoritesList extends tsc<IRecentFavoritesListProps> {
  @Prop({ default: false, type: Boolean }) hasTwoRows: boolean;
  @Prop({ default: () => [], type: Array }) selectedCategories!: string[];
  @Prop({ default: () => [], type: Array }) selectedNames!: string[];
  @Prop({ default: false, type: Boolean }) isRecentView: boolean;

  recentItems: IRecentList[] = []; // 最近使用列表
  favoriteItems: IRecentList[] = []; // 收藏列表

  loadingRecentList = true;

  // 计算布局策略
  get rowClass() {
    return layoutClassesByLength[this.selectedCategories.length] || '';
  }

  // 根据当前视图状态获取要显示的项目
  get categoriesAfterSort() {
    return this.selectedCategories.sort((a, b) => {
      const orderA = this.orderMap[a] !== undefined ? this.orderMap[a] : Number.POSITIVE_INFINITY;
      const orderB = this.orderMap[b] !== undefined ? this.orderMap[b] : Number.POSITIVE_INFINITY;
      return orderA - orderB;
    });
  }

  get orderMap() {
    return this.selectedNames.reduce((acc, category, index) => {
      acc[category] = index;
      return acc;
    }, {});
  }

  getItemByName(functionName): IRecentList {
    const items = this.isRecentView ? this.recentItems : this.favoriteItems;
    return items.filter(item => item.function === functionName)?.[0];
  }

  @Watch('selectedCategories')
  handleSelect(newVal, oldVal) {
    if (newVal === oldVal) return;
    this.updateFunctionShortcut();
  }

  async updateFunctionShortcut() {
    // TODO 分页
    this.loadingRecentList = true;
    try {
      const data = await getFunctionShortcut({
        type: this.isRecentView ? 'recent' : 'favorite',
        functions: this.selectedCategories,
        limit: 7, // 最多展示七条
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

  /** 处理点击最近使用列表，实现跳转 */
  handleRecentList(type: string, item: any) {
    const currentUrl = window.location.href;
    const questionMarkIndex = currentUrl.indexOf('?');
    // 如果有 '?'，则截取字符串；否则返回完整的 URL
    let baseUrl = questionMarkIndex !== -1 ? currentUrl.substring(0, questionMarkIndex) : currentUrl;
    baseUrl += `?bizId=${item.bk_biz_id}`;
    const callbacks: Record<string, () => void> = {
      /** 仪表盘 */
      dashboard: () => {
        const url = `${baseUrl}#/grafana/d/${item.dashboard_uid}`;
        reportLogStore.reportHomeSearchNavLog({ type: 'dashboard', name: '仪表盘' });
        window.open(url, '_blank');
      },
      /** APM */
      apm_service: () => {
        const url = `${baseUrl}#/apm/service?filter-app_name=${item.app_name}&filter-service_name=${item.service_name}`;
        reportLogStore.reportHomeSearchNavLog({ type: 'apm_service', name: '服务' });
        window.open(url, '_blank');
      },
      /** 日志检索 */
      log_retrieve: () => {
        reportLogStore.reportHomeSearchNavLog({ type: 'log_retrieve', name: '日志检索' });
        const url = `${baseUrl}#/log-retrieval?indexId=${item.index_set_id}&spaceUid=${item.space_uid}`;
        window.open(url, '_blank');
      },
    };

    if (callbacks[type]) {
      callbacks[type]();
    } else {
      console.warn(`Unhandled type: ${type}`);
    }
  }

  // 最近使用列表
  listItem({ item, title = '', tag = '', type }: { item: any; tag?: string; title?: string; type: string }) {
    if (!item) return null;
    return (
      <li
        key={item.id}
        class='recent-item'
        onClick={() => this.handleRecentList(type, item)}
      >
        <div
          class='detail'
          v-bk-overflow-tips
        >
          {!this.isRecentView && <i class='icon-mc-collect icon-monitor favorite' />}
          {tag && (
            <span class='tag'>
              <span>{tag}</span>
            </span>
          )}
          <span>{title}</span>
        </div>
        <span
          class='desc'
          v-bk-overflow-tips
        >
          {item.bk_biz_name}
        </span>
      </li>
    );
  }

  // 根据模块类型，获取对应参数
  getListItemParams(type: string, item: any) {
    const typeHandlers: Record<string, any> = {
      /** 仪表盘 */
      dashboard: {
        type,
        item,
        id: item.dashboard_uid,
        title: `${item.folder_title ? `${item.folder_title}/ ` : ''}${item.dashboard_title}`,
      },
      /** APM */
      apm_service: {
        type,
        item,
        id: item.application_id,
        title: `${item.app_name}/${item.service_name}`,
      },
      /** 日志检索 */
      log_retrieve: {
        type,
        item,
        title: item.index_set_name,
      },
    };

    return typeHandlers[type] || {};
  }

  renderList(param) {
    const shortcut: IRecentList = this.getItemByName(param);

    return shortcut?.items.length ? (
      shortcut.items.slice(0, 7).map(item => this.listItem(this.getListItemParams(shortcut.function, item)))
    ) : (
      <div class='recent-list-empty'>
        <div class='empty-img'>
          <img
            alt=''
            src={emptyImageSrc}
          />
        </div>
        {this.$t('暂无数据')}
      </div>
    );
  }

  render() {
    return (
      <div class={['recent-content', this.rowClass, this.hasTwoRows ? 'has-line' : '']}>
        {this.categoriesAfterSort.map(functionName => (
          <div
            key={functionName}
            class='category'
          >
            <div class='sub-head'>
              {!this.loadingRecentList ? (
                <div class='head'>
                  {categoryIcons[functionName] ? (
                    <div class='img'>
                      <img
                        alt=''
                        src={categoryIcons[functionName]}
                      />
                    </div>
                  ) : (
                    <i class={['bk-icon bk-icon', functionName]} />
                  )}
                  <span class='recent-subtitle'>{this.$tc(`route-${EFunctionNameType[functionName]}`)}</span>
                  {/* <span class='more'>更多</span> */}
                </div>
              ) : (
                <div class='skeleton-element' />
              )}
            </div>
            <ul class='recent-list'>
              {!this.loadingRecentList ? (
                this.renderList(functionName)
              ) : (
                <div class='skeleton-list'>
                  {Array(7)
                    .fill(null)
                    .map((_, index) => (
                      <div
                        key={index}
                        class='skeleton-element'
                      />
                    ))}
                </div>
              )}
            </ul>
          </div>
        ))}
      </div>
    );
  }
}
