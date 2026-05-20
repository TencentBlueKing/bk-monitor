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

import type { PropType } from 'vue';
import { defineComponent, nextTick, shallowRef } from 'vue';

import { Input, Loading } from 'bkui-vue';

import './issue-name-cell.scss';

/**
 * @description Issue 名称行内编辑组件，支持查看/编辑/提交中三态切换
 * - 查看态：名称文本 + 编辑图标（hover 显示）
 * - 编辑态：Input + suffix 插槽 loading 图标
 * - 提交中：Input disabled + suffix 旋转加载图标 + ESC 拦截
 */
export default defineComponent({
  name: 'IssueNameCell',
  props: {
    /** 省略号 CSS 类名 */
    ellipsisClass: {
      type: String,
      default: '',
    },
    /** Issue 名称 */
    name: {
      type: String,
      default: '',
    },
    /** 提交重命名，返回 Promise */
    onSubmit: {
      type: Function as PropType<(newName: string) => Promise<void>>,
      required: true,
    },
    /** 点击名称查看详情 */
    onShowDetail: {
      type: Function as PropType<() => void>,
      required: true,
    },
  },
  setup(props) {
    const isEditing = shallowRef(false);
    const editingName = shallowRef('');
    const editingOriginName = shallowRef('');
    const loading = shallowRef(false);
    const inputRef = shallowRef<null | { focus?: () => void }>(null);

    /**
     * @description 进入编辑态并自动聚焦输入框
     */
    const startEdit = () => {
      editingOriginName.value = props.name || '';
      editingName.value = props.name || '';
      isEditing.value = true;
      nextTick(() => {
        inputRef.value?.focus?.();
      });
    };

    /**
     * @description 提交名称编辑
     * - 名称未变或为空时退出编辑态
     * - 名称有变化时调用 onSubmit，根据 Promise 结果决定是否退出编辑态
     * - 若编辑期间外部 name 被更新且用户未做修改，自动同步为最新值
     */
    const handleSubmit = async () => {
      if (loading.value || !isEditing.value) return;

      const nextName = editingName.value.trim();
      const currentName = (props.name || '').trim();
      const originName = editingOriginName.value.trim();

      // 编辑期间外部 name 变化且用户未修改 → 自动同步并退出编辑态
      if (currentName !== originName && nextName === originName) {
        isEditing.value = false;
        return;
      }

      if (!nextName || nextName === currentName) {
        isEditing.value = false;
        return;
      }

      loading.value = true;
      try {
        await props.onSubmit(nextName);
        isEditing.value = false;
      } catch {
        // 失败时保留编辑态，用户可直接修改后重试
      } finally {
        loading.value = false;
      }
    };

    /**
     * @description 键盘事件处理：Enter 提交 / ESC 退出编辑态（loading 时拦截）
     * @param _value bkui-vue Input onKeydown 回调的首个参数（Input 当前值），此处未使用
     * @param e      原生键盘事件
     */
    const handleKeydown = (_value: unknown, e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (loading.value) {
          e.preventDefault();
          return;
        }
        isEditing.value = false;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      }
    };

    return {
      isEditing,
      editingName,
      loading,
      inputRef,
      startEdit,
      handleSubmit,
      handleKeydown,
    };
  },
  render() {
    if (this.isEditing) {
      return (
        <div class='issue-name-cell-editing'>
          <Input
            ref={(el: null | object) => {
              this.inputRef = el as null | { focus?: () => void };
            }}
            class='issue-name-cell-input'
            v-slots={
              this.loading
                ? {
                    suffix: () => (
                      <div class='issue-name-cell-loading-wrap'>
                        <Loading
                          color='transparent'
                          loading={this.loading}
                          mode='spin'
                          opacity={0}
                          size='mini'
                          theme='primary'
                        />
                      </div>
                    ),
                  }
                : undefined
            }
            disabled={this.loading}
            modelValue={this.editingName}
            size='small'
            onBlur={this.handleSubmit}
            onInput={(value: string) => {
              this.editingName = value ?? '';
            }}
            onKeydown={this.handleKeydown}
          />
        </div>
      );
    }

    return (
      <div class='issue-name-cell-view'>
        <span
          class={`issue-name-cell-text ${this.ellipsisClass}`}
          onClick={() => this.onShowDetail?.()}
        >
          {this.name || '--'}
        </span>
        <span
          class='issue-name-cell-edit-btn'
          onClick={(e: MouseEvent) => {
            e.stopPropagation();
            this.startEdit();
          }}
        >
          <i class='icon-monitor icon-bianji' />
        </span>
      </div>
    );
  },
});
