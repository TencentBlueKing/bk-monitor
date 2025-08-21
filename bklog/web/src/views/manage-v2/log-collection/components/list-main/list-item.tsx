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
import { computed, defineComponent, onBeforeUnmount, onMounted, ref, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import AddIndexSet from '../common-comp/add-index-set';

import './list-item.scss';

interface ListItemData {
  key: string;
  label: string;
  count?: number;
  icon?: string;
  unEditable?: boolean;
  [key: string]: any;
}

export default defineComponent({
  name: 'ListItem',
  props: {
    data: {
      type: Object as PropType<ListItemData>,
      required: true,
    },
    activeKey: {
      type: String,
      default: 'all',
    },
  },
  emits: ['choose'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const rootRef = ref<HTMLSpanElement>();
    const panelRef = ref<HTMLDivElement>();
    const groupNameEditPanelRef = ref<HTMLDivElement>();
    const delPanelRef = ref<HTMLDivElement>();
    const isHover = ref(false);
    const popoverOptions = {
      arrow: false,
      trigger: 'click',
      interactive: true,
      hideOnClick: true,
      appendTo: () => document.body,
    };

    const menuList = [
      { label: t('重命名'), key: 'edit' },
      { label: t('删除'), key: 'delete' },
    ];

    const isEnableGroupAction = computed(() => !props.data.unEditable);

    let tippyInstance: Instance | null = null;
    let editGroupInstance: Instance | null = null;
    let delInstance: Instance | null = null;

    const initActionPop = () => {
      if (!isEnableGroupAction.value) return;
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        ...popoverOptions,
        content: panelRef.value as any,
        placement: 'bottom-end',
        theme: 'light group-item-action-panel',
        onShow: () => {
          isHover.value = true;
        },
        onHide: () => {
          isHover.value = false;
        },
      });
    };

    /** 渲染相关操作 */
    const initManagePop = (kind: 'delete' | 'edit') => {
      if (!isEnableGroupAction.value) return;
      isHover.value = true;
      const isEdit = kind === 'edit';
      const content = isEdit ? (groupNameEditPanelRef.value as any) : (delPanelRef.value as any);
      const theme = isEdit ? 'light group-item-edit-panel' : 'light group-item-del-panel';

      const instance = tippy(rootRef.value as SingleTarget, {
        ...popoverOptions,
        content,
        arrow: true,
        placement: 'bottom',
        theme,
        offset: [1, -5],
        onShow: () => {
          tippyInstance?.hide();
          // if (isEdit) editFormRef.value?.clearError?.();
        },
        onHide: () => {
          setTimeout(() => {
            if (isEdit) {
              editGroupInstance?.destroy();
            } else {
              delInstance?.destroy();
            }
          }, 0);
          isHover.value = false;
        },
      });

      if (isEdit) {
        editGroupInstance = instance;
      } else {
        delInstance = instance;
      }

      instance.show();
    };

    /** 重命名 */
    const initEditGroupPop = () => initManagePop('edit');
    /** 删除索引集 */
    const initDelPop = () => initManagePop('delete');
    /** 选中具体某个操作 */
    const handleMenuClick = (type: string) => {
      tippyInstance?.hide();
      if (type === 'edit') initEditGroupPop();
      else if (type === 'delete') initDelPop();
    };

    const handleEditGroupCancel = () => editGroupInstance?.hide();
    const handleDelCancel = () => delInstance?.hide();
    /** 确认重命名 */
    const handleEditGroupSubmit = () => {
      handleEditGroupCancel();
    };
    /** 确认删除 */
    const handleDelSubmit = () => {
      handleDelCancel();
    };

    onMounted(initActionPop);

    onBeforeUnmount(() => {
      tippyInstance?.hide();
      tippyInstance?.destroy();
      editGroupInstance?.hide();
      editGroupInstance?.destroy();
      delInstance?.hide();
      delInstance?.destroy();
    });

    const handleItem = () => emit('choose', props.data);

    // 渲染操作项
    const renderOperations = () => (
      <div
        ref={panelRef}
        class='popover-operations-box'
      >
        {menuList.map(menu => {
          const isCanDel = menu.key === 'delete' && !props.data.isDelete;
          return (
            <span
              key={menu.key}
              class={{
                'operation-item': true,
                disabled: isCanDel,
              }}
              v-bk-tooltips={{
                content: t('当前索引集在 仪表盘/告警策略 中有使用无法删除'),
                placements: ['right'],
                width: 240,
                disabled: !isCanDel,
              }}
              onClick={() => !isCanDel && handleMenuClick(menu.key)}
            >
              {menu.label}
            </span>
          );
        })}
      </div>
    );

    // 新增/修改索引集名称
    const renderAddIndexSet = (item: ListItemData) => (
      <AddIndexSet
        data={item}
        on-cancel={handleEditGroupCancel}
        on-submit={handleEditGroupSubmit}
      />
    );

    // 删除索引集
    const renderDelIndexSet = (item: ListItemData) => (
      <div class='popover-del-index-set'>
        <div class='title'>{t('确认删除该索引集？')}</div>
        <div class='del-content'>
          {t('索引集名称')}：<span class='del-index-name'>{item.label}</span>
        </div>
        <div class='del-tips'>{t('删除索引集，不影响已有的采集项。')}</div>
        <div class='btns-box del-btns'>
          <bk-button
            class='mr8'
            size='small'
            theme='danger'
            onClick={handleDelSubmit}
          >
            {t('删除')}
          </bk-button>
          <bk-button
            size='small'
            onClick={handleDelCancel}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );

    return () => (
      <div
        class={{
          'group-item-info': true,
          'is-hover': isHover.value,
          'is-editable-disable': !isEnableGroupAction.value,
        }}
      >
        <div
          class={['base-item', { active: props.activeKey === props.data.key }]}
          onClick={handleItem}
        >
          <i class={`bklog-icon item-icon bklog-${props.data.icon || 'file-close'}`}></i>
          <div class='item-label'>{props.data.label}</div>
          <div class='item-count'>{props.data.count}</div>
        </div>
        {isEnableGroupAction.value && (
          <span
            ref={rootRef}
            class='base-item-more'
          >
            <i class='bklog-icon bklog-more' />
          </span>
        )}
        {isEnableGroupAction.value && (
          <div>
            {renderOperations()}
            <div style='display: none'>
              <div ref={groupNameEditPanelRef}>{renderAddIndexSet(props.data)}</div>
              <div ref={delPanelRef}>{renderDelIndexSet(props.data)}</div>
            </div>
          </div>
        )}
      </div>
    );
  },
});
