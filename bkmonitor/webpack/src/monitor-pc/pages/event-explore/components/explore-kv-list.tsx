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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils';

import { EMethod } from '../../../components/retrieval-filter/utils';
import { type DimensionType, ExploreEntitiesTypeEnum } from '../typing';
import FieldTypeIcon from './field-type-icon';
import StatisticsList from './statistics-list';

import './explore-kv-list.scss';

export interface KVFieldList {
  /** kv 面板中的 key */
  name: string;
  /** 字段的类型 */
  type: DimensionType;
  /** kv 面板中的 value */
  value: string;
  /** 部分字段目前显示的 name 是经过拼接处理后的值，sourceName 则是最原始未处理前的 name */
  sourceName: string;
  /** 跳转到其他哪个页面（容器/主机） */
  entitiesType: '' | ExploreEntitiesTypeEnum;
  /** 是否显示跳转入口 */
  hasEntities: boolean;
  /** 跳转入口显示的文案 */
  entitiesAlias: string;
  /** 点击 name 是否能够弹出 统计面板popover */
  canOpenStatistics: boolean;
  externalParams: Record<string, any>;
}

interface IExploreKvListProps {
  fieldList: KVFieldList[];
}

interface IExploreKvListEvents {
  onConditionChange(val): void;
}

@Component
export default class ExploreKvList extends tsc<IExploreKvListProps, IExploreKvListEvents> {
  @Prop({ default: () => [], type: Array }) fieldList: KVFieldList[];

  @Ref('menu') menuRef: HTMLUListElement;
  @Ref('statisticsList') statisticsListRef!: InstanceType<typeof StatisticsList>;

  menuList = [
    {
      id: 'copy',
      name: this.$t('复制'),
      icon: 'icon-mc-copy',
      onClick: this.handleCopy,
    },
    {
      id: 'add',
      name: this.$t('添加到本次检索'),
      icon: 'icon-a-sousuo',
      onClick: () => this.handleConditionChange(EMethod.eq),
    },
    {
      id: 'delete',
      name: this.$t('从本次检索中排除'),
      icon: 'icon-sousuo-',
      onClick: () => this.handleConditionChange(EMethod.ne),
    },
    {
      id: 'new-page',
      name: this.$t('新建检索'),
      icon: 'icon-mc-search',
      onClick: this.handleNewExplorePage,
    },
  ];
  popoverInstance = null;
  fieldTarget: KVFieldList = null;
  /** 统计面板的 抽屉页展示状态 */
  statisticsSliderShow = false;

  @Emit('conditionChange')
  conditionChange(condition) {
    return condition;
  }

