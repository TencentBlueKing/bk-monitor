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
import { Button as TButton, Popup as TPopup } from 'tdesign-vue-next';
import { defineComponent, onMounted, ref } from 'vue';

import useLocale from '../../../../shared/composables/use-locale';

import { BK_LOG_STORAGE } from '../../../../app/state/store.type.ts';

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
  /** 结果展示 */
  resultDisplayLines: [
    { value: 1, name: window.$t('单行') },
    { value: 3, name: window.$t('三行') },
  ],
};

export default defineComponent({
  name: 'BarGlobalSetting',
  emits: {
    'show-index-config-slider': () => true,
  },
  setup(_, ctx) {
    const { emit } = ctx;
    const { $t } = useLocale();
    const store = useApplicationStore();

    /** popover 弹窗显隐 */
    const popoverVisible = ref(false);
    /** 显示配置 */
    const showFieldAlias = ref(true);
    // 文本省略方向
    const textEllipsisDir = ref('end');
    // 结果展示行数
    const resultDisplayLines = ref(3);

    const initDefaultSettings = () => {
      showFieldAlias.value = store.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS];
      textEllipsisDir.value = store.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
      resultDisplayLines.value = store.storage[BK_LOG_STORAGE.RESULT_DISPLAY_LINES] ?? 3;
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
     * @description 修改结果展示行数
     * @param {number} value
     */
    function setResultDisplayLines(value: number) {
      resultDisplayLines.value = value;
    }

    /**
     * @description 更新 popover 弹窗显隐
     *
     */
    function handleVisibleChange(visible: boolean) {
      popoverVisible.value = visible;
      if (!visible) initDefaultSettings();
    }

    /**
     * @description 关闭 menu下拉菜单 popover 弹窗
     *
     */
    function handlePopoverHide() {
      handleVisibleChange(false);
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
      store.updateStorage({
        [BK_LOG_STORAGE.SHOW_FIELD_ALIAS]: showFieldAlias.value,
        [BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR]: textEllipsisDir.value,
        [BK_LOG_STORAGE.RESULT_DISPLAY_LINES]: resultDisplayLines.value,
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
    function checkboxRender(activeValue: boolean | number | string, options: IOption[], clickCallback: { (value: boolean): void; (value: string): void; (value: number): void; (arg0: string|number|boolean): any; }) {
      return (
        <div class='bk-button-group'>
          {options.map(item => (
            <TButton
              key={String(item.value)}
              class={`setting-checkbox ${item.value === activeValue ? 'is-selected' : ''}`}
              size='small'
              theme='default'
              onClick={() => clickCallback(item.value)}
            >
              {item.name}
            </TButton>
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
        <div class='setting-container'>
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
            <div class='setting-item'>
              <div class='item-label'>{$t('结果展示')}</div>
              <div class='item-main'>
                {checkboxRender(
                  resultDisplayLines.value,
                  GLOBAL_SETTING_OPTIONS.resultDisplayLines,
                  setResultDisplayLines,
                )}
              </div>
            </div>
          </div>
          <div class='setting-operation'>
            <TButton
              size='small'
              theme='primary'
              onClick={handleConfirm}
            >
              {$t('确认')}
            </TButton>
            <TButton theme="default"
              size='small'
              theme='default'
              onClick={handlePopoverHide}
            >
              {$t('取消')}
            </TButton>
          </div>
        </div>
      );
    }

    return { popoverVisible, settingContainerRender, handleVisibleChange, t: $t };
  },
  render() {
    const { popoverVisible, settingContainerRender, handleVisibleChange, t } = this;

    return (
      <div class='bar-global-setting'>
        <TPopup
          visible={popoverVisible}
          trigger='click'
          placement='bottom'
          showArrow={false}
          attach='body'
          overlayInnerClassName='bar-global-setting-popover-theme'
          overlayInnerStyle={{ margin: 0 }}
          popperOptions={{ modifiers: [{ name: 'offset', options: { offset: [0, -4] } }] }}
          onVisibleChange={handleVisibleChange}
          v-slots={{ content: settingContainerRender }}
        >
          <div class={`popover-trigger ${popoverVisible ? 'is-active' : ''}`}>
            <i
              class='bklog-icon bklog-setting-line'
              v-log-tooltip={t('全局设置')}
            />
            <span class='trigger-label'>{t('全局设置')}</span>
          </div>
        </TPopup>
      </div>
    );
  },
});
