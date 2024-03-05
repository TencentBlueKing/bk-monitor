/* eslint-disable @typescript-eslint/no-misused-promises */
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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Debounce } from 'monitor-common/utils/utils';

import { SPACE_FIRST_CODE_COLOR_MAP, SPACE_TYPE_MAP } from '../../common/constant';
import authorityStore from '../../store/modules/authority';
import { ISpaceItem } from '../../types';
import { Storage } from '../../utils';

import List, { ETagsType, IListItem } from './list';

import './biz-select.scss';
/** 业务组件常用的业务缓存key */
const BIZ_SELECTOR_COMMON_IDS = 'BIZ_SELECTOR_COMMON_IDS';
/** 业务组件常用业务缓存最大个数 */
const BIZ_SELECTOR_COMMON_MAX = 5;
const BIZ_COLOR_LIST = [
  '#7250A9',
  '#3563BE',
  '#3799BA',
  '#4FB17F',
  '#86AF4A',
  '#E9AE1D',
  '#EB9258',
  '#D36C68',
  '#BC4FB3'
];
interface IProps {
  value: number;
  zIndex?: number;
  bizList: ISpaceItem[];
  isShrink?: boolean;
  theme?: ThemeType;
  minWidth?: number;
  stickyList?: string[];
  isShowCommon?: boolean;
}
export type ThemeType = 'dark' | 'light';
interface IEvents {
  onChange: number;
  onOpenSpaceManager: void;
}
/**
 * 业务选择器组件
 */
