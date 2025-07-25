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

import { Debounce } from 'monitor-common/utils/utils';

import { SPACE_TYPE_MAP } from '../../../../common/constant';
import List, { type IListItem } from '../../../../components/biz-select/list';
import { Storage } from '../../../../utils';

import type { ISpaceItem } from '../../../../types';

import './home-biz-list.scss';

/** 业务组件常用的业务缓存key */
const BIZ_SELECTOR_COMMON_IDS = 'BIZ_SELECTOR_COMMON_IDS';

export type ThemeType = 'dark' | 'light';
interface IEvents {
  onChange: number;
  onOpenSpaceManager: () => void;
}
interface IProps {
  bizList: ISpaceItem[];
  isShowCommon?: boolean;
  minWidth?: number;
  stickyList?: string[];
  theme?: ThemeType;
  zIndex?: number;
}

/**
 * 业务选择器组件
 */
@Component
export default class HomeBizSelect extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) bizList: ISpaceItem[];
  @Prop({ default: true, type: Boolean }) isShowCommon: boolean;
  @Prop({ default: null, type: Number }) zIndex: number;
  @Prop({ default: 200, type: Number }) minWidth: number;
  @Prop({ default: () => [], type: Array }) stickyList: string[];
  @Prop({
    default: 'light',
    type: String,
    validator: (val: string) => ['dark', 'light'].includes(val),
  })
  theme: ThemeType;
  @Ref() menuSearchInput: any;
  @Ref() homePopoverRef: any;
  @Ref('typeList') typeListRef: HTMLDivElement;

  showBizList = false;
  keyword = '';

  listWidth = 200;

  storage: Storage = null;
  commonListIds: number[] = [];
  spaceTypeIdList: { id: string; name: string; styles: any }[] = [];
  searchTypeId = '';

  bizListFilter = [];

  generalList: IListItem[] = [];
  pagination: {
    count: number;
    current: number;
    data: IListItem[];
    limit: number;
  } = {
    current: 1,
    count: 0,
    limit: 20,
    data: [],
  };

  typeWrapInfo = {
    showBtn: false,
    nextDisable: false,
    preDisable: false,
  };

  firstCodeBgColor = '';

  created() {
    const spaceTypeMap: Record<string, any> = {};
    for (const item of this.bizList) {
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    }
    this.spaceTypeIdList = Object.keys(spaceTypeMap).map(key => ({
      id: key,
      name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
      styles: (this.theme === 'dark' ? SPACE_TYPE_MAP[key]?.dark : SPACE_TYPE_MAP[key]?.light) || {},
    }));
  }

  mounted() {
    this.storage = new Storage();
    this.commonListIds = this.storage.get(BIZ_SELECTOR_COMMON_IDS) || [];
  }

  @Debounce(300)
  handleBizSearch(keyword?: string) {
    this.keyword = keyword;
    this.bizListFilter = this.getBizListFilter();
  }

  @Emit('change')
  handleBizChange(id: number) {
    this.homePopoverRef.instance.hide();
    return id;
  }

  getBizListFilter() {
    const stickyList: IListItem = {
      id: null,
      name: this.$tc('置顶'),
      children: [],
    };
    const commonList: IListItem = {
      id: null,
      name: this.$tc('常用的'),
      children: [],
    };
    const list: IListItem = {
      id: 'general',
      name: '',
      children: [],
    };
    const keyword = this.keyword.trim().toLocaleLowerCase();
    const listTemp = {
      stickyList: {
        preArr: [],
        nextArr: [],
      },
      commonList: {
        preArr: [],
        nextArr: [],
      },
      generalList: {
        preArr: [],
        nextArr: [],
      },
    };
    const setListTemp = (key: keyof typeof listTemp, item: IListItem, preciseMatch: boolean) => {
      if (preciseMatch) {
        listTemp[key].preArr.push(item);
      } else {
        listTemp[key].nextArr.push(item);
      }
    };
    const concatListTemp = (key: keyof typeof listTemp) => {
      const { preArr, nextArr } = listTemp[key];
      return [...preArr, ...nextArr];
    };

    for (const item of this.bizList) {
      let preciseMatch = false;
      let show = false;
      if (this.searchTypeId) {
        show =
          this.searchTypeId === 'bcs'
            ? item.space_type_id === 'bkci' && !!item.space_code
            : item.space_type_id === this.searchTypeId;
      }
      if ((show && keyword) || (!this.searchTypeId && !show)) {
        preciseMatch =
          item.space_name?.toLocaleLowerCase() === keyword ||
          item.py_text === keyword ||
          item.pyf_text === keyword ||
          `${item.id}` === keyword ||
          `${item.space_id}`.toLocaleLowerCase() === keyword;
        show =
          preciseMatch ||
          item.space_name?.toLocaleLowerCase().indexOf(keyword) > -1 ||
          item.py_text?.indexOf(keyword) > -1 ||
          item.pyf_text?.indexOf(keyword) > -1 ||
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
          tags,
        };
        if (this.stickyList.includes(item.space_uid)) {
          setListTemp('stickyList', newItem as IListItem, preciseMatch);
        } else if (this.commonListIds.includes(item.id) && this.isShowCommon) {
          setListTemp('commonList', newItem as IListItem, preciseMatch);
        } else {
          setListTemp('generalList', newItem as IListItem, preciseMatch);
        }
      }
    }
    this.generalList = concatListTemp('generalList');
    stickyList.children = concatListTemp('stickyList');
    this.setPaginationData(true);
    list.children = this.pagination.data;
    const allList: IListItem[] = [];
    if (stickyList.children.length) {
      allList.push(stickyList);
    }
    let preTemp = [];
    let nextTemp = [];
    if (listTemp.commonList.preArr.length) {
      preTemp = this.commonListIds.reduce((total, id) => {
        const item = listTemp.commonList.preArr.find(item => item.id === id);
        if (item) total.push(item);
        return total;
      }, []);
    }
    if (listTemp.commonList.nextArr.length) {
      nextTemp = this.commonListIds.reduce((total, id) => {
        const item = listTemp.commonList.nextArr.find(item => item.id === id);
        if (item) total.push(item);
        return total;
      }, []);
    }
    if (preTemp.length || nextTemp.length) {
      commonList.children = [...preTemp, ...nextTemp];
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

  handleSetListWidth() {
    this.bizListFilter = this.getBizListFilter();
    const react = this.$el.getBoundingClientRect();
    this.listWidth = react.width <= this.minWidth ? this.minWidth : react.width;
    this.showBizList = !this.showBizList;
    setTimeout(() => {
      this.menuSearchInput.focus();
    }, 100);
    this.homePopoverRef.instance.popper.querySelector('.tippy-tooltip').style.width = `${this.listWidth}px`;
    this.zIndex &&
      this.homePopoverRef.instance.set({
        zIndex: this.zIndex,
      });
    this.typeListWrapNextPreShowChange();
  }

  handleSearchBlur() {
    setTimeout(() => {
      const popover = this.homePopoverRef;
      const isVisible = popover?.instance?.state?.isVisible;
      if (isVisible) popover?.hideHandler();
    }, 200);
  }

  handleContentMouseDown(e: MouseEvent) {
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

  typeListWrapNextPreShowChange() {
    this.$nextTick(() => {
      const hasScroll = this.typeListRef?.scrollWidth > this.typeListRef?.clientWidth;
      this.typeWrapInfo.showBtn = hasScroll;
      this.typeWrapInfo.preDisable = true;
    });
  }

  handleTypeWrapScrollChange(type: 'next' | 'pre') {
    const smoothScrollTo = (element: HTMLDivElement, targetPosition: number, duration: number, callback) => {
      const startPosition = element.scrollLeft;
      const distance = targetPosition - startPosition;
      const startTime = new Date().getTime();
      const easeOutCubic = t => 1 - (1 - t) ** 3;
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

  render() {
    return (
      <div class={['new-biz-select-wrap', this.theme]}>
        <bk-popover
          ref='homePopoverRef'
          width={this.listWidth}
          ext-cls={`biz-select-list-${this.theme}`}
          tippy-options={{
            appendTo: 'parent',
            onShow: this.handleSetListWidth,
            onHide: () => {
              this.showBizList = false;
              this.handleBizSearch('');
              return true;
            },
          }}
          animation='slide-toggle'
          arrow={false}
          offset={'158, -6'}
          theme={`${this.theme} common-popover list-${this.theme}`}
          trigger='click'
        >
          <span class='add-task'>
            <i class='bk-icon icon-plus-circle' />
            {this.$t('添加业务')}
          </span>
          <div
            style={{ width: `${this.listWidth}px`, minWidth: `${this.minWidth}px` }}
            class={['biz-list-wrap', this.theme]}
            slot='content'
            onMousedown={this.handleContentMouseDown}
          >
            <div class='biz-list-mian'>
              <div class='biz-search-wrap'>
                <bk-input
                  ref='menuSearchInput'
                  class='biz-search'
                  behavior='simplicity'
                  clearable={false}
                  left-icon='bk-icon icon-search'
                  placeholder={this.$t('输入关键字')}
                  value={this.keyword}
                  on-blur={this.handleSearchBlur}
                  on-change={this.handleBizSearch}
                  on-clear={() => this.handleBizSearch('')}
                />
              </div>
              {this.spaceTypeIdList.length > 1 && (
                <div class={['space-type-list-wrap', { 'show-btn': this.typeWrapInfo.showBtn }, this.theme]}>
                  <ul
                    ref='typeList'
                    class={'space-type-list'}
                  >
                    {this.spaceTypeIdList.map(item => (
                      <li
                        key={item.id}
                        class={[
                          'space-type-item',
                          item.id,
                          { 'hover-active': item.id !== this.searchTypeId },
                          { selected: item.id === this.searchTypeId },
                          item.id,
                        ]}
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
                    <span class='icon-monitor icon-arrow-left' />
                  </div>
                  <div
                    class={['next-btn', { disable: this.typeWrapInfo.nextDisable }]}
                    onClick={() => !this.typeWrapInfo.nextDisable && this.handleTypeWrapScrollChange('next')}
                  >
                    <span class='icon-monitor icon-arrow-right' />
                  </div>
                </div>
              )}
              <ul
                class='biz-list'
                onScroll={this.handleScroll}
              >
                <List
                  canSetDefaultSpace={false}
                  list={this.bizListFilter}
                  theme={this.theme}
                  onSelected={this.handleBizChange}
                />
              </ul>
            </div>
          </div>
        </bk-popover>
      </div>
    );
  }
}
