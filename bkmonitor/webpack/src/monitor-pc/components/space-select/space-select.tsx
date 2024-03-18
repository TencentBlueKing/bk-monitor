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
import { bizWithAlertStatistics } from 'monitor-api/modules/home';
import { Debounce } from 'monitor-common/utils';

import { ISpaceItem } from '../../types';
import { getEventPaths } from '../../utils';
import { ETagsType } from '../biz-select/list';

import { SPACE_TYPE_MAP } from './utils';

import './space-select.scss';

interface ItagsItem {
  id: string;
  name: string;
  type: ETagsType;
}
interface IlocalSpaceList extends ISpaceItem {
  isCheck?: boolean;
  tags?: ItagsItem[];
  name?: string;
  show?: boolean;
  isSpecial?: boolean;
  noAuth?: boolean;
  hasData?: boolean;
}
interface IProps {
  value?: string[];
  spaceList?: ISpaceItem[];
  multiple?: boolean;
  needAuthorityOption?: boolean;
  needAlarmOption?: boolean;
  needDefalutOptions?: boolean;
  disabled?: boolean;
  hasAuthApply?: boolean;
  currentSpace?: number | string;
  isCommonStyle?: boolean;
  onChange?: (value: number[]) => void;
}

const componentClassNames = {
  selectInput: 'space-select-content',
  pop: 'space-select-component-popover-content'
};
const rightIconClassName = 'space-select-right-icon';
// 有权限的业务id
const authorityBizId = -1;
// 有数据的业务id
const hasDataBizId = -2;

const defaultRadioList = [
  { id: 'all', bk_biz_id: 'all', name: window.i18n.tc('有权限的业务(最大20个)') },
  { id: 'settings', bk_biz_id: 'settings', name: window.i18n.tc('配置管理业务') },
  { id: 'notify', bk_biz_id: 'notify', name: window.i18n.tc('告警接收业务') }
];

const specialIds = [authorityBizId, hasDataBizId, ...defaultRadioList.map(d => d.id)];

@Component
export default class SpaceSelect extends tsc<
  IProps,
  {
    onApplyAuth: string[];
  }
