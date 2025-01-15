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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, random } from 'monitor-common/utils';
import { debounce, throttle } from 'throttle-debounce';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import { EDimensionKey, type ICommonParams } from '../../typings/k8s-new';
import KvTag from './kv-tag';
import {
  type IGroupOptionsItem,
  type ITagListItem,
  type IValueItem,
  type IFilterByItem,
  FilterByOptions,
} from './utils';

import './filter-by-condition.scss';

type TFilterByDict = Record<EDimensionKey | string, string[]>;

interface IProps {
  filterBy?: IFilterByItem[] | TFilterByDict;
  commonParams?: ICommonParams;
  onChange?: (v: IFilterByItem[]) => void;
}

@Component
export default class FilterByCondition extends tsc<IProps> {
  @Prop({ type: [Array, Object], default: () => [] }) filterBy: IFilterByItem[] | TFilterByDict;
  @Prop({ type: Object, default: () => ({}) }) commonParams: ICommonParams;
  @Ref('selector') selectorRef: HTMLDivElement;
  @Ref('valueItems') valueItemsRef: HTMLDivElement;
  // tags
  tagList: ITagListItem[] = [];
  popoverInstance = null;
  // 头部group选项
  groupOptions: IGroupOptionsItem[] = [];
  // 当前选择的group
  groupSelected: EDimensionKey | string = '';
  // 当前选择的group下的value选项
  valueOptions: IValueItem[] = [];
  // 当前选择的value下的value选项 (二级分类)
  valueCategoryOptions: IValueItem[] = [];
  //  当前选择的分类
  valueCategorySelected = '';
  // 搜索框输入的值
  searchValue = '';
  // searchValueOptions = [];
  // searchValueCategoryOptions = [];
  // 当前点击的tag
  updateActive = '';
  // 溢出的数量
  overflowCount = 0;
  // 当前溢出的下标
  overflowIndex = 0;
  // 展开tagList
  isExpand = false;
  localFilterBy = [];
  oldLocalFilterBy = [];
  allOptions = [];
  allOptionsMap = new Map();
  // 点击加号时，记录当前选择的group和value
  addValueSelected: Map<string, Set<string>> = new Map();
  // 编辑tag时缓存workload的已选值
  workloadValueSelected = '';

  loading = false;
  scrollLoading = false;
  valueLoading = false;
  rightValueLoading = false;
  filterByOptions: FilterByOptions;

  resizeObserver = null;
  overflowCountRenderDebounce = null;
  overflowCountTip = [];

  handleValueOptionsScrollThrottle = _v => {};

  @Watch('commonParams', { deep: true, immediate: true })
  handleWatchScene() {
    this.initData();
  }

  @Debounce(200)
  async initData() {
    if (!this.commonParams?.bcs_cluster_id) {
      return;
    }
    this.loading = true;
    this.filterByOptions = new FilterByOptions({
      ...this.commonParams,
      page_size: 10,
      page_type: 'scrolling',
      filter_dict: {},
      with_history: false,
      query_string: this.searchValue,
    });
    await this.filterByOptions.init();
    this.allOptions = this.getGroupList(this.filterByOptions.dimensionData);
    await this.initNextPage();
    this.loading = false;
  }

  get hasAdd() {
    const ids = this.allOptions.map(item => item.id);
    const tags = new Set(this.tagList.map(item => item.id));
    return !ids.every(id => tags.has(id));
  }

  get isSelectedWorkload() {
    return this.groupSelected === EDimensionKey.workload;
  }

  mounted() {
    this.handleValueOptionsScrollThrottle = throttle(500, this.handleValueOptionsScroll);
    this.overflowCountRenderDebounce = debounce(300, this.overflowCountRender);
    this.resizeObserver = new ResizeObserver(entries => {
      for (const _entry of entries) {
        this.overflowCountRenderDebounce();
      }
    });
    this.resizeObserver.observe(this.$el);
  }

  destroyed() {
    this.resizeObserver.disconnect();
  }

