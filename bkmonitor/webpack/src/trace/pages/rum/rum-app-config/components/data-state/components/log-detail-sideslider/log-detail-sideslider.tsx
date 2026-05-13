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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type PropType, defineComponent, nextTick, onMounted, onUnmounted, shallowRef, watch } from 'vue';

import { Button, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import './log-detail-sideslider.scss';
import 'vue-json-pretty/lib/styles.css';

/** 日志详情侧边栏组件 */
export default defineComponent({
  name: 'LogDetailSideslider',
  props: {
    /** 日志数据 */
    log: {
      type: Object as PropType<null | Record<string, unknown>>,
      default: null,
    },
    /** 是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:isShow': (_val: boolean) => true,
    copy: (_log: Record<string, unknown>) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** JSON 容器的 ref */
    const jsonContainerRef = shallowRef<HTMLElement | null>(null);
    /** VueJsonPretty 的高度（由 jsonContainerRef.offsetHeight 计算得出） */
    const jsonContainerHeight = shallowRef(0);

    /**
     * @description 触发复制事件
     * @returns {void}
     */
    const handleCopy = (): void => {
      if (props.log) {
        emit('copy', props.log);
      }
    };

    /**
     * @description 计算容器高度
     * @returns {void}
     */
    const calculateHeight = (): void => {
      nextTick(() => {
        if (jsonContainerRef.value) {
          jsonContainerHeight.value = jsonContainerRef.value.offsetHeight;
        }
      });
    };

    /**
     * @description 监听 sideslider 显示状态与日志数据变化，触发高度重算
     * @returns {void}
     */
    watch(
      () => [props.isShow, props.log] as const,
      ([isShow]) => {
        if (isShow) {
          // 等待 sideslider 展开动画完成后再计算高度
          setTimeout(calculateHeight, 300);
        }
      }
    );

    onMounted(() => {
      window.addEventListener('resize', calculateHeight);
      calculateHeight();
    });

    onUnmounted(() => {
      window.removeEventListener('resize', calculateHeight);
    });

    return { handleCopy, t, jsonContainerRef, jsonContainerHeight };
  },
  render() {
    return (
      <Sideslider
        width={596}
        class='rum-origin-log-sideslider'
        isShow={this.isShow}
        quickClose={true}
        onUpdate:isShow={(val: boolean) => this.$emit('update:isShow', val)}
      >
        {{
          header: () => (
            <div class='sideslider-title-wrap'>
              <span>{this.t('上报日志详情')}</span>
              <Button onClick={this.handleCopy}>{this.t('复制')}</Button>
            </div>
          ),
          default: () => (
            <div
              ref='jsonContainerRef'
              class='json-text-style'
            >
              <VueJsonPretty
                height={this.jsonContainerHeight}
                data={this.log}
                deep={5}
                itemHeight={20}
                virtual={true}
              />
            </div>
          ),
        }}
      </Sideslider>
    );
  },
});
