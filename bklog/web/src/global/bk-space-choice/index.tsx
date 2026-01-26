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
import { defineComponent, ref, computed, watch, nextTick, onUnmounted } from 'vue';

import useLocale from '@/hooks/use-locale';
import { useNavMenu } from '@/hooks/use-nav-menu';
import { SPACE_TYPE_MAP } from '@/store/constant';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { debounce } from 'throttle-debounce';
import { useRouter, useRoute } from 'vue-router/composables';

import * as authorityMap from '../../common/authority-map';
import useStore from '../../hooks/use-store';
import useListSort from '../../hooks/use-list-sort';
import UserConfigMixin from '../../mixins/user-store-config';
import List from './list';

import './index.scss';

const userConfigMixin = new UserConfigMixin();

export type ThemeType = 'dark' | 'light';

export default defineComponent({
  name: 'BkSpaceChoice',
  props: {
    isExpand: { type: Boolean, default: true },
    theme: { type: String, default: 'dark' },
    isExternalAuth: { type: Boolean, default: false },
    canSetDefaultSpace: { type: Boolean, default: false },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const BIZ_SELECTOR_COMMON_MAX = 5; // 常用业务缓存最大个数

    const store = useStore();
    const route = useRoute();
    const router = useRouter();
    const navMenu = useNavMenu({ t, bkInfo: (window as any).bkInfo, http: (window as any).$http, emit });

    const mySpaceList = navMenu.mySpaceList;
    const checkSpaceChange = navMenu.checkSpaceChange;
    const spaceBgColor = ref('#3799BA');
    const showBizList = ref(false);
    const keyword = ref('');
    const searchTypeId = ref('');
    const exterlAuthSpaceName = ref('');
    const showDialog = ref(false);
    const defaultSpace = ref(null); // 当前弹窗中选中的业务
    const isSetBizIdDefault = ref(true); // 设为默认or取消默认
    const setDefaultBizIdLoading = ref(false); // 设置默认业务时的 loading 状态
    const DEFAULT_BIZ_ID_KEY = 'DEFAULT_BIZ_ID';
    const refRootElement = ref<HTMLElement>(null);

    const isExternal = computed(() => store.state.isExternal);
    const demoUid = computed(() => store.getters.demoUid);
    const demoSpace = computed(() => mySpaceList.value.find(item => item.space_uid === demoUid.value));

    const menuSearchInput = ref();
    const bizListRef = ref();
    const bizBoxWidth = ref(418);
    const selectedIndex = ref(-1); // 当前键盘选中的索引

    const commonListIdsLog = computed(() => store.state.storage[BK_LOG_STORAGE.COMMON_SPACE_ID_LIST] ?? []);
    const spaceUid = computed(() => store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID]);

    // 业务名称和首字母
    const bizName = computed(() => {
      if (props.isExternalAuth && !!exterlAuthSpaceName.value) {
        return exterlAuthSpaceName.value;
      }
      return mySpaceList.value.find(item => item.space_uid === spaceUid.value)?.space_name ?? '';
    });
    const bizNameIcon = computed(() => {
      return bizName.value?.[0]?.toLocaleUpperCase() ?? '';
    });

    // 是否展示空间类型列表
    const showSpaceTypeIdList = computed(() => !isExternal.value && spaceTypeIdList.value.length > 1);
    const spaceTypeIdList = computed(() => {
      const spaceTypeMap: Record<string, 1> = {};
      for (const item of mySpaceList.value) {
        spaceTypeMap[item.space_type_id] = 1;
        if (item.space_type_id === 'bkci' && item.space_code) {
          spaceTypeMap.bcs = 1;
        }
      }
      return Object.keys(spaceTypeMap).map(key => ({
        id: key,
        name: SPACE_TYPE_MAP[key]?.name || t('未知'),
        styles: (props.theme === 'dark' ? SPACE_TYPE_MAP[key]?.dark : SPACE_TYPE_MAP[key]?.light) || {},
      }));
    });

    // 点击下拉框外内容，收起下拉框
    const handleGlobalClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const isInside = refRootElement.value?.contains(target);
      if (!isInside) {
        handleClickOutSide();
      }
    };

    // 监听showBizList
    watch(showBizList, async (val) => {
      if (val) {
        document.addEventListener('click', handleGlobalClick);
        document.addEventListener('keydown', handleKeyDown);
        selectedIndex.value = -1; // 重置选中索引
        await nextTick();
        const el = document.querySelector('#space-type-ul');
        bizBoxWidth.value = Math.max(394, el?.clientWidth ?? 394) + 24;
      } else {
        document.removeEventListener('click', handleGlobalClick);
        document.removeEventListener('keydown', handleKeyDown);
        selectedIndex.value = -1; // 重置选中索引
        bizListRef.value && (bizListRef.value.scrollTop = 0);
      }
    });

    // 在组件卸载时清除监听
    onUnmounted(() => {
      document.removeEventListener('click', handleGlobalClick);
      document.removeEventListener('keydown', handleKeyDown);
    });

    // 先进行类型过滤和权限过滤，得到基础列表
    const baseFilteredList = computed(() => {
      return mySpaceList.value.filter((item) => {
        // 类型过滤
        if (searchTypeId.value) {
          const typeMatch = searchTypeId.value === 'bcs'
            ? item.space_type_id === 'bkci' && !!item.space_code
            : item.space_type_id === searchTypeId.value;
          if (!typeMatch) {
            return false;
          }
        }

        // 权限过滤
        if (!item.permission?.[authorityMap.VIEW_BUSINESS]) {
          return false;
        }

        return true;
      });
    });

    // 使用 use-list-sort 进行文本匹配和排序
    // 匹配的字段：space_name, py_text, space_uid, bk_biz_id, space_code
    const matchKeys = ['space_name', 'py_text', 'space_uid'];
    const { sortList: authorizedList, updateList, updateSearchText } = useListSort(
      baseFilteredList.value,
      matchKeys,
    );

    // 监听基础列表变化，更新排序列表
    watch(baseFilteredList, (newList) => {
      updateList(newList);
    }, { immediate: true });

    // 监听搜索关键词变化，更新搜索文本
    watch(keyword, (newKeyword) => {
      updateSearchText(newKeyword);
      // 搜索时重置选中索引
      selectedIndex.value = -1;
    }, { immediate: true });

    const commonList = computed(
      () => commonListIdsLog.value.map(id => authorizedList.value.find(item => Number(item.id) === id)).filter(Boolean)
        || [],
    );

    // 初始化业务列表
    const groupList = computed(() => {
      // 有权限业务
      const generalList = authorizedList.value.filter(item => !commonListIdsLog.value.includes(Number(item.id))) || [];

      if (commonList.value.length > 0) {
        return [
          {
            id: '__group_common__',
            name: '常用的',
            type: 'group-title',
          } as any,
          ...commonList.value,
          ...generalList,
        ];
      }
      return [...generalList];
    });

    // 获取可选择的业务项列表（过滤掉分组标题）
    const selectableItems = computed(() => {
      return groupList.value.filter(item => item.type !== 'group-title');
    });

    // 键盘事件处理
    const handleKeyDown = (e: KeyboardEvent) => {
      // 只在组件展开时处理键盘事件
      if (!showBizList.value) {
        return;
      }

      // 对于上下键、回车键和ESC键进行处理
      if (['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(e.key)) {
        switch (e.key) {
          case 'ArrowDown':
            e.preventDefault();
            e.stopPropagation();
            if (selectableItems.value.length > 0) {
              selectedIndex.value = selectedIndex.value < selectableItems.value.length - 1
                ? selectedIndex.value + 1
                : 0;
              scrollToSelectedItem();
            }
            break;
          case 'ArrowUp':
            e.preventDefault();
            e.stopPropagation();
            if (selectableItems.value.length > 0) {
              selectedIndex.value = selectedIndex.value > 0
                ? selectedIndex.value - 1
                : selectableItems.value.length - 1;
              scrollToSelectedItem();
            }
            break;
          case 'Enter':
            // 阻止默认行为，避免表单提交等
            e.preventDefault();
            e.stopPropagation();

            // 如果没有选中项，选择第一项；否则选择当前选中项
            if (selectableItems.value.length > 0) {
              let targetIndex = selectedIndex.value;

              // 如果还没有选中项，选择第一项
              if (targetIndex < 0 || targetIndex >= selectableItems.value.length) {
                targetIndex = 0;
                selectedIndex.value = 0;
              }

              const selectedItem = selectableItems.value[targetIndex];
              if (selectedItem) {
                handleClickMenuItem(selectedItem);
              }
            }
            break;
          case 'Escape':
            e.preventDefault();
            e.stopPropagation();
            showBizList.value = false;
            selectedIndex.value = -1;
            break;
          default:
            break;
        }
      }
    };

    // 滚动到选中的项
    const scrollToSelectedItem = () => {
      if (!bizListRef.value || selectedIndex.value < 0) {
        return;
      }

      nextTick(() => {
        // 找到虚拟滚动容器
        const listContainer = bizListRef.value?.$el || bizListRef.value;
        if (!listContainer) {
          return;
        }

        // 获取所有列表项（排除分组标题）
        const items = listContainer.querySelectorAll('.list-item');
        if (items.length === 0) {
          return;
        }

        // 找到当前选中的项在 DOM 中的位置
        const selectedItem = selectableItems.value[selectedIndex.value];
        if (!selectedItem) {
          return;
        }

        // 遍历 DOM 项，找到匹配的项
        let targetItem: Element | null = null;
        for (let i = 0; i < items.length; i++) {
          const item = items[i];
          const itemId = item.getAttribute('data-id') || item.querySelector('[data-space-uid]')?.getAttribute('data-space-uid');
          if (itemId && (itemId === String(selectedItem.id) || itemId === selectedItem.space_uid)) {
            targetItem = item;
            break;
          }
        }

        // 如果没找到，尝试通过索引查找
        if (!targetItem && selectedIndex.value < items.length) {
          targetItem = items[selectedIndex.value];
        }

        if (targetItem) {
          // 滚动到目标项
          targetItem.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest',
          });
        }
      });
    };

    // 点击业务名称时触发，切换下拉框显示并聚焦搜索框
    const handleClickBizSelect = () => {
      showBizList.value = !showBizList.value;
      setTimeout(() => {
        menuSearchInput.value?.focus();
      }, 100);
    };

    // 业务搜索防抖处理
    const handleBizSearchDebounce = debounce(300, (v: string) => {
      keyword.value = v;
    });

    // 点击下拉框外部，收起下拉框
    const handleClickOutSide = () => {
      showBizList.value = false;
      selectedIndex.value = -1; // 重置选中索引
    };

    // 打开设置/取消默认弹窗
    const openDialog = (data: any, isSetDefault: boolean) => {
      showDialog.value = true;
      defaultSpace.value = null; // 先清空再赋值，确保弹窗能正确响应
      setTimeout(() => {
        defaultSpace.value = data;
        isSetBizIdDefault.value = isSetDefault;
      });
    };

    // 设置/取消默认业务
    const handleDefaultId = () => {
      setDefaultBizIdLoading.value = true;
      // 如果是设置默认，取当前选中的业务ID，否则传 'undefined'
      const bizId = isSetBizIdDefault.value ? Number(defaultSpace.value?.id) : 'undefined';
      userConfigMixin
        .handleSetUserConfig(DEFAULT_BIZ_ID_KEY, `${bizId}`, '')
        .then((result) => {
          if (result) {
            store.commit('SET_APP_STATE', {
              defaultBizId: bizId,
            });
          }
        })
        .catch((e) => {
          console.log(e);
        })
        .finally(() => {
          setDefaultBizIdLoading.value = false;
          showDialog.value = false;
          defaultSpace.value = null;
        });
    };

    // 更新路由
    const debounceUpdateRouter = () => {
      return debounce(60, (space: any) => {
        store.commit('updateSpace', space.space_uid);
        store.commit('updateStorage', {
          [BK_LOG_STORAGE.BK_SPACE_UID]: space.space_uid,
          [BK_LOG_STORAGE.BK_BIZ_ID]: space.bk_biz_id,
        });

        if (`${space.bk_biz_id}` !== route.query.bizId || space.space_uid !== route.query.spaceUid) {
          const routeName = route.name === 'un-authorized' ? route.query.page_from as string : undefined;
          const appendOptions = routeName ? { name: routeName } : {};
          router.push({
            ...appendOptions,
            params: {
              ...(route.params ?? {}),
              indexId: undefined,
            },
            query: {
              ...(route.query ?? {}),
              bizId: space.bk_biz_id,
              spaceUid: space.space_uid,
            },
          });
        }
      });
    };

    // 点击空间类型选项
    const handleSearchType = (typeId: string) => {
      searchTypeId.value = typeId === searchTypeId.value ? '' : typeId;
    };

    // 点击业务选项
    const handleClickMenuItem = (space: any) => {
      debounceUpdateRouter()(space);
      try {
        if (props.isExternalAuth) {
          exterlAuthSpaceName.value = space.space_name;
          emit('space-change', space.space_uid);
          return;
        }
        navMenu.isFirstLoad.value = false;
        checkSpaceChange(space.space_uid);
        // 更新常用业务缓存
        if (space.id) {
          updateCacheBizId(Number(space.id));
        }
      } catch (error) {
        console.warn(error);
      } finally {
        showBizList.value = false;
        selectedIndex.value = -1; // 重置选中索引
      }
    };

    // 更新缓存的常用业务ids
    const updateCacheBizId = (id: number) => {
      const maxLen = BIZ_SELECTOR_COMMON_MAX;
      // 移除已存在的 id
      const cacheIds = commonListIdsLog.value.filter(item => item !== id);
      // 将当前 id 插入第一位
      cacheIds.unshift(id);

      store.commit('updateStorage', { [BK_LOG_STORAGE.COMMON_SPACE_ID_LIST]: cacheIds.slice(0, maxLen) });
    };

    // 下拉框内容渲染
    const dropdownContent = () => {
      return (
        props.isExpand && (
          <div
            style={{ display: showBizList.value ? 'flex' : 'none' }}
            class='menu-select-list'
          >
            {/* 搜索框 */}
            <bk-input
              ref={menuSearchInput}
              class='menu-select-search'
              clearable={false}
              left-icon='bk-icon icon-search'
              placeholder={t('输入关键字')}
              value={keyword.value}
              onChange={handleBizSearchDebounce}
              onClear={() => handleBizSearchDebounce('')}
            />
            {/* 空间列表 */}
            {showSpaceTypeIdList.value && (
              <ul
                id='space-type-ul'
                class='space-type-list'
              >
                {spaceTypeIdList.value.map((item: any) => (
                  <li
                    key={item.id}
                    style={{
                      ...item.styles,
                      borderColor: item.id === searchTypeId.value ? item.styles.color : 'transparent',
                    }}
                    class='space-type-item'
                    onClick={() => handleSearchType(item.id)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            )}
            {/* 业务列表 */}
            <div
              ref={bizListRef}
              style={{ width: `${bizBoxWidth.value}px` }}
              class='biz-list'
            >
              <List
                canSetDefaultSpace={props.canSetDefaultSpace as boolean}
                checked={spaceUid.value}
                commonList={commonList.value}
                list={groupList.value}
                theme={props.theme as ThemeType}
                selectedIndex={selectedIndex.value}
                selectableItems={selectableItems.value}
                on-HandleClickMenuItem={handleClickMenuItem}
                on-HandleClickOutSide={handleClickOutSide}
                on-OpenDialog={openDialog}
              />
            </div>
            {/* 体验DEMO按钮 */}
            <div class='menu-select-extension'>
              {!isExternal.value && demoUid.value && (
                <div
                  class='menu-select-extension-item'
                  onMousedown={(e) => {
                    e.stopPropagation();
                    handleClickMenuItem(demoSpace.value);
                  }}
                >
                  <span class='icon bklog-icon bklog-app-store' />
                  {t('体验DEMO')}
                </div>
              )}
            </div>
          </div>
        )
      );
    };

    // 渲染主入口
    return () => (
      <div
        ref={refRootElement}
        class={['biz-menu-select', { 'light-theme': props.theme === 'light' }]}
      >
        {/* 图标+业务名称 */}
        <div class='menu-select'>
          {/* 图标 */}
          <span
            style={{ backgroundColor: spaceBgColor.value }}
            class='menu-title'
          >
            {bizNameIcon.value}
          </span>
          {/* 业务名称 */}
          {props.isExpand && (
            <span
              class='menu-select-name'
              tabindex={0}
              onMousedown={handleClickBizSelect}
            >
              {bizName.value}
              <i
                style={{
                  transform: `rotate(${showBizList.value ? '-180deg' : '0deg'})`,
                }}
                class='bk-select-angle bk-icon icon-angle-up-fill select-icon'
              />
            </span>
          )}
          {/* 设置默认弹窗内容 */}
          <bk-dialog
            width={480}
            ext-cls='confirm-dialog__set-default'
            footer-position='center'
            mask-close={false}
            transfer={true}
            value={showDialog.value}
          >
            <div class='confirm-dialog__hd'>
              {isSetBizIdDefault.value ? '是否将该业务设为默认业务？' : '是否取消默认业务？'}
            </div>
            <div class='confirm-dialog__bd'>
              业务名称：<span class='confirm-dialog__bd-name'>{defaultSpace.value?.name || ''}</span>
            </div>
            <div class='confirm-dialog__ft'>
              {isSetBizIdDefault.value
                ? '设为默认后，每次进入日志平台将会默认选中该业务'
                : '取消默认业务后，每次进入日志平台将会默认选中最近使用的业务而非当前默认业务'}
            </div>
            <div slot='footer'>
              <bk-button
                class='btn-confirm'
                loading={setDefaultBizIdLoading.value}
                theme='primary'
                onClick={handleDefaultId}
              >
                确认
              </bk-button>
              <bk-button
                class='btn-cancel'
                onClick={() => {
                  defaultSpace.value = null;
                  showDialog.value = false;
                }}
              >
                取消
              </bk-button>
            </div>
          </bk-dialog>
        </div>
        {/* 下拉框内容 */}
        {showBizList.value && dropdownContent()}
      </div>
    );
  },
});
