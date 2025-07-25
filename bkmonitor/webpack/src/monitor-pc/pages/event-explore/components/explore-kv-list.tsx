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

import dayjs from 'dayjs';
import { isHttpUrl } from 'monitor-common/regex/url';
import { copyText } from 'monitor-common/utils';

import { ECondition, EMethod, EMode } from '../../../components/retrieval-filter/utils';
import { APIType } from '../api-utils';
import { type ExploreSubject, ExploreObserver } from '../utils';
import FieldTypeIcon from './field-type-icon';
import StatisticsList from './statistics-list';

import type { ConditionChangeEvent, DimensionType, ExploreEntitiesItem, KVSplitItem } from '../typing';

import './explore-kv-list.scss';

export interface KVFieldList {
  /** kv 面板中的 value 部分是否可以点击打开 menu popover 操作弹窗 */
  canClick: boolean;
  /** 点击 name 是否能够弹出 统计面板popover */
  canOpenStatistics: boolean;
  /** 跳转到其他哪个页面入口list（容器/主机） */
  entities: KVEntities[];
  /** kv 面板中的 key */
  name: string;
  /** 部分字段目前显示的 name 是经过拼接处理后的值，sourceName 则是最原始未处理前的 name */
  sourceName: string;
  /** 字段的类型 */
  type: DimensionType;
  /** kv 面板中的 value */
  value: KVSplitItem[] | string;
}
interface IExploreKvListEvents {
  onConditionChange(e: ConditionChangeEvent): void;
}
interface IExploreKvListProps {
  fieldList: KVFieldList[];
  /** 滚动事件被观察者实例 */
  scrollSubject?: ExploreSubject;
  source: APIType;
}

type KVEntities = Pick<ExploreEntitiesItem, 'alias' | 'type'> & { path: string };