  @Watch('filterBy', { immediate: true, deep: true })
  handleWatchFilterBy() {
    let filterBy = [];
    if (Array.isArray(this.filterBy)) {
      filterBy = this.filterBy;
    } else {
      for (const key in this.filterBy) {
        if (this.filterBy[key]?.length) {
          filterBy.push({
            key,
            value: this.filterBy[key],
          });
        }
      }
    }
    const filterByStr = JSON.stringify(filterBy);
    const localFilterByStr = JSON.stringify(this.localFilterBy);
    if (filterByStr !== localFilterByStr) {
      this.localFilterBy = JSON.parse(JSON.stringify(filterBy));
      this.oldLocalFilterBy = JSON.parse(JSON.stringify(filterBy));
      this.filterByToTags();
      this.overflowCountRender();
    }
  }

  /**
   * @description change
   */
  handleChange() {
    const filterBy = [];
    for (const item of this.tagList) {
      filterBy.push({
        key: item.id,
        value: item.values.map(v => v.id),
      });
    }
    this.localFilterBy = JSON.parse(JSON.stringify(filterBy));
    if (JSON.stringify(this.oldLocalFilterBy) !== JSON.stringify(this.localFilterBy)) {
      const filterDict = {};
      for (const item of filterBy) {
        filterDict[item.key] = item.value;
      }
      this.$emit('change', filterDict);
    }
    this.oldLocalFilterBy = JSON.parse(JSON.stringify(filterBy));
  }

  /**
   * @description filterBy => Tags
   */
  filterByToTags() {
    const tagList = [];
    for (const item of this.localFilterBy) {
      const groupMap = this.allOptionsMap.get(item.key);
      if (item.value.length) {
        tagList.push({
          id: item.key,
          name: groupMap?.name || item.key || '--',
          key: random(8),
          values: item.value.map(v => ({
            id: v,
            name: groupMap?.itemsMap.get(v) || v || '--',
          })),
        });
      }
    }
    this.tagList = tagList;
    this.updateActive = '';
    this.groupSelected = '';
  }

  /**
   * @description 从上层获取所有选项
   * @returns
   */
  getGroupList(list) {
    const result = [];
    for (const item of list) {
      const obj = {
        id: item.id,
        name: item.name,
        count: item.count,
        children: [],
      };
      if (item.id === EDimensionKey.workload) {
        for (const child of item.children) {
          const tempSet = new Set();
          const objChild = {
            id: child.id,
            name: child.name,
            count: child?.count,
            children: [],
          };
          for (const cc of child.children) {
            if (!tempSet.has(cc.id)) {
              const regex = new RegExp(`^${child.name}:`);
              const name = cc.name.replace(regex, '');
              objChild.children.push({
                id: cc.id,
                name: name,
              });
            }
            tempSet.add(cc.id);
          }
          obj.children.push(objChild);
        }
      } else {
        const tempSet = new Set();
        for (const c of item.children) {
          if (!tempSet.has(c.id)) {
            obj.children.push({
              id: c.id,
              name: c.name,
            });
          }
          tempSet.add(c.id);
        }
      }
      result.push(obj);
    }

    return result;
  }

