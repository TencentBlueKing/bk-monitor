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
import { computed, defineComponent, ref, type PropType } from 'vue';
import { Popup } from 'tdesign-vue-next';
import useLocale from '@/shared/composables/use-locale';
import './setting-more-menu.scss';

type MenuOperation = 'edit' | 'export' | 'delete';
interface MenuOption {
  id: MenuOperation;
  name: string;
}

export default defineComponent({
  name: 'FieldSettingMoreMenu',
  props: {
    settingMoreList: { type: Array as PropType<MenuOption[]>, default: undefined },
  },
  emits: { 'menu-click': (_operation: MenuOperation) => true },
  setup(props, { emit }) {
    const { $t } = useLocale();
    const visible = ref(false);
    const menu = computed<MenuOption[]>(
      () =>
        props.settingMoreList ?? [
          { id: 'edit', name: $t('重命名') },
          { id: 'export', name: $t('导出') },
          { id: 'delete', name: $t('删除') },
        ],
    );
    function handleMenuClick(operation: MenuOperation) {
      visible.value = false;
      emit('menu-click', operation);
    }
    return () => (
      <div class='field-setting-more'>
        <Popup
          visible={visible.value}
          onVisibleChange={(value) => {
            visible.value = value;
          }}
          trigger='click'
          placement='bottom-right'
          overlayClassName='bklog-v3-popover-tag field-template-menu field-template-menu-expand'
          content={() => (
            <ul class='field-setting-list-menu bklog-v3-popover-tag'>
              {menu.value.map((item) => (
                <li key={item.id} class='menu-item' onClick={() => handleMenuClick(item.id)}>
                  {item.name}
                </li>
              ))}
            </ul>
          )}
        >
          <div class={`popover-trigger ${visible.value ? 'is-active' : ''}`}>
            <i class='bklog-icon bklog-more' />
          </div>
        </Popup>
      </div>
    );
  },
});
