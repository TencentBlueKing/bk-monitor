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
import { Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import emptyImageSrc from '../../../../static/images/png/empty.png';
import dashboardSrc from '../../../../static/images/png/new-page/dashboard.png';
import retrievalSrc from '../../../../static/images/png/new-page/retrieval.png';
import serviceSrc from '../../../../static/images/png/new-page/service.png';
import { EFunctionNameType } from '../utils';

import type { IRecentList } from '../type';

import './recent-favorites-list.scss';

interface IRecentFavoritesListProps {
  hasTwoRows: boolean;
  isRecentView: boolean;
  itemsToDisplay: IRecentList[];
  selectedCategories: string[];
}

const categoryIcons = {
  dashboard: dashboardSrc,
  retrieval: retrievalSrc,
  apm_service: serviceSrc,
};

// 三种布局方式
const strategies = {
  1: 'row-1',
  2: 'row-2',
  3: 'row-3',
  4: 'row-2',
  5: 'row-3',
  6: 'row-3',
};

@Component({
  name: 'RecentFavoritesList',
})
export default class RecentFavoritesList extends tsc<IRecentFavoritesListProps> {
  @Prop({ default: false, type: Boolean }) hasTwoRows: boolean;
  @Prop({ default: () => [], type: Array }) selectedCategories!: string[];
  @Prop({ default: () => [], type: Array }) itemsToDisplay!: IRecentList[];
  @Prop({ default: false, type: Boolean }) isRecentView: boolean;

  // 计算布局策略
  get rowClass() {
    this.hasTwoRows = this.selectedCategories.length > 3;
    return strategies[this.selectedCategories.length] || '';
  }

  /** 处理点击最近使用列表，实现跳转 */
  handleRecentList(type: string, item: any) {
    const currentUrl = window.location.href;
    const baseUrl = currentUrl.split('#')[0];
    const callbacks: Record<string, () => void> = {
      /** 仪表盘 */
      dashboard: () => {
        const url = `${baseUrl}#/grafana/d/${item.dashboard_uid}`;
        window.open(url, '_blank');
      },
      /** APM */
      apm_service: () => {
        const url = `${baseUrl}#/apm/service?filter-app_name=${item.app_name}&filter-service_name=${item.service_name}`;
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
  listItem({ item, title = '', tag = '', type }: { item: any; title?: string; tag?: string; type: string }) {
    if (!item) return null;
    return (
      <li
        key={item.id}
        class='recent-item'
        onClick={() => this.handleRecentList(type, item)}
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
  getListItemParams(type: string, item: any) {
    const typeHandlers: Record<string, any> = {
      /** 仪表盘 */
      dashboard: {
        type,
        item,
        id: item.dashboard_uid,
        title: item.dashboard_title,
      },
      /** APM */
      apm_service: {
        type,
        item,
        id: item.application_id,
        title: `${item.app_name}/${item.service_name}`,
      },
      /** 检索 */
      retrieval: {
        type,
        item,
        title: item.dashboard_title,
      },
    };

    return typeHandlers[type] || {};
  }

  render() {
    return (
      <div class={['recent-content', this.rowClass, this.hasTwoRows ? 'has-line' : '']}>
        {this.itemsToDisplay.map(shortcut => (
          <div
            key={shortcut.function}
            class='category'
          >
            <div class='sub-head'>
              <div>
                {categoryIcons[shortcut.function] ? (
                  <div class='img'>
                    <img
                      alt=''
                      src={categoryIcons[shortcut.function]}
                    />
                  </div>
                ) : (
                  <i class={['bk-icon bk-icon icon-search', shortcut.icon]} />
                )}
                <span class='recent-subtitle'>{EFunctionNameType[shortcut.function]}</span>
                {/* <span class='more'>更多</span> */}
              </div>
            </div>
            <ul class='recent-list'>
              {shortcut.items.length ? (
                shortcut.items.map(item => this.listItem(this.getListItemParams(shortcut.function, item)))
              ) : (
                <div class='recent-list-empty'>
                  <div class='empty-img'>
                    <img
                      alt=''
                      src={emptyImageSrc}
                    />
                  </div>
                  {this.$t('暂无相关记录')}
                </div>
              )}
            </ul>
          </div>
        ))}
      </div>
    );
  }
}