> {
  /* 当前选中的空间 */
  @Prop({ default: () => [], type: Array }) value: number[];
  /* 当前的主空间（勾选的第一个空间） */
  @Prop({ default: () => null, type: [Number, String] }) currentSpace: number;
  /* 所有空间列表 */
  @Prop({ default: () => [], type: Array }) spaceList: ISpaceItem[];
  /* 是否为多选 */
  @Prop({ default: true, type: Boolean }) multiple: boolean;
  /* 是否包含我有权限的选项 */
  @Prop({ default: true, type: Boolean }) needAuthorityOption: boolean;
  /* 是否包含我有告警的选项 */
  @Prop({ default: true, type: Boolean }) needAlarmOption: boolean;
  /* 是否包含有权限的业务（最大20个）, 配置管理业务  告警接收业务 三个选项  */
  @Prop({ default: false, type: Boolean }) needDefalutOptions: boolean;
  /* 禁用 */
  @Prop({ default: false, type: Boolean }) disabled: boolean;
  /* 是否包含申请权限功能 */
  @Prop({ default: false, type: Boolean }) hasAuthApply: boolean;
  /*  */
  @Prop({ default: true, type: Boolean }) isCommonStyle: boolean;

  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('select') selectRef: HTMLDivElement;
  @Ref('typeList') typeListRef: HTMLDivElement;

  localValue: number[] = [];
  /* 当前的主空间 */
  localCurrentSpace: number = null;
  /* 搜索 */
  searchValue = '';
  /* 空间列表 */
  localSpaceList: IlocalSpaceList[] = [];
  /* 空间类型列表 */
  spaceTypeIdList = [];
  /* 当前选中的空间类型 */
  searchTypeId = '';
  /* 弹出实例 */
  popInstance = null;
  /* 添加可被移除的事件监听器 */
  controller: AbortController = null;
  /* 已选择部分文字 */
  valueStr = '';
  /* 已选择部分文字（包含id） */
  valueStrList = [];
  /* 是否标红 */
  isErr = false;
  /* 是否弹出弹窗 */
  isOpen = false;
  /* 当前分页数据 */
  pagination: {
    current: number;
    count: number;
    limit: number;
    data: IlocalSpaceList[];
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

  /* 是否需要当前空间功能 */
  get needCurSpace() {
    return this.currentSpace !== null;
  }

  @Watch('value')
  handleWatchValue(v: number[]) {
    if (JSON.stringify(v) === JSON.stringify(this.localValue)) {
      return;
    }
    const defaultRadioListIds = defaultRadioList.map(d => d.id);
    this.localValue = [...v].map(b => (defaultRadioListIds.includes(String(b)) ? b : Number(b)));
    const strs = [];
    const strList = [];
    this.localSpaceList.forEach(item => {
      const has = this.localValue.includes(item.id);
      item.isCheck = has;
      if (has) {
        strs.push(item.name);
        strList.push({
          name: item.name,
          id: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code
        });
      }
    });
    this.valueStr = strs.join(',');
    this.valueStrList = strList;
    this.sortSpaceList();
  }
  @Watch('currentSpace', { immediate: true })
  handleWatchCureentSpace(v: number) {
    if (v !== null) {
      this.localCurrentSpace = v;
    }
  }

  @Emit('change')
  handleChange() {
    return this.localValue;
  }

  created() {
    this.localSpaceList = this.getSpaceList(this.spaceList);
    const nullItem = {
      space_name: '',
      isSpecial: true,
      tags: [],
      isCheck: false,
      show: true,
      py_text: '',
      pyf_text: '',
      space_id: ''
    };
    if (this.needAlarmOption) {
      this.localSpaceList.unshift({
        ...nullItem,
        bk_biz_id: hasDataBizId,
        id: hasDataBizId,
        name: this.$t('-我有告警的空间-')
      } as any);
    }
    if (this.needAuthorityOption) {
      this.localSpaceList.unshift({
        ...nullItem,
        bk_biz_id: authorityBizId,
        id: authorityBizId,
        name: this.$t('-我有权限的空间-')
      } as any);
    }
    if (this.needDefalutOptions) {
      this.localSpaceList = [...defaultRadioList.map(d => ({ ...nullItem, ...d })), ...this.localSpaceList] as any;
    }
    if (this.hasAuthApply) {
      this.setAlllowed();
    } else {
      if (this.value.length && !this.localValue.length) {
        this.handleWatchValue(this.value);
      }
      this.setPaginationData(true);
    }
  }

  /* 获取权限信息 */
  async setAlllowed() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { business_list, business_with_alert, business_with_permission } = await bizWithAlertStatistics().catch(
      () => ({})
    );
    const allBizList = business_list.map(item => ({
      id: item.bk_biz_id,
      name: item.bk_biz_name
    }));
    // const businessWithPermissionSet = new Set();
    const curidsSet = new Set();
    this.localSpaceList.forEach(item => {
      if (!specialIds.includes(item.id)) {
        curidsSet.add(item.id);
      }
    });
    const nullItem = {
      space_name: '',
      isSpecial: false,
      tags: [],
      isCheck: false,
      show: true,
      py_text: '',
      space_id: '',
      space_type_id: ETagsType.BKCC
    };
    const otherSpaces = [];
    if (business_with_alert?.length) {
      business_with_alert.forEach(item => {
        if (!curidsSet.has(item.bk_biz_id)) {
          curidsSet.add(item.bk_biz_id);
          otherSpaces.push({
            ...nullItem,
            ...item,
            id: item.bk_biz_id,
            name: item.bk_biz_name,
            noAuth: true,
            hasData: true
          });
        }
      });
    }
    const data =
      business_with_permission.map(item => ({
        ...item,
        id: item.bk_biz_id,
        name: `[${item.bk_biz_id}] ${item.bk_biz_name}`
      })) || [];
    this.value.forEach(id => {
      const bizItem = allBizList.find(set => set.id === id);
      if (bizItem && !data.some(set => set.id === id)) {
        if (!curidsSet.has(bizItem.id)) {
          curidsSet.add(bizItem.id);
          otherSpaces.push({
            ...nullItem,
            ...bizItem,
            id: bizItem.id,
            name: bizItem.name,
            noAuth: true,
            hasData: false
          });
        }
      }
    });
    this.localSpaceList.push(...otherSpaces);
    this.localValue = [];
    this.handleWatchValue(this.value);
    this.setPaginationData(true);
  }

  setPaginationData(isInit = false) {
    const showData = this.localSpaceList.filter(item => item.show);
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

  destroyed() {
    this.handlePopoverHidden();
  }

  /* 整理space_list */
  getSpaceList(spaceList: ISpaceItem[]) {
    const list = [];
    const spaceTypeMap: Record<string, any> = {};
    spaceList.forEach(item => {
      const tags = [{ id: item.space_type_id, name: item.type_name, type: item.space_type_id }];
      if (item.space_type_id === 'bkci' && item.space_code) {
        tags.push({ id: 'bcs', name: this.$tc('容器项目'), type: 'bcs' });
      }
      const newItem = {
        ...item,
        name: item.space_name.replace(/\[.*?\]/, ''),
        tags,
        isCheck: false,
        show: true
      };
      list.push(newItem);
      /* 空间类型 */
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    });
    this.spaceTypeIdList = Object.keys(spaceTypeMap).map(key => ({
      id: key,
      name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
      styles: SPACE_TYPE_MAP[key] || SPACE_TYPE_MAP.default
    }));
    return list;
  }
  /* 显示弹出层 */
  handleMousedown() {
    if (this.popInstance || this.disabled) {
      return;
    }
    const target = this.selectRef;
    this.popInstance = this.$bkPopover(target, {
      content: this.wrapRef,
      trigger: 'manual',
      interactive: true,
      theme: 'light common-monitor',
      arrow: false,
      placement: 'bottom-start',
      boundary: 'window',
      hideOnClick: false,
      distance: 5
    });
    this.popInstance?.show?.();
    this.isOpen = true;
    this.sortSpaceList();
    this.setPaginationData(true);
    setTimeout(() => {
      this.addMousedownEvent();
    }, 50);
  }
  /* 添加清楚弹出层事件 */
  addMousedownEvent() {
    this.controller?.abort?.();
    this.controller = new AbortController();
    document.addEventListener('mousedown', this.handleMousedownRemovePop, { signal: this.controller.signal });
    this.typeListWrapNextPreShowChange();
  }
  /* 清除弹出实例 */
  handleMousedownRemovePop(event: Event) {
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
    // 关闭侧栏组件时需要关闭弹层
    if (pathsClass.some(c => ['slide-leave', 'bk-sideslider-closer'].some(s => (c?.indexOf(s) || -1) >= 0))) {
      this.handlePopoverHidden();
      return;
    }
    if (!this.localValue.length) {
      this.isErr = true;
      return;
    }
    if (pathsClass.includes(rightIconClassName)) {
      return;
    }
    if (pathsClass.includes(componentClassNames.pop)) {
      return;
    }
    this.handlePopoverHidden();
  }
  /* 清楚弹出层 */
  handlePopoverHidden() {
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.searchValue = '';
    this.searchTypeId = '';
    this.popInstance = null;
    this.controller?.abort?.();
    this.isOpen = false;
    this.localSpaceList.forEach(item => {
      item.show = true;
    });
    if (this.needCurSpace) {
      this.resetCurBiz();
    }
    if (!!this.localValue.length && JSON.stringify(this.value) !== JSON.stringify(this.localValue)) {
      setTimeout(() => {
        this.handleChange();
      }, 50);
    }
  }

  /* 搜索 */
  @Debounce(300)
  handleSearchChange(value: string) {
    this.localSpaceList.forEach(item => {
      const keyword = value.trim().toLocaleLowerCase();
      const typeShow = (() => {
        if (!!this.searchTypeId) {
          return this.searchTypeId === 'bcs'
            ? item.space_type_id === 'bkci' && !!item.space_code
            : item.space_type_id === this.searchTypeId;
        }
        return true;
      })();
      const searchShow =
        item.space_name.toLocaleLowerCase().indexOf(keyword) > -1 ||
        item.py_text.indexOf(keyword) > -1 ||
        item.pyf_text.indexOf(keyword) > -1 ||
        `${item.id}`.includes(keyword) ||
        `${item.space_id}`.toLocaleLowerCase().includes(keyword) ||
        item.tags?.some(t => !!keyword && t.name.indexOf(keyword) > -1);
      item.show = typeShow && searchShow;
    });
    this.setPaginationData(true);
  }
  selectOption(item: IlocalSpaceList, v: boolean) {
    if (this.multiple) {
      this.localSpaceList.forEach(l => {
        if (specialIds.includes(item.id)) {
          if (l.id === item.id) {
            l.isCheck = v;
          } else {
            l.isCheck = false;
          }
        } else {
          if (specialIds.includes(l.id)) {
            l.isCheck = false;
          } else if (l.id === item.id) {
            l.isCheck = v;
          }
        }
      });
    } else {
      this.localSpaceList.forEach(l => {
        l.isCheck = l.id === item.id;
      });
    }
  }
  /* check */
  handleSelectOption(item: IlocalSpaceList) {
    if (!!item.noAuth && !item.hasData) {
      return;
    }
    this.selectOption(item, !item.isCheck);
    this.getLocalValue();
    this.setPaginationData(true);
    if (!this.multiple) {
      this.handlePopoverHidden();
    }
  }
  handleCheckOption(v: boolean, item: IlocalSpaceList) {
    this.selectOption(item, v);
    this.getLocalValue();
    this.setPaginationData(true);
  }
  /**
   * @description 设为当前空间
   * @param item
   */
  handleSetCurBiz(item: IlocalSpaceList) {
    this.localCurrentSpace = item.id;
    if (!item.isCheck) {
      this.handleSelectOption(item);
    }
  }
  /**
   * @description 如当前空间切换，则刷新页面
   */
  resetCurBiz() {
    if (+this.localCurrentSpace === +this.currentSpace) {
      return;
    }
    this.$store.commit('app/SET_BIZ_ID', +this.localCurrentSpace);
    const serachParams = new URLSearchParams({ bizId: `${+this.localCurrentSpace}` });
    const newUrl = `${window.location.pathname}?${serachParams.toString()}#${this.$route.fullPath}`;
    history.replaceState({}, '', newUrl);
  }
  /* 获取当前选中的值 */
  getLocalValue() {
    const value = [];
    const strs = [];
    const strList = [];
    this.localSpaceList.forEach(item => {
      if (item.isCheck) {
        value.push(item.id);
        strs.push(item.name);
        strList.push({
          name: item.name,
          id: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code
        });
      }
    });
    this.valueStr = strs.join(',');
    this.valueStrList = strList;
    this.localValue = value;
    this.isErr = !this.localValue.length;
    // if (!!this.localValue.length) {
    //   this.handleChange();
    // }
    this.sortSpaceList();
  }
  /* 清空 */
  handleClear() {
    if (!this.multiple || this.disabled) return;
    this.localValue = [];
    this.valueStr = '';
    this.valueStrList = [];
    this.localSpaceList.forEach(item => {
      item.isCheck = false;
    });
    this.setPaginationData(true);
  }

  /* 排序，已选择默认置于我有告警的下方 */
  sortSpaceList() {
    const list = this.localSpaceList.map(item => ({
      ...item,
      sort: (() => {
        if (specialIds.includes(item.id)) {
          return 4;
        }
        if (+this.localCurrentSpace === +item.id) {
          return 3;
        }
        return this.localValue.includes(item.id) ? 2 : 1;
      })()
    }));
    this.localSpaceList = list.sort((a, b) => b.sort - a.sort);
  }

  handleScroll(event) {
    const el = event.target;
    const { scrollHeight, scrollTop, clientHeight } = el;
    if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
      this.setPaginationData(false);
    }
  }
  @Emit('applyAuth')
  async handleApplyAuth(bizId: string | number) {
    this.handlePopoverHidden();
    return [bizId];
  }
  /**
   * @description 切换当前空间类型
   * @param typeId
   */
  handleSearchType(typeId: string) {
    this.searchTypeId = typeId === this.searchTypeId ? '' : typeId;
    this.handleSearchChange(this.searchValue);
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

  render() {
    return (
      <span
        class={[
          'space-select-component',
          { 'space-select-component-common-style': this.isCommonStyle },
          { error: this.isErr },
          { active: this.isOpen }
        ]}
      >
        <div
          ref='select'
          class={[componentClassNames.selectInput, { single: !this.multiple }, { disabled: this.disabled }]}
          onMousedown={this.handleMousedown}
        >
          {this.isCommonStyle && <span class='selected-wrap-title'>{`${this.$t('空间筛选')} : `}</span>}
          <span class='selected-text'>
            {this.isCommonStyle
              ? this.valueStrList.map((item, index) => (
                  <span
                    class='selected-text-item'
                    key={index}
                  >
                    {index !== 0 ? `   , ${item.name}` : item.name}
                    {!!item.id && <span class='selected-text-id'>({item.id})</span>}
                  </span>
                ))
              : this.valueStr}
          </span>
          <span
            class={rightIconClassName}
            onClick={this.handleClear}
          >
            <span class='icon-monitor icon-arrow-down'></span>
            {this.multiple && <span class='icon-monitor icon-mc-close-fill'></span>}
          </span>
        </div>
        <div style={{ display: 'none' }}>
          <div
            class={componentClassNames.pop}
            ref='wrap'
          >
            <div class='search-input'>
              <bk-input
                placeholder={this.$t('请输入关键字或标签')}
                v-model={this.searchValue}
                left-icon='bk-icon icon-search'
                behavior={'simplicity'}
                onChange={this.handleSearchChange}
              ></bk-input>
            </div>
            <div class={['space-type-list-wrap', { 'show-btn': this.typeWrapInfo.showBtn }]}>
              <ul
                class={'space-type-list'}
                ref='typeList'
              >
                {this.spaceTypeIdList.map(item => (
                  <li
                    class={[
                      'space-type-item',
                      item.id,
                      { 'hover-active': item.id !== this.searchTypeId },
                      { selected: item.id === this.searchTypeId },
                      item.id
                    ]}
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
            <div
              class='space-list'
              onScroll={this.handleScroll}
            >
              {this.pagination.data.map(item => (
                <div
                  class={[
                    'space-list-item',
                    { active: !this.multiple && item.isCheck },
                    {
                      'no-hover-btn':
                        !this.needCurSpace ||
                        +this.localCurrentSpace === +item.id ||
                        specialIds.includes(item.id) ||
                        (!!item.noAuth && !item.hasData)
                    }
                  ]}
                  key={item.id}
                  onClick={() => this.handleSelectOption(item)}
                >
                  {this.multiple && (
                    <div onClick={(e: Event) => e.stopPropagation()}>
                      <bk-checkbox
                        disabled={!!item.noAuth && !item.hasData}
                        value={item.isCheck}
                        onChange={v => this.handleCheckOption(v, item)}
                      ></bk-checkbox>
                    </div>
                  )}
                  <span class='space-name'>
                    <span
                      class={['name', { disabled: !!item.noAuth && !item.hasData }]}
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </span>
                    {!item?.isSpecial && (
                      <span
                        class='id'
                        v-bk-overflow-tips
                      >
                        ({item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code})
                      </span>
                    )}
                    {+this.localCurrentSpace === +item.id && (
                      <span
                        class='icon-monitor icon-dingwei1 cur-position'
                        v-bk-tooltips={{
                          content: this.$t('当前空间'),
                          placements: ['top']
                        }}
                      ></span>
                    )}
                  </span>
                  <span class='space-tags'>
                    {!!item.noAuth && !item.hasData ? (
                      <bk-button
                        class='auth-button'
                        size='small'
                        text
                        theme='primary'
                        onClick={() => this.handleApplyAuth(item.id)}
                      >
                        {this.$t('申请权限')}
                      </bk-button>
                    ) : (
                      item.tags?.map?.(tag => (
                        <span
                          class='space-tags-item'
                          style={{ ...(SPACE_TYPE_MAP[tag.id] || SPACE_TYPE_MAP.default) }}
                        >
                          {SPACE_TYPE_MAP[tag.id]?.name || this.$t('未知')}
                        </span>
                      ))
                    )}
                  </span>
                  {this.needCurSpace && (
                    <span class='space-hover-btn'>
                      <bk-button
                        class='auth-button'
                        size='small'
                        text
                        theme='primary'
                        onClick={e => {
                          e.stopPropagation();
                          this.handleSetCurBiz(item);
                        }}
                      >
                        {this.$t('设为当前空间')}
                      </bk-button>
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </span>
    );
  }
}