  async handleAdd(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 20,
      zIndex: 9999,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
        this.setTagList();
        this.updateActive = '';
        this.addValueSelected = new Map();
        this.workloadValueSelected = '';
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /**
   * @description 选择某项group
   * @param id
   */
  handleSelectGroup(id: string, search = false) {
    if (this.groupSelected !== id || search) {
      this.groupSelected = id;
      let checkedSet = new Set();
      for (const [id, valueSets] of this.addValueSelected) {
        if (id === this.groupSelected) {
          checkedSet = new Set(valueSets);
        }
      }
      if (this.groupSelected === EDimensionKey.workload) {
        const groupValues = this.allOptions.find(item => item.id === this.groupSelected)?.children || [];
        this.valueCategoryOptions = groupValues.map(item => ({
          ...item,
          checked: false,
          children:
            item?.children?.map(l => ({
              ...l,
              checked: this.workloadValueSelected ? this.workloadValueSelected === l.id : checkedSet.has(l.id),
            })) || [],
        }));
        if (this.valueCategorySelected) {
          this.valueOptions =
            this.valueCategoryOptions.find(item => item.id === this.valueCategorySelected)?.children || [];
        } else {
          this.valueCategorySelected = this.valueCategoryOptions[0]?.id || '';
          this.valueOptions = this.valueCategoryOptions?.[0]?.children || [];
        }
      } else {
        this.valueCategoryOptions = [];
        const groupValues = this.allOptions.find(item => item.id === this.groupSelected)?.children || [];
        this.valueOptions = groupValues.map(item => ({ ...item, checked: checkedSet.has(item.id) }));
      }
      this.valueOptionsSticky();
    }
  }

  @Debounce(300)
  handleSearchChangeDebounce(value: string) {
    this.handleSearchChange(value);
  }

  /**
   * @description 搜索
   * @param value
   * @returns
   */
  async handleSearchChange(value: string) {
    this.searchValue = value;
    this.valueLoading = true;
    const params = {
      0: this.groupSelected as EDimensionKey,
      1: this.groupSelected === EDimensionKey.workload ? this.valueCategorySelected : '',
    };
    await this.filterByOptions.search(value, params[0], params[1]);
    this.allOptions = this.getGroupList(this.filterByOptions.dimensionData);
    for (const item of this.groupOptions) {
      if (item.id === this.groupSelected) {
        const count = this.allOptions.find(o => o.id === item.id)?.count || 0;
        item.count = count;
        break;
      }
    }
    await this.initNextPage(params[0], params[1]);
    this.handleSelectGroup(this.groupSelected, true);
    this.valueLoading = false;
  }

  /**
   * @description 选择value选项
   * @param item
   */
  handleCheck(item: IValueItem) {
    item.checked = !item.checked;
    this.addValueSelectedSet(item);
    if (this.groupSelected === EDimensionKey.workload) {
      // workload 当前只能单选
      if (this.updateActive) {
        this.workloadValueSelected = item.checked ? item.id : '';
      }
      for (const option of this.valueCategoryOptions) {
        for (const l of option.children) {
          if (l.id === item.id) {
            l.checked = item.checked;
          } else {
            l.checked = false;
          }
        }
      }
      this.valueOptions =
        this.valueCategoryOptions.find(item => item.id === this.valueCategorySelected)?.children || [];
    } else {
      for (const v of this.valueOptions) {
        if (v.id === item.id) {
          v.checked = item.checked;
          break;
        }
      }
    }
  }

  /**
   * @description 整理tags
   */
  setTagList() {
    const curSelected = [];
    const tagSelected = []; // 获取当前不存在下拉选项的tags
    for (const tag of this.tagList) {
      if (tag.id === this.groupSelected) {
        tagSelected.push(...tag.values.map(item => item.id));
        break;
      }
    }
    const tempSet = new Set();
    // 获取可选项中已选项
    if (this.groupSelected === EDimensionKey.workload) {
      for (const option of this.valueCategoryOptions) {
        for (const l of option.children) {
          if (l.checked) {
            curSelected.push(l);
          }
          tempSet.add(l.id);
        }
      }
    } else {
      for (const value of this.valueOptions) {
        if (value.checked) {
          curSelected.push(value);
        }
        tempSet.add(value.id);
      }
    }
    // 获取不可选项中的以选项
    const otherIds = [];
    for (const t of tagSelected) {
      if (!tempSet.has(t)) {
        otherIds.push(t);
      }
    }
    if (!curSelected.length) {
      const delIndex = this.tagList.findIndex(item => item.id === this.groupSelected);
      if (delIndex > -1) {
        if (otherIds.length) {
          this.tagList[delIndex].values = otherIds.map(id => ({
            id: id,
            name: id,
          }));
        } else {
          this.tagList.splice(delIndex, 1);
        }
      }
    } else {
      if (this.updateActive) {
        const updateActiveId = this.tagList.find(tag => tag.key === this.updateActive)?.id || '';
        // 更新 （如果切换到其他group 则更改当前tag）
        if (updateActiveId !== this.groupSelected) {
          const updateIndex = this.tagList.findIndex(item => item.id === updateActiveId);
          const groupItem = this.groupOptions.find(item => item.id === this.groupSelected);
          this.tagList.splice(updateIndex, 1, {
            key: random(8),
            id: groupItem.id,
            name: groupItem.name,
            values: curSelected.map(item => ({
              id: item.id,
              // name: item.name,
              name: item.id,
            })),
          });
        } else {
          for (const tag of this.tagList) {
            if (tag.id === this.groupSelected) {
              const values = curSelected.map(item => ({
                id: item.id,
                // name: item.name,
                name: item.id,
              }));
              values.unshift(
                ...otherIds.map(id => ({
                  id: id,
                  name: id,
                }))
              );
              tag.values = values;
              break;
            }
          }
        }
      } else {
        // 添加
        const tags = [];
        for (const [id, valueSets] of this.addValueSelected) {
          tags.push({
            key: random(8),
            id: id,
            name: id,
            values: Array.from(valueSets).map(v => ({
              id: v,
              name: v,
            })),
          });
        }
        this.tagList.push(...tags);
      }
    }
    this.handleChange();
    this.overflowCountRender();
  }

  /**
   * @description 点击添加按钮
   * @param event
   */
  async handleAddTag(event: MouseEvent) {
    this.searchValue = '';
    this.setGroupOptions();
    this.handleAdd(event);
    this.handleSearchChange('');
  }
  /**
   * @description 点击了某条tag准备进行更新操作
   * @param target
   * @param item
   */
  async handleUpdateTag(target: any, item: ITagListItem) {
    this.updateActive = item.key;
    if (item.id === EDimensionKey.workload) {
      this.workloadValueSelected = item.values?.[0]?.id || '';
    } else {
      this.addValueSelected.set(item.id, new Set(item.values.map(v => v.id)));
    }
    this.setGroupOptions();
    this.handleAdd({ target } as any);
    this.handleSearchChange('');
  }

  // 切换workload 分类
  async handleSelectCategory(item: IValueItem) {
    this.valueCategorySelected = item.id;
    this.rightValueLoading = true;
    await this.filterByOptions.initOfType(this.groupSelected as EDimensionKey, item.id);
    this.allOptions = this.getGroupList(this.filterByOptions.dimensionData);
    this.handleSelectGroup(this.groupSelected, true);
    this.rightValueLoading = false;
  }

  // 计算溢出个数
  async overflowCountRender() {
    setTimeout(() => {
      const wrapWidth = this.$el.clientWidth - 70;
      const hiddenWrap = this.$el.querySelector('.tag-list-wrap-hidden');
      let index = 0;
      let w = 0;
      let count = 0;
      for (const item of Array.from(hiddenWrap.children)) {
        w += item.offsetWidth + 4;
        if (w > wrapWidth) {
          break;
        }
        index += 1;
        if (index % 2) {
          count += 1;
        }
      }
      this.overflowIndex = index;
      this.overflowCount = this.tagList.length - count;
      if (!this.overflowCount) {
        this.isExpand = false;
      }
      const overflowCountTip = [];
      if (this.overflowCount) {
        for (let i = this.overflowCount; i > 0; i--) {
          const tag = this.tagList[this.tagList.length - i];
          if (tag) {
            overflowCountTip.push(`${tag.id} = ${tag.values.map(v => v.id).join(', ')}`);
          }
        }
      }
      this.overflowCountTip = overflowCountTip;
    }, 100);
  }

  /**
   * @description 展开收起
   */
  handleExpand() {
    this.isExpand = !this.isExpand;
  }

  /**
   * @description 获取当前剩余group选项
   */
  setGroupOptions() {
    const groupsSet = new Set();
    let updateActiveId = '';
    for (const tag of this.tagList) {
      groupsSet.add(tag.id);
      if (tag.key === this.updateActive) {
        updateActiveId = tag.id;
      }
    }
    const groupOptions = [];
    for (const item of this.allOptions) {
      if (!groupsSet.has(item.id) || updateActiveId === item.id) {
        groupOptions.push({
          ...item,
          list: [],
        });
      }
    }
    this.groupOptions = groupOptions;
    this.handleSelectGroup(updateActiveId || groupOptions?.[0]?.id);
  }

  /**
   * @description 删除tag
   * @param item
   */
  handleDeleteTag(item: ITagListItem) {
    this.destroyPopoverInstance();
    this.tagList = this.tagList.filter(tag => tag.key !== item.key);
    this.updateActive = '';
    this.groupSelected = '';
    this.handleChange();
    this.overflowCountRender();
  }

  /**
   * @description 下拉加载
   * @param e
   */
  async handleValueOptionsScroll(e: any) {
    const { scrollTop, clientHeight, scrollHeight } = e.target;
    const isEnd = Math.abs(scrollTop + clientHeight - scrollHeight) <= 1;
    const pageEnd = this.filterByOptions.getPageEnd(this.groupSelected as EDimensionKey, this.valueCategorySelected);
    if (isEnd && !this.scrollLoading && !pageEnd) {
      this.scrollLoading = true;
      this.$nextTick(() => {
        this.valueItemsRef.scrollTop = this.valueItemsRef.scrollHeight - clientHeight;
      });
      await this.filterByOptions.getNextPageData(this.groupSelected as EDimensionKey, this.valueCategorySelected);
      this.allOptions = this.getGroupList(this.filterByOptions.dimensionData);
      this.handleSelectGroup(this.groupSelected, true);
      this.scrollLoading = false;
    }
  }

  handleEmptyOperation() {
    this.handleSearchChange('');
  }

  // 去重后发现数据过少，需立即加载下一页
  async initNextPage(type?: EDimensionKey, categoryDim?: string) {
    const promiseList = [];
    const nextPage = async (dimension: EDimensionKey, categoryDim?: string) => {
      const pageEnd = this.filterByOptions.getPageEnd(this.groupSelected as EDimensionKey, this.valueCategorySelected);
      if (!pageEnd) {
        await this.filterByOptions.getNextPageData(dimension, categoryDim);
      }
    };
    for (const item of this.allOptions) {
      if (type && item.id !== type) continue;
      if (item.id === EDimensionKey.workload) {
        for (const child of item.children) {
          if (child && child.id !== categoryDim) continue;
          if (child.children.length < 10 && child.count >= 10) {
            promiseList.push(nextPage(item.id, child.id));
          }
        }
      } else {
        if (item.children.length < 10 && item.count >= 10) {
          promiseList.push(nextPage(item.id));
        }
      }
    }
    await Promise.all(promiseList);
    this.allOptions = this.getGroupList(this.filterByOptions.dimensionData);
  }

  async handleSelectGroupProxy(id: string) {
    this.handleSelectGroup(id);
    this.searchValue = '';
    await this.handleSearchChange(this.searchValue);
  }

  /**
   * @description 记录当前选中项
   * @param item
   */
  addValueSelectedSet(item: IValueItem) {
    // if (!this.updateActive) {
    // }
    const groupSet = this.addValueSelected.get(this.groupSelected);
    if (item.checked) {
      if (groupSet && this.groupSelected !== EDimensionKey.workload) {
        groupSet.add(item.id);
      } else {
        this.addValueSelected.set(this.groupSelected, new Set([item.id]));
      }
    } else {
      if (groupSet) {
        groupSet.delete(item.id);
      }
    }
  }

  /**
   * @description 已选项置顶
   */
  valueOptionsSticky() {
    if (this.groupSelected === EDimensionKey.workload) {
      const category = this.workloadValueSelected.match(/^[^:]+/)?.[0];
      if (category === this.valueCategorySelected) {
        const isSearch = this.workloadValueSelected.toLocaleLowerCase().includes(this.searchValue.toLocaleLowerCase());
        const regex = new RegExp(`^${category}:`);
        const name = this.workloadValueSelected.replace(regex, '');
        const sticky = {
          id: this.workloadValueSelected,
          name,
          checked: true,
        };
        const other = [];
        for (const item of this.valueOptions) {
          if (this.workloadValueSelected !== item.id) {
            other.push({
              ...item,
              checked: false,
            });
          }
        }
        if (isSearch) {
          other.unshift(sticky);
        }
        this.valueOptions = other;
      }
    } else {
      const other = [];
      const checkedSet = this.addValueSelected.get(this.groupSelected);
      const checkedList = checkedSet ? Array.from(checkedSet) : [];
      const sticky = checkedList
        .map(id => ({
          id,
          name: id,
          checked: true,
        }))
        .filter(item => item.id.toLocaleLowerCase().includes(this.searchValue.toLocaleLowerCase()));
      for (const item of this.valueOptions) {
        if (!item.checked && !checkedSet?.has?.(item.id)) {
          other.push(item);
        }
      }
      this.valueOptions = [...sticky, ...other];
    }
  }

  valuesWrap() {
    return (
      <div
        ref='valueItems'
        class={['value-items', { 'value-items--workload': this.isSelectedWorkload }]}
        onScroll={this.handleValueOptionsScrollThrottle}
      >
        {this.valueOptions.length ? (
          this.valueOptions.map((item, index) => (
            <div
              key={`${item.id}_${index}`}
              class={['value-item', { checked: item.checked }]}
              onClick={() => this.handleCheck(item)}
            >
              <span
                class='value-item-name'
                v-bk-overflow-tips={{ content: item.id }}
              >
                {item.name}
              </span>
              {!this.isSelectedWorkload && (
                <span class='value-item-checked'>
                  {item.checked && <span class='icon-monitor icon-mc-check-small' />}
                </span>
              )}
            </div>
          ))
        ) : (
          <EmptyStatus
            type={this.searchValue ? 'search-empty' : 'empty'}
            onOperation={this.handleEmptyOperation}
          />
        )}
        {this.scrollLoading && (
          <div class='scroll-loading-wrap'>
            <bk-spin size={'mini'} />
          </div>
        )}
      </div>
    );
  }

  tagsWrap(ishidden = false) {
    if (ishidden) {
      return this.tagList.map((item, index) => {
        return [
          index >= 1 && (
            <span
              key={`and_${item.key}`}
              class='filter-by-condition-tag type-condition'
            >
              AND
            </span>
          ),
          <KvTag
            key={item.key}
            active={this.updateActive === item.key}
            value={item}
          />,
        ];
      });
    }
    const list = [];
    let i = 0;
    for (const tag of this.tagList) {
      if (i > 0) {
        list.push({
          name: 'AND',
          id: '__and__',
          key: random(8),
          values: [],
        });
      }
      list.push(tag);
      i += 1;
    }
    return [
      list.map((item, index) => {
        if (!this.isExpand && index >= this.overflowIndex && this.overflowCount > 0) {
          return undefined;
        }
        if (item.id === '__and__') {
          return (
            <span
              key={`and_${item.key}`}
              class='filter-by-condition-tag type-condition'
            >
              AND
            </span>
          );
        }
        return (
          <KvTag
            key={item.key}
            active={this.updateActive === item.key}
            value={item}
            onClickTag={target => this.handleUpdateTag(target, item)}
            onDeleteTag={() => this.handleDeleteTag(item)}
          />
        );
      }),
      this.overflowCount && !this.isExpand ? (
        <span
          key={'__count__'}
          class='filter-by-condition-tag type-count'
          v-bk-tooltips={{
            content: `<div>${this.overflowCountTip.map(o => `<div>${o}</div>`).join('')}</div>`,
            allowHTML: true,
            delay: [300, 0],
          }}
          onClick={() => this.handleExpand()}
        >
          <span class='count-text'>{`+${this.overflowCount}`}</span>
          <span class='icon-monitor icon-arrow-down' />
        </span>
      ) : this.hasAdd ? (
        <span
          key='__add__'
          class='filter-by-condition-tag type-add'
          onClick={this.handleAddTag}
        >
          <span class='icon-monitor icon-plus-line' />
        </span>
      ) : undefined,
      this.isExpand && (
        <span
          key={'__count__'}
          class='filter-by-condition-tag type-expand'
          onClick={() => this.handleExpand()}
        >
          <span class='count-text'>{this.$t('收起')}</span>
          <span class='icon-monitor icon-arrow-up' />
        </span>
      ),
    ];
  }

  render() {
    return (
      <div class={['filter-by-condition-component', { 'expand-tags': this.isExpand }]}>
        <div class='tag-list-wrap'>{this.tagsWrap()}</div>
        <div class='tag-list-wrap-hidden'>{this.tagsWrap(true)}</div>
        <div
          style={{
            display: 'none',
          }}
        >
          <div
            ref='selector'
            class='filter-by-condition-component-popover'
          >
            {this.loading ? (
              <div class='filter-by-condition-skeleton'>
                <div class='header-skeleton'>
                  <div class='skeleton-element skeleton-item' />
                </div>
                <div class='content-skeleton'>
                  <div class='skeleton-loading-wrap'>
                    {new Array(8).fill(null).map((_item, index) => {
                      return (
                        <div
                          key={index}
                          class='loading-item'
                        >
                          <div class='skeleton-element skeleton-item' />
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              [
                <div
                  key='header'
                  class='filter-by-condition-component-popover-header'
                >
                  {this.groupOptions.map(option => (
                    <div
                      key={option.id}
                      class={['group-item', { active: this.groupSelected === option.id }]}
                      onClick={() => this.handleSelectGroupProxy(option.id)}
                    >
                      <span class='group-item-name'>{option.name}</span>
                      <span class='group-item-count'>{option.count}</span>
                    </div>
                  ))}
                </div>,
                <div
                  key='content'
                  class='filter-by-condition-component-popover-content'
                >
                  <div class='values-search'>
                    <bk-input
                      behavior='simplicity'
                      clearable={true}
                      left-icon='bk-icon icon-search'
                      placeholder={this.$t('请输入关键字')}
                      value={this.searchValue}
                      onChange={this.handleSearchChangeDebounce}
                    />
                  </div>
                  {this.valueLoading ? (
                    <div class='skeleton-loading-wrap'>
                      {new Array(8).fill(null).map((_item, index) => {
                        return (
                          <div
                            key={index}
                            class='loading-item'
                          >
                            <div class='skeleton-element skeleton-item' />
                          </div>
                        );
                      })}
                    </div>
                  ) : this.valueCategoryOptions.length ? (
                    <div class='value-items-wrap'>
                      <div class='left-wrap'>
                        {this.valueCategoryOptions.map(item => (
                          <div
                            key={item.id}
                            class={['cate-item', { active: this.valueCategorySelected === item.id }]}
                            onClick={() => this.handleSelectCategory(item)}
                          >
                            <span class='cate-item-name'>{item.name}</span>
                            <span class='cate-item-count'>({item.count})</span>
                            <span class='cate-item-right'>
                              <span class='icon-monitor icon-arrow-right' />
                            </span>
                          </div>
                        ))}
                      </div>
                      {this.rightValueLoading ? (
                        <div class='skeleton-loading-wrap'>
                          {new Array(8).fill(null).map((_item, index) => {
                            return (
                              <div
                                key={index}
                                class='loading-item'
                              >
                                <div class='skeleton-element skeleton-item' />
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        this.valuesWrap()
                      )}
                    </div>
                  ) : (
                    this.valuesWrap()
                  )}
                </div>,
              ]
            )}
          </div>
        </div>
      </div>
    );
  }
}
