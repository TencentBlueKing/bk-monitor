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
import { computed, defineComponent, nextTick, shallowRef, useTemplateRef, watch } from 'vue';

import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import './text-overflow-copy.scss';

/**
 * TextOverflowCopy 组件
 * Vue 3 版本 - 文本溢出显示复制按钮
 */
export default defineComponent({
  name: 'TextOverflowCopy',
  props: {
    /**
     * 值
     */
    val: {
      type: [Array, String, Object],
      default: '',
    },
    /**
     * 是否总是显示复制按钮
     */
    isEveryCopy: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useI18n();

    // 包装元素引用
    const wrapRef = useTemplateRef<HTMLDivElement>('wrapRef');

    // 是否显示复制按钮
    const hasCopy = shallowRef(false);

    // 计算文本值
    const text = computed(() => {
      const val = props.val;
      if (Array.isArray(val)) {
        return val.join(',');
      }
      if (typeof val === 'object' && val !== null) {
        return ((val as Record<string, unknown>).text as string) || '';
      }
      return String(val);
    });

    /**
     * 检查文本是否溢出
     */
    const checkOverflow = () => {
      nextTick(() => {
        const el = wrapRef.value;
        if (!el) {
          hasCopy.value = false;
          return;
        }
        const { scrollWidth, clientWidth } = el;
        hasCopy.value = scrollWidth > clientWidth;
      });
    };

    // 监听 val 变化
    watch(
      () => props.val,
      () => {
        checkOverflow();
      },
      { immediate: true }
    );

    /**
     * 处理复制
     */
    const handleCopy = (e: MouseEvent) => {
      e.stopPropagation();
      copyText(text.value, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };

    /**
     * 获取图标
     */
    const getIcon = () => {
      const val = props.val;
      if (typeof val === 'object' && val !== null && 'icon' in val) {
        const icon = (val as Record<string, unknown>).icon as string;
        if (!icon) return null;
        if (icon.length > 30) {
          return (
            <img
              alt=''
              src={icon}
            />
          );
        }
        return <i class={['icon-monitor', 'string-icon', icon]} />;
      }
      return null;
    };

    return {
      text,
      hasCopy,
      handleCopy,
      getIcon,
    };
  },
  render() {
    return (
      <div
        ref='wrapRef'
        class={{
          'text-overflow-copy-comp': true,
          'has-copy': this.hasCopy || this.isEveryCopy,
        }}
      >
        {this.getIcon()}
        {this.text}
        {(this.isEveryCopy || this.hasCopy) && (
          <span
            class='icon-monitor icon-mc-copy'
            v-bk-tooltips={{ content: this.$t('复制') }}
            onClick={this.handleCopy}
          />
        )}
      </div>
    );
  },
});
