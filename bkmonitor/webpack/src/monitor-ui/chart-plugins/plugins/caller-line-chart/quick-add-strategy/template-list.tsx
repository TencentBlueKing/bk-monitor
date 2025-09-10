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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { ICategoryItem, ITempLateItem, TTemplateList } from './typing';

import './template-list.scss';

interface IProps {
  checked?: string[];
  templateList?: ITempLateItem[];
}

@Component
export default class TemplateList extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) templateList: ITempLateItem[];
  @Prop({ type: Array, default: () => [] }) checked: string[];

  templateTree: TTemplateList[] = [];

  @Watch('templateList', { immediate: true })
  handleWatchTemplateList() {
    if (!this.templateList.length) {
      return;
    }
    this.getTemplateTree();
  }
  @Watch('checked', { immediate: true })
  handleWatchChecked() {
    this.getTemplateTree();
  }

  getTemplateTree() {
    const checkedSet = new Set(this.checked);
    const templateTree: TTemplateList[] = [];
    for (const item of this.templateList) {
      if (item.category) {
        const systemItem = templateTree.find(child => child.system === item.system);
        if (systemItem?.children) {
          const secondChild = systemItem.children.find(child => child.category === item.category);
          if ((secondChild as ICategoryItem)?.children) {
            (secondChild as ICategoryItem).children.push({
              ...item,
              checked: checkedSet.has(item.id),
            });
          } else {
            (systemItem as TTemplateList<ICategoryItem>).children.push({
              category: item.category,
              system: item.system,
              children: [item],
              checked: false,
            });
          }
        } else {
          (templateTree as TTemplateList<ICategoryItem>[]).push({
            name: item.system,
            system: item.system,
            children: [
              {
                category: item.category,
                system: item.system,
                children: [item],
                checked: false,
              },
            ],
          });
        }
      } else {
        const systemItem = templateTree.find(child => child.system === item.system);
        if (systemItem?.children) {
          systemItem.children.push({
            ...item,
            checked: checkedSet.has(item.id),
          });
        } else {
          templateTree.push({
            name: item.system,
            system: item.system,
            children: [item],
          });
        }
      }
    }
    console.log(templateTree);
    this.templateTree = templateTree;
  }

  render() {
    const renderTemplateItem = (item: ITempLateItem) => {
      return (
        <div
          key={item.id}
          class='template-item'
        >
          <bk-checkbox class='template-item-checkbox' />
          <span class='template-item-icon icon-monitor icon-check' />
          <div class='template-item-desc'>{item.name}</div>
          <div class='template-item-status'>
            <span>{this.$t('已配置')}</span>
            <span class='icon-monitor icon-mc-goto' />
          </div>
        </div>
      );
    };

    return (
      <div class='quick-add-strategy-template-list'>
        {this.templateTree.map(item => (
          <div
            key={item.system}
            class='system-item'
          >
            <div class='system-name'>{item.name}</div>
            {item.children.map(child => {
              if ((child as ICategoryItem)?.children) {
                return (
                  <div
                    key={child.category}
                    class='category-item'
                  >
                    <bk-checkbox class='category-item-checkbox'>{child.category}</bk-checkbox>
                    {(child as ICategoryItem).children.map(c => renderTemplateItem(c))}
                  </div>
                );
              } else {
                return renderTemplateItem(child);
              }
            })}
          </div>
        ))}
      </div>
    );
  }
}
