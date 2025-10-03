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

import './configuration-item-list.scss';

/**
 * ConfigurationItem 组件
 * 用于展示一个可折叠的配置项界面
 */

export default defineComponent({
  name: 'ConfigurationItemList', // 组件名称

  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },

  emits: ['change'], // 组件触发的事件，当宽度改变时触发

  setup(props, { emit }) {
    // 使用国际化翻译函数
    const { t } = useLocale();
    // 打印日志，包含翻译文本、组件属性和事件触发函数
    console.log(t('v2.logCollection.title'), props, emit);
    // 添加索引转字母的函数
    const indexToLetter = (index: number): string => {
      // 65 是 'A' 的 ASCII 码
      const asciiCode = 65;
      return String.fromCharCode(asciiCode + index);
    };
    const renderItem = (item, ind) => (
      <div class='item-box'>
        <div class='item-header'>
          <span>{indexToLetter(ind)}</span>
          {ind !== 0 && (
            <i
              class='bk-icon icon-delete del-icons'
              // on-Click={() => deleteFilterGroup(groupIndex)}
            />
          )}
        </div>
        <div class='item-content'>{ind}</div>
      </div>
    );
    // 组件渲染函数
    return () => (
      <div class='configuration-item-list-main'>
        {props.data.map((item, ind) => renderItem(item, ind))}
        <div class='add-btn'>
          <i class='bk-icon icon-plus-line icons' />
          {t('添加配置项')}
        </div>
      </div>
    );
  },
});
