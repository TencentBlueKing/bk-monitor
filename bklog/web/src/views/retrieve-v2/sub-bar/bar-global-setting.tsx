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
import Vue, { defineComponent, nextTick, onMounted, ref } from 'vue';

import { Instance } from 'tippy.js';

import useLocale from '../../../hooks/use-locale';
import useStore from '../../../hooks/use-store';
import { BK_LOG_STORAGE } from '../../../store/store.type';

import './bar-global-setting.scss';

interface IOption {
  value: boolean | number | string;
  name: string;
}

/** 全局设置选项列表配置 */
const GLOBAL_SETTING_OPTIONS: Record<string, IOption[]> = {
  /** 显示 */
  showFieldAlias: [
    {
      value: false,
      name: window.$t('名称'),
    },
    {
      value: true,
      name: window.$t('别名'),
    },
  ],
  /** 文本省略方向 */
  textEllipsisDirs: [
    { value: 'end', name: 'ab...' },
    { value: 'start', name: '...yz' },
  ],
};

export default defineComponent({
  name: 'BarGlobalSetting',
  emits: {
    'show-index-config-slider': () => true,
  },
  setup(_, ctx) {
    const { emit } = ctx;
    const { $bkPopover } = Vue.prototype;
    const { $t } = useLocale();
    const store = useStore();

    /** popover 弹出显示内容容器 */
    const containerRef = ref<Element | null>(null);

    /** popover 弹窗实例 */
    const popoverInstance = ref<Instance>(null);
    /** 显示配置 */
    const showFieldAlias = ref(true);
    // 文本省略方向
    const textEllipsisDir = ref('end');

    const initDefaultSettings = () => {
      showFieldAlias.value = store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS];
      textEllipsisDir.value = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
    };

    onMounted(() => {
      initDefaultSettings();
    });

    /**
     * @description 修改显示配置
     * @param {Boolean} value
     *
     */
    function setShowFieldAlias(value: boolean) {
      showFieldAlias.value = value;
    }
    /**
     * @description 修改文本省略方向
     * @param {'start' | 'end'} value
     */
    function setTextEllipsisDir(value: string) {
      textEllipsisDir.value = value;
    }

    /**
     * @description 打开 menu下拉菜单 popover 弹窗
     *
     */
    function handleSettingPopoverShow(e: Event) {
      if (popoverInstance.value) {
        handlePopoverHide();
        return;
      }
      popoverInstance.value = $bkPopover(e.currentTarget, {
        content: containerRef.value,
        animateFill: false,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light bk-select-dropdown bk-select-dropdown-expand bar-global-setting-popover',
        arrow: false,
        followCursor: false,
        boundary: 'viewport',
        interactive: true,
        distance: -4,
        onHidden: () => {
          popoverInstance.value?.destroy?.();
          popoverInstance.value = null;
          initDefaultSettings();
        },
      });
      nextTick(() => {
        popoverInstance.value?.show();
      });
    }

    /**
     * @description 关闭 menu下拉菜单 popover 弹窗
     *
     */
    function handlePopoverHide() {
      popoverInstance.value?.hide?.();
      popoverInstance.value?.destroy?.();
      popoverInstance.value = null;
    }

    /**
     * @description 打开 索引配置 抽屉页
     */
    function handleIndexConfigSliderShow() {
      handlePopoverHide();
      emit('show-index-config-slider');
    }

    /**
     * @description 确认修改配置
     *
     */
    function handleConfirm() {
      // 存入localstorage
      store.commit('updateStorage', {
        [BK_LOG_STORAGE.SHOW_FIELD_ALIAS]: showFieldAlias.value,
        [BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR]: textEllipsisDir.value,
      });
      handlePopoverHide();
    }

    /**
     * @description checkbox 渲染
     * @param activeValue 当前选中项
     * @param options 选项列表
     * @param clickCallback 点击回调
     *
     */
    function checkboxRender(activeValue: boolean | number | string, options: IOption[], clickCallback) {
      return (
        <div class='bk-button-group'>
          {options.map(item => (
            <bk-button
              key={item.value}
              class={`setting-checkbox ${item.value === activeValue ? 'is-selected' : ''}`}
              size='small'
              onClick={() => clickCallback(item.value)}
            >
              {item.name}
            </bk-button>
          ))}
        </div>
      );
    }

    /**
     * @description popover 弹窗内容区域渲染
     *
     */
    function settingContainerRender() {
      return (
        <div
          ref={vm => (containerRef.value = vm as Element)}
          class='setting-container'
        >
          <div class='setting-content'>
            <div class='setting-item'>
              <div class='item-label'>{$t('字段名称设置')}</div>
              <div class='item-main'>
                {checkboxRender(showFieldAlias.value, GLOBAL_SETTING_OPTIONS.showFieldAlias, setShowFieldAlias)}
                <div
                  class='link'
                  onClick={handleIndexConfigSliderShow}
                >
                  <span class='link-text'>{$t('前往 "批量编辑别名" 批量修改别名')}</span>
                  <i class='bklog-icon bklog-jump' />
                </div>
              </div>
            </div>
            <div class='setting-item'>
              <div class='item-label'>{$t('文本溢出（省略设置）')}</div>
              <div class='item-main'>
                {checkboxRender(textEllipsisDir.value, GLOBAL_SETTING_OPTIONS.textEllipsisDirs, setTextEllipsisDir)}
              </div>
            </div>
          </div>
          <div class='setting-operation'>
            <bk-button
              size='small'
              theme='primary'
              onclick={handleConfirm}
            >
              {$t('确认')}
            </bk-button>
            <bk-button
              size='small'
              onclick={handlePopoverHide}
            >
              {$t('取消')}
            </bk-button>
          </div>
        </div>
      );
    }

    return { popoverInstance, settingContainerRender, handleSettingPopoverShow, t: $t };
  },
  render() {
    const { popoverInstance, settingContainerRender, handleSettingPopoverShow, t } = this;

    return (
      <div class='bar-global-setting'>
        <div
          class={`popover-trigger ${popoverInstance ? 'is-active' : ''}`}
          onClick={handleSettingPopoverShow}
        >
          <i
            class='bklog-icon bklog-setting-line'
            v-bk-tooltips={t('全局设置')}
          />
          <span class='trigger-label'>{t('全局设置')}</span>
        </div>
        <div style='display: none'>{settingContainerRender()}</div>
      </div>
    );
  },
});
