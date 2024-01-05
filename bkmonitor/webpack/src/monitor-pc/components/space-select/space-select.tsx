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

import { bizWithAlertStatistics } from '../../../monitor-api/modules/home';
import { Debounce } from '../../../monitor-common/utils';
import { SPACE_TYPE_MAP } from '../../common/constant';
import { ISpaceItem } from '../../types';
import { getEventPaths } from '../../utils';
import { ETagsType } from '../biz-select/list';

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
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('select') selectRef: HTMLDivElement;

  localValue: number[] = [];
  /* 搜索 */
  searchValue = '';
  /* 空间列表 */
  localSpaceList: IlocalSpaceList[] = [];
  /* 弹出实例 */
  popInstance = null;
  /* 添加可被移除的事件监听器 */
  controller: AbortController = null;
  /* 已选择部分文字 */
  valueStr = '';
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

  @Watch('value')
  handleWatchValue(v: number[]) {
    if (JSON.stringify(v) === JSON.stringify(this.localValue)) {
      return;
    }
    const defaultRadioListIds = defaultRadioList.map(d => d.id);
    this.localValue = [...v].map(b => (defaultRadioListIds.includes(String(b)) ? b : Number(b)));
    const strs = [];
    this.localSpaceList.forEach(item => {
      const has = this.localValue.includes(item.id);
      item.isCheck = has;
      if (has) {
        strs.push(item.name);
      }
    });
    this.valueStr = strs.join(',');
    this.sortSpaceList();
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
    });
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
      hideOnClick: false
    });
    this.popInstance?.show?.();
    this.isOpen = true;
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
    this.popInstance = null;
    this.controller?.abort?.();
    this.isOpen = false;
    this.localSpaceList.forEach(item => {
      item.show = true;
    });
  }

  /* 搜索 */
  @Debounce(300)
  handleSearchChange(value: string) {
    this.localSpaceList.forEach(item => {
      const keyword = value.trim().toLocaleLowerCase();
      item.show =
        item.space_name.toLocaleLowerCase().indexOf(keyword) > -1 ||
        item.py_text.toLocaleLowerCase().indexOf(keyword) > -1 ||
        `${item.id}`.includes(keyword) ||
        `${item.space_id}`.toLocaleLowerCase().includes(keyword);
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
  /* 获取当前选中的值 */
  getLocalValue() {
    const value = [];
    const strs = [];
    this.localSpaceList.forEach(item => {
      if (item.isCheck) {
        value.push(item.id);
        strs.push(item.name);
      }
    });
    this.valueStr = strs.join(',');
    this.localValue = value;
    this.isErr = !this.localValue.length;
    if (!!this.localValue.length) {
      this.handleChange();
    }
    this.sortSpaceList();
  }
  /* 清空 */
  handleClear() {
    if (!this.multiple || this.disabled) return;
    this.localValue = [];
    this.valueStr = '';
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

  render() {
    return (
      <span class={['space-select-component', { error: this.isErr }, { active: this.isOpen }]}>
        <div
          ref='select'
          class={[componentClassNames.selectInput, { single: !this.multiple }, { disabled: this.disabled }]}
          onMousedown={this.handleMousedown}
        >
          <span class='selected-text'>{this.valueStr}</span>
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
                placeholder={this.$t('请输入关键字')}
                v-model={this.searchValue}
                left-icon='bk-icon icon-search'
                behavior={'simplicity'}
                onChange={this.handleSearchChange}
              ></bk-input>
            </div>
            <div
              class='space-list'
              onScroll={this.handleScroll}
            >
              {this.pagination.data.map(item => (
                <div
                  class={['space-list-item', { active: !this.multiple && item.isCheck }]}
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
                          style={{ ...SPACE_TYPE_MAP[tag.id]?.light }}
                        >
                          {SPACE_TYPE_MAP[tag.id]?.name || ''}
                        </span>
                      ))
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </span>
    );
  }
}
