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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { deepClone } from 'monitor-common/utils';

import './table-tag-list.scss';

interface IProps {
  list: string[];
  onShowMore?: () => void;
}

/**
 * 展示 字符串标签列表 ，常用在 table 中。一行展示标签。
 * 组件内容 :
 * 1. 如果不能整行展示完整，则会显示 省略号 和 更多 按钮。
 * 2. table 进行 resize 后会重新计算该显示多少 标签 。
 * 3. “更多” 按钮在不同的语言环境下所占用的宽度的自适应。通过 flex-shrink 实现。
 * 4. 边界情况：仅剩一个标签时，且无法整行展示时，将该标签行内进行溢出省略。
 */
@Component
export default class MoreTag extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) list: string[];

  //   标签列表容器的 DOM ，用作计算是否溢出
  targetContainer: HTMLElement = null;
  //   中间量 list
  clonedList: string[] = [];
  //   是否完成溢出计算的 flag ，用作处理 边界情况 的问题
  isFinishCalc = false;

  hasScroll = false;

  //   检查容器宽度是否溢出的工具函数
  checkContainerIsOverflowing(): boolean {
    if (this.targetContainer) return this.targetContainer.scrollWidth > this.targetContainer.clientWidth;
    return false;
  }

  //   计算列表容器在减少一个 tag 的 dom 后是否还存在溢出，如果还存在溢出则不断递归计算，减到 tag 数为 1 的情况。
  reCalculateAndDecreaseTags() {
    const atLeaseShowTagNum = 1;
    if (this.clonedList.length > atLeaseShowTagNum) {
      // 每次末尾都减一个
      this.clonedList.splice(this.clonedList.length - 1, 1);
      this.$nextTick(() => {
        if (this.checkContainerIsOverflowing()) this.reCalculateAndDecreaseTags();
        // 计算完毕，将对应的水平溢出的 css 属性给剩下能展示的标签
        else this.isFinishCalc = true;
      });
    } else {
      this.isFinishCalc = true;
    }
  }

  async mounted() {
    this.clonedList = deepClone(this.list);
    this.targetContainer = this.$el.querySelector('#tag-list-container');
    await this.$nextTick();
    // 获取标签的容器是否出现溢出，用作显示 ‘更多’ 按钮
    this.hasScroll = this.checkContainerIsOverflowing();
    if (this.hasScroll) this.reCalculateAndDecreaseTags();
    const currentElement = this.$el as HTMLElement;
    // 处理表格 resize 的情况，需要将基础属性还原，再重新计算
    addListener(currentElement, async () => {
      this.clonedList = deepClone(this.list);
      this.isFinishCalc = false;
      await this.$nextTick();
      this.hasScroll = this.checkContainerIsOverflowing();
      if (this.hasScroll) this.reCalculateAndDecreaseTags();
    });
    this.$once('hook:deactivated', () => {
      removeListener(currentElement);
    });
    this.$once('hook:beforeDestroy', () => {
      removeListener(currentElement);
    });
  }

  render() {
    return (
      <div class='tag-btn-container'>
        {/* 计算完毕时，说明容器不存在宽度溢出的可能，
        或者时边界情况：第一个标签 + 省略号 还是溢出了。
        这里先禁止水平溢出。overflow-x: hidden
         */}
        <div
          id='tag-list-container'
          style={this.isFinishCalc && { 'overflow-x': 'hidden' }}
          class='tag-list-container'
        >
          {/* 如果出现了上述的边界情况，这里会将该标签设置为溢出省略，保证了外观正常 */}
          {this.clonedList.map((s, index) => (
            <div
              key={index}
              class={this.isFinishCalc ? 'tag tag-overflow' : 'tag'}
            >
              {s}
            </div>
          ))}
          {this.hasScroll && <div class='tag'>...</div>}
        </div>
        {this.hasScroll && (
          <bk-button
            class='more-btn'
            text
            onClick={() => this.$emit('showMore')}
          >
            {this.$t('更多')}
          </bk-button>
        )}
      </div>
    );
  }
}
