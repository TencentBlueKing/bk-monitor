/* eslint-disable no-param-reassign */
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
import { VNode } from 'vue';
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deleteStrategyLabel, strategyLabel } from '../../../../monitor-api/modules/strategies';
import { deepClone } from '../../../../monitor-common/utils/utils';
import { ITreeItem, TMode } from '../types';

import './label-tree.scss';

const { i18n } = window;
interface IContainerProps {
  mode?: TMode;
  treeData?: ITreeItem[];
  checkedNode?: string[];
}

@Component
export default class LabelTree extends tsc<IContainerProps> {
  @Prop({ default: 'select' }) private mode: TMode;
  @Prop({ default: () => [] }) private treeData: ITreeItem[];
  @Prop({ default: () => [], type: Array }) private checkedNode: string[];

  private localTreeList: ITreeItem[] = [];

  private tooltipsMessage = {
    rename: {
      name: 'bk-tooltips',
      value: {
        content: i18n.t('重命名')
      }
    },
    add: {
      name: 'bk-tooltips',
      value: {
        content: i18n.t('添加子级')
      }
    },
    del: {
      name: 'bk-tooltips',
      value: {
        content: i18n.t('删除')
      }
    }
  };

  private inputValue = '';
  private isEdit = false;

  @Emit('listChange')
  localTreeListChange() {
    return deepClone(this.localTreeList);
  }

  @Emit('checkedChange')
  handleCheckedChange(checkedList: string[], obj: any) {
    return {
      checked: deepClone(checkedList),
      valueChange: obj
    };
  }

  @Emit('loading')
  handleLoading(v: boolean) {
    return v;
  }

  @Watch('treeData', { immediate: true, deep: true })
  treeDataChange() {
    this.localTreeList = deepClone(this.treeData);
  }

  updateNodeApi(name: string, id?: number | string) {
    this.handleLoading(true);
    const param = {
      bk_biz_id: 0,
      strategy_id: 0,
      label_name: name,
      id
    };
    return strategyLabel(param, { needMessage: false }).finally(() => this.handleLoading(false));
    // return new Promise((resolve, reject) => {
    //     setTimeout(() => {
    //         Math.random() > 0.5 ? resolve(true) : reject()
    //     }, 1000)
    // }).finally(() => this.handleLoading(false))
  }

  handleInputChange(val: string) {
    this.inputValue = val;
  }

  getNodeKey(node: ITreeItem) {
    const ids = [];
    ids.unshift(node.name);
    let temp = node;
    while (temp.parent) {
      temp = temp.parent;
      ids.unshift(temp.name);
    }
    return ids.join('/');
  }

  /**
   * 取消编辑
   * @param node
   */
  cancelEdit(e, node: ITreeItem) {
    e?.stopPropagation();
    if (node.isCreate) {
      this.removeNode(node);
      this.localTreeListChange();
    } else if (node.renamed) {
      this.$delete(node, 'renamed');
    }
    this.inputValue = '';
    this.isEdit = false;
  }

  checkDuplicateName(node: ITreeItem) {
    const list = node?.parent?.children || this.localTreeList;
    const isDuplicateName = list.some(item => item.name === this.inputValue.trim());
    return isDuplicateName;
  }

  /**
   * 确认编辑
   * @param node
   */
  async confirmEdit(node: ITreeItem) {
    if (!this.inputValue) return;
    if (this.checkDuplicateName(node)) {
      this.$bkMessage({
        message: this.$t('注意: 名字冲突'),
        theme: 'error'
      });
      return;
    }
    if (this.inputValue.indexOf('/') > -1) {
      this.$bkMessage({
        message: `${this.$t('标签名字不能含有分隔符：')} /`,
        theme: 'error'
      });
      return;
    }
    if (node.isCreate) {
      try {
        node.name = this.inputValue;
        const key = this.getNodeKey(node);
        node.key = key;
        node.id = `/${key}/`;
        await this.updateNodeApi(key);
        this.$delete(node, 'isCreate');
        this.isEdit = false;
      } catch (error) {
        console.error(error);
        this.cancelEdit(null, node);
        this.$bkMessage({
          message: this.$t('创建标签失败'),
          theme: 'error'
        });
      }
    } else if (node.renamed) {
      const tempName = node.name;
      try {
        node.name = this.inputValue;
        const key = this.getNodeKey(node);
        node.key = key;
        await this.updateNodeApi(key, node.id);
        this.$delete(node, 'renamed');
        this.isEdit = false;
      } catch (error) {
        console.error(error);
        node.name = tempName;
        this.cancelEdit(null, node);
        this.$bkMessage({
          message: this.$t('标签重命名失败'),
          theme: 'error'
        });
      }
    }
    this.inputValue = '';
    this.localTreeListChange();
  }

