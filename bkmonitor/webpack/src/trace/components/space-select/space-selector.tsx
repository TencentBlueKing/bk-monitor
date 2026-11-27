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

import {
  computed,
  defineComponent,
  nextTick,
  onUnmounted,
  shallowReactive,
  shallowRef,
  triggerRef,
  useTemplateRef,
  watch,
} from 'vue';

import { useDebounceFn, useEventListener } from '@vueuse/core';
import { Button, Checkbox, Input } from 'bkui-vue';
import { bizWithAlertStatistics } from 'monitor-api/modules/home';
import { DIRECTORY_SPACE_TYPES, supportsSpaceDirectoryPages } from 'monitor-common/utils/space-directory';
import { canSwitchSpace } from 'monitor-common/utils/space-entry';
import EmptyStatus, { type EmptyStatusOperationType } from 'trace/components/empty-status/empty-status';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { useTippy } from 'vue-tippy';

import { useAppStore } from '../../store/modules/app';
import { type DirectoryOption, PagedSpaceOptions } from './paged-space-options';
import {
  type ILocalSpaceList,
  type IValueStrListItem,
  ETagsType,
  SPACE_SELECTOR_EMITS,
  SPACE_SELECTOR_PROPS,
} from './typing';
import { getEventPaths, SPACE_TYPE_MAP } from './utils';

import type { ISpaceItem } from 'monitor-common/typings';

import './space-selector.scss';

const componentClassNames = {
  selectInput: 'space-select-content',
  pop: 'vue3__space-select-component-popover-content',
};
const rightIconClassName = 'space-select-right-icon';
// 有权限的业务id
const authorityBizId = -1;
// 有数据的业务id
const hasDataBizId = -2;
const defaultRadioList = [
  { id: 'all', bk_biz_id: 'all', name: window.i18n.t('有权限的业务(最大20个)') },
  { id: 'settings', bk_biz_id: 'settings', name: window.i18n.t('配置管理业务') },
  { id: 'notify', bk_biz_id: 'notify', name: window.i18n.t('告警接收业务') },
];
const specialIds = [authorityBizId, hasDataBizId, ...defaultRadioList.map(d => d.id)];

