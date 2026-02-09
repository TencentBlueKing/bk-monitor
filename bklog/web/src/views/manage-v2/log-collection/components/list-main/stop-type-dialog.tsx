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

import { defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import './stop-type-dialog.scss';
/**
 * 请确认停用类型弹窗
 */

export default defineComponent({
  name: 'StopTypeDialog',
  props: {
    showDialog: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const activeKey = ref(true);
    const typeList = [
      {
        label: t('停用索引集'),
        tips: t('索引集停用后，该索引集将无法检索。'),
        icon: 'tingyongwenjianjia',
        key: true,
      },
      {
        label: t('停用采集配置'),
        tips: t('采集项停用后，在有效期内，您仍可检索历史日志。'),
        icon: 'tingyongcaijixiang',
        key: false,
      },
    ];

    const handleSave = () => {
      emit('update', activeKey.value);
      handleCancel();
    };

    const handleCancel = () => {
      emit('cancel', !props.showDialog);
    };

    return () => (
      <bk-dialog
        width={480}
        class='stop-type-dialog'
        header-position='left'
        mask-close={false}
        ok-text={t('下一步')}
        title={t('请确认停用类型')}
        value={props.showDialog}
        on-cancel={handleCancel}
        on-confirm={handleSave}
      >
        <div class='stop-type-dialog-content'>
          {typeList.map(item => (
            <div
              class={{
                'type-item': true,
                active: item.key === activeKey.value,
              }}
              on-click={() => {
                activeKey.value = item.key;
              }}
            >
              <div class='item-icon'>
                <i class={`bklog-icon bklog-${item.icon} method-item-icon`}></i>
              </div>
              <div class='item-main'>
                <p>{item.label}</p>
                <p class='item-tips'>{item.tips}</p>
              </div>
              <i class='bklog-icon bklog-correct icon-correct' />
            </div>
          ))}
        </div>
      </bk-dialog>
    );
  },
});