  /**
   * 重命名
   * @param e
   * @param node
   */
  handleRename(e, node: ITreeItem) {
    e.stopPropagation();
    if (this.isEdit) return;
    this.$set(node, 'renamed', true);
    this.$nextTick(() => {
      this.inputFocus();
      this.isEdit = true;
    });
  }

  /**
   * 创建一个节点
   * @param node
   */
  createChild(node: ITreeItem = null) {
    const newChild: any = {
      id: '',
      name: '',
      parent: node,
      isCreate: true
    };
    if (!node) {
      this.localTreeList.push(newChild);
      return;
    }
    const childs = node.children;
    if (childs) {
      childs.push(newChild);
    } else {
      this.$set(node, 'children', [newChild]);
    }
    this.$set(node, 'expanded', true);
  }

  /**
   * 删除一个节点以及子节点
   * @param node
   */
  removeNode(node: ITreeItem) {
    const parentChilList = node.parent ? node.parent.children : this.localTreeList;
    const index = parentChilList.findIndex(item => item.key === node.key);
    if (node.parent && parentChilList.length === 1) {
      const { parent } = node;
      this.$delete(parent, 'children');
      return;
    }
    parentChilList.splice(index, 1);
  }

  inputFocus() {
    const inputVm: any = this.$refs.input;
    inputVm.focus();
  }

  handleAddChild(e, node: ITreeItem = null) {
    e?.stopPropagation();
    if (this.isEdit) return;
    const addFirst = !node;
    if (addFirst) {
      const isCreate = !!this.localTreeList?.find(item => item.isCreate);
      if (isCreate) return;
    } else {
      const isCreate = !!node.children?.find(item => item.isCreate);
      if (isCreate) return;
    }
    this.createChild(node);
    this.$nextTick(() => {
      this.inputFocus();
      this.isEdit = true;
    });
  }

  handleDel(e, node: ITreeItem) {
    e.stopPropagation();
    const count = this.getTreeNodeCount(node);
    const h = this.$createElement;
    const subHeader =
      count > 1
        ? h('div', { class: ['info-subHeader'] }, [
            '将同时删除下级',
            h('span', { class: ['count'] }, `${count - 1}`),
            '个标签'
          ])
        : '';
    const subTitle = count === 1 ? this.$t('删除当前分类') : '';
    this.$bkInfo({
      title: this.$t('你确认要删除?'),
      subHeader,
      subTitle,
      confirmLoading: true,
      confirmFn: async () => {
        try {
          // const res = await new Promise((resolve, reject) => {
          //     setTimeout(() => {
          //        Math.random() > 0.5 ? resolve(true) : reject()
          //     }, 1000)
          // })
          const params = {
            bk_biz_id: 0,
            label_name: this.getNodeKey(node)
          };
          await deleteStrategyLabel(params).then(() => {
            this.removeNode(node);
            this.localTreeListChange();
            this.$bkMessage({
              message: this.$t('删除成功'),
              theme: 'success'
            });
          });
          return true;
        } catch (e) {
          this.$bkMessage({
            message: this.$t('删除失败'),
            theme: 'error'
          });
          console.warn(e);
          return false;
        }
      }
    });
  }

  getTreeNodeCount(node: ITreeItem) {
    if (node.children) {
      let count = 0;
      const fn = tree => {
        tree.forEach(item => {
          count += 1;
          item.children && fn(item.children);
        });
      };
      fn([node]);
      return count;
    }
    return 1;
  }

