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

import { K8sDimension } from '../../k8s-dimension';
import { EDimensionKey, type GroupListItem, type SceneType } from '../../typings/k8s-new';
import KvTag from './kv-tag';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IGroupOptionsItem, ITagListItem, IValueItem, IFilterByItem } from './utils';

import './filter-by-condition.scss';

interface IProps {
  filterBy?: IFilterByItem[];
  scene?: SceneType;
  bcsClusterId?: string;
  timeRange?: TimeRangeType;
  onChange?: (v: IFilterByItem[]) => void;
}

@Component
export default class FilterByCondition extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) filterBy: IFilterByItem[];
  /* 场景 */
  @Prop({ type: String, default: '' }) scene: SceneType;
  /* 集群id */
  @Prop({ type: String, default: '' }) bcsClusterId: string;
  /* 时间范围 */
  @Prop({ type: Array, default: () => [] }) timeRange: TimeRangeType;
  @Ref('selector') selectorRef: HTMLDivElement;
  groupList: GroupListItem[] = [];
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
  allOptions = [];
  allOptionsMap = new Map();

  loading = false;
  scrollLoading = false;
  valueLoading = false;
  k8sDimension: K8sDimension;

  resizeObserver = null;
  overflowCountRenderDebounce = null;
  handleValueOptionsScrollThrottle = _v => {};

  @Watch('scene', { immediate: true })
  handleWatchScene() {
    this.initData();
  }
  @Watch('bcsClusterId', { immediate: true })
  handleWatchBcsClusterId() {
    this.initData();
  }
  @Watch('timeRange', { immediate: true })
  handleWatchTimeRange() {
    this.initData();
  }

  @Debounce(200)
  async initData() {
    this.loading = true;
    this.k8sDimension = new K8sDimension({
      scene: this.scene,
      pageSize: 10,
      keyword: '',
      pageType: 'scrolling',
      bcsClusterId: this.bcsClusterId,
    });
    await this.k8sDimension.init();
    this.groupList = this.k8sDimension.originDimensionData;
    this.allOptions = this.getGroupList();
    this.loading = false;
  }

  get hasAdd() {
    const ids = this.allOptions.map(item => item.id);
    const tags = new Set(this.tagList.map(item => item.id));
    return !ids.every(id => tags.has(id));
  }

  mounted() {
    this.handleValueOptionsScrollThrottle = throttle(300, this.handleValueOptionsScroll);
    this.overflowCountRenderDebounce = debounce(300, this.overflowCountRender);
    this.resizeObserver = new ResizeObserver(entries => {
      for (const _entry of entries) {
        this.overflowCountRenderDebounce();
      }
    });
    this.resizeObserver.observe(this.$el);
  }

  @Watch('filterBy')
  handleWatchFilterBy() {
    const filterByStr = JSON.stringify(this.filterBy);
    const localFilterByStr = JSON.stringify(this.localFilterBy);
    if (filterByStr !== localFilterByStr) {
      this.localFilterBy = JSON.parse(JSON.stringify(this.filterBy));
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
    this.$emit('change', filterBy);
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
          name: groupMap?.name || '--',
          key: random(8),
          values: item.value.map(v => ({
            id: v,
            name: groupMap?.itemsMap.get(v) || '--',
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
  getGroupList() {
    return this.groupList.map(item => {
      const itemsMap = new Map();
      const result = {
        id: item.id,
        name: item.name,
        count: item.count,
        list: item.children.map(child => {
          if (item.id !== EDimensionKey.workload) {
            itemsMap.set(child.id, child.name);
          }
          return {
            id: child.id,
            name: child.name,
            count: child?.count,
            list: child?.children?.map(c => {
              itemsMap.set(c.id, c.name);
              return {
                id: c.id,
                name: c.name,
              };
            }),
          };
        }),
      };
      this.allOptionsMap.set(item.id, {
        itemsMap: itemsMap,
        name: item.name,
      });
      return result;
    });
  }

  async handleAdd(event: MouseEvent) {
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
  handleSelectGroup(id: string) {
    if (this.groupSelected !== id) {
      this.groupSelected = id;
      const checkedSet = new Set();
      for (const tag of this.tagList) {
        if (tag.id === id) {
          for (const v of tag.values) {
            checkedSet.add(v.id);
          }
          break;
        }
      }
      if (this.groupSelected === EDimensionKey.workload) {
        const groupValues = this.allOptions.find(item => item.id === this.groupSelected)?.list || [];
        this.valueCategoryOptions = groupValues.map(item => ({
          ...item,
          checked: false,
          list:
            item?.list?.map(l => ({
              ...l,
              checked: checkedSet.has(l.id),
            })) || [],
        }));
        if (this.valueCategorySelected) {
          this.valueOptions =
            this.valueCategoryOptions.find(item => item.id === this.valueCategorySelected)?.list || [];
        } else {
          this.valueCategorySelected = this.valueCategoryOptions[0]?.id || '';
          this.valueOptions = this.valueCategoryOptions?.[0]?.list || [];
        }
      } else {
        this.valueCategoryOptions = [];
        const groupValues = this.allOptions.find(item => item.id === this.groupSelected)?.list || [];
        this.valueOptions = groupValues.map(item => ({ ...item, checked: checkedSet.has(item.id) }));
      }
      // this.handleSearchChange('');
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
    await this.k8sDimension.search(value, this.groupSelected as EDimensionKey);
    this.groupList = this.k8sDimension.originDimensionData;
    this.allOptions = this.getGroupList();
    this.handleSelectGroup(this.groupSelected);
    this.valueLoading = false;
    // if (!value) {
    //   this.searchValueOptions = this.valueOptions;
    //   this.searchValueCategoryOptions = this.valueCategoryOptions;
    //   return;
    // }
    // if (this.groupSelected === EGroupBy.workload) {
    //   this.searchValueCategoryOptions = this.valueCategoryOptions.filter(item => {
    //     return item.list.some(l => {
    //       const lName = l.name.toLocaleLowerCase();
    //       return lName.includes(searchValue);
    //     });
    //   });
    // }
    // this.searchValueOptions = this.valueOptions.filter(item => {
    //   const name = item.name.toLocaleLowerCase();
    //   return name.includes(searchValue);
    // });
  }

  /**
   * @description 选择value选项
   * @param item
   */
  handleCheck(item: IValueItem) {
    item.checked = !item.checked;
    if (this.groupSelected === EDimensionKey.workload) {
      let isBreak = false;
      for (const option of this.valueCategoryOptions) {
        for (const l of option.list) {
          if (l.id === item.id) {
            l.checked = item.checked;
            isBreak = true;
            break;
          }
        }
        if (isBreak) {
          break;
        }
      }
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
    if (this.groupSelected === EDimensionKey.workload) {
      for (const option of this.valueCategoryOptions) {
        for (const l of option.list) {
          if (l.checked) {
            curSelected.push(l);
          }
        }
      }
    } else {
      for (const value of this.valueOptions) {
        if (value.checked) {
          curSelected.push(value);
        }
      }
    }
    let has = false;
    if (!curSelected.length) {
      const delIndex = this.tagList.findIndex(item => item.id === this.groupSelected);
      if (delIndex > -1) {
        this.tagList.splice(delIndex, 1);
      }
    } else {
      for (const tag of this.tagList) {
        if (tag.id === this.groupSelected) {
          tag.values = curSelected.map(item => ({
            id: item.id,
            name: item.name,
          }));
          has = true;
          break;
        }
      }
      if (!has) {
        const groupItem = this.groupOptions.find(item => item.id === this.groupSelected);
        const obj = {
          key: random(8),
          id: groupItem.id,
          name: groupItem.name,
          values: curSelected.map(item => ({
            id: item.id,
            name: item.name,
          })),
        };
        this.tagList.push(obj);
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
    this.setGroupOptions();
    this.handleAdd(event);
  }
  /**
   * @description 点击了某条tag准备进行更新操作
   * @param target
   * @param item
   */
  async handleUpdateTag(target: any, item: ITagListItem) {
    this.updateActive = item.key;
    this.setGroupOptions();
    this.handleAdd({ target } as any);
  }

  // 切换workload 分类
  handleSelectCategory(item: IValueItem) {
    this.valueCategorySelected = item.id;
    const values = this.valueCategoryOptions.find(item => item.id === this.valueCategorySelected)?.list || [];
    this.valueOptions = values;
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
    if (isEnd && !this.scrollLoading) {
      this.scrollLoading = true;
      await this.k8sDimension.loadMore(this.groupSelected);
      this.scrollLoading = false;
    }
  }

  valuesWrap() {
    return (
      <div
        class='value-items'
        onScroll={this.handleValueOptionsScrollThrottle}
      >
        {this.valueOptions.map(item => (
          <div
            key={item.id}
            class={['value-item', { checked: item.checked }]}
            onClick={() => this.handleCheck(item)}
          >
            <span class='value-item-name'>{item.name}</span>
            <span class='value-item-checked'>{item.checked && <span class='icon-monitor icon-mc-check-small' />}</span>
          </div>
        ))}
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
          onClick={() => this.handleExpand()}
        >
          <span class='count-text'>{this.overflowCount}</span>
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
        {!this.loading ? (
          <div class='tag-list-wrap'>{this.tagsWrap()}</div>
        ) : (
          <div class='skeleton-element tags-wrap-loading'></div>
        )}
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
            <div class='filter-by-condition-component-popover-header'>
              {this.groupOptions.map(option => (
                <div
                  key={option.id}
                  class={['group-item', { active: this.groupSelected === option.id }]}
                  onClick={() => this.handleSelectGroup(option.id)}
                >
                  <span class='group-item-name'>{option.name}</span>
                  <span class='group-item-count'>{option.count}</span>
                </div>
              ))}
            </div>
            <div class='filter-by-condition-component-popover-content'>
              <div class='values-search'>
                <bk-input
                  behavior='simplicity'
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
                  {this.valuesWrap()}
                </div>
              ) : (
                this.valuesWrap()
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }
}
