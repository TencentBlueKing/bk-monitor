/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { computed, defineComponent } from 'vue';

import { Exception } from 'bkui-vue';

import ErrorImg from '../../static/img/error.svg';
import NoDataImg from '../../static/img/no-data.svg';

import './index.scss';

export default defineComponent({
  name: 'ExceptionComponent',
  props: {
    // 是否显示错误状态
    isError: {
      type: Boolean,
      default: false,
    },
    // 是否为暗色背景
    isDarkTheme: {
      type: Boolean,
      default: false,
    },
    // 图片显示高度
    imgHeight: {
      type: [Number, String],
      default: 100,
    },
    // 主标题文本
    title: {
      type: String,
      default: '暂无数据',
    },
    // 错误详情信息
    errorMsg: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    // 计算样式
    const styles = computed(() => {
      const { isDarkTheme, isError, imgHeight } = props;
      return {
        exceptionStyle: {
          '--height': `${imgHeight}px`,
          '--marginTop': isDarkTheme ? '12px' : '0',
        },
        titleStyle: {
          color: isDarkTheme ? (isError ? '#E04949' : '#979BA5') : '#313238',
        },
        descStyle: {
          color: isDarkTheme ? '#E04949' : '#979BA5',
        },
      };
    });

    return () => {
      const { exceptionStyle, titleStyle, descStyle } = styles.value;
      return (
        <Exception
          style={exceptionStyle}
          class='exception-wrap'
          // 暗色背景下使用自定义图片插槽
          v-slots={
            props.isDarkTheme
              ? {
                  type: () => (
                    // 根据错误状态切换图片
                    <img
                      class='exception-img'
                      alt=''
                      src={props.isError ? ErrorImg : NoDataImg}
                    />
                  ),
                }
              : null
          }
          // 非暗色背景时使用内置类型
          type={props.isError ? '500' : 'empty'}
        >
          <div>
            {/* 主标题 */}
            <div
              style={titleStyle}
              class='exception-title'
            >
              {props.title}
            </div>
            {/* 仅在错误状态显示详情信息 */}
            {props.isError && (
              <div
                style={descStyle}
                class='exception-desc'
              >
                {props.errorMsg}
              </div>
            )}
          </div>
        </Exception>
      );
    };
  },
});
