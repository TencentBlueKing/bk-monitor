/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { APIType } from '../api-utils';
import {
  type ConditionChangeEvent,
  type DimensionType,
  type ExploreEntitiesItem,
  type IExploreSceneUrlItem,
  type KVSplitItem,
  KVSplitEnum,
} from '../typing';
import { type ExploreSubject, ExploreObserver } from '../utils';
import ExploreConditionMenu from './explore-condition-menu';
import FieldTypeIcon from './field-type-icon';
import StatisticsList from './statistics-list';

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
  /** kv 点击 value 打开的 menu popover 中 查看该对象的其他场景 项中可选场景数据（空数组则不渲染） */
  sceneUrls?: IExploreSceneUrlItem[];
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

  @Ref('menuRef') menuRef: InstanceType<typeof ExploreConditionMenu>;
  @Ref('statisticsList') statisticsListRef!: InstanceType<typeof StatisticsList>;

  showStatisticsPopover = false;
  /** 一级 popover 实例(条件菜单/维度统计面板) */
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

  /**
   * @description 一级 popover 显示
   *
   */
  async handlePopoverShow(e: MouseEvent) {
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.menuRef.$el,
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
        this.handlePopoverHide();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
  }

  /**
   * @description 一级 popover 隐藏
   *
   */
  handlePopoverHide(resetFieldTarget = true) {
    this.menuRef?.handleScenePopoverHide?.();
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
    const currentColumnOrIndex = this.activeColumnOrIndex;
    if (this.popoverInstance) {
      this.handlePopoverHide();
    }
    if (!item.canClick) {
      return;
    }
    // 判断当前触发节点是否是分词中的分词符号，如果是则不触发打开menu操作
    if ((item?.value?.[activeIndex] as KVSplitItem)?.type === KVSplitEnum.SEGMENTS) {
      return;
    }
    // 判断是否是同一个 key 触发
    if (currentName === item.name) {
      // 判断 value 是分词还是字符串，字符串则本次点击为接关闭popover menu菜单操作
      if (!Array.isArray(item?.value)) {
        return;
      }
      // 为分词则判断触发索引是否和之前一样，一样则本次点击为接关闭popover menu菜单操作
      if (activeIndex === currentColumnOrIndex) {
        return;
      }
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
        this.handlePopoverHide(!this.statisticsSliderShow);
        this.showStatisticsPopover = false;
      },
      interactive: true,
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
    this.showStatisticsPopover = true;
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
    this.handlePopoverHide();
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
      return dayjs(Number(item.value)).format('YYYY-MM-DD HH:mm:ssZZ');
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
   * @description 处理复制事件
   * @param {ClipboardEvent} event
   */
  handleCopy(event: ClipboardEvent) {
    // 1. 获取当前选中的文本
    const selection = document.getSelection();

    // 2. 这里的处理逻辑：获取文本后移除所有换行符
    // 如果你想保留空格但去除换行，可以使用 replace
    let text = selection.toString();

    // 将换行符替换为空格，或者直接移除（视需求而定）
    // 这里演示替换为空字符串，恢复成一行
    text = text.replace(/[\r\n]+/g, '');

    // 3. 写入剪贴板
    event.clipboardData.setData('text/plain', text);

    // 4. 阻止默认的复制行为
    event.preventDefault();
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
            onCopy={this.handleCopy}
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
        <div style={{ display: 'none' }}>
          {/* kv 值点击弹出菜单popover渲染 */}
          <ExploreConditionMenu
            ref='menuRef'
            activeColumnOrIndex={this.activeColumnOrIndex}
            fieldTarget={this.fieldTarget}
            onConditionChange={this.conditionChange}
            onMenuClick={this.handlePopoverHide}
          />
          {/* 统计数据 popover面板渲染 */}
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
      </div>
    );
  }
}
