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

import { templateIconMap } from './utils';

import type { ICategoryItem, ITempLateItem, TTemplateList } from './typing';

import './template-list.scss';

interface IProps {
  checked?: (number | string)[];
  cursorId?: number | string;
  templateList?: ITempLateItem[];
  onCheckedChange?: (checked: (number | string)[]) => void;
  onCursorChange?: (id: number | string) => void;
  onGoStrategy?: (id: number | string) => void;
}

@Component
export default class TemplateList extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) templateList: ITempLateItem[];
  @Prop({ type: Array, default: () => [] }) checked: (number | string)[];
  @Prop({ type: [String, Number], default: '' }) cursorId: number | string;

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

  /**
   * 获取模板树结构
   * 将模板列表按系统和分类组织成树形结构，用于界面展示
   * 处理分类模板和非分类模板的不同组织方式，并设置选中状态
   * 分类模板：按系统->分类->模板的三级结构组织
   * 非分类模板：按系统->模板的二级结构组织
   * 同时更新分类级别的选中状态（全选/部分选中）
   */
  getTemplateTree() {
    const iconFn = (id: string) => templateIconMap?.[id] || 'icon-gaojing';
    const checkedSet = new Set(this.checked);
    const templateTree: TTemplateList[] = [];
    for (const item of this.templateList) {
      if (item.category && item.category !== 'DEFAULT') {
        const systemItem = templateTree.find(child => child.system === item.system);
        if (systemItem?.children) {
          const secondChild = systemItem.children.find(child => child.category === item.category);
          if ((secondChild as unknown as ICategoryItem)?.children) {
            (secondChild as unknown as ICategoryItem).children.push({
              ...item,
              checked: checkedSet.has(item.id),
              icon: iconFn(item.monitor_type),
            });
          } else {
            (systemItem as unknown as TTemplateList<ICategoryItem>).children.push({
              category: item.category,
              system: item.system,
              system_alias: item.system_alias,
              category_alias: item.category_alias,
              children: [
                {
                  ...item,
                  checked: checkedSet.has(item.id),
                  icon: iconFn(item.monitor_type),
                },
              ],
              checked: false,
              indeterminate: false,
            });
          }
        } else {
          (templateTree as unknown as TTemplateList<ICategoryItem>[]).push({
            name: item.system,
            system: item.system,
            system_alias: item.system_alias,
            children: [
              {
                category: item.category,
                category_alias: item.category_alias,
                system: item.system,
                system_alias: item.system_alias,
                children: [
                  {
                    ...item,
                    checked: checkedSet.has(item.id),
                    icon: iconFn(item.monitor_type),
                  },
                ],
                checked: false,
                indeterminate: false,
              },
            ],
          });
        }
        for (const child of systemItem?.children || []) {
          if ((child as unknown as ICategoryItem).children) {
            (child as unknown as ICategoryItem).checked = (child as unknown as ICategoryItem).children.every(
              c => c.checked
            );
            (child as unknown as ICategoryItem).indeterminate =
              !(child as unknown as ICategoryItem).checked &&
              (child as unknown as ICategoryItem).children.some(c => c.checked);
          }
        }
      } else {
        const systemItem = templateTree.find(child => child.system === item.system);
        if (systemItem?.children) {
          systemItem.children.push({
            ...item,
            checked: checkedSet.has(item.id),
            icon: iconFn(item.monitor_type),
          });
        } else {
          templateTree.push({
            name: item.system,
            system: item.system,
            system_alias: item.system_alias,
            children: [
              {
                ...item,
                checked: checkedSet.has(item.id),
                icon: iconFn(item.monitor_type),
              },
            ],
          });
        }
      }
    }
    this.templateTree = templateTree;
  }

  handleClickTemplateItem(item: ITempLateItem) {
    this.$emit('cursorChange', item.id);
  }

  handleChangeChecked(item: ITempLateItem, checked: boolean) {
    item.checked = checked;
    this.handleChange();
  }

  handleChange() {
    const checkedList = [];
    for (const item of this.templateTree) {
      for (const child of item.children) {
        if ((child as unknown as ICategoryItem)?.children) {
          for (const c of (child as unknown as ICategoryItem).children) {
            if (c.checked) {
              checkedList.push(c.id);
            }
          }
        } else {
          if (child.checked) {
            checkedList.push(child.id);
          }
        }
      }
    }
    this.$emit('checkedChange', checkedList);
  }

  handleChangeCategoryChecked(category: ICategoryItem, checked: boolean) {
    category.checked = checked;
    for (const item of category.children) {
      item.checked = checked;
    }
    this.handleChange();
  }

  handleClickGoStrategy(item: ITempLateItem) {
    this.$emit('goStrategy', item?.strategy?.id);
  }

  render() {
    const renderTemplateItem = (item: ITempLateItem) => {
      return (
        <div
          key={item.id}
          class={['template-item', { active: item.id === this.cursorId }]}
          onClick={() => this.handleClickTemplateItem(item)}
        >
          <span
            v-bk-tooltips={{
              content: this.$t('再次勾选「已配置」的策略，可重新下发，覆盖原有的策略'),
              width: 188,
              placement: 'left',
              distance: 18,
              disabled: !item?.has_been_applied,
            }}
            onClick={e => {
              e.stopPropagation();
            }}
          >
            <bk-checkbox
              class='template-item-checkbox'
              value={item.checked}
              onChange={v => this.handleChangeChecked(item, v)}
            />
          </span>
          {item.icon.length > 100 ? (
            <span
              style={{ backgroundImage: `url(${item.icon})` }}
              class='template-item-icon'
            />
          ) : (
            <span class={['template-item-icon icon-monitor', item.icon]} />
          )}
          <div class='template-item-desc'>{item.name}</div>
          {item?.has_been_applied ? (
            <div
              class='template-item-status'
              onClick={e => {
                e.stopPropagation();
                this.handleClickGoStrategy(item);
              }}
            >
              <span>{this.$t('已配置')}</span>
              <span class='icon-monitor icon-mc-goto' />
            </div>
          ) : undefined}
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
            <div class='system-name'>{item?.system_alias || item.name}</div>
            {item.children.map(child => {
              if ((child as unknown as ICategoryItem)?.children) {
                return (
                  <div
                    key={child.category}
                    class='category-item'
                  >
                    <bk-checkbox
                      class='category-item-checkbox'
                      indeterminate={(child as unknown as ICategoryItem).indeterminate}
                      value={child.checked}
                      onChange={v => {
                        this.handleChangeCategoryChecked(child as unknown as ICategoryItem, v);
                      }}
                    >
                      {child?.category_alias || child.category}(
                      {`${(child as unknown as ICategoryItem).children.filter(c => c.checked).length} / ${(child as unknown as ICategoryItem).children.length}`}
                      )
                    </bk-checkbox>
                    {(child as unknown as ICategoryItem).children.map(c => renderTemplateItem(c))}
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
