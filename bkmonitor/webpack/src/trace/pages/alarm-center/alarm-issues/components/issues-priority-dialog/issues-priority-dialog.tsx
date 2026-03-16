/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { defineComponent, shallowRef, watch } from 'vue';

import { Button, Dialog, Radio } from 'bkui-vue';

import { IssuePriorityEnum, IssuesPriorityMap } from '../../constant';

import type { IssuePriorityType } from '../../typing';

import './issues-priority-dialog.scss';

/** 优先级选项列表 */
const PRIORITY_OPTIONS: IssuePriorityType[] = [IssuePriorityEnum.HIGH, IssuePriorityEnum.MEDIUM, IssuePriorityEnum.LOW];

export default defineComponent({
  name: 'IssuesPriorityDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    confirm: (priority: IssuePriorityType) => typeof priority === 'string',
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    /** 当前选中的优先级 */
    const selectedPriority = shallowRef<'' | IssuePriorityType>('');

    // 每次弹窗打开时重置选中状态
    watch(
      () => props.isShow,
      val => {
        if (val) {
          selectedPriority.value = '';
        }
      }
    );

    /**
     * @description 确认修改优先级
     */
    const handleConfirm = () => {
      if (!selectedPriority.value) return;
      emit('confirm', selectedPriority.value as IssuePriorityType);
    };

    /**
     * @description 取消修改优先级
     */
    const handleCancel = () => {
      emit('cancel');
    };

    return {
      selectedPriority,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={480}
        v-slots={{
          default: () => (
            <div class='issues-priority-dialog-content'>
              <div class='priority-field'>
                <span class='priority-label'>
                  {window.i18n.t('优先级')}
                  <span class='required'>*</span>
                </span>
                <Radio.Group
                  class='priority-radio-group'
                  modelValue={this.selectedPriority}
                  onChange={(val: IssuePriorityType) => {
                    this.selectedPriority = val;
                  }}
                >
                  {PRIORITY_OPTIONS.map(priority => {
                    const config = IssuesPriorityMap[priority];
                    return (
                      <Radio
                        key={priority}
                        label={priority}
                      >
                        <span
                          style={{
                            backgroundColor: config.bgColor,
                            color: config.color,
                          }}
                          class='priority-tag'
                        >
                          {config.alias}
                        </span>
                      </Radio>
                    );
                  })}
                </Radio.Group>
              </div>
            </div>
          ),
          footer: () => (
            <div class='issues-priority-dialog-footer'>
              <Button
                style='margin-right: 8px'
                disabled={!this.selectedPriority}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {window.i18n.t('确定')}
              </Button>
              <Button onClick={this.handleCancel}>{window.i18n.t('取消')}</Button>
            </div>
          ),
        }}
        header-position='left'
        isShow={this.isShow}
        title={window.i18n.t('批量修改优先级')}
        onUpdate:isShow={(v: boolean) => {
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