  async handlePopoverShow(e: MouseEvent) {
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.menuRef,
      trigger: 'click',
      placement: 'bottom',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      followCursor: 'initial',
      boundary: 'viewport',
      distance: 4,
      offset: '-2, 0',
      onHidden: () => {
        this.popoverInstance?.destroy?.();
        this.popoverInstance = null;
        this.fieldTarget = null;
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
  }

  handlePopoverHide(resetFieldTarget = true) {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    if (resetFieldTarget) {
      this.fieldTarget = null;
    }
  }

  /**
   * @description 处理 kv 值点击事件
   * @param {MouseEvent} e
   * @param {KVFieldList} item
   */
  handleValueTextClick(e: MouseEvent, item: KVFieldList) {
    const currentName = this.fieldTarget?.name;
    if (this.popoverInstance) {
      this.handlePopoverHide();
    }
    if (currentName === item.name) {
      return;
    }
    this.fieldTarget = item;
    this.handlePopoverShow(e);
  }

  /**
   * @description 处理维度项点击事件
   * @param {MouseEvent} e
   * @param {KVFieldList} item
   *
   */
  async handleDimensionItemClick(e: MouseEvent, item: KVFieldList) {
    const currentName = this.fieldTarget?.name;
    if (this.popoverInstance) {
      this.handlePopoverHide();
    }

    if (!item.canOpenStatistics || currentName === item.name) {
      return;
    }
    this.fieldTarget = item;
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.statisticsListRef.$refs.dimensionPopover,
      placement: 'right',
      width: 400,
      distance: -5,
      boundary: 'window',
      trigger: 'manual',
      theme: 'light event-retrieval-dimension-filter',
      arrow: true,
      onHidden: () => {
        this.popoverInstance?.destroy?.();
        this.popoverInstance = null;
        if (!this.statisticsSliderShow) {
          this.fieldTarget = null;
        }
      },
      interactive: true,
    });
    this.popoverInstance?.show(100);
  }

  /**
   * @description 处理复制事件
   *
   */
  handleCopy() {
    copyText(this.fieldTarget.value || '--', msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
    this.handlePopoverHide();
  }

  /**
   * @description 新建检索 回调
   *
   */
  handleNewExplorePage() {
    if (!this.fieldTarget?.value) {
      return;
    }
    const { targets, from, to, timezone, refreshInterval } = this.$route.query;
    const targetsList = JSON.parse(decodeURIComponent(targets as string));
    const [
      {
        data: {
          query_configs: [{ data_type_label, data_source_label, result_table_id }],
        },
      },
    ] = targetsList;

    const query = {
      targets: JSON.stringify([
        {
          from: from,
          to: to,
          timezone: timezone,
          refreshInterval: String(refreshInterval),
          data: {
            query_configs: [
              {
                data_type_label,
                data_source_label,
                result_table_id,
                query_string: '*',
                where: [
                  {
                    condition: 'and',
                    key: this.fieldTarget?.sourceName,
                    method: EMethod.eq,
                    value: [this.fieldTarget?.value],
                  },
                ],
              },
            ],
          },
        },
      ]),
    };
    const targetRoute = this.$router.resolve({
      query,
    });
    this.handlePopoverHide();
    window.open(`${location.origin}${location.pathname}${location.search}${targetRoute.href}`, '_blank');
  }

  /**
   * @description 添加/删除 检索 回调
   */
  handleConditionChange(method: EMethod) {
    if (!this.fieldTarget?.value) {
      return;
    }
    const condition = [
      { condition: 'and', key: this.fieldTarget?.sourceName, method, value: [this.fieldTarget?.value] },
    ];
    this.handlePopoverHide();
    this.conditionChange(condition);
  }

  /**
   * @description 统计面板中 抽屉页 展示/消失 状态回调
   */
  handleStatisticsSliderShow(sliderShow: boolean) {
    this.statisticsSliderShow = sliderShow;
    if (!sliderShow) {
      this.handlePopoverHide();
    }
  }

  /**
   * @description 统计面板中 添加/删除 检索 回调
   */
  handleStatisticsConditionChange(condition) {
    this.conditionChange(condition);
    this.handlePopoverHide(false);
  }

  /**
   * @description 主机/容器 跳转链接回调
   */
  handleJumpLink(item: KVFieldList) {
    let path = '';
    switch (item.entitiesType) {
      case ExploreEntitiesTypeEnum.HOST:
        {
          const { value, sourceName } = item;
          const endStr = `${value}${sourceName === 'bk_host_id' ? '' : `-${item.externalParams.cloudId}`}`;
          path = `#/performance/detail/${endStr}`;
        }
        break;
      case ExploreEntitiesTypeEnum.K8S:
        path = '#/k8s?dashboardId=pod';
        break;
    }
    if (path) {
      const url = `${location.origin}${location.pathname}${location.search}${path}`;
      window.open(url, '_blank');
    }
  }

  /**
   * @description 容器/主机 跳转链接入口渲染
   *
   */
  jumpLinkRender(item: KVFieldList) {
    if (!item.hasEntities || !item.value) {
      return;
    }
    return (
      <div
        class='value-jump-link'
        onClick={() => this.handleJumpLink(item)}
      >
        <span class='jump-link-label'>{item.entitiesAlias}</span>
        <i class='icon-monitor icon-mc-goto' />
      </div>
    );
  }

  /**
   * @description kv 值点击弹出菜单popover渲染
   *
   */
  menuPopoverRender() {
    return (
      <div style='display: none'>
        <ul
          ref='menu'
          class='explore-kv-list-menu'
        >
          {this.menuList.map(item => (
            <li
              key={item.id}
              class='menu-item'
              onClick={item.onClick}
            >
              <i class={`icon-monitor ${item.icon}`} />
              <span>{item.name}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  /**
   * @description 统计数据 popover面板渲染
   *
   */
  statisticsPopoverRender() {
    return (
      <div style={{ display: 'none' }}>
        <StatisticsList
          ref='statisticsList'
          popoverInstance={this.popoverInstance}
          selectField={this.fieldTarget?.sourceName || '--'}
          onConditionChange={this.handleStatisticsConditionChange}
          onShowMore={() => this.handlePopoverHide(false)}
          onSliderShowChange={this.handleStatisticsSliderShow}
        />
      </div>
    );
  }

  render() {
    return (
      <div class='explore-kv-list'>
        {this.fieldList.map(item => (
          <div
            key={item.name}
            class={`kv-list-item ${this.fieldTarget?.name === item.name ? 'active' : ''}`}
          >
            <div class='item-label'>
              <FieldTypeIcon
                class='kv-label-icon'
                type={item.type || ''}
              />
              <span
                title={item.name}
                onClick={e => this.handleDimensionItemClick(e, item)}
              >
                {item.name}
              </span>
            </div>
            <div class='item-value'>
              {this.jumpLinkRender(item)}
              <span
                class='value-text'
                onClick={e => this.handleValueTextClick(e, item)}
              >
                {item.value || '--'}
              </span>
            </div>
          </div>
        ))}
        {this.menuPopoverRender()}
        {this.statisticsPopoverRender()}
      </div>
    );
  }
}
