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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './more-list.scss';

const numClassName = 'num-overflow-item';
interface IProps {
  list: string[];
  onChange?: string[];
  onActive?: (v: string) => void;
}

@Component
export default class MoreList extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) list: string[];
  @Ref('list') listRef: HTMLDivElement;
  @Ref('opreate') opreateRef: HTMLDivElement;

  localList: string[] = [];
  /* 是否展开 */
  isExpand = false;
  tempInput = '';
  popoverInstance: any = null;
  isAdd = false;
  editActive = '';
  /* 校验文案 */
  errMsg = '';

  created() {
    this.localList = this.list;
  }

  mounted() {
    setTimeout(() => {
      this.handleOverflow();
    }, 100);
  }
  /* 计算溢出数量 */
  async handleOverflow() {
    this.removeOverflow();
    const list = this.listRef;
    const childs = list?.children || [];
    const listWidth = list?.offsetWidth || 0;
    const overflowTagWidth = 41;
    let totalWidth = 0;
    await this.$nextTick();
    // eslint-disable-next-line no-restricted-syntax
    for (const i in childs) {
      const item = childs[i] as HTMLDivElement;
      if (!item.className || item.className.indexOf('list-item') === -1) continue;
      totalWidth += item.offsetWidth + 4;
      // 超出省略
      if (totalWidth + overflowTagWidth > listWidth) {
        const hideNum = this.localList.length + 1 - +i;
        hideNum > 1 && this.insertOverflow(item, hideNum > 99 ? 99 : hideNum);
        break;
      }
    }
  }
  /* 删除溢出数量 */
  removeOverflow() {
    const overflowList = this.listRef?.querySelectorAll?.(`.${numClassName}`);
    if (!overflowList?.length) return;
    overflowList.forEach(item => {
      this.listRef?.removeChild?.(item);
    });
  }
  /* 展示溢出数量 */
  insertOverflow(target, num) {
    if ((this.isExpand && num > 1) || num < 0) return;
    const li = document.createElement('li');
    li.className = numClassName;
    li.innerText = `+${num - 1}`;
    li.addEventListener('click', this.handleExpandMore, false);
    this.listRef.insertBefore(li, target);
  }
  /* 收起更多 */
  handleClickOutSide(evt: Event) {
    const targetEl = evt.target as HTMLBaseElement;
    if (this.$el.contains(targetEl) || this.opreateRef?.contains?.(targetEl)) return;
    this.isExpand = false;
    setTimeout(() => this.handleOverflow(), 100);
  }
  /* 展开更多 */
  handleExpandMore() {
    this.isExpand = !this.isExpand;
    if (this.isExpand) {
      document.addEventListener('click', this.handleClickOutSide, false);
      setTimeout(() => this.removeOverflow(), 100);
    } else {
      document.removeEventListener('click', this.handleClickOutSide, false);
      setTimeout(() => this.handleOverflow(), 100);
    }
  }
  /* 点击tag 进入编辑 */
  handleEdit(item: string, event: Event) {
    this.errMsg = '';
    this.tempInput = item;
    this.removePopoverInstance();
    this.editActive = item;
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.opreateRef,
      boundary: 'window',
      arrow: true,
      placement: 'bottom-start',
      theme: 'light',
      trigger: 'click',
      interactive: true,
      onHide: () => {
        this.isAdd = false;
        this.editActive = '';
      }
    });
    this.popoverInstance?.show?.();
  }
  /* 清空pop */
  removePopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }
  /* 点击添加按钮 */
  handleAdd(event: Event) {
    this.isAdd = true;
    this.handleEdit('', event);
  }

  /* 保存并匹配 */
  handleSave() {
    if (!this.tempInput) return;
    if (!!this.editActive) {
      const index = this.localList.findIndex(item => item === this.editActive);
      if (this.localList.filter(item => item !== this.editActive).includes(this.tempInput)) {
        this.errMsg = this.$tc('注意: 名字冲突');
        return;
      }
      this.localList[index] = this.tempInput;
    } else {
      if (this.localList.includes(this.tempInput)) {
        this.errMsg = this.$tc('注意: 名字冲突');
        return;
      }
      this.localList.push(this.tempInput);
    }
    this.removePopoverInstance();
    this.handleChange();
    this.handleActive(this.tempInput);
    setTimeout(() => {
      this.handleOverflow();
    }, 100);
  }
  /* 取消 */
  handleCancel() {
    this.isAdd = false;
    this.removePopoverInstance();
  }

  handleInputChange() {
    this.errMsg = '';
  }

  @Emit('change')
  handleChange() {
    return this.localList;
  }

  /* 删除 */
  handleDelete(e: Event, index: number) {
    e.stopPropagation();
    this.localList.splice(index, 1);
    this.handleChange();
    setTimeout(() => {
      this.handleOverflow();
    }, 100);
  }

  @Emit('active')
  handleActive(v: string) {
    return v;
  }

  render() {
    return (
      <div class={['match-rule-more-list-component', { 'is-expand': this.isExpand }]}>
        <ul
          class='more-list'
          ref='list'
        >
          {this.localList.map((item, index) => (
            <li
              key={index}
              class={['list-item', { active: item === this.editActive }]}
              onClick={(event: Event) => this.handleEdit(item, event)}
              onMouseenter={() => this.handleActive(item)}
            >
              <span class='item-name'>{item}</span>
              <span
                class='icon-monitor icon-mc-close'
                onClick={e => this.handleDelete(e, index)}
              ></span>
            </li>
          ))}
          <li
            class={['list-item', 'add', { 'add-active': this.isAdd }]}
            onClick={this.handleAdd}
          >
            <span class='icon-monitor icon-mc-add'></span>
          </li>
        </ul>
        <div style='display: none'>
          <div
            class='match-rule-more-list-component-operate-wrap'
            ref='opreate'
          >
            <bk-input
              class='edit-input'
              maxlength={40}
              v-model={this.tempInput}
              onChange={this.handleInputChange}
              onEnter={this.handleSave}
            ></bk-input>
            <div
              class='err-msg'
              style={{ display: !!this.errMsg ? 'block' : 'none' }}
            >
              {this.errMsg}
            </div>
            <div class='tip-msg'>{this.$t('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total')}</div>
            <div class='operate-btn'>
              <bk-button
                class='mr8'
                theme='primary'
                onClick={this.handleSave}
              >
                {this.$t('保存并匹配')}
              </bk-button>
              <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
