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

import { defineComponent } from 'vue';
import { getOsCommandLabel } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  name: 'ControlOperate',
  props: {
    confirmEnable: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const handelClickConfirm = () => {
      emit('confirm');
    };

    const handleKeydownClick = e => {
      // key arrow-up
      if (e.keyCode === 38) {
        emit('up');
        return;
      }

      // key arrow-down
      if (e.keyCode === 40) {
        emit('down');
        return;
      }

      // ctrl + enter  e.ctrlKey || e.metaKey兼容Mac的Command键‌
      if ((e.ctrlKey || e.metaKey) && e.keyCode === 13) {
        emit('ctrlenter');
        return;
      }

      // key enter
      if (e.keyCode === 13 || e.code === 'NumpadEnter') {
        emit('enter');
        return;
      }

      // key esc
      if (e.keyCode === 27) {
        emit('esc');
        return;
      }
    };

    const handleClickCancel = () => {
      emit('cancel');
    };

    const bindKeyEvent = () => {
      window.addEventListener('keydown', handleKeydownClick);
    };

    const unbindKeyEvent = () => {
      window.removeEventListener('keydown', handleKeydownClick);
    };

    expose({ bindKeyEvent, unbindKeyEvent });

    return () => (
      <div class='control-operate-main'>
        <div class='shortcut-key'>
          <div class='shortcut-item'>
            <log-icon
              type='arrow-down-filled'
              class='label up'
            />
            <log-icon
              type='arrow-down-filled'
              class='label'
            />
            <span class='value'>{t('移动光标')}</span>
          </div>
          <div class='shortcut-item'>
            <span class='label'>Enter</span>
            <span class='value'>{t('选中')}</span>
          </div>
          <div class='shortcut-item'>
            <span class='label'>Esc</span>
            <span class='value'>{t('收起查询')}</span>
          </div>
          <div class='shortcut-item'>
            <span class='label'>{getOsCommandLabel()}+Enter</span>
            <span class='value'>{t('提交查询')}</span>
          </div>
        </div>
        <div class='btn-opts'>
          <bk-button
            class='save-btn'
            disabled={props.confirmEnable}
            theme='primary'
            on-click={handelClickConfirm}
          >
            {t('确定')} {getOsCommandLabel()} + Enter
          </bk-button>
          <bk-button
            class='cancel-btn'
            on-click={handleClickCancel}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
