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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { bizWithAlertStatistics } from 'monitor-api/modules/home';
import { Debounce } from 'monitor-common/utils';
import {
  DIRECTORY_SPACE_TYPES,
  queryAlertSpaceDirectory,
  querySpaceDirectory,
  SpaceDirectoryPager,
  supportsSpaceDirectoryPages,
} from 'monitor-common/utils/space-directory';
import { canSwitchSpace } from 'monitor-common/utils/space-entry';

import { getEventPaths } from '../../utils';
import { ETagsType } from '../biz-select/list';
import { SPACE_TYPE_MAP } from './utils';

import type { ISpaceItem } from '../../types';

import './space-select.scss';
interface ILocalSpaceList extends ISpaceItem {
  hasData?: boolean;
  isCheck?: boolean;
  isSpecial?: boolean;
  name?: string;
  noAuth?: boolean;
  preciseMatch?: boolean;
  show?: boolean;
  tags?: ITagsItem[];
}
interface IProps {
  currentSpace?: number | string;
  disabled?: boolean;
  hasAuthApply?: boolean;
  isAutoSelectCurrentSpace?: boolean;
  isCommonStyle?: boolean;
  multiple?: boolean;
  needAlarmOption?: boolean;
  needAuthorityOption?: boolean;
  needDefaultOptions?: boolean;
  needIncidentOption?: boolean;
  remote?: boolean;
  spaceList?: ISpaceItem[];
  value?: string[];
  onChange?: (value: number[]) => void;
}
interface ITagsItem {
  id: string;
  name: string;
  type: ETagsType;
}
const componentClassNames = {
  selectInput: 'space-select-content',
  pop: 'space-select-component-popover-content',
};
const rightIconClassName = 'space-select-right-icon';
// 有权限的业务id
const authorityBizId = -1;
// 有数据的业务id
const hasDataBizId = -2;
const defaultRadioList = [
  { id: 'all', bk_biz_id: 'all', name: window.i18n.tc('有权限的业务(最大20个)') },
  { id: 'settings', bk_biz_id: 'settings', name: window.i18n.tc('配置管理业务') },
  { id: 'notify', bk_biz_id: 'notify', name: window.i18n.tc('告警接收业务') },
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
  @Prop({ default: false, type: Boolean }) remote: boolean;
  @Prop({ default: () => [], type: Array }) spaceList: ISpaceItem[];
  /* 是否为多选 */
  @Prop({ default: true, type: Boolean }) multiple: boolean;
  /* 是否包含我有权限的选项 */
  @Prop({ default: true, type: Boolean }) needAuthorityOption: boolean;
  /* 是否包含我有告警的选项 */
  @Prop({ default: true, type: Boolean }) needAlarmOption: boolean;
  /* 是否包含有权限的业务（最大20个）, 配置管理业务  告警接收业务  三个选项  */
  @Prop({ default: false, type: Boolean }) needDefaultOptions: boolean;
  /* 禁用 */
  @Prop({ default: false, type: Boolean }) disabled: boolean;
  /* 是否包含申请权限功能 */
  @Prop({ default: false, type: Boolean }) hasAuthApply: boolean;
  /*  */
  @Prop({ default: true, type: Boolean }) isCommonStyle: boolean;
  /* 是否包含我有故障的选项 */
  @Prop({ default: false, type: Boolean }) needIncidentOption: boolean;
  /* 是否自动选择为当前空间（将空间添加到url上）单选时自动选择为当前空间, 多选时则（选择的第一个空间为当前空间） */
  @Prop({ default: false, type: Boolean }) isAutoSelectCurrentSpace: boolean;
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('select') selectRef: HTMLDivElement;
  @Ref('typeList') typeListRef: HTMLDivElement;
  @Ref('searchInput') searchInputRef: any;
  localValue: number[] = [];
  /* 当前的主空间 */
  localCurrentSpace: number = null;
  /* 搜索 */
  searchValue = '';
  /* 空间列表 */
  localSpaceList: ILocalSpaceList[] = [];
  pages = new SpaceDirectoryPager();
  alertPages = new SpaceDirectoryPager(queryAlertSpaceDirectory);
  selectedRows: ISpaceItem[] = [];
  selectedRequest = 0;
  selectionIncomplete = false;

  get paged() {
    return this.remote && supportsSpaceDirectoryPages();
  }

  async resolveSelection(value: number[], refresh = false) {
    const request = ++this.selectedRequest;
    if (!this.paged) return;
    this.selectionIncomplete = false;
    const selected = new Set(value);
    const known = new Map<number, ISpaceItem>();
    for (const row of [...this.selectedRows, ...this.alertPages.items, ...this.pages.items]) {
      if (selected.has(row.id)) known.set(row.id, row);
    }
    this.selectedRows = [...known.values()];
    const found = new Set(this.selectedRows.map(row => row.id));
    const missing = value.filter(id => Number.isFinite(id) && !specialIds.includes(id) && (refresh || !found.has(id)));
    for (let i = 0; i < missing.length; i += 100) {
      const ids = missing.slice(i, i + 100);
      const page = await querySpaceDirectory({ bkBizIds: ids, pageSize: 100 }).catch(() => null);
      if (request !== this.selectedRequest) return;
      if (!page) {
        this.selectionIncomplete = true;
        break;
      }
      const resolved = new Set(page.items.map(row => row.id));
      const checked = page.partial ? resolved : new Set(ids);
      this.selectedRows = this.selectedRows.filter(row => !checked.has(row.id)).concat(page.items);
      if (page.partial) {
        this.selectionIncomplete = true;
        continue;
      }
      if (this.hasAuthApply) {
        const remaining = ids.filter(id => !resolved.has(id));
        if (remaining.length) {
          const alerts = await queryAlertSpaceDirectory({ bkBizIds: remaining, pageSize: 100 }).catch(() => null);
          if (request !== this.selectedRequest) return;
          if (alerts) this.selectedRows.push(...alerts.items);
          if (!alerts || alerts.partial) this.selectionIncomplete = true;
        }
      }
    }
    if (missing.length) this.initLocalSpaceList();
  }

  async loadDirectory(append = false) {
    if (!this.isOpen || !this.paged) return false;
    const options = { query: this.searchValue, type: this.searchTypeId };
    const pagers = this.hasAuthApply ? [this.pages, this.alertPages] : [this.pages];
    const changed = (
      await Promise.all(pagers.map(pager => (append ? pager.next() : pager.reset(options)).catch(() => false)))
    ).some(Boolean);
    if (changed) this.initLocalSpaceList();
    return changed;
  }
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
  private selectionSession = 0;
  /* 当前分页数据 */
  pagination: {
    count: number;
    current: number;
    data: ILocalSpaceList[];
    limit: number;
  } = {
    current: 1,
    count: 0,
    limit: 20,
    data: [],
  };
  /* type栏左右切换数据 */
  typeWrapInfo = {
    showBtn: false,
    nextDisable: false,
    preDisable: false,
  };
  /** 键盘高亮项 id */
  highlightId: null | number | string = null;

  /* 是否需要当前空间功能 */
  get needCurSpace() {
    return this.currentSpace !== null;
  }
  @Watch('value')
  valueChanged(v: number[]) {
    this.handleWatchValue(v);
    void this.resolveSelection(this.localValue);
  }

  handleWatchValue(v: number[]) {
    const defaultRadioListIds = defaultRadioList.map(d => d.id);
    this.localValue = [...v].map(b => (defaultRadioListIds.includes(String(b)) ? b : Number(b)));
    const nameList = [];
    const strList = [];
    // biome-ignore lint/complexity/noForEach: <explanation>
    this.localSpaceList.forEach(item => {
      const has = this.localValue.includes(item.id);
      item.isCheck = has;
      if (has) {
        nameList.push(item.name);
        strList.push({
          name: item.name,
          id: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code,
        });
      }
    });
    if (this.paged) {
      const known = new Set(this.localSpaceList.map(item => item.id));
      for (const id of this.localValue) {
        if (!known.has(id)) {
          nameList.push(String(id));
          strList.push({ name: String(id), id: '' });
        }
      }
    }
    this.valueStr = nameList.join(',');
    this.valueStrList = strList;
    this.sortSpaceList();
  }
  @Watch('currentSpace', { immediate: true })
  handleWatchCurrentSpace(v: number) {
    if (v !== null) {
      this.localCurrentSpace = v;
    }
  }
  /** 初始化空间列表 */
  @Watch('spaceList')
  initLocalSpaceList() {
    const selected = this.isOpen ? this.localValue : this.value;
    const records = this.paged
      ? [
          ...new Map(
            [...this.selectedRows, ...this.alertPages.items, ...this.pages.items].map(row => [row.id, row])
          ).values(),
        ]
      : this.spaceList;
    this.localSpaceList = this.getSpaceList(records);
    const nullItem = {
      space_name: '',
      isSpecial: true,
      tags: [],
      isCheck: false,
      show: true,
      preciseMatch: false,
      py_text: '',
      pyf_text: '',
      space_id: '',
    };
    if (this.needAlarmOption) {
      this.localSpaceList.unshift({
        ...nullItem,
        bk_biz_id: hasDataBizId,
        id: hasDataBizId,
        name: this.$t('-我有告警的空间-'),
      } as any);
    }
    // if (this.needIncidentOption) {
    //   this.localSpaceList.unshift({
    //     ...nullItem,
    //     bk_biz_id: hasDataBizId,
    //     id: hasDataBizId,
    //     name: this.$t('-我有故障的空间-'),
    //   } as any);
    // }
    if (this.needAuthorityOption) {
      this.localSpaceList.unshift({
        ...nullItem,
        bk_biz_id: authorityBizId,
        id: authorityBizId,
        name: this.$t('-我有权限的空间-'),
      } as any);
    }
    if (this.needDefaultOptions) {
      this.localSpaceList = [...defaultRadioList.map(d => ({ ...nullItem, ...d })), ...this.localSpaceList] as any;
    }
    this.localValue = [];
    this.handleWatchValue(selected);
    if (this.paged && (this.searchValue || this.searchTypeId)) {
      const visible = new Set([...this.pages.items, ...this.alertPages.items].map(row => row.id));
      for (const row of this.localSpaceList) row.show = visible.has(row.id);
    }
    this.setPaginationData(true);
    if (!this.paged && this.hasAuthApply && window.space_list_state !== 'deferred') {
      this.setAllowed();
    }
  }
  @Watch('needAlarmOption')
  handleWatchNeedAlarmOption() {
    this.initLocalSpaceList();
  }
  @Watch('needIncidentOption')
  handleWatchNeedIncidentOption(v: boolean) {
    const hasSpace: ILocalSpaceList = this.localSpaceList.find(space => space.id === hasDataBizId) as ILocalSpaceList;
    hasSpace.name = (v ? this.$t('-我有故障的空间-') : this.$t('-我有告警的空间-')) as string;
  }
  created() {
    this.initLocalSpaceList();
    void this.resolveSelection(this.localValue);
  }
  /* 获取权限信息 */
  async setAllowed() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { business_list, business_with_alert, business_with_permission } = await bizWithAlertStatistics().catch(
      () => ({})
    );
    const allBizList = business_list.map(item => ({
      id: item.bk_biz_id,
      name: item.bk_biz_name,
    }));
    // const businessWithPermissionSet = new Set();
    const curIdsSet = new Set();
    for (const item of this.localSpaceList) {
      if (!specialIds.includes(item.id)) {
        curIdsSet.add(item.id);
      }
    }
    const nullItem = {
      space_name: '',
      isSpecial: false,
      tags: [],
      isCheck: false,
      show: true,
      preciseMatch: false,
      py_text: '',
      space_id: '',
      space_type_id: ETagsType.BKCC,
    };
    const otherSpaces = [];
    if (business_with_alert?.length) {
      for (const item of business_with_alert) {
        if (!curIdsSet.has(item.bk_biz_id)) {
          curIdsSet.add(item.bk_biz_id);
          otherSpaces.push({
            ...nullItem,
            ...item,
            id: item.bk_biz_id,
            name: item.bk_biz_name,
            noAuth: true,
            hasData: true,
          });
        }
      }
    }
    const data =
      business_with_permission.map(item => ({
        ...item,
        id: item.bk_biz_id,
        name: `[${item.bk_biz_id}] ${item.bk_biz_name}`,
      })) || [];
    for (const id of this.value) {
      const bizItem = allBizList.find(set => set.id === id);
      if (bizItem && !data.some(set => set.id === id)) {
        if (!curIdsSet.has(bizItem.id)) {
          curIdsSet.add(bizItem.id);
          otherSpaces.push({
            ...nullItem,
            ...bizItem,
            id: bizItem.id,
            name: bizItem.name,
            noAuth: true,
            hasData: false,
          });
        }
      }
    }
    this.localSpaceList.push(...otherSpaces);
    const selected = this.isOpen ? this.localValue : this.value;
    this.localValue = [];
    this.handleWatchValue(selected);
    this.setPaginationData(true);
  }
  setPaginationData(isInit = false) {
    const showData = [];
    const prevArr = [];
    const nextArr = [];

    for (const item of this.localSpaceList) {
      if (item.show) {
        if (item.preciseMatch) {
          prevArr.push(item);
        } else {
          nextArr.push(item);
        }
      }
    }
    showData.push(...prevArr, ...nextArr);
    this.pagination.count = showData.length;
    if (this.paged) {
      this.pagination.data = showData;
      return;
    }
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
    this.selectionSession++;
    this.selectedRequest++;
    if (this.paged) {
      this.pages.close();
      this.alertPages.close();
    }
    this.popInstance?.destroy?.();
    this.controller?.abort?.();
  }
  /* 整理space_list */
  getSpaceList(spaceList: ISpaceItem[]) {
    const list = [];
    const spaceTypeMap: Record<string, any> = {};
    // biome-ignore lint/complexity/noForEach: <explanation>
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
        show: true,
        preciseMatch: false,
      };
      list.push(newItem);
      /* 空间类型 */
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    });
    this.spaceTypeIdList = (
      this.paged ? [...new Set([...DIRECTORY_SPACE_TYPES, ...Object.keys(spaceTypeMap)])] : Object.keys(spaceTypeMap)
    ).map(key => ({
      id: key,
      name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
      styles: SPACE_TYPE_MAP[key] || SPACE_TYPE_MAP.default,
    }));
    return list;
  }
  /* 显示弹出层 */
  handleMousedown() {
    if (this.popInstance || this.disabled) {
      return;
    }
    const session = ++this.selectionSession;
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
      distance: 5,
    });
    this.popInstance?.show?.();
    this.isOpen = true;
    if (this.paged) {
      void this.resolveSelection(this.localValue, true);
      void this.loadDirectory();
    }
    this.sortSpaceList();
    this.setPaginationData(true);
    this.resetHighlight(true);
    setTimeout(() => {
      if (session !== this.selectionSession || !this.isOpen) return;
      this.addMousedownEvent();
      this.searchInputRef?.focus?.();
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
      if (pathsClass.includes('list-title')) {
        const target = this.selectRef;
        setTimeout(() => {
          this.popInstance?.update?.(target, {
            content: this.wrapRef,
          });
          this.popInstance?.show?.();
        }, 200);
      }
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
  async handlePopoverHidden() {
    if (!this.isOpen) return;
    const session = this.selectionSession;
    const isCurrent = () => session === this.selectionSession;
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.searchValue = '';
    this.searchTypeId = '';
    this.highlightId = null;
    this.popInstance = null;
    this.controller?.abort?.();
    this.isOpen = false;
    if (this.paged) {
      this.selectedRequest++;
      this.pages.close();
      this.alertPages.close();
    }
    for (const item of this.localSpaceList) {
      item.show = true;
      item.preciseMatch = false;
    }
    const value = [...this.localValue];
    const changed = value.length && JSON.stringify(this.value) !== JSON.stringify(value);
    const selected = value.filter(v => !specialIds.includes(v));
    const autoSelect =
      changed &&
      this.isAutoSelectCurrentSpace &&
      selected.length === 1 &&
      (!this.paged || this.localSpaceList.some(row => row.id === selected[0] && !row.noAuth));
    const nextSpace = autoSelect ? +selected[0] : +this.localCurrentSpace;
    if ((this.needCurSpace || autoSelect) && nextSpace !== +this.currentSpace) {
      if (!(await canSwitchSpace(nextSpace, isCurrent)) || !isCurrent()) return;
      this.resetCurBiz(nextSpace);
      this.localCurrentSpace = nextSpace;
    }
    if (changed) {
      this.$emit('change', value);
    }
  }
  /* 搜索 */
  handleSearchChange(value: string) {
    if (this.paged) {
      this.searchValue = value;
      this.pages.close();
      this.alertPages.close();
      this.pagination.data = [];
    }
    this.applySearch(value, this.selectionSession);
  }
  @Debounce(300)
  applySearch(value: string, session: number) {
    if (this.paged) {
      if (this.isOpen && session === this.selectionSession) void this.loadDirectory();
      return;
    }
    // biome-ignore lint/complexity/noForEach: <explanation>
    this.localSpaceList.forEach(item => {
      const keyword = value.trim().toLocaleLowerCase();
      const typeShow = (() => {
        if (this.searchTypeId) {
          return this.searchTypeId === 'bcs'
            ? item.space_type_id === 'bkci' && !!item.space_code
            : item.space_type_id === this.searchTypeId;
        }
        return true;
      })();
      const preciseMatch =
        item.space_name?.toLocaleLowerCase() === keyword ||
        item.py_text === keyword ||
        item.pyf_text === keyword ||
        `${item.id}` === keyword ||
        `${item.space_id}`.toLocaleLowerCase() === keyword;

      const searchShow =
        preciseMatch ||
        item.space_name?.toLocaleLowerCase().indexOf(keyword) > -1 ||
        item.py_text?.indexOf(keyword) > -1 ||
        item.pyf_text?.indexOf(keyword) > -1 ||
        `${item.id}`.includes(keyword) ||
        `${item.space_id}`.toLocaleLowerCase().includes(keyword) ||
        item.tags?.some(t => !!keyword && t.name.indexOf(keyword) > -1);
      item.show = typeShow && searchShow;
      item.preciseMatch = typeShow && preciseMatch;
    });
    this.setPaginationData(true);
    if (this.isOpen) {
      this.resetHighlight(false);
    }
  }
  selectOption(item: ILocalSpaceList, v: boolean) {
    if (this.paged && (!this.multiple || specialIds.includes(item.id))) this.localValue = [];
    if (this.multiple) {
      for (const space of this.localSpaceList) {
        if (specialIds.includes(item.id)) {
          if (space.id === item.id) {
            space.isCheck = v;
          } else {
            space.isCheck = false;
          }
        } else {
          if (specialIds.includes(space.id)) {
            space.isCheck = false;
          } else if (space.id === item.id) {
            space.isCheck = v;
          }
        }
      }
    } else {
      for (const space of this.localSpaceList) {
        space.isCheck = space.id === item.id;
      }
    }
  }
  /* check */
  handleSelectOption(item: ILocalSpaceList) {
    if (item.noAuth && !item.hasData) {
      return;
    }
    this.selectOption(item, !item.isCheck);
    this.getLocalValue();
    this.setPaginationData(true);
    if (!this.multiple) {
      this.handlePopoverHidden();
    }
  }
  handleCheckOption(v: boolean, item: ILocalSpaceList) {
    this.selectOption(item, v);
    this.getLocalValue();
    this.setPaginationData(true);
  }
  /**
   * @description 设为当前空间
   * @param item
   */
  handleSetCurBiz(item: ILocalSpaceList) {
    if (this.paged && item.noAuth) return;
    this.localCurrentSpace = item.id;
    if (!item.isCheck) {
      this.handleSelectOption(item);
    }
  }
  /**
   * @description 如当前空间切换，则刷新页面
   */
  resetCurBiz(curSpace: number) {
    this.$store.commit('app/SET_BIZ_ID', curSpace);
    const searchParams = new URLSearchParams({ bizId: `${curSpace}` });
    const newUrl = `${window.location.pathname}?${searchParams.toString()}#${this.$route.fullPath}`;
    history.replaceState({}, '', newUrl);
  }
  /* 获取当前选中的值 */
  getLocalValue() {
    this.selectedRequest++;
    const value = [];
    const valueList = [];
    const strList = [];
    for (const item of this.localSpaceList) {
      if (item.isCheck) {
        value.push(item.id);
        valueList.push(item.name);
        strList.push({
          name: item.name,
          id: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code,
        });
      }
    }
    this.valueStr = valueList.join(',');
    this.valueStrList = strList;
    if (this.paged) {
      const displayed = new Set(this.localSpaceList.map(row => row.id));
      value.push(...this.localValue.filter(id => !displayed.has(id)));
      const selected = new Set(value);
      this.selectedRows = this.localSpaceList.filter(row => selected.has(row.id) && !row.isSpecial);
    }
    this.localValue = value;
    this.isErr = !this.localValue.length;
    this.sortSpaceList();
  }
  /* 清空 */
  handleClear() {
    if (!this.multiple || this.disabled) return;
    this.localValue = [];
    this.valueStr = '';
    this.valueStrList = [];
    for (const item of this.localSpaceList) {
      item.isCheck = false;
    }
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
      })(),
    }));
    this.localSpaceList = list.sort((a, b) => b.sort - a.sort);
  }
  handleScroll(event) {
    const el = event.target;
    const { scrollHeight, scrollTop, clientHeight } = el;
    if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
      if (this.paged) {
        void this.loadDirectory(true);
        return;
      }
      this.setPaginationData(false);
    }
  }
  @Emit('applyAuth')
  async handleApplyAuth(bizId: number | string) {
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

  isSameSpaceId(a: null | number | string, b: null | number | string) {
    if (a == null || b == null) return false;
    return String(a) === String(b);
  }

  /** 打开时优先高亮当前/已选空间；搜索/筛选后高亮第一项 */
  resetHighlight(preferCurrent: boolean) {
    const items = this.pagination.data;
    if (!items.length) {
      this.highlightId = null;
      return;
    }
    if (preferCurrent) {
      const preferredId = this.needCurSpace ? this.localCurrentSpace : this.localValue[0];
      const matched =
        preferredId != null
          ? items.find(item => this.isSameSpaceId(item.id, preferredId))
          : items.find(item => item.isCheck);
      if (matched) {
        this.highlightId = matched.id;
        this.scrollHighlightIntoView();
        return;
      }
    }
    this.highlightId = items[0].id;
    this.scrollHighlightIntoView();
  }

  scrollHighlightIntoView() {
    if (this.highlightId == null || this.highlightId === '') return;
    this.$nextTick(() => {
      const el = this.wrapRef?.querySelector?.(`[data-space-id="${this.highlightId}"]`) as HTMLElement;
      el?.scrollIntoView?.({ block: 'nearest' });
    });
  }

  handleSearchKeydown(value: KeyboardEvent | string, event?: KeyboardEvent) {
    const keyEvent = (event || value) as KeyboardEvent;
    if (!keyEvent?.key) return;
    if (keyEvent.key === 'Enter') {
      keyEvent.preventDefault();
      return;
    }
    if (keyEvent.key !== 'ArrowDown' && keyEvent.key !== 'ArrowUp') return;
    keyEvent.preventDefault();
    keyEvent.stopPropagation();
    this.moveHighlight(keyEvent.key === 'ArrowDown' ? 1 : -1);
  }

  handleSearchEnter(_value: string, event?: KeyboardEvent) {
    event?.preventDefault?.();
    const target = this.pagination.data.find(item => this.isSameSpaceId(item.id, this.highlightId));
    if (target) {
      this.handleSelectOption(target);
      this.scrollHighlightIntoView();
    }
  }

  /** 方向键在可见项间移动；触底且还有分页时先加载再继续 */
  async moveHighlight(step: number) {
    const items = this.pagination.data;
    if (!items.length) return;
    const index = items.findIndex(item => this.isSameSpaceId(item.id, this.highlightId));
    if (index < 0) {
      this.highlightId = items[step > 0 ? 0 : items.length - 1].id;
      this.scrollHighlightIntoView();
      return;
    }
    let next = index + step;
    if (next < 0) {
      next = 0;
    } else if (next >= items.length) {
      const beforeCount = items.length;
      if (this.paged && (this.pages.hasMore || this.alertPages.hasMore)) {
        if (await this.loadDirectory(true)) {
          this.highlightId = this.pagination.data[index + 1]?.id ?? this.highlightId;
          this.scrollHighlightIntoView();
        }
        return;
      }
      this.setPaginationData(false);
      if (this.pagination.data.length > beforeCount) {
        next = Math.min(index + step, this.pagination.data.length - 1);
        this.highlightId = this.pagination.data[next].id;
        this.scrollHighlightIntoView();
        return;
      }
      next = items.length - 1;
    }
    this.highlightId = this.pagination.data[next].id;
    this.scrollHighlightIntoView();
  }

  handleContentMouseDown(e: MouseEvent) {
    if (this.searchInputRef?.$el?.contains(e.target as Node)) {
      return;
    }
    const target = e.target as HTMLElement;
    // 复选框、权限按钮等需要保留默认行为，避免 mousedown.preventDefault 把 click 吃掉
    if (target.closest?.('.bk-checkbox, .bk-button, a, button')) {
      return;
    }
    e.preventDefault();
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
  handleTypeWrapScrollChange(type: 'next' | 'pre') {
    const smoothScrollTo = (element: HTMLDivElement, targetPosition: number, duration: number, callback) => {
      const startPosition = element.scrollLeft;
      const distance = targetPosition - startPosition;
      const startTime = Date.now();
      const easeOutCubic = t => 1 - (1 - t) ** 3;
      const scroll = () => {
        const elapsed = Date.now() - startTime;
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
          { active: this.isOpen },
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
                    key={item.id}
                    class='selected-text-item'
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
            <span class='icon-monitor icon-arrow-down' />
            {this.multiple && <span class='icon-monitor icon-mc-close-fill' />}
          </span>
        </div>
        <div style={{ display: 'none' }}>
          <div
            ref='wrap'
            class={componentClassNames.pop}
            onMousedown={this.handleContentMouseDown}
          >
            <div class='search-input'>
              <bk-input
                ref='searchInput'
                v-model={this.searchValue}
                behavior={'simplicity'}
                left-icon='bk-icon icon-search'
                placeholder={this.$t('请输入 关键字')}
                onChange={this.handleSearchChange}
                onEnter={this.handleSearchEnter}
                onKeydown={this.handleSearchKeydown}
              />
            </div>
            <div class={['space-type-list-wrap', { 'show-btn': this.typeWrapInfo.showBtn }]}>
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
            <div
              class='space-list'
              onScroll={this.handleScroll}
            >
              {this.pagination.data.map(item => (
                <div
                  key={item.id}
                  class={[
                    'space-list-item',
                    { active: !this.multiple && item.isCheck },
                    { highlight: this.isSameSpaceId(item.id, this.highlightId) },
                    {
                      'no-hover-btn':
                        !this.needCurSpace ||
                        +this.localCurrentSpace === +item.id ||
                        specialIds.includes(item.id) ||
                        (!!item.noAuth && !item.hasData),
                    },
                  ]}
                  data-space-id={item.id}
                  onClick={() => this.handleSelectOption(item)}
                >
                  {this.multiple && (
                    <div onClick={(e: Event) => e.stopPropagation()}>
                      <bk-checkbox
                        disabled={!!item.noAuth && !item.hasData}
                        value={item.isCheck}
                        onChange={v => this.handleCheckOption(v, item)}
                      />
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
                    {/* {+this.localCurrentSpace === +item.id && (
                      <span
                        class='icon-monitor icon-dingwei1 cur-position'
                        v-bk-tooltips={{
                          content: this.$t('当前空间'),
                          placements: ['top'],
                        }}
                      />
                    )} */}
                  </span>
                  <span class='space-tags'>
                    {item.noAuth && !item.hasData ? (
                      <bk-button
                        class='auth-button'
                        size='small'
                        theme='primary'
                        text
                        onClick={() => this.handleApplyAuth(item.id)}
                      >
                        {this.$t('申请权限')}
                      </bk-button>
                    ) : (
                      item.tags?.map?.(tag => (
                        <span
                          key={tag.id}
                          style={{ ...(SPACE_TYPE_MAP[tag.id] || SPACE_TYPE_MAP.default) }}
                          class='space-tags-item'
                        >
                          {SPACE_TYPE_MAP[tag.id]?.name || this.$t('未知')}
                        </span>
                      ))
                    )}
                  </span>
                  {this.needCurSpace && !(this.paged && item.noAuth) && (
                    <span class='space-hover-btn'>
                      <bk-button
                        class='auth-button'
                        size='small'
                        theme='primary'
                        text
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
              {this.paged && (this.pages.hasMore || this.alertPages.hasMore) && (
                <button
                  disabled={this.pages.isLoading || this.alertPages.isLoading}
                  type='button'
                  onClick={() => this.loadDirectory(true)}
                >
                  {this.$t('加载更多')}
                </button>
              )}
              {this.paged &&
                (this.selectionIncomplete ||
                  this.pages.failed ||
                  this.pages.partial ||
                  this.alertPages.failed ||
                  this.alertPages.partial) && (
                  <button
                    type='button'
                    onClick={() => {
                      void this.resolveSelection(this.localValue);
                      void this.loadDirectory();
                    }}
                  >
                    {this.$t('部分空间未能确认，请重试')}
                  </button>
                )}
            </div>
          </div>
        </div>
      </span>
    );
  }
}
