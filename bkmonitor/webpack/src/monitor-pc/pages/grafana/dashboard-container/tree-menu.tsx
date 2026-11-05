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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import TreeList, { type IMoreData } from './tree-list';
import { type ITreeMenuItem, TreeMenuItem } from './utils';

interface IEvents {
  onMore: IMoreData;
  onRename: TreeMenuItem;
  onSelected: TreeMenuItem;
}
interface IProps {
  checked?: string;
  closeIcon?: string;
  data: ITreeMenuItem[];
  defaultExpend?: boolean;
  expendIcon?: string;
}

@Component
export default class TreeMenu extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) data: ITreeMenuItem[];
  /** 是否默认打开分组 */
  @Prop({ type: Boolean, default: false }) defaultExpend: boolean;
  /** 展开icon */
  @Prop({ type: String, default: 'icon-mc-open-folder' }) expendIcon: string;
  /** 收起icon */
  @Prop({ type: String, default: 'icon-mc-full-folder' }) closeIcon: string;
  /** 选中 */
  @Prop({ type: String, default: '' }) checked: string;

  localData: TreeMenuItem[] = [];
  /** 当前选中项 */
  localChecked: string = null;
  initialized = false;
  scrollTimer = 0;
  scrollFrame = 0;
  stopScroll: (() => void) | null = null;

  beforeDestroy() {
    window.clearTimeout(this.scrollTimer);
    this.stopScroll?.();
  }

  @Watch('checked', { immediate: true })
  checkedChange(val: string) {
    this.localChecked = val;
    window.clearTimeout(this.scrollTimer);
    this.stopScroll?.();
    if (!val) {
      return;
    }
    const folder = this.localData.find(item => item.children?.some(child => child.uid === val));
    if (!folder) {
      return;
    }
    folder.expend = true;
    this.scrollTimer = window.setTimeout(() => this.jumpChecked(val), 320);
  }

  /** 只滚外层目录。吸顶目录占住顶部，选中项落到这块区域的正中。终点只算一次。 */
  jumpChecked(uid: string) {
    const target = document.getElementById(uid);
    const scroller = target?.closest('.grafana-list') as HTMLElement | null;
    if (!target || !scroller) {
      return;
    }
    const header = target.closest('.monitor-collapse-wrap')?.previousElementSibling as HTMLElement | null;
    const scrollerRect = scroller.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const paddingTop = Number.parseFloat(window.getComputedStyle(scroller).paddingTop) || 0;
    const stickyCover = header ? header.getBoundingClientRect().height + paddingTop : 0;
    const viewCenter = scrollerRect.top + stickyCover + (scroller.clientHeight - stickyCover) / 2;
    const delta = targetRect.top + targetRect.height / 2 - viewCenter;
    const maxTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
    const next = Math.round(Math.min(maxTop, Math.max(0, scroller.scrollTop + delta)));
    this.stopScroll?.();
    if (next === Math.round(scroller.scrollTop)) {
      return;
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      scroller.scrollTop = next;
      return;
    }
    const from = scroller.scrollTop;
    const distance = next - from;
    const duration = Math.min(380, Math.max(160, Math.abs(distance) * 0.45));
    const start = performance.now();
    const stop = () => {
      window.cancelAnimationFrame(this.scrollFrame);
      this.scrollFrame = 0;
      scroller.removeEventListener('wheel', stop);
      if (this.stopScroll === stop) {
        this.stopScroll = null;
      }
    };
    const step = (now: number) => {
      if (this.stopScroll !== stop) {
        return;
      }
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      scroller.scrollTop = progress === 1 ? next : Math.round(from + distance * eased);
      if (progress < 1) {
        this.scrollFrame = window.requestAnimationFrame(step);
        return;
      }
      stop();
    };
    this.stopScroll = stop;
    scroller.addEventListener('wheel', stop, { passive: true });
    this.scrollFrame = window.requestAnimationFrame(step);
  }

  @Watch('data', { immediate: true })
  handleDataChange(data: ITreeMenuItem[]) {
    if (data) {
      this.initialized = true;
      this.localData = this.handleTreeData(data);
      this.checkedChange(this.checked);
    }
  }

  /** 生成列表渲染所需的数据 */
  handleTreeData(data: ITreeMenuItem[], level = 0): TreeMenuItem[] {
    return data.map(item => {
      const newItem = new TreeMenuItem(
        {
          ...item,
          expend: !this.initialized
            ? this.defaultExpend
            : (this.localData?.find(set => set.id === item.id)?.expend ?? false),
          level,
        },
        {
          expendIcon: this.expendIcon,
          closeIcon: this.closeIcon,
        }
      );
      return newItem;
    });
  }

  @Emit('selected')
  handleSelectedItem(item: TreeMenuItem) {
    this.localChecked = item.uid;
    return item;
  }
  @Emit('more')
  handleMore(data: IMoreData) {
    return data;
  }
  @Emit('rename')
  handleRename(item: TreeMenuItem) {
    return item;
  }
  render() {
    return (
      <TreeList
        checked={this.localChecked}
        list={this.localData}
        onMore={this.handleMore}
        onRename={this.handleRename}
        onSelected={this.handleSelectedItem}
      />
    );
  }
}
