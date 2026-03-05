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

import { useDebounceFn } from '@vueuse/core';
import { Button, Checkbox, Input } from 'bkui-vue';
import { bizWithAlertStatistics } from 'monitor-api/modules/home';
import EmptyStatus, { type EmptyStatusOperationType } from 'trace/components/empty-status/empty-status';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { useTippy } from 'vue-tippy';

import { useAppStore } from '../../store/modules/app';
import { type ILocalSpaceList, ETagsType, SPACE_SELECTOR_EMITS, SPACE_SELECTOR_PROPS } from './typing';
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

    const localValue = shallowRef<number[]>([]);
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
    const valueStrList = shallowRef<{ id: string; name: string }[]>([]);
    /* 是否标红 */
    const isErr = shallowRef(false);
    /* 是否弹出弹窗 */
    const isOpen = shallowRef(false);
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

    initLocalSpaceList();
    onUnmounted(() => {});
    watch(
      () => props.value,
      val => {
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
    watch(
      () => props.needAlarmOption,
      () => {
        initLocalSpaceList();
      }
    );
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

    function handleChange() {
      emit('change', localValue.value);
    }
    function handleApplyAuth(bizId: number | string) {
      handlePopoverHidden();
      emit('applyAuth', [bizId]);
    }

    function handleWatchValue(val) {
      if (JSON.stringify(val) === JSON.stringify(localValue.value)) {
        return;
      }
      const defaultRadioListIds = defaultRadioList.map(d => d.id);
      localValue.value = [...val].map(b => (defaultRadioListIds.includes(String(b)) ? b : Number(b))) as any;
      const nameList = [];
      const strList = [];
      for (const item of localSpaceList.value) {
        const has = localValue.value.includes(item.id);
        item.isCheck = has;
        if (has) {
          nameList.push(item.name);
          strList.push({
            name: item.name,
            id: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code,
          });
        }
      }
      valueStr.value = nameList.join(',');
      valueStrList.value = strList;
      sortSpaceList();
    }

    function initLocalSpaceList() {
      localSpaceList.value = getSpaceList(props.spaceList);
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
          name: t('-我有告警的空间-'),
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
      if (props.hasAuthApply) {
        setAllowed();
      } else {
        if (props.value.length && !localValue.value.length) {
          handleWatchValue(props.value);
        }
        setPaginationData(true);
      }
    }

    function handleMousedown() {
      if (popInstance || props.disabled) {
        return;
      }
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
      sortSpaceList();
      setPaginationData(true);
      setTimeout(() => {
        addMousedownEvent();
      }, 300);
    }

    function addMousedownEvent() {
      controller?.abort?.();
      controller = new AbortController();
      document.addEventListener('click', handleMousedownRemovePop, { signal: controller.signal });
      typeListWrapNextPreShowChange();
    }

    function handleMousedownRemovePop(event: Event) {
      const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
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
      if (pathsClass.includes(componentClassNames.pop)) {
        return;
      }
      handlePopoverHidden();
    }

    function handlePopoverHidden() {
      popInstance?.hide();
      popInstance?.destroy?.();
      searchValue.value = '';
      searchTypeId.value = '';
      popInstance = null;
      controller?.abort?.();
      isOpen.value = false;
      for (const item of localSpaceList.value) {
        item.show = true;
        item.preciseMatch = false;
      }
      triggerRef(localSpaceList);
      if (needCurSpace.value) {
        if (+localCurrentSpace.value !== +props.currentSpace) {
          resetCurBiz(+localCurrentSpace.value);
        }
      }
      if (!!localValue.value.length && JSON.stringify(props.value) !== JSON.stringify(localValue.value)) {
        handleAutoSetCurBiz();
        setTimeout(() => {
          handleChange();
        }, 50);
      }
    }

    function resetCurBiz(curSpace: number) {
      appStore.bizId = curSpace;
      const searchParams = new URLSearchParams({ bizId: `${curSpace}` });
      const newUrl = `${window.location.pathname}?${searchParams.toString()}#${route.fullPath}`;
      history.replaceState({}, '', newUrl);
    }

    function handleAutoSetCurBiz() {
      if (props.isAutoSelectCurrentSpace) {
        const selected = localValue.value.filter(v => !specialIds.includes(v));
        if (selected.length === 1) {
          if (+selected[0] !== localCurrentSpace.value) {
            resetCurBiz(+selected[0]);
          }
          localCurrentSpace.value = +selected[0];
        }
      }
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
            id: item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code,
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
        const tags = [{ id: item.space_type_id, name: item.type_name, type: item.space_type_id }];
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
        spaceTypeMap[item.space_type_id] = 1;
        if (item.space_type_id === 'bkci' && item.space_code) {
          spaceTypeMap.bcs = 1;
        }
      });
      spaceTypeIdList.value = Object.keys(spaceTypeMap).map(key => ({
        id: key,
        name: SPACE_TYPE_MAP[key]?.name || t('未知'),
        styles: SPACE_TYPE_MAP[key] || SPACE_TYPE_MAP.default,
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
      for (const item of localSpaceList.value) {
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
      for (const id of props.value) {
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
      localSpaceList.value.push(...otherSpaces);
      localValue.value = [];
      handleWatchValue(props.value);
      setPaginationData(true);
    }

    function setPaginationData(isInit = false) {
      const showData = [];
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

      showData.push(...prevArr, ...nextArr);
      pagination.count = showData.length;
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
      if (!!item.noAuth && !item.hasData) {
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
        setPaginationData(false);
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
        )}
        <div style={{ display: 'none' }}>
          <div
            ref='wrapRef'
            class={componentClassNames.pop}
          >
            <div class='search-input'>
              <Input
                v-model={this.searchValue}
                behavior={'simplicity'}
                placeholder={this.t('请输入关键字或标签')}
                onInput={this.handleDebounceSearchChange}
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
                      {
                        'no-hover-btn':
                          !this.needCurSpace ||
                          +this.localCurrentSpace === +item.id ||
                          specialIds.includes(item.id) ||
                          (!!item.noAuth && !item.hasData),
                      },
                    ]}
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
                      {!!item.noAuth && !item.hasData ? (
                        <Button
                          class='auth-button'
                          size='small'
                          theme='primary'
                          text
                          onClick={() => this.handleApplyAuth(item.id)}
                        >
                          {this.t('申请权限')}
                        </Button>
                      ) : (
                        item.tags?.map?.(tag => (
                          <span
                            key={tag.id}
                            style={{ ...(SPACE_TYPE_MAP[tag.id] || SPACE_TYPE_MAP.default) }}
                            class='space-tags-item'
                          >
                            {SPACE_TYPE_MAP[tag.id]?.name || this.t('未知')}
                          </span>
                        ))
                      )}
                    </span>
                    {this.needCurSpace && (
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
                  <EmptyStatus
                    type={this.searchValue ? 'search-empty' : 'empty'}
                    onOperation={this.handleOperation}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </span>
    );
  },
});