@Component
export default class ExploreKvList extends tsc<IExploreKvListProps, IExploreKvListEvents> {
  @Prop({ default: () => [], type: Array }) fieldList: KVFieldList[];
  /** 滚动事件被观察者实例 */
  @Prop({ type: Object }) scrollSubject: ExploreSubject;
  /** 来源 */
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;

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
      suffixRender: this.menuItemSuffixRender({ method: EMethod.eq }),
      onClick: () => this.handleConditionChange(EMethod.eq),
    },
    {
      id: 'delete',
      name: this.$t('从本次检索中排除'),
      icon: 'icon-sousuo-',
      suffixRender: this.menuItemSuffixRender({ method: EMethod.ne }),
      onClick: () => this.handleConditionChange(EMethod.ne),
    },
    {
      id: 'new-page',
      name: this.$t('新建检索'),
      icon: 'icon-mc-search',
      suffixRender: this.menuItemSuffixRender({ hasClick: false }),
      onClick: this.handleNewExplorePage,
    },
  ];
  showStatisticsPopover = false;
  popoverInstance = null;
  fieldTarget: KVFieldList = null;
  /** 当前激活触发弹出 popover 的列或者激活的分词下标 */
  activeColumnOrIndex: 'key' | 'value' | number = null;
  /** 统计面板的 抽屉页展示状态 */
  statisticsSliderShow = false;
  /** 容器滚动 popover 弹窗关闭 观察者 */
  scrollPopoverHideObserver: ExploreObserver;

  get activeColumnIsKey() {
    return this.activeColumnOrIndex === 'key';
  }

  @Emit('conditionChange')
  conditionChange(condition: ConditionChangeEvent) {
    return condition;
  }

  mounted() {
    if (this.scrollSubject) {
      this.scrollPopoverHideObserver = new ExploreObserver(this.handlePopoverHide.bind(this));
      this.scrollSubject.addObserver(this.scrollPopoverHideObserver);
    }
  }

  beforeDestroy() {
    this.handlePopoverHide();
    if (this.scrollSubject) {
      this.scrollSubject.deleteObserver(this.scrollPopoverHideObserver);
    }
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
        this.activeColumnOrIndex = null;
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
      this.activeColumnOrIndex = null;
    }
  }

  /**
   * @description 处理 kv 值点击事件
   * @param {MouseEvent} e
   * @param {KVFieldList} item
   */
  handleValueTextClick(e: MouseEvent, item: KVFieldList, activeIndex?: number) {
    const currentName = this.fieldTarget?.name;
    if (this.popoverInstance) {
      this.handlePopoverHide();
    }
    if (!item.canClick || currentName === item.name) {
      return;
    }
    this.fieldTarget = item;
    this.activeColumnOrIndex = activeIndex ?? 'value';

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
    this.activeColumnOrIndex = 'key';

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
        this.showStatisticsPopover = false;
        if (!this.statisticsSliderShow) {
          this.fieldTarget = null;
          this.activeColumnOrIndex = null;
        }
      },
      interactive: true,
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
    this.showStatisticsPopover = true;
  }

  /**
   * @description 获取当前激活menu 弹窗popover的 value
   * 由于存在分词，所以 fieldTarget 的 value 并不一定是最终激活的 value
   */
  getActiveValue() {
    const { value } = this.fieldTarget;
    if (!Array.isArray(value)) {
      return value;
    }
    return value?.[this.activeColumnOrIndex]?.value;
  }

  /**
   * @description 处理复制事件
   *
   */
  handleCopy() {
    copyText(this.getActiveValue() || '--', msg => {
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
   * @param {MouseEvent} event 点击事件
   * @param {EMethod} method 条件类型（eq等于 / ne不等于） 如果为空未传则走新建检索逻辑
   *
   */
  handleNewExplorePage(event, method?: EMethod) {
    event.stopPropagation();
    if (!this.fieldTarget?.value) {
      return;
    }
    const { targets, ...rest } = this.$route.query;
    const targetsList = targets ? JSON.parse(decodeURIComponent(targets as string)) : [];
    const sourceTarget = targetsList?.[0] || {};
    const queryConfig = sourceTarget?.data?.query_configs?.[0] || {};
    const { name, sourceName } = this.fieldTarget;
    const value = this.getActiveValue();
    let queryString = '';
    const where = [];
    const actualMethod = method || EMethod.eq;

    if (method) {
      where.push(...(queryConfig?.where || []));
      queryString = queryConfig?.query_string || '';
    }
    if (rest.filterMode === EMode.queryString) {
      let endStr = `${name} : "${value || ''}"`;
      actualMethod === EMethod.ne && (endStr = `NOT ${endStr}`);
      queryString = queryString ? `${queryString} AND ${endStr}` : `${endStr}`;
    } else {
      where.push({
        condition: ECondition.and,
        key: sourceName,
        method: actualMethod,
        value: [value || '""'],
      });
    }
    const query = {
      ...rest,
      targets: JSON.stringify([
        {
          ...sourceTarget,
          data: {
            query_configs: [
              {
                ...queryConfig,
                where,
                query_string: queryString,
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
    this.conditionChange({
      key: this.fieldTarget?.sourceName,
      method: method,
      value: this.getActiveValue(),
    });
    this.handlePopoverHide();
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
  handleJumpLink(entitiesItem: KVEntities) {
    if (entitiesItem.path) {
      let url = entitiesItem.path;
      if (!isHttpUrl(url)) {
        url = `${location.origin}${location.pathname}${location.search}${url}`;
      }
      window.open(url, '_blank');
    }
  }
  /**
   * @description kv 值渲染
   * @param {KVFieldList} item
   *
   */
  transformValue(item: KVFieldList) {
    const { value } = item;
    if (value == null || value === '') {
      return '--';
    }
    if (item.type === 'date') {
      return dayjs(Number(item.value)).format('YYYY-MM-DD HH:mm:ss');
    }
    return value;
  }

  /**
   * @description 容器/主机 跳转链接入口渲染
   *
   */
  jumpLinkRender(item: KVFieldList) {
    return item.entities.map(entitiesItem => (
      <div
        key={entitiesItem.alias}
        class='value-jump-link'
        onClick={() => this.handleJumpLink(entitiesItem)}
      >
        <span class='jump-link-label'>{entitiesItem.alias}</span>
        <i class='icon-monitor icon-mc-goto' />
      </div>
    ));
  }

  /**
   * @description kv 值渲染-分两种模式（value 为字符串则直接渲染，如为数组则是进行了 分词 操作的，需遍历）
   * @param {KVFieldList} item
   */
  valueTextRender(item: KVFieldList) {
    const { value } = item;
    if (!Array.isArray(value)) {
      return (
        <span
          class={{
            'value-text': true,
            'disable-click': !item.canClick,
            'active-column': !this.activeColumnIsKey,
          }}
          onClick={e => this.handleValueTextClick(e, item)}
        >
          {`${this.transformValue(item)}`}
        </span>
      );
    }

    return value.map((splitItem, index) => (
      <span
        key={`${splitItem.value}-${index}`}
        class={`value-${splitItem.type} ${this.activeColumnOrIndex === index ? 'active-column' : ''}`}
        onClick={e => this.handleValueTextClick(e, item, index)}
      >
        {splitItem.value}
      </span>
    ));
  }

  /**
   * @description kv 值点击弹出菜单popover 自定义后缀icon渲染
   * @param {EMethod} config.method 条件类型（eq等于 / ne不等于） 如果为空未传则走新建检索逻辑
   * @param {boolean} config.hasClick 是否有点击事件及 hover新开标签页 tooltip 提示
   *
   */
  menuItemSuffixRender(config: { hasClick?: boolean; method?: EMethod }) {
    const { method, hasClick = true } = config;
    return () => (
      <i
        class={`icon-monitor icon-mc-goto ${hasClick ? 'hover-blue' : ''}`}
        v-bk-tooltips={{ content: this.$t('新开标签页'), disabled: !hasClick }}
        onClick={e => this.handleNewExplorePage(e, method)}
      />
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
              <div class='item-suffix'>{item?.suffixRender?.()}</div>
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
          fieldType={this.fieldTarget?.type}
          isDimensions={this.fieldTarget?.name.startsWith('dimensions')}
          isShow={this.showStatisticsPopover}
          isShowChart={false}
          popoverInstance={this.popoverInstance}
          selectField={this.fieldTarget?.sourceName}
          source={this.source}
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
            class={{
              'kv-list-item': true,
              'active-row': this.fieldTarget?.name === item.name,
            }}
          >
            <div class='item-label'>
              <FieldTypeIcon
                class='kv-label-icon'
                type={item.type || ''}
              />
              <span
                class={{
                  'label-text': true,
                  'disable-click': !item.canOpenStatistics,
                  'active-column': this.activeColumnIsKey,
                }}
                title={item.name}
                onClick={e => this.handleDimensionItemClick(e, item)}
              >
                {item.name}
              </span>
            </div>
            <div class='item-value'>
              {this.jumpLinkRender(item)}
              {this.valueTextRender(item)}
            </div>
          </div>
        ))}
        {this.menuPopoverRender()}
        {this.statisticsPopoverRender()}
      </div>
    );
  }
}
