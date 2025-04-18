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
import { defineComponent, shallowRef, useTemplateRef, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { $bkPopover, Button, Input } from 'bkui-vue';
import { Transfer } from 'bkui-vue/lib/icon';

import './explore-field-setting.scss';

export default defineComponent({
  name: 'ExploreFieldSetting',
  props: {
    sourceList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    targetList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** popover 弹窗实例 */
    let popoverInstance = null;

    /** popover 弹出显示内容容器 */
    const containerRef = useTemplateRef<HTMLElement | null>('containerRef');

    const searchInput = shallowRef('');

    /**
     * @description 打开 menu下拉菜单 popover 弹窗
     *
     */
    function handleSettingPopoverShow(e: MouseEvent) {
      if (popoverInstance) {
        handlePopoverHide();
        return;
      }
      popoverInstance = $bkPopover({
        target: e.currentTarget as HTMLElement,
        content: containerRef.value,
        trigger: 'click',
        placement: 'bottom-end',
        theme: 'light explore-table-field-setting',
        arrow: true,
        boundary: 'viewport',
        popoverDelay: 0,
        isShow: false,
        always: false,
        disabled: false,
        clickContentAutoHide: false,
        height: '',
        maxWidth: '',
        maxHeight: '',
        renderDirective: 'if',
        allowHtml: false,
        renderType: 'auto',
        padding: 0,
        offset: 0,
        zIndex: 0,
        disableTeleport: false,
        autoPlacement: false,
        autoVisibility: false,
        disableOutsideClick: false,
        disableTransform: false,
        modifiers: [],
        extCls: '',
        referenceCls: '',
        hideIgnoreReference: false,
        componentEventDelay: 0,
        forceClickoutside: false,
        immediate: false,
        // @ts-ignore
        onHide: () => {
          handlePopoverHide();
        },
      });
      popoverInstance.install();
      setTimeout(() => {
        popoverInstance?.vm?.show();
      }, 100);
    }

    /**
     * @description 关闭 menu下拉菜单 popover 弹窗
     *
     */
    function handlePopoverHide() {
      popoverInstance?.hide?.();
      popoverInstance?.close?.();
      popoverInstance = null;
    }

    /**
     * @description popover 弹窗内容区域渲染
     *
     */
    function settingContainerRender() {
      return (
        <div
          ref='containerRef'
          class='setting-container'
        >
          <span class='setting-title'>{t('字段显示')}</span>
          <div class='setting-transfer'>
            <div class='transfer-source'>
              <div class='transfer-header source-header'>
                <div class='header-title'>
                  <span class='title-label'>{t('待选字段')}</span>
                  <span class='list-count'>（213）</span>
                </div>
                <span class='header-operation disabled'>{t('全部添加')}</span>
              </div>
              <div class='source-search-input'>
                <Input
                  v-model={searchInput.value}
                  v-slots={{ prefix: () => <i class='icon-monitor icon-mc-search' /> }}
                  behavior='simplicity'
                  placeholder={t('请输入关键字')}
                  clearable
                />
              </div>
              <div class='source-list' />
            </div>
            <Transfer class='transfer-icon bk-transfer-icon' />
            <div class='transfer-target'>
              <div class='transfer-header target-header'>
                <div class='header-title'>
                  <span class='title-label'>{t('已选字段')}</span>
                  <span class='list-count'>（213）</span>
                </div>
                <span class='header-operation'>{t('清空')}</span>
              </div>
            </div>
          </div>
          <div class='setting-operation'>
            <Button
              theme='primary'
              onClick={handlePopoverHide}
            >
              {t('确定')}
            </Button>
            <Button onClick={handlePopoverHide}>{t('取消')}</Button>
          </div>
        </div>
      );
    }
    return { settingContainerRender, handleSettingPopoverShow };
  },
  render() {
    const { settingContainerRender, handleSettingPopoverShow } = this;
    return (
      <div class='explore-field-setting'>
        <div
          class='popover-trigger'
          onClick={handleSettingPopoverShow}
        >
          <i class='icon-monitor icon-shezhi1' />
        </div>
        <div style='display: none'>{settingContainerRender()}</div>
      </div>
    );
  },
});