  itemPadding(node: ITreeItem) {
    let temp = node;
    let count = 0;
    const hasChil = !!node.children;
    while (temp.parent) {
      count += 1;
      temp = temp.parent;
    }
    const firstLevelNoChil = !hasChil && !node.parent ? 21 : 0;
    const noChild = !hasChil && node.parent ? 21 : 0;
    return `${count * 30 + firstLevelNoChil + noChild + (!node.parent ? 9 : 0)}px`;
  }

  handleCheckedNode(node: ITreeItem) {
    if (this.mode !== 'select' || node.children) return;
    const temp = deepClone(this.checkedNode);
    const existed = this.checkedNode.includes(node.id);
    if (existed) {
      const index = temp.findIndex(item => item === node.id);
      temp.splice(index, 1);
    } else {
      temp.push(node.id);
    }
    this.handleCheckedChange(temp, {
      type: existed ? 'remove' : 'add',
      value: node.id
    });
  }

  /**
   * 限制标签层级为4层
   * @param node
   */
  showAddBtn(node: ITreeItem) {
    const MAX_LEVEL = 4;
    const level = node.key.split('/').length;
    return level < MAX_LEVEL;
  }

  /**
   * 编辑状态
   * @param node
   */
  editTpl(node): VNode[] {
    const h = this.$createElement;
    return [
      h(
        'div',
        {
          class: ['edit-item-wrap'],
          on: { click: e => e.stopPropagation() }
        },
        [
          h('bk-input', {
            ref: 'input',
            props: {
              value: this.inputValue
            },
            on: {
              change: val => this.handleInputChange(val)
            }
          }),
          h('span', { class: ['icon-group'] }, [
            h('i', {
              class: ['icon-monitor', 'icon-mc-check-small'],
              on: {
                click: () => this.confirmEdit(node)
              }
            }),
            h('i', {
              class: ['icon-monitor', 'icon-mc-close'],
              on: {
                click: e => this.cancelEdit(e, node)
              }
            })
          ])
        ]
      )
    ];
  }
  /**
   * 正常状态
   * @param node
   */
  normalTpl(node): VNode[] {
    const h = this.$createElement;
    return [
      h('div', { class: ['normal-item-wrap'] }, [
        h('div', { class: ['item-name-wrap'], directives: [{ name: 'bk-overflow-tips' }] }, [
          h('i', {
            class: ['icon-monitor', 'icon-mc-triangle-down', { hidden: !node.children, 'to-right': !node.expanded }]
          }),
          h('span', { class: ['item-name'] }, node.name)
        ]),
        this.mode === 'create'
          ? h('span', { class: ['item-icon-group'] }, [
              h('i', {
                directives: [this.tooltipsMessage.rename],
                class: ['icon-monitor', 'icon-bianji'],
                on: { click: e => this.handleRename(e, node) }
              }),
              h('i', {
                directives: [
                  this.tooltipsMessage.add,
                  {
                    name: 'show',
                    value: this.showAddBtn(node)
                  }
                ],
                class: ['icon-monitor', 'icon-mc-add'],
                on: { click: e => this.handleAddChild(e, node) }
              }),
              h('i', {
                directives: [this.tooltipsMessage.del],
                class: ['icon-monitor', 'icon-mc-delete-line'],
                on: { click: e => this.handleDel(e, node) }
              })
            ])
          : h('i', {
              class: [
                'icon-monitor',
                { 'icon-mc-check-small': this.checkedNode.includes(node.id) && !node.children?.length }
              ],
              on: {
                click: () => this.confirmEdit(node)
              }
            })
      ])
    ];
  }

  tpl(node): VNode {
    const h = this.$createElement;
    return h(
      'div',
      {
        class: ['tree-node-item', { 'node-item-active': this.checkedNode.includes(node.id) && this.mode === 'select' }],
        style: { 'padding-left': this.itemPadding(node) },
        on: { click: () => this.handleCheckedNode(node) }
      },
      node.isCreate || node.renamed ? this.editTpl(node) : this.normalTpl(node)
    );
  }

  protected render(): VNode {
    return (
      <div class='label-tree-wrap'>
        <bk-tree
          show-icon={false}
          tpl={this.tpl}
          data={this.localTreeList}
          node-key='id'
        ></bk-tree>
      </div>
    );
  }
}
