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
import { computed, defineComponent, shallowRef, watch } from 'vue';

import { Button, Checkbox, Dialog } from 'bkui-vue';
import { Close } from 'bkui-vue/lib/icon';

import './tapd-field-config-dialog.scss';

export interface FieldConfigItem {
  id: string;
  isCore?: boolean;
  name: string;
  required?: boolean;
  source?: string;
}

export default defineComponent({
  name: 'TapdFieldConfigDialog',
  props: {
    show: {
      type: Boolean,
      default: true,
    },
    /** 所有可选字段 */
    sourceList: {
      type: Array as () => FieldConfigItem[],
      default: () => [],
    },
    /** 已选字段（包含核心字段） */
    targetList: {
      type: Array as () => FieldConfigItem[],
      default: () => [],
    },
  },
  emits: ['update:show', 'confirm'],
  setup(props, { emit }) {
    /** 已选字段列表（内部状态） */
    const selectedList = shallowRef<FieldConfigItem[]>([]);

    /** 已选字段 id 集合 */
    const selectedIdSet = computed(() => new Set(selectedList.value.map(item => item.id)));

    /** 核心字段 id 集合 */
    const coreIdSet = computed(() => new Set(props.targetList.filter(item => item.isCore).map(item => item.id)));

    /** 可选字段列表 */
    const optionalList = computed(() => {
      return props.sourceList.filter(item => !selectedIdSet.value.has(item.id));
    });

    /** 打开弹窗时初始化 */
    const handleAfterShow = () => {
      selectedList.value = props.targetList.map(item => ({ ...item }));
    };

    /** 关闭弹窗 */
    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    /** 添加字段到已选 */
    const handleAddField = (field: FieldConfigItem) => {
      if (selectedIdSet.value.has(field.id)) return;
      selectedList.value = [...selectedList.value, { ...field, required: false }];
    };

    /** 移除已选字段 */
    const handleRemoveField = (index: number) => {
      selectedList.value = selectedList.value.filter((_, i) => i !== index);
    };

    /** 切换字段必填状态 */
    const handleToggleRequired = (item: FieldConfigItem) => {
      if (item.isCore) return;
      selectedList.value = selectedList.value.map(i => (i.id === item.id ? { ...i, required: !i.required } : i));
    };

    /** 确定 */
    const handleConfirm = () => {
      emit('confirm', selectedList.value);
      handleShowChange(false);
    };

    /** 监听 show 变化，打开时初始化 */
    watch(
      () => props.show,
      isShow => {
        if (isShow) {
          handleAfterShow();
        }
      }
    );

    return {
      selectedList,
      optionalList,
      coreIdSet,
      handleAfterShow,
      handleShowChange,
      handleAddField,
      handleRemoveField,
      handleToggleRequired,
      handleConfirm,
    };
  },
  render() {
    return (
      <Dialog
        width={848}
        class='tapd-field-config-dialog'
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          header: () => (
            <div class='tapd-field-config-dialog-header'>
              <span class='dialog-header-title'>{this.$t('管理字段')}</span>
              <div class='dialog-header-divider' />
              <span class='dialog-header-subtitle'>{this.$t('配置创建 Issue 单据时展示的字段')}</span>
            </div>
          ),
          default: () => (
            <div class='tapd-field-config-dialog-body'>
              <div class='dialog-tips'>
                <i class='icon-monitor icon-hint' />
                <ul class='dialog-tips-content'>
                  <li>{this.$t('核心字段：为平台固定必填、不可移除；')}</li>
                  <li>{this.$t('可选字段：只能从模板 / 单据类型已有字段中勾选，不支持新增字段；')}</li>
                  <li>{this.$t('必填配置：可选字段勾选后可设置为「必填」，AI 将按照来源自动回填默认值。')}</li>
                </ul>
              </div>

              <div class='dialog-transfer'>
                {/* 可选字段 */}
                <div class='dialog-panel dialog-panel-source'>
                  <div class='dialog-panel-header'>
                    <span class='dialog-panel-title'>{this.$t('可选字段')}</span>
                    <div class='dialog-panel-divider' />
                    <span class='dialog-panel-description'>{this.$t('点击添加到 <已选字段>')}</span>
                  </div>
                  <ul class='dialog-panel-list'>
                    {this.optionalList.map(field => (
                      <li
                        key={field.id}
                        class='dialog-panel-item'
                        onClick={() => this.handleAddField(field)}
                      >
                        <div class='item-left'>
                          <span class='dialog-panel-item-name'>{field.name}</span>
                        </div>
                        <div class='item-right'>
                          {field.source && (
                            <div class='item-tag'>
                              <span class='dialog-tag-label'>{field.source}</span>
                            </div>
                          )}
                          <i class='icon-monitor icon-back-right dialog-panel-item-arrow' />
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 已选字段 */}
                <div class='dialog-panel dialog-panel-target'>
                  <div class='dialog-panel-header'>
                    <span class='dialog-panel-title'>{this.$t('已选字段')}</span>
                    <div class='dialog-panel-divider' />
                    <span class='dialog-panel-description'>{this.$t(' <核心字段> 锁定不可移除且必填')}</span>
                  </div>
                  <ul class='dialog-panel-list'>
                    {this.selectedList.map((field, index) => {
                      const isCore = field.isCore || this.coreIdSet.has(field.id);
                      return (
                        <li
                          key={field.id}
                          class={{
                            'dialog-panel-item': true,
                            'dialog-panel-item-core': isCore,
                          }}
                        >
                          <div class='item-left'>
                            <span class='dialog-panel-item-name'>{field.name}</span>
                          </div>
                          <div class='item-right'>
                            {isCore ? (
                              <div class='item-tag dialog-core-tag'>
                                <span class='dialog-tag-label'>{this.$t('核心 · 必填')}</span>
                              </div>
                            ) : (
                              <>
                                {field.source && (
                                  <div class='item-tag'>
                                    <span class='dialog-tag-label'>{field.source}</span>
                                  </div>
                                )}
                                <div class='item-required-operation'>
                                  <Checkbox
                                    class='dialog-required-checkbox'
                                    modelValue={field.required}
                                    onChange={() => this.handleToggleRequired(field)}
                                  />
                                  <span class='dialog-required-label'>{this.$t('必填')}</span>
                                </div>
                                <span
                                  class='dialog-remove-btn'
                                  onClick={() => this.handleRemoveField(index)}
                                >
                                  <Close />
                                </span>
                              </>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>
            </div>
          ),
          footer: () => (
            <div class='tapd-field-config-dialog-footer'>
              <Button
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.$t('确定')}
              </Button>
              <Button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</Button>
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