export default defineComponent({
  name: 'SpaceSelector',
  props: SPACE_SELECTOR_PROPS,
  emits: SPACE_SELECTOR_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const appStore = useAppStore();
    const selectRef = useTemplateRef<HTMLDivElement>('selectRef');
    const wrapRef = useTemplateRef<HTMLDivElement>('wrapRef');
    const typeListRef = useTemplateRef<HTMLDivElement>('typeListRef');
    const searchInputRef = useTemplateRef<InstanceType<typeof Input>>('searchInput');

    const localValue = shallowRef<(number | string)[]>([]);
    /* 当前的主空间 */
    const localCurrentSpace = shallowRef<number>(null);
    /* 搜索 */
    const searchValue = shallowRef('');
    /* 空间列表 */
    const localSpaceList = shallowRef<ILocalSpaceList[]>([]);
    /* 空间类型列表 */
    const spaceTypeIdList = shallowRef<{ id: string; name: string; styles: Record<string, string> }[]>([]);
    /* 当前选中的空间类型 */
    const searchTypeId = shallowRef('');
    /* 弹出实例 */
    let popInstance = null;
    /* 添加可被移除的事件监听器 */
    let controller: AbortController = null;
    /* 已选择部分文字 */
    const valueStr = shallowRef('');
    /* 已选择部分文字（包含id） */
    const valueStrList = shallowRef<IValueStrListItem[]>([]);
    /* 是否标红 */
    const isErr = shallowRef(false);
    /* 是否弹出弹窗 */
    const isOpen = shallowRef(false);
    let selectionSession = 0;
    /** 键盘高亮项 id */
    const highlightId = shallowRef<null | number | string>(null);
    /** 避免 keydown 与 enter 各触发一次导致多选勾选被抵消 */
    let lastEnterAt = 0;
    /** 下拉打开时在 window 捕获阶段监听键盘，绕过 Input 默认 stopPropagation */
    let stopKeyboardListen: (() => void) | null = null;
    /* 当前分页数据 */
    const pagination = shallowReactive<{
      count: number;
      current: number;
      data: ILocalSpaceList[];
      limit: number;
    }>({
      current: 1,
      limit: 20,
      data: [],
      count: 0,
    });
    /* type栏左右切换数据 */
    const typeWrapInfo = shallowReactive({
      showBtn: false,
      nextDisable: false,
      preDisable: false,
    });
    /* 是否需要当前空间功能 */
    const needCurSpace = computed(() => {
      return props.currentSpace !== null;
    });

    const handleDebounceSearchChange = useDebounceFn(handleSearchChange, 300);
    /** bizWithAlertStatistics 返回的业务名缓存，供已选无权限业务兜底展示 */
    const bizNameMap = shallowRef(new Map<number, string>());

    const remote = props.remote && supportsSpaceDirectoryPages() ? new PagedSpaceOptions() : null;
    const pageError = shallowRef(false);
    const lookupError = shallowRef(false);
    const pageLoading = shallowRef(false);
    const hasMore = shallowRef(false);
    let pageGeneration = 0;

    initLocalSpaceList();
    if (remote) void resolveSelected(props.value);
    onUnmounted(() => {
      ++selectionSession;
      if (props.remote && remote) closePages();
      popInstance?.destroy?.();
      controller?.abort?.();
      unbindKeyboard();
    });
    watch(
      () => props.value,
      val => {
        if (remote) {
          localValue.value = [...val];
          initLocalSpaceList();
          void resolveSelected(val);
          return;
        }
        // value 可能在 setAllowed 完成后才变为目标无权限 biz，需补齐列表项后再同步勾选文案
        ensureSelectedNoAuthSpaces(val);
        handleWatchValue(val);
      }
    );

    watch(
      () => props.currentSpace,
      val => {
        if (val !== null) {
          localCurrentSpace.value = val as any;
        }
      },
      { immediate: true }
    );
    watch([() => props.spaceList, () => props.needAlarmOption], () => {
      initLocalSpaceList();
    });
    watch(
      () => props.needIncidentOption,
      val => {
        const hasSpace: ILocalSpaceList = localSpaceList.value.find(
          space => space.id === hasDataBizId
        ) as ILocalSpaceList;
        hasSpace.name = (val ? t('-我有故障的空间-') : t('-我有告警的空间-')) as string;
        triggerRef(localSpaceList);
      }
    );

    function handleApplyAuth(bizId: number | string) {
      handlePopoverHidden();
      emit('applyAuth', [bizId]);
    }

    function selectedIds(value: (number | string)[]) {
      const ids = [...value, props.currentSpace].filter(id => id != null && !isSpecialSpaceId(id)).map(Number);
      return [...new Set(ids.filter(id => Number.isFinite(id) && id !== 0))];
    }

    function localRows(value: (number | string)[]) {
      const rows = remote.rows;
      const refs = selectedIds(value).map<DirectoryOption>(
        id =>
          remote.selected(id) ?? {
            bk_biz_id: id,
            id,
            is_demo: false,
            space_code: '',
            space_name: `#${id}`,
            space_id: String(id),
            space_type_id: '',
            space_uid: '',
            status: '',
            text: `#${id}`,
            type_name: '',
          }
      );
      const options = new Map([...refs, ...rows].map(item => [item.bk_biz_id, item]));
      return [...options.values()];
    }

    async function resolveSelected(value: (number | string)[]) {
      const session = selectionSession;
      try {
        const current = await remote.resolveSelected(selectedIds(value), props.hasAuthApply);
        if (current) {
          lookupError.value = false;
          initLocalSpaceList();
        }
      } catch {
        if (session === selectionSession) {
          lookupError.value = true;
          initLocalSpaceList();
        }
      }
    }

    function closePages() {
      ++pageGeneration;
      remote.close();
      hasMore.value = false;
      pageLoading.value = false;
      pageError.value = false;
    }

    async function loadPage(first: boolean) {
      if (!isOpen.value || (!first && pageLoading.value)) return;
      const generation = first ? ++pageGeneration : pageGeneration;
      remote.retain(selectedIds(localValue.value));
      pageLoading.value = true;
      if (first) pageError.value = false;
      const response = first
        ? remote.reset({ query: searchValue.value.trim(), type: searchTypeId.value }, props.hasAuthApply)
        : remote.next(props.hasAuthApply);
      if (first) initLocalSpaceList();
      const results = await response;
      if (generation !== pageGeneration) return;
      remote.updateRows(first);
      pageLoading.value = false;
      hasMore.value = remote.allowed.hasMore || remote.alerts.hasMore;
      pageError.value =
        results.some(result => result.status === 'rejected') ||
        remote.allowed.partial ||
        remote.alerts.partial ||
        remote.allowed.failed ||
        remote.alerts.failed;
      initLocalSpaceList();
      if (first || !pagination.data.some(row => isSameSpaceId(row.id, highlightId.value))) resetHighlight(first);
    }

    function retryPages() {
      void resolveSelected(localValue.value);
      void loadPage(true);
    }

    function handleSearchInput(value: string) {
      if (remote && isOpen.value) {
        searchValue.value = value;
        ++pageGeneration;
        remote.retain(selectedIds(localValue.value));
        remote.clearPages();
        pageError.value = false;
        pageLoading.value = true;
        hasMore.value = false;
        initLocalSpaceList();
      }
      handleDebounceSearchChange(value);
    }

    function isSpecialSpaceId(id: number | string) {
      if (specialIds.includes(id as (typeof specialIds)[number]) || specialIds.includes(String(id) as any)) {
        return true;
      }
      const num = Number(id);
      return num === authorityBizId || num === hasDataBizId;
    }

    function syncNoAuthBizIds() {
      const noAuthIds: number[] = [];
      for (const item of localSpaceList.value) {
        if (item.noAuth && !item.hasData) {
          noAuthIds.push(+item.id);
        }
      }
      appStore.noAuthBizIds = noAuthIds;
    }

    /**
     * 已选但不在列表中的业务补成无权限项（对齐旧版：无权限也可展示并申请）
     * 不依赖 business_list 是否命中，避免 id 类型不一致 / 接口缺项导致触发器空白
     */
    function ensureSelectedNoAuthSpaces(val: (number | string)[] = []) {
      if (window.space_list_state === 'deferred') return;
      const existingIds = new Set(localSpaceList.value.map(item => +item.id));
      const missing: ILocalSpaceList[] = [];
      for (const id of val) {
        if (isSpecialSpaceId(id)) continue;
        const numId = Number(id);
        if (!Number.isFinite(numId) || numId === 0 || existingIds.has(numId)) continue;
        const name = bizNameMap.value.get(numId) || `#${numId}`;
        const noAuthItem = {
          space_name: name,
          isSpecial: false,
          tags: [],
          isCheck: false,
          show: true,
          preciseMatch: false,
          py_text: '',
          space_id: String(numId),
          space_type_id: ETagsType.BKCC,
          id: numId,
          bk_biz_id: numId,
          name,
          noAuth: true,
          hasData: false,
        } as unknown as ILocalSpaceList;
        missing.push(noAuthItem);
        existingIds.add(numId);
      }
      if (!missing.length) return;
      localSpaceList.value = [...localSpaceList.value, ...missing];
      syncNoAuthBizIds();
      setPaginationData(true);
    }

    function handleWatchValue(val) {
      if (JSON.stringify(val) === JSON.stringify(localValue.value)) {
        return;
      }
      const defaultRadioListIds = defaultRadioList.map(d => d.id);
      localValue.value = val.map(b => (defaultRadioListIds.includes(String(b)) ? b : Number(b)));
      const nameList = [];
      const strList = [];
      for (const item of localSpaceList.value) {
        // 兼容 number / string id，避免无权限项勾选与触发器文案丢失
        const has = localValue.value.some(v => String(v) === String(item.id) || +v === +item.id);
        item.isCheck = has;
        if (has) {
          nameList.push(item.name);
          strList.push({
            name: item.name,
            id: item.id,
            idDisplayName: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code,
            tags: item?.tags || [],
          });
        }
      }
      valueStr.value = nameList.join(',');
      valueStrList.value = strList;
      sortSpaceList();
    }

    function initLocalSpaceList() {
      const selected = isOpen.value ? localValue.value : props.value;
      localSpaceList.value = getSpaceList(props.remote && remote ? localRows(selected) : props.spaceList);
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
      if (props.needAlarmOption) {
        localSpaceList.value.unshift({
          ...nullItem,
          bk_biz_id: hasDataBizId,
          id: hasDataBizId,
          name: props.needIncidentOption ? t('-我有故障的空间-') : t('-我有告警的空间-'),
        } as any);
      }
      if (props.needAuthorityOption) {
        localSpaceList.value.unshift({
          ...nullItem,
          bk_biz_id: authorityBizId,
          id: authorityBizId,
          name: t('-我有权限的空间-'),
        } as any);
      }
      if (props.needDefaultOptions) {
        localSpaceList.value = [...defaultRadioList.map(d => ({ ...nullItem, ...d })), ...localSpaceList.value] as any;
      }
      if (props.remote && remote) {
        const filtered = Boolean(searchValue.value.trim() || searchTypeId.value);
        if (!selected.length) {
          valueStr.value = '';
          valueStrList.value = [];
        }
        const visible = new Set(remote.rows.map(row => row.bk_biz_id));
        for (const item of localSpaceList.value) {
          item.show = !filtered || visible.has(item.bk_biz_id);
        }
        if (props.hasAuthApply) syncNoAuthBizIds();
      }
      localValue.value = [];
      handleWatchValue(selected);
      setPaginationData(true);
      if (props.hasAuthApply && !(props.remote && remote) && window.space_list_state !== 'deferred') {
        setAllowed();
      }
    }

    function handleMousedown() {
      if (popInstance || props.disabled) {
        return;
      }
      const session = ++selectionSession;
      if (props.value.length > 1 && !props.multiple) {
        handleChangeChoiceType(true);
      }
      const target = selectRef.value;
      popInstance = useTippy(target, {
        content: () => wrapRef.value,
        trigger: 'manual',
        interactive: true,
        theme: 'light common-monitor',
        arrow: false,
        placement: 'bottom-start',
        appendTo: () => document.body,
        hideOnClick: false,
        offset: [0, 5],
        maxWidth: 'none',
      });
      popInstance?.show?.();
      isOpen.value = true;
      if (props.remote && remote) {
        remote.forgetReferences();
        void resolveSelected(localValue.value);
        void loadPage(true);
      }
      sortSpaceList();
      setPaginationData(true);
      resetHighlight(true);
      bindKeyboard();
      setTimeout(() => {
        if (session !== selectionSession || !isOpen.value) return;
        addMousedownEvent();
        searchInputRef.value?.focus();
      }, 300);
    }

    function addMousedownEvent() {
      controller?.abort?.();
      controller = new AbortController();
      document.addEventListener('click', handleMousedownRemovePop, { signal: controller.signal });
      typeListWrapNextPreShowChange();
    }

    function handleMousedownRemovePop(event: Event) {
      // A loading state can remove the clicked button before the event bubbles to document.
      const path = event.composedPath?.() ?? getEventPaths(event);
      const pathsClass = path
        .map(item => (item as HTMLElement).className)
        .filter((name): name is string => typeof name === 'string');
      // 关闭侧栏组件时需要关闭弹层
      if (pathsClass.some(c => ['slide-leave', 'bk-sideslider-closer'].some(s => (c?.indexOf(s) || -1) >= 0))) {
        handlePopoverHidden();
        return;
      }
      if (!localValue.value.length) {
        isErr.value = true;
        if (pathsClass.includes('list-title')) {
          setTimeout(() => {
            popInstance?.show?.();
          }, 200);
        }
        return;
      }
      if (pathsClass.includes(rightIconClassName)) {
        return;
      }
      if (path.includes(wrapRef.value)) {
        return;
      }
      handlePopoverHidden();
    }

    async function handlePopoverHidden() {
      if (!isOpen.value) return;
      const session = selectionSession;
      const isCurrent = () => session === selectionSession;
      popInstance?.hide();
      popInstance?.destroy?.();
      searchValue.value = '';
      searchTypeId.value = '';
      highlightId.value = null;
      popInstance = null;
      controller?.abort?.();
      isOpen.value = false;
      if (props.remote && remote) {
        remote.retain(selectedIds(localValue.value));
        closePages();
        localSpaceList.value = localSpaceList.value.filter(item => item.isSpecial || item.isCheck);
        setPaginationData(true);
      }
      unbindKeyboard();
      for (const item of localSpaceList.value) {
        item.show = true;
        item.preciseMatch = false;
      }
      triggerRef(localSpaceList);
      const value = [...localValue.value];
      const changed = value.length && JSON.stringify(props.value) !== JSON.stringify(value);
      const selected = value.filter(v => !specialIds.includes(v));
      const autoSelect =
        changed &&
        props.isAutoSelectCurrentSpace &&
        selected.length === 1 &&
        (!(props.remote && remote) || canMakeCurrent(+selected[0]));
      const nextSpace = autoSelect ? +selected[0] : +localCurrentSpace.value;
      if ((needCurSpace.value || autoSelect) && nextSpace !== +props.currentSpace) {
        if (!(await canSwitchSpace(nextSpace, isCurrent)) || !isCurrent()) return;
        resetCurBiz(nextSpace);
        localCurrentSpace.value = nextSpace;
      }
      if (changed) {
        emit('change', value);
      }
    }

    function canMakeCurrent(id: number) {
      const record: DirectoryOption = remote.selected(id);
      return Boolean(record && !record.noAuth);
    }

    function resetCurBiz(curSpace: number) {
      appStore.bizId = curSpace;
      const searchParams = new URLSearchParams({ bizId: `${curSpace}` });
      const newUrl = `${window.location.pathname}?${searchParams.toString()}#${route.fullPath}`;
      history.replaceState({}, '', newUrl);
    }

    function getLocalValue() {
      const value = [];
      const valueList = [];
      const strList = [];
      for (const item of localSpaceList.value) {
        if (item.isCheck) {
          value.push(item.id);
          valueList.push(item.name);
          strList.push({
            name: item.name,
            id: item.id,
            idDisplayName: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code,
            tags: item?.tags || [],
          });
        }
      }
      valueStr.value = valueList.join(',');
      valueStrList.value = strList;
      localValue.value = value;
      isErr.value = !localValue.value.length;
      sortSpaceList();
    }

    function typeListWrapNextPreShowChange() {
      nextTick(() => {
        const hasScroll = typeListRef.value.scrollWidth > typeListRef.value.clientWidth;
        typeWrapInfo.showBtn = hasScroll;
        typeWrapInfo.preDisable = true;
      });
    }

    function getSpaceList(spaceList: ISpaceItem[]) {
      const list = [];
      const spaceTypeMap: Record<string, any> = {};
      // biome-ignore lint/complexity/noForEach: <explanation>
      spaceList.forEach(item => {
        const tags = item.space_type_id
          ? [{ id: item.space_type_id, name: item.type_name, type: item.space_type_id }]
          : [];
        if (item.space_type_id === 'bkci' && item.space_code) {
          tags.push({ id: 'bcs', name: t('容器项目'), type: 'bcs' });
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
        if (item.space_type_id) spaceTypeMap[item.space_type_id] = 1;
        if (item.space_type_id === 'bkci' && item.space_code) {
          spaceTypeMap.bcs = 1;
        }
      });
      const types = Object.keys(spaceTypeMap);
      spaceTypeIdList.value = (remote ? [...new Set([...DIRECTORY_SPACE_TYPES, ...types])] : types).map(key => ({
        id: key,
        name: SPACE_TYPE_MAP[key]?.name || t('未知'),
        styles: SPACE_TYPE_MAP[key]?.light || SPACE_TYPE_MAP.default.light,
      }));
      return list;
    }

    /**
     * @description 排序，已选择默认置于我有告警的下方
     */
    function sortSpaceList() {
      const list = localSpaceList.value.map(item => ({
        ...item,
        sort: (() => {
          if (specialIds.includes(item.id)) {
            return 4;
          }
          if (+localCurrentSpace.value === +item.id) {
            return 3;
          }
          return localValue.value.includes(item.id) ? 2 : 1;
        })(),
      }));
      localSpaceList.value = list.sort((a, b) => b.sort - a.sort);
    }

    async function setAllowed() {
      const statistics = (await bizWithAlertStatistics().catch(() => ({}))) as {
        business_list?: { bk_biz_id: number; bk_biz_name: string }[];
        business_with_alert?: { bk_biz_id: number; bk_biz_name: string }[];
        business_with_permission?: { bk_biz_id: number; bk_biz_name: string }[];
      };
      const businessList = statistics.business_list || [];
      const businessWithAlert = statistics.business_with_alert || [];
      const businessWithPermission = statistics.business_with_permission || [];
      const allBizList = businessList.map(item => ({
        id: +item.bk_biz_id,
        name: item.bk_biz_name,
      }));
      const nameMap = new Map<number, string>();
      for (const item of allBizList) {
        nameMap.set(item.id, item.name);
      }
      for (const item of businessWithAlert) {
        nameMap.set(+item.bk_biz_id, item.bk_biz_name);
      }
      bizNameMap.value = nameMap;

      const curIdsSet = new Set<number>();
      for (const item of localSpaceList.value) {
        if (!isSpecialSpaceId(item.id)) {
          curIdsSet.add(+item.id);
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
      for (const item of businessWithAlert) {
        const bizId = +item.bk_biz_id;
        if (!curIdsSet.has(bizId)) {
          curIdsSet.add(bizId);
          otherSpaces.push({
            ...nullItem,
            ...item,
            id: bizId,
            bk_biz_id: bizId,
            name: item.bk_biz_name,
            noAuth: true,
            hasData: true,
          });
        }
      }
      const permissionIds = new Set(businessWithPermission.map(item => +item.bk_biz_id));
      // 当前已选但不在有权限列表中的业务：补无权限项（接口无名时用 #id 兜底）
      for (const id of props.value) {
        if (isSpecialSpaceId(id)) continue;
        const numId = Number(id);
        if (!Number.isFinite(numId) || numId === 0 || curIdsSet.has(numId) || permissionIds.has(numId)) continue;
        const bizItem = allBizList.find(set => set.id === numId);
        const name = bizItem?.name || nameMap.get(numId) || `#${numId}`;
        curIdsSet.add(numId);
        otherSpaces.push({
          ...nullItem,
          ...(bizItem || {}),
          id: numId,
          bk_biz_id: numId,
          name,
          space_name: name,
          space_id: String(numId),
          noAuth: true,
          hasData: false,
        });
      }
      if (otherSpaces.length) {
        localSpaceList.value = [...localSpaceList.value, ...otherSpaces];
      }
      syncNoAuthBizIds();
      // value 可能已在 await 期间更新，再兜底补一次
      const selected = isOpen.value ? localValue.value : props.value;
      ensureSelectedNoAuthSpaces(selected);
      localValue.value = [];
      handleWatchValue(selected);
      setPaginationData(true);
    }

    function setPaginationData(isInit = false) {
      const prevArr = [];
      const nextArr = [];

      for (const item of localSpaceList.value) {
        if (item.show) {
          if (item.preciseMatch) {
            prevArr.push(item);
          } else {
            nextArr.push(item);
          }
        }
      }

      const showData = prevArr.concat(nextArr);
      pagination.count = showData.length;
      if (remote) {
        pagination.data = showData;
        return;
      }
      if (isInit) {
        pagination.current = 1;
        pagination.data = showData.slice(0, pagination.limit);
      } else {
        if (pagination.current * pagination.limit < pagination.count) {
          pagination.current += 1;
          const temp = showData.slice(
            (pagination.current - 1) * pagination.limit,
            pagination.current * pagination.limit
          );
          pagination.data = [...pagination.data, ...temp];
        }
      }
    }
    function handleSearchChange(value: string) {
      if (remote) {
        if (value === searchValue.value) void loadPage(true);
        return;
      }
      for (const item of localSpaceList.value) {
        const keyword = value.trim().toLocaleLowerCase();
        const typeShow = (() => {
          if (searchTypeId.value) {
            return searchTypeId.value === 'bcs'
              ? item.space_type_id === 'bkci' && !!item.space_code
              : item.space_type_id === searchTypeId.value;
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
      }
      triggerRef(localSpaceList);
      setPaginationData(true);
      if (isOpen.value) {
        resetHighlight(false);
      }
    }

    function selectOption(item: ILocalSpaceList, v: boolean) {
      if (props.multiple) {
        for (const space of localSpaceList.value) {
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
        for (const space of localSpaceList.value) {
          space.isCheck = space.id === item.id;
        }
      }
      triggerRef(localSpaceList);
    }

    function handleSelectOption(item: ILocalSpaceList) {
      // 无权限业务：点击整行与「申请权限」一致，走申请流程
      if (item.noAuth && !item.hasData) {
        handleApplyAuth(item.id);
        return;
      }
      selectOption(item, !item.isCheck);
      getLocalValue();
      setPaginationData(true);
      if (!props.multiple) {
        handlePopoverHidden();
      }
    }

    function handleCheckOption(v: boolean, item: ILocalSpaceList) {
      selectOption(item, v);
      getLocalValue();
      setPaginationData(true);
    }

    function handleSetCurBiz(item: ILocalSpaceList) {
      if (remote && !canMakeCurrent(item.id)) return;
      localCurrentSpace.value = item.id;
      if (!item.isCheck) {
        handleSelectOption(item);
      }
    }

    function handleClear() {
      if (!props.multiple || props.disabled) return;
      localValue.value = [];
      valueStr.value = '';
      valueStrList.value = [];
      for (const item of localSpaceList.value) {
        item.isCheck = false;
      }
      triggerRef(localSpaceList);
      setPaginationData(true);
    }

    function handleScroll(event) {
      const el = event.target;
      const { scrollHeight, scrollTop, clientHeight } = el;
      if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
        if (remote) {
          if (remote.allowed.hasMore || remote.alerts.hasMore) void loadPage(false);
        } else setPaginationData(false);
      }
    }

    /**
     * @description 切换当前空间类型
     * @param typeId
     */
    function handleSearchType(typeId: string) {
      searchTypeId.value = typeId === searchTypeId.value ? '' : typeId;
      handleSearchChange(searchValue.value);
    }

    function isSameSpaceId(a: null | number | string, b: null | number | string) {
      if (a == null || b == null) return false;
      return String(a) === String(b);
    }

    /** 打开时优先高亮当前/已选空间；搜索/筛选后高亮第一项 */
    function resetHighlight(preferCurrent: boolean) {
      const items = pagination.data;
      if (!items.length) {
        highlightId.value = null;
        return;
      }
      if (preferCurrent) {
        const preferredId = needCurSpace.value ? localCurrentSpace.value : localValue.value[0];
        const matched =
          preferredId != null
            ? items.find(item => isSameSpaceId(item.id, preferredId))
            : items.find(item => item.isCheck);
        if (matched) {
          highlightId.value = matched.id;
          scrollHighlightIntoView();
          return;
        }
      }
      highlightId.value = items[0].id;
      scrollHighlightIntoView();
    }

    function scrollHighlightIntoView() {
      if (highlightId.value == null || highlightId.value === '') return;
      nextTick(() => {
        const el = wrapRef.value?.querySelector?.(`[data-space-id="${highlightId.value}"]`) as HTMLElement;
        el?.scrollIntoView?.({ block: 'nearest' });
      });
    }

    function bindKeyboard() {
      unbindKeyboard();
      stopKeyboardListen = useEventListener(window, 'keydown', handleWindowKeydown, { capture: true });
    }

    function unbindKeyboard() {
      stopKeyboardListen?.();
      stopKeyboardListen = null;
    }

    function handleWindowKeydown(event: KeyboardEvent) {
      if (!isOpen.value || event.isComposing) return;
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        moveHighlight(event.key === 'ArrowDown' ? 1 : -1);
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        confirmHighlightItem();
      }
    }

    /** 单选：Enter 选中并关闭；多选：Enter 只切换勾选，面板保持打开 */
    function confirmHighlightItem() {
      const now = Date.now();
      if (now - lastEnterAt < 50) return;
      lastEnterAt = now;
      const target = pagination.data.find(item => isSameSpaceId(item.id, highlightId.value));
      if (!target) return;
      if (props.multiple) {
        if (target.noAuth && !target.hasData) return;
        handleCheckOption(!target.isCheck, target);
        scrollHighlightIntoView();
        return;
      }
      handleSelectOption(target);
    }

    /** 方向键在可见项间移动；触底且还有分页时先加载再继续 */
    async function moveHighlight(step: number) {
      const items = pagination.data;
      if (!items.length) return;
      const index = items.findIndex(item => isSameSpaceId(item.id, highlightId.value));
      if (index < 0) {
        highlightId.value = items[step > 0 ? 0 : items.length - 1].id;
        scrollHighlightIntoView();
        return;
      }
      let next = index + step;
      if (next < 0) {
        next = 0;
      } else if (next >= items.length) {
        const beforeCount = items.length;
        if (remote && (remote.allowed.hasMore || remote.alerts.hasMore)) {
          const generation = pageGeneration;
          const previous = highlightId.value;
          await loadPage(false);
          if (generation !== pageGeneration || !isOpen.value || !isSameSpaceId(highlightId.value, previous)) return;
        } else setPaginationData(false);
        if (pagination.data.length > beforeCount) {
          next = Math.min(index + step, pagination.data.length - 1);
          highlightId.value = pagination.data[next].id;
          scrollHighlightIntoView();
          return;
        }
        next = items.length - 1;
      }
      highlightId.value = pagination.data[next].id;
      scrollHighlightIntoView();
    }

    function handleContentMouseDown(e: MouseEvent) {
      const inputEl = (searchInputRef.value as null | { $el?: HTMLElement })?.$el;
      if (inputEl?.contains(e.target as Node)) {
        return;
      }
      const target = e.target as HTMLElement;
      // 复选框、权限按钮等需要保留默认行为，避免 mousedown.preventDefault 把 click 吃掉
      if (target.closest?.('.bk-checkbox, .bk-button, a, button')) {
        return;
      }
      e.preventDefault();
    }

    /**
     * @description 左右切换type栏
     * @param type
     */
    function handleTypeWrapScrollChange(type: 'next' | 'pre') {
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
      const { scrollWidth, scrollLeft, clientWidth } = typeListRef.value;
      const total = scrollWidth - clientWidth;
      if (type === 'next') {
        const temp = scrollLeft + speed;
        target = temp > total ? total : temp;
      } else {
        const temp = scrollLeft - speed;
        target = temp < 0 ? 0 : temp;
      }
      smoothScrollTo(typeListRef.value, target, duration, () => {
        typeWrapInfo.nextDisable = typeListRef.value.scrollLeft > total - 1;
        typeWrapInfo.preDisable = typeListRef.value.scrollLeft === 0;
      });
    }

    function handleChangeChoiceType(val) {
      if (!val && localValue.value.length > 1) {
        handleWatchValue([localValue.value[0]]);
      }
      emit('changeChoiceType', val);
    }

    function handleOperation(type: EmptyStatusOperationType) {
      if (type === 'clear-filter') {
        searchValue.value = '';
        handleSearchChange(searchValue.value);
      }
    }

    return {
      pageError,
      lookupError,
      pageLoading,
      retryPages,
      hasMore,
      handleSearchInput,
      loadNext: () => loadPage(false),
      canMakeCurrent: (id: number) => !remote || canMakeCurrent(id),
      isErr,
      isOpen,
      valueStrList,
      valueStr,
      searchValue,
      typeWrapInfo,
      spaceTypeIdList,
      searchTypeId,
      pagination,
      needCurSpace,
      localCurrentSpace,
      highlightId,
      handleChangeChoiceType,
      handleSearchType,
      t,
      handleMousedown,
      handleClear,
      handleTypeWrapScrollChange,
      handleScroll,
      handleSelectOption,
      handleCheckOption,
      handleApplyAuth,
      handleSetCurBiz,
      handleDebounceSearchChange,
      handleOperation,
      handleContentMouseDown,
      isSameSpaceId,
    };
  },
  render() {
    return (
      <span
        class={[
          'vue3__space-select-component',
          { 'space-select-component-common-style': this.isCommonStyle },
          { error: this.isErr },
          { active: this.isOpen },
        ]}
      >
        {this.$slots?.trigger ? (
          <div
            ref='selectRef'
            onMousedown={this.handleMousedown}
          >
            {this.$slots.trigger({
              multiple: this.multiple,
              disabled: this.disabled,
              error: this.isErr,
              active: this.isOpen,
              valueStrList: this.valueStrList,
              valueStr: this.valueStr,
              clear: this.handleClear,
            })}
          </div>
        ) : (
          <div
            ref='selectRef'
            class={[componentClassNames.selectInput, { single: !this.multiple }, { disabled: this.disabled }]}
            onMousedown={this.handleMousedown}
          >
            {this.isCommonStyle && <span class='selected-wrap-title'>{`${this.t('空间筛选')} : `}</span>}
            <span class='selected-text'>
              {this.isCommonStyle
                ? this.valueStrList.map((item, index) => (
                    <span
                      key={item.id}
                      class='selected-text-item'
                    >
                      {index !== 0 ? `   , ${item.name}` : item.name}
                      {!!item.idDisplayName && <span class='selected-text-id'>({item.idDisplayName})</span>}
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
        )}
        <div style={{ display: 'none' }}>
          <div
            ref='wrapRef'
            class={componentClassNames.pop}
            onMousedown={this.handleContentMouseDown}
          >
            <div class='search-input'>
              <Input
                ref='searchInput'
                v-model={this.searchValue}
                behavior={'simplicity'}
                placeholder={this.t('请输入关键字或标签')}
                onInput={this.handleSearchInput}
              >
                {{
                  prefix: () => <span class='icon-monitor icon-mc-search' />,
                }}
              </Input>
            </div>
            <div class='group-choice-wrap'>
              <div class={['space-type-list-wrap', { 'show-btn': this.typeWrapInfo.showBtn }]}>
                <ul
                  ref='typeListRef'
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
              {this.needChangeChoiceType && (
                <Checkbox
                  class='choice-type-checkbox'
                  modelValue={this.multiple}
                  onChange={this.handleChangeChoiceType}
                >
                  {this.t('多选')}
                </Checkbox>
              )}
            </div>

            <div
              class='space-list'
              onScroll={this.handleScroll}
            >
              {this.pagination.data.length ? (
                this.pagination.data.map(item => (
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
                    v-authority={{ active: !!(item.noAuth && !item.hasData) }}
                    data-space-id={item.id}
                    onClick={() => this.handleSelectOption(item)}
                  >
                    {this.multiple && (
                      <div onClick={(e: Event) => e.stopPropagation()}>
                        <Checkbox
                          disabled={!!item.noAuth && !item.hasData}
                          modelValue={item.isCheck}
                          onChange={v => this.handleCheckOption(v, item)}
                        />
                      </div>
                    )}
                    <span class='space-name'>
                      <span
                        class={['name', { disabled: !!item.noAuth && !item.hasData }]}
                        v-overflow-tips
                      >
                        {item.name}
                      </span>
                      {!item?.isSpecial && (
                        <span
                          class='id'
                          v-overflow-tips
                        >
                          ({item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code})
                        </span>
                      )}
                      {/* {+this.localCurrentSpace === +item.id && (
                      <span
                        class='icon-monitor icon-dingwei1 cur-position'
                        v-bk-tooltips={{
                          content: this.t('当前空间'),
                          placements: ['top'],
                        }}
                      />
                    )} */}
                    </span>
                    <span class='space-tags'>
                      {item.noAuth && !item.hasData ? (
                        <Button
                          class='auth-button'
                          size='small'
                          theme='primary'
                          text
                          onClick={(e: Event) => {
                            e.stopPropagation();
                            this.handleApplyAuth(item.id);
                          }}
                        >
                          {this.t('申请权限')}
                        </Button>
                      ) : (
                        item.tags?.map?.(tag => (
                          <span
                            key={tag.id}
                            style={{ ...(SPACE_TYPE_MAP[tag.id]?.light || SPACE_TYPE_MAP.default.light) }}
                            class='space-tags-item'
                          >
                            {SPACE_TYPE_MAP[tag.id]?.name || this.t('未知')}
                          </span>
                        ))
                      )}
                    </span>
                    {this.needCurSpace && this.canMakeCurrent(+item.id) && (
                      <span class='space-hover-btn'>
                        <Button
                          class='auth-button'
                          size='small'
                          theme='primary'
                          text
                          onClick={e => {
                            e.stopPropagation();
                            this.handleSetCurBiz(item);
                          }}
                        >
                          {this.t('设为当前空间')}
                        </Button>
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div
                  onClick={e => {
                    e.stopPropagation();
                  }}
                >
                  {!this.pageLoading && !this.pageError && !this.hasMore && (
                    <EmptyStatus
                      type={this.searchValue ? 'search-empty' : 'empty'}
                      onOperation={this.handleOperation}
                    />
                  )}
                </div>
              )}
              {this.pageLoading && <div>{this.t('加载中...')}</div>}
              {this.hasMore && !this.pageLoading && (
                <Button
                  text
                  onClick={this.loadNext}
                >
                  {this.t('加载更多...')}
                </Button>
              )}
              {(this.pageError || this.lookupError) && (
                <Button
                  text
                  onClick={this.retryPages}
                >
                  {this.t('部分空间未能确认，请重试')}
                </Button>
              )}
            </div>
          </div>
        </div>
      </span>
    );
  },
});
