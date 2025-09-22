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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './select-index-set-input.scss';

@Component
export default class SelectIndexSetInput extends tsc<object> {
  @Prop({ type: Array, required: true }) selectedItemList: any[];
  @Prop({ type: Boolean, required: true }) isShowSelectPopover: boolean;
  @Prop({ type: Boolean, required: true }) isAloneType: boolean;
  @Prop({ type: Object, required: true }) selectedItem: object;

  overflowTagNode = null;
  overflowTagIndex = null;

  get watchCalcOverflowVal() {
    return `${this.isShowSelectPopover} ${this.selectedItemList.length}`;
  }

  @Watch('watchCalcOverflowVal', { immediate: true })
  initCalcOverflow() {
    if (!this.isAloneType) {
      this.calcOverflow();
    }
  }

  @Watch('isAloneType')
  watchCloseTagNode(val) {
    if (val) {
      this.removeOverflowTagNode();
    }
  }

  getTagDOM(index?) {
    const tags = [].slice.call(this.$el.querySelectorAll('.select-tag'));
    return typeof index === 'number' ? tags[index] : tags;
  }

  // 计算第二行第一个的index，在其前方插入overflow tag
  calcOverflow() {
    this.removeOverflowTagNode();
    if (this.selectedItemList.length < 2) {
      return false;
    }
    setTimeout(() => {
      const tags = this.getTagDOM();
      const tagIndexInSecondRow = tags.findIndex((currentUser, index) => {
        if (!index) {
          return false;
        }
        const previousTag = tags[index - 1];
        return previousTag.offsetTop !== currentUser.offsetTop;
      });
      if (tagIndexInSecondRow > -1) {
        this.overflowTagIndex = tagIndexInSecondRow;
      } else {
        this.overflowTagIndex = null;
      }
      this.$el.scrollTop = 0;
      this.insertOverflowTag();
    });
  }
  // 根据计算的overflow index，插入tag并进行校正
  insertOverflowTag() {
    if (!this.overflowTagIndex) {
      return;
    }
    const overflowTagNode = this.getOverflowTagNode();
    const referenceTag = this.getTagDOM(this.overflowTagIndex);
    if (referenceTag) {
      this.setOverflowTagContent();
      this.$el.insertBefore(overflowTagNode, referenceTag);
    } else {
      this.overflowTagIndex = null;
      return;
    }
    setTimeout(() => {
      const previousTag = this.getTagDOM(this.overflowTagIndex - 1);
      if (overflowTagNode.offsetTop !== previousTag.offsetTop) {
        this.overflowTagIndex -= 1;
        this.$el.insertBefore(overflowTagNode, overflowTagNode.previousSibling);
        this.setOverflowTagContent();
      }
    });
  }
  setOverflowTagContent() {
    this.overflowTagNode.textContent = `+${this.selectedItemList.length - this.overflowTagIndex}`;
  }
  // 创建/获取溢出数字节点
  getOverflowTagNode() {
    if (this.overflowTagNode) {
      return this.overflowTagNode;
    }
    const overflowTagNode = document.createElement('span');
    overflowTagNode.className = 'select-overflow-tag';
    this.overflowTagNode = overflowTagNode;
    return overflowTagNode;
  }
  // 从容器中移除溢出数字节点
  removeOverflowTagNode() {
    if (this.overflowTagNode && this.overflowTagNode.parentNode === this.$el) {
      this.$el.removeChild(this.overflowTagNode);
    }
  }

  isShowNotVal(item) {
    return item.tags.some(newItem => newItem.tag_id === 4);
  }

  render() {
    const inputShowDom = () => {
      if (this.isAloneType) {
        return (
          <div
            class='bk-select-name'
            v-bk-overflow-tips={{ placement: 'right' }}
          >
            <span>{(this.selectedItem as any).indexName}</span>
            <span style='color: #979ba5;'>{(this.selectedItem as any).lightenName}</span>
          </div>
        );
      }
      return (
        <div
          class={{
            'index-select-tag-container': true,
            'is-fixed-height': !this.isShowSelectPopover,
          }}
        >
          {this.selectedItemList.map(item => (
            <div
              key={item}
              class='select-tag width-limit-tag'
            >
              <span class='tag-name'>
                {this.isShowNotVal(item) && <i class='not-val' />}
                <span
                  class='title-overflow'
                  v-bk-overflow-tips={{
                    content: `${item.indexName}${item.lightenName}`,
                  }}
                >{`${item.indexName}${item.lightenName}`}</span>
              </span>
            </div>
          ))}
        </div>
      );
    };
    return inputShowDom();
  }
}