@Component
export default class BizSelect extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) bizList: ISpaceItem[];
  @Prop({ default: '', type: [Number, String] }) value: number;
  @Prop({ default: false, type: Boolean }) isShrink: boolean; // 是否收起显示首字母
  @Prop({ default: true, type: Boolean }) isShowCommon: boolean; // 是否展示常用
  @Prop({ default: null, type: Number }) zIndex: number;
  @Prop({ default: 200, type: Number }) minWidth: number;
  @Prop({ default: () => [], type: Array }) stickyList: string[]; // 置顶空间的uid
  @Prop({
    default: 'light',
    type: String,
    validator: (val: string) => ['dark', 'light'].includes(val)
  })
  theme: ThemeType;
  @Ref() menuSearchInput: any;
  @Ref() popoverRef: any;
  @Ref('typeList') typeListRef: HTMLDivElement;

  localValue: number = null;

  showBizList = false;
  keyword = '';

  listWidth = 200;

  /** 操作缓存实例 */
  storage: Storage = null;
  /** 常用业务id */
  commonListIds: number[] = [];
  spaceTypeIdList: { id: string; name: string; styles: any }[] = [];
  searchTypeId = '';
  bizBgColor = '';

  bizListFilter = [];

  /* 当前分页数据 */
  generalList: IListItem[] = [];
  pagination: {
    current: number;
    count: number;
    limit: number;
    data: IListItem[];
  } = {
    current: 1,
    count: 0,
    limit: 20,
    data: []
  };

  /* type栏左右切换数据 */
  typeWrapInfo = {
    showBtn: false,
    nextDisable: false,
    preDisable: false
  };

  firstCodeBgColor = '';

  created() {
    this.localValue = this.value;
    this.bizBgColor = this.$store.getters.bizBgColor || this.getRandomColor();
    const spaceTypeMap: Record<string, any> = {};
    this.bizList.forEach(item => {
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    });
    this.spaceTypeIdList = Object.keys(spaceTypeMap).map(key => ({
      id: key,
      name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
      styles: (this.theme === 'dark' ? SPACE_TYPE_MAP[key]?.dark : SPACE_TYPE_MAP[key]?.light) || {}
    }));
    this.getFirstCodeBgColor();
  }
  mounted() {
    this.storage = new Storage();
    this.commonListIds = this.storage.get(BIZ_SELECTOR_COMMON_IDS) || [];
  }

  /** 当前选中的业务 */
  get curentBizItem() {
    return this.bizList.find(item => item.id === this.localValue);
  }
  /** 业务名 */
  get bizName() {
    return this.curentBizItem?.space_name || '';
  }
  /** 业务首字母 */
  get bizSortNameKey() {
    const name = this.curentBizItem?.space_name || this.curentBizItem?.py_text || '';
    return name
      ?.replace?.(/^\[\d+\]/, '')
      ?.trim()
      ?.slice(0, 1)
      ?.toLocaleUpperCase();
  }
  /* 当前业务的ID */
  get curentBizId() {
    return this.curentBizItem?.space_type_id === ETagsType.BKCC
      ? `#${this.curentBizItem?.id}`
      : this.curentBizItem?.space_id || this.curentBizItem?.space_code || '';
  }

  /**  */
  get demo() {
    return this.bizList.find(item => item.is_demo);
  }

  @Watch('value')
  valueChange(val: number) {
    this.localValue = val;
    this.bizBgColor = this.getRandomColor();
    this.getFirstCodeBgColor();
  }
  @Watch('isShrink')
  isShrinkChange(val: boolean) {
    val && this.showBizList && this.popoverRef?.instance?.hide();
  }

  /** 搜索操作 */
  @Debounce(300)
  handleBizSearch(keyword?: string) {
    this.keyword = keyword;
    this.bizListFilter = this.getBizListFilter();
  }

  @Emit('change')
  handleBizChange(id: number) {
    this.popoverRef.instance.hide();
    this.localValue = id;
    this.getFirstCodeBgColor();
    this.handleCacheBizId(id);
    return id;
  }
  /** 业务列表 */
  getBizListFilter() {
    const stickyList: IListItem = {
      id: null,
      name: this.$tc('置顶'),
      children: []
    };
    const commonList: IListItem = {
      id: null,
      name: this.$tc('常用的'),
      children: []
    };
    const list: IListItem = {
      id: 'general',
      name: '' /** 普通列表 */,
      children: []
    };
    const keyword = this.keyword.trim().toLocaleLowerCase();
    const generalList = [];
    this.bizList.forEach(item => {
      let show = false;
      if (this.searchTypeId) {
        show =
          this.searchTypeId === 'bcs'
            ? item.space_type_id === 'bkci' && !!item.space_code
            : item.space_type_id === this.searchTypeId;
      }
      if ((show && keyword) || (!this.searchTypeId && !show)) {
        show =
          item.space_name.toLocaleLowerCase().indexOf(keyword) > -1 ||
          item.py_text.toLocaleLowerCase().indexOf(keyword) > -1 ||
          `${item.id}`.includes(keyword) ||
          `${item.space_id}`.toLocaleLowerCase().includes(keyword);
      }
      if (show) {
        const tags = [{ id: item.space_type_id, name: item.type_name, type: item.space_type_id }];
        if (item.space_type_id === 'bkci' && item.space_code) {
          tags.push({ id: 'bcs', name: this.$tc('容器项目'), type: 'bcs' });
        }
        const newItem = {
          ...item,
          name: item.space_name.replace(/\[.*?\]/, ''),
          tags
        };
        if (this.stickyList.includes(item.space_uid)) {
          /** 置顶数据 */
          stickyList.children.push(newItem as IListItem);
        } else if (this.commonListIds.includes(item.id) && this.isShowCommon) {
          /** 常用数据 */
          commonList.children.push(newItem as IListItem);
        } else {
          /** 普通列表 */
          // list.children.push(newItem as IListItem);
          generalList.push(newItem);
        }
      }
    });
    this.generalList = generalList;
    this.setPaginationData(true);
    list.children = this.pagination.data;
    const allList: IListItem[] = [];
    if (!!stickyList.children.length) {
      allList.push(stickyList);
    }
    if (!!commonList.children.length) {
      const temp = this.commonListIds.reduce((total, id) => {
        const item = commonList.children.find(item => item.id === id);
        if (!!item) total.push(item);
        return total;
      }, []);
      commonList.children = [...temp];
      allList.push(commonList);
    }
    !!list.children.length && allList.push(list);
    return allList;
  }
  setPaginationData(isInit = false) {
    const showData = this.generalList;
    this.pagination.count = showData.length;
    if (isInit) {
      this.pagination.current = 1;
      this.pagination.data = showData.slice(0, this.pagination.limit);
    } else {
      if (this.pagination.current * this.pagination.limit < this.pagination.count) {
        this.pagination.current += 1;
        const temp = showData.slice(
          (this.pagination.current - 1) * this.pagination.limit,
          this.pagination.current * this.pagination.limit
        );
        this.pagination.data.push(...temp);
      }
    }
  }
  getRandomColor() {
    const color = BIZ_COLOR_LIST[Math.floor(Math.random() * BIZ_COLOR_LIST.length)];
    this.$store.commit('app/SET_BIZ_BGCOLOR', color);
    return color;
  }
  /**
   * 更新常用业务id以及缓存的ids, 更新最常用的在数据前面
   * @param id 业务id
   */
  handleCacheBizId(id: number) {
    const leng = this.commonListIds.length;
    const isExist = this.commonListIds.includes(id);
    let newIds = [...this.commonListIds];
    if (isExist) {
      newIds = newIds.filter(item => item !== id);
      newIds.unshift(id);
    } else {
      newIds.unshift(id);
      leng >= BIZ_SELECTOR_COMMON_MAX && (newIds.length = BIZ_SELECTOR_COMMON_MAX);
    }
    this.commonListIds = newIds;
    this.storage.set(BIZ_SELECTOR_COMMON_IDS, this.commonListIds);
  }

  /** 设置下拉列表的宽度 */
  handleSetListWidth() {
    this.bizListFilter = this.getBizListFilter();
    const react = this.$el.getBoundingClientRect();
    this.listWidth = react.width <= this.minWidth ? this.minWidth : react.width;
    this.showBizList = !this.showBizList;
    setTimeout(() => {
      this.menuSearchInput.focus();
    }, 100);
    /** 防止渲染在父级元素tippy宽度计算错误问题 */
    this.popoverRef.instance.popper.querySelector('.tippy-tooltip').style.width = `${this.listWidth}px`;
    this.zIndex &&
      this.popoverRef.instance.set({
        zIndex: this.zIndex
      });
    this.typeListWrapNextPreShowChange();
  }
  /** 点击申请权限 */
  async handleGetBizAuth() {
    const data = await authorityStore.handleGetAuthDetail('view_business_v2');
    if (!data.apply_url) return;
    try {
      if (self === top) {
        window.open(data.apply_url, '__blank');
      } else {
        (top as any).BLUEKING.api.open_app_by_other('bk_iam', data.apply_url);
      }
    } catch (_) {
      // 防止跨域问题
      window.open(data.apply_url, '__blank');
    }
  }
  @Emit('openSpaceManager')
  handleOpenSpaceManager() {
    this.handleSearchBlur();
  }

  /** 搜索框失焦事件 */
  handleSearchBlur() {
    setTimeout(() => {
      const popover = this.popoverRef;
      const isVisible = popover?.instance?.state?.isVisible;
      if (isVisible) popover?.hideHandler();
    }, 200);
  }

  /**
   * @description: 跳转demo业务
   */
  handleToDemo() {
    if (this.demo?.id) {
      if (+this.$store.getters.bizId === +this.demo.id) {
        location.reload();
      } else {
        /** 切换为demo业务 */
        this.$store.commit('app/handleChangeBizId', {
          bizId: this.demo.id,
          ctx: this
        });
      }
    }
  }

  handleContentMouseDown(e: MouseEvent) {
    /**
     * 解决输入框文本无法双击选中的bug
     * 原因:因为点击内容区域时，会执行取消默认行为函数，导致输入框文本无法双击选中
     * 方案：当点击输入框区域时，不执行后面取消默认行为函数
     */
    if (this.menuSearchInput.$el.contains(e.target)) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
  }
  handleSearchType(typeId: string) {
    this.searchTypeId = typeId === this.searchTypeId ? '' : typeId;
    this.bizListFilter = this.getBizListFilter();
  }

  handleScroll(event) {
    const el = event.target;
    const { scrollHeight, scrollTop, clientHeight } = el;
    if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
      this.setPaginationData(false);
      const generalData = this.bizListFilter.find(item => item.id === 'general');
      if (generalData?.children) {
        generalData.children = this.pagination.data;
      }
    }
  }

  /* 是否展示type栏左右切换按钮 */
  typeListWrapNextPreShowChange() {
    this.$nextTick(() => {
      const hasScroll = this.typeListRef.scrollWidth > this.typeListRef.clientWidth;
      this.typeWrapInfo.showBtn = hasScroll;
      this.typeWrapInfo.preDisable = true;
    });
  }

  /**
   * @description 左右切换type栏
   * @param type
   */
  handleTypeWrapScrollChange(type: 'pre' | 'next') {
    const smoothScrollTo = (element: HTMLDivElement, targetPosition: number, duration: number, callback) => {
      const startPosition = element.scrollLeft;
      const distance = targetPosition - startPosition;
      const startTime = new Date().getTime();
      const easeOutCubic = t => 1 - Math.pow(1 - t, 3);
      const scroll = () => {
        const elapsed = new Date().getTime() - startTime;
        const progress = easeOutCubic(Math.min(elapsed / duration, 1));
        element.scrollLeft = startPosition + distance * progress;
        if (progress < 1) requestAnimationFrame(scroll);
        callback();
      };
      scroll();
    };
    let target = 0;
    const speed = 100;
    const duration = 300;
    const { scrollWidth, scrollLeft, clientWidth } = this.typeListRef;
    const total = scrollWidth - clientWidth;
    if (type === 'next') {
      const temp = scrollLeft + speed;
      target = temp > total ? total : temp;
    } else {
      const temp = scrollLeft - speed;
      target = temp < 0 ? 0 : temp;
    }
    smoothScrollTo(this.typeListRef, target, duration, () => {
      this.typeWrapInfo.nextDisable = this.typeListRef.scrollLeft > total - 1;
      this.typeWrapInfo.preDisable = this.typeListRef.scrollLeft === 0;
    });
  }

  /* 当前业务的tag颜色 多个tag取第一个 */
  getFirstCodeBgColor() {
    let tags = [];
    this.bizList.forEach(item => {
      if (item.id === this.localValue) {
        tags = [item.space_type_id];
        if (item.space_type_id === 'bkci' && item.space_code) {
          tags.push('bcs');
        }
      }
    });
    this.firstCodeBgColor =
      SPACE_FIRST_CODE_COLOR_MAP[tags?.[0] || 'default']?.[this.theme]?.backgroundColor || '#63656E';
  }

  render() {
    const firstCode = (
      <span
        class='biz-name-first-code'
        style={{ backgroundColor: this.firstCodeBgColor }}
      >
        {this.bizSortNameKey}
      </span>
    );
    return (
      <div class={['biz-select-wrap', this.theme]}>
        <bk-popover
          ref='popoverRef'
          trigger='click'
          placement='bottom-start'
          theme={`${this.theme} common-popover list-${this.theme}`}
          animation='slide-toggle'
          ext-cls={`biz-select-list-${this.theme}`}
          arrow={false}
          offset={-1}
          distance={16}
          width={this.listWidth}
          tippy-options={{
            appendTo: 'parent',
            onShow: this.handleSetListWidth,
            onHide: () => {
              this.showBizList = false;
              return true;
            }
          }}
        >
          <div class={['biz-select-target', { 'is-shrink': this.isShrink }]}>
            {this.isShrink ? (
              firstCode
            ) : (
              <div class='biz-select-target-main'>
                {firstCode}
                <span
                  class='biz-name-text'
                  v-bk-overflow-tips
                >
                  {this.bizName}
                  <span class='biz-name-text-id'>({this.curentBizId})</span>
                </span>
                <i
                  class='icon-monitor icon-mc-triangle-down'
                  style={{ transform: `rotate(${!this.showBizList ? '0deg' : '-180deg'})` }}
                ></i>
              </div>
            )}
          </div>
          <div
            slot='content'
            class={['biz-list-wrap', this.theme]}
            onMousedown={this.handleContentMouseDown}
            style={{ width: `${this.listWidth}px`, minWidth: `${this.minWidth}px` }}
          >
            <div class='biz-list-mian'>
              <div class='biz-search-wrap'>
                <bk-input
                  ref='menuSearchInput'
                  class='biz-search'
                  clearable={false}
                  left-icon='bk-icon icon-search'
                  placeholder={this.$t('输入关键字')}
                  behavior='simplicity'
                  value={this.keyword}
                  on-clear={() => this.handleBizSearch('')}
                  on-change={this.handleBizSearch}
                  on-blur={this.handleSearchBlur}
                />
              </div>
              {this.spaceTypeIdList.length > 1 && (
                <div class={['space-type-list-wrap', { 'show-btn': this.typeWrapInfo.showBtn }, this.theme]}>
                  <ul
                    class={'space-type-list'}
                    ref='typeList'
                  >
                    {this.spaceTypeIdList.map(item => (
                      <li
                        class='space-type-item'
                        style={{
                          ...item.styles,
                          borderColor: item.id === this.searchTypeId ? item.styles.color : 'transparent'
                        }}
                        key={item.id}
                        onClick={() => this.handleSearchType(item.id)}
                      >
                        {item.name}
                      </li>
                    ))}
                  </ul>
                  <div
                    class={['pre-btn', { disable: this.typeWrapInfo.preDisable }]}
                    onClick={() => !this.typeWrapInfo.preDisable && this.handleTypeWrapScrollChange('pre')}
                  >
                    <span class='icon-monitor icon-arrow-left'></span>
                  </div>
                  <div
                    class={['next-btn', { disable: this.typeWrapInfo.nextDisable }]}
                    onClick={() => !this.typeWrapInfo.nextDisable && this.handleTypeWrapScrollChange('next')}
                  >
                    <span class='icon-monitor icon-arrow-right'></span>
                  </div>
                </div>
              )}
              <ul
                class='biz-list'
                onScroll={this.handleScroll}
              >
                <List
                  list={this.bizListFilter}
                  checked={this.localValue}
                  theme={this.theme}
                  onSelected={this.handleBizChange}
                ></List>
              </ul>
            </div>
            {(process.env.APP !== 'external' || !!this.demo) && (
              <div class='biz-btn-groups'>
                {process.env.APP !== 'external' && (
                  <span
                    class='biz-btn'
                    onClick={this.handleOpenSpaceManager}
                  >
                    <i class='biz-btn-icon icon-monitor icon-mc-two-column'></i>
                    <span class='biz-btn-text'>{this.$t('空间管理')}</span>
                  </span>
                )}
                {/* <span class="biz-btn" onClick={this.handleGetBizAuth}>
                <i class="biz-btn-icon icon-monitor icon-jia"></i>
                <span class="biz-btn-text">{this.$t('申请业务权限')}</span>
              </span> */}
                {!!this.demo && (
                  <span
                    class='biz-btn'
                    onClick={this.handleToDemo}
                  >
                    <i class='biz-btn-icon icon-monitor icon-mc-demo'></i>
                    <span class='biz-btn-text'>{this.$t('DEMO')}</span>
                  </span>
                )}
              </div>
            )}
          </div>
        </bk-popover>
      </div>
    );
  }
}
