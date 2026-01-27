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

import useLocale from '@/hooks/use-locale';

import './grep-cli-total.scss';
/**
 * GrepCliTotal 组件
 * 用于显示 grep 命令的总结果数
 *
 * Props:
 * - total: number - 总结果数
 * - text: string - 自定义完整文案模板，支持使用 {total} 占位符
 * - loading: boolean - 加载状态，为 true 时不渲染内容
 *
 * 行为:
 * - 当 loading 为 true 时不渲染任何内容
 * - 当 total 为 0 时不渲染任何内容
 * - 优先使用 text 模板渲染结果
 * - 否则使用 prefix + total + suffix 组合渲染结果
 *
 * 使用示例
 * 方式1：使用默认文案
 * <GrepCliTotal total={234} />
 * 输出：- 共检索出 234 条结果 -
 *
 * 方式2：使用完整文案模板
 * <GrepCliTotal total={50} text="搜索到 {total} 条匹配记录" />
 * 输出：搜索到 50 条匹配记录
 *
 * 方式3：total为0时不渲染
 * <GrepCliTotal total={0} />
 *
 * 方式4：加载中时不渲染
 * <GrepCliTotal total={100} loading={true} />
 */

export default defineComponent({
  name: 'GrepCliTotal',
  props: {
    total: {
      type: Number,
      default: 0,
    },
    text: {
      type: String,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useLocale();

    const renderTextWithTotal = () => {
      if (!props.text) return null;

      const parts = props.text.split('{total}');
      if (parts.length === 1) {
        // 没有 {total} 占位符，直接返回文本
        return <span>{props.text}</span>;
      }

      // 将文本分割后，中间插入带样式的 total
      return (
        <span>
          {t(parts[0])}
          <span class='total-box'>{props.total}</span>
          {t(parts[1])}
        </span>
      );
    };

    return () => {
      // 加载中时不渲染
      if (props.loading) {
        return null;
      }

      // 根据total决定是否渲染
      if (props.total === 0 || props.total === null || props.total === undefined) {
        return null;
      }

      return <div class='grep-cli-total-main'>{renderTextWithTotal()}</div>;
    };
  },
});
