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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { defineComponent, type PropType } from 'vue';

import { Dialog } from 'tdesign-vue-next';

import MaskingSetting from '../masking/components/masking-setting';

import './index.scss';

interface IMenuItem {
  id: string;
  name: string;
  href?: string;
}

interface IProps {
  value: boolean;
  /** 左侧menu list 不设置则不显示左侧栏 */
  menuList?: IMenuItem[];
  /** 选中的左侧栏项 */
  activeMenu?: string;
}

export default defineComponent({
compatConfig: { MODE: 3 },
name: 'global-setting',
props: {value: { type: Boolean, default: false },
menuList: { type: Array as PropType<IMenuItem[]>, default: () => [] },
activeMenu: { type: String, default: '' }},
emits: ['change', 'menu-change', "menuChange"],
computed: {showAlert() {
    return useApplicationStore().showAlert;
  }},
methods: {handleCloseDialog() {
    useApplicationStore().updateState({ isShowGlobalDialog: false });
  },
getContentPanel(activeMenu: string) {
    switch (activeMenu) {
      case 'masking-setting':
        return <MaskingSetting style={'padding: 20px 24px;'} />;
      default:
        return this.$slots.default?.();
    }
  }},
render() {
    // 关闭时不要挂 Dialog / MaskingSetting。TDesign Dialog 在 visible=false 时仍会创建内容，
    // 父级每次更新都会让这个异步组件再跑一遍，从而抛出 component update。
    if (!this.value) return null;
    return (
      <Dialog
        width='100%'
        dialogClassName='masking-dialog'
        zIndex={2999}
        top={0}
        header={false}
        closeBtn={false}
        draggable={false}
        destroyOnClose={true}
        footer={false}
        showOverlay={false}
        visible={this.value}
      >
        <div class={`masking-container ${this.showAlert ? 'is-show-notice' : ''}`}>
          <div class='masking-title'>
            <div />
            <span>{this.$t('全局设置')}</span>
            <div
              class='bk-icon icon-close'
              onClick={this.handleCloseDialog}
            />
          </div>
          <div class='center-box'>
            <div
              style={{ display: this.menuList?.length ? 'flex' : 'none' }}
              class='left-panel'
            >
              {this.menuList.map(item => (
                <div
                  key={item.id}
                  class={`menu-item ${this.activeMenu === item.id ? 'active-menu' : ''}`}
                  onClick={() => this.activeMenu !== item.id && this.$emit('menu-change', item)}
                >
                  {item.name}
                </div>
              ))}
            </div>
            <div class='content-panel'>{this.getContentPanel(this.activeMenu)}</div>
          </div>
        </div>
      </Dialog>
    );
  }
});
