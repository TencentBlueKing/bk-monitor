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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import Collapse from '../../../components/collapse/collapse';

import './fav-list.scss';

export interface IFavListItem {
  children?: IFavListItem[];
  expend?: boolean;
  id: number | string;
  name: string;
  uid?: string;
  url?: string;
}
interface IEvents {
  onSelected: IFavListItem;
  onUnstarred: (id: number, name: string) => void;
}
interface IProps {
  checked?: string;
  list: IFavListItem[];
}
@Component
export default class FavList extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) list: IFavListItem[];
  @Prop({ type: String }) checked: string;
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  localList: IFavListItem[] = [];

  localChecked: string = null;

  /** 正在播消失动画的收藏项，列表刷新前保持收起，失败再展开 */
  leavingId: number | string = null;

  leaveTimer = 0;

  beforeDestroy() {
    window.clearInterval(this.leaveTimer);
  }

  @Watch('checked', { immediate: true })
  checkedChange(val: string) {
    this.localChecked = val;
  }

  @Watch('list', { immediate: true })
  listChange(list: IFavListItem[]) {
    this.localList =
      list?.map?.(item => {
        this.$set(item, 'expend', true);
        return item;
      }) || [];
    const ids = new Set(list?.flatMap(item => item.children?.map(child => child.id) || []) || []);
    if (this.leavingId != null && !ids.has(this.leavingId)) {
      this.leavingId = null;
    }
  }

  handleExpend(item: IFavListItem) {
    item.expend = !item.expend;
  }

  @Emit('selected')
  handleSelectItem(item: IFavListItem) {
    this.localChecked = item.uid;
    return item;
  }
  handleUnstarred(item: IFavListItem) {
    if (this.leavingId != null) {
      return;
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.$emit('unstarred', item.id, item.name);
      return;
    }
    this.leavingId = item.id;
    this.$nextTick(() => this.playLeave(item));
  }

  /** 收藏项先收起，折叠容器的高度跟着内容走，不改公共 Collapse */
  playLeave(item: IFavListItem) {
    const row = this.$el.querySelector('.fav-item.is-leaving') as HTMLElement | null;
    if (!row) {
      this.leavingId = null;
      this.$emit('unstarred', item.id, item.name);
      return;
    }
    const wrap = row.closest('.monitor-collapse-wrap') as HTMLElement | null;
    let stopped = false;
    const syncHeight = () => {
      this.syncCollapseHeight(wrap);
    };
    const finish = () => {
      if (stopped) {
        return;
      }
      stopped = true;
      window.clearInterval(this.leaveTimer);
      row.removeEventListener('transitionend', onEnd);
      syncHeight();
      this.requestUnstarred(item);
    };
    const onEnd = (evt: TransitionEvent) => {
      if (evt.target !== row || evt.propertyName !== 'height') {
        return;
      }
      finish();
    };
    row.addEventListener('transitionend', onEnd);
    syncHeight();
    this.leaveTimer = window.setInterval(syncHeight, 16);
    window.setTimeout(finish, 280);
  }

  requestUnstarred(item: IFavListItem) {
    const listener = this.$listeners.unstarred;
    const handler = (Array.isArray(listener) ? listener[0] : listener) as
      | ((id: number, name: string) => Promise<boolean> | boolean)
      | undefined;
    const result = handler?.(item.id as number, item.name);
    if (result && typeof (result as Promise<boolean>).then === 'function') {
      (result as Promise<boolean>)
        .then(ok => {
          if (ok !== true) {
            this.restoreLeavingItem();
          }
        })
        .catch(() => {
          this.restoreLeavingItem();
        });
      return;
    }
    this.$emit('unstarred', item.id, item.name);
  }

  /** 列表仍保留该项时收回收起态。先关掉行过渡再量高，避免把折叠高度锁在 0 */
  restoreLeavingItem() {
    const row = this.$el?.querySelector('.fav-item.is-leaving') as HTMLElement | null;
    if (row) {
      row.style.transition = 'none';
    }
    this.leavingId = null;
    this.$nextTick(() => {
      this.syncOpenHeight();
      if (row?.isConnected) {
        row.style.transition = '';
      }
    });
  }

  syncOpenHeight() {
    const wrap = this.$el.querySelector('.fav-item')?.closest('.monitor-collapse-wrap') as HTMLElement | null;
    this.syncCollapseHeight(wrap);
  }

  /** 公共 Collapse 把高度写死并自带 300ms 过渡。收藏删除期间改掉实例高度，让容器跟着当前内容 */
  syncCollapseHeight(wrap: HTMLElement | null) {
    const content = wrap?.querySelector('.monitor-collapse-content') as HTMLElement | null;
    if (!wrap || !content) {
      return;
    }
    const collapse = (wrap as HTMLElement & { __vue__?: { height: number } }).__vue__;
    if (collapse) {
      collapse.height = content.scrollHeight;
    }
  }
  render() {
    return (
      <div
        class={[
          'fav-list',
          { 'is-expend': this.list.some(item => item.expend), 'is-leaving': this.leavingId != null },
        ]}
      >
        {this.list.map((item, index) => (
          <div
            key={index}
            class='fav-list-group'
          >
            <div
              class='fav-list-header'
              onClick={() => this.handleExpend(item)}
            >
              <span class='fav-list-title'>
                <span class='fav-list-name'>{item.name}</span>
                {!item.expend && <span class='fav-list-count'>（{item.children?.length || 0}）</span>}
              </span>
              <i class={['bk-icon icon-angle-right', { expend: item.expend }]} />
            </div>
            <Collapse
              expand={item.expend}
              needCloseButton={false}
            >
              <div class='fav-list-main'>
                {item.children.map(child => (
                  <div
                    key={child.id}
                    class={[
                      'fav-item',
                      {
                        checked: this.localChecked === child.uid,
                        'is-leaving': this.leavingId === child.id,
                      },
                    ]}
                  >
                    <i
                      class='icon-monitor icon-mc-collect'
                      v-bk-tooltips={{
                        content: this.$t('取消收藏'),
                        extCls: 'garfana-link-tips',
                      }}
                      onClick={() => this.handleUnstarred(child)}
                    />
                    <span
                      class='fav-item-name'
                      v-bk-overflow-tips
                      onClick={() => this.handleSelectItem(child)}
                    >
                      {child.name}
                    </span>
                  </div>
                ))}
              </div>
            </Collapse>
          </div>
        ))}
      </div>
    );
  }
}
