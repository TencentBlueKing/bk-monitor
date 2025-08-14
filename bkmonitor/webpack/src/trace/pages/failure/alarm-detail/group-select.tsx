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
import { type PropType, computed, defineComponent, ref, watch } from 'vue';

import { Exception, Input, Popover } from 'bkui-vue';
import { Search } from 'bkui-vue/lib/icon';
// import { $bkPopover } from 'bkui-vue/lib/popover';
import { debounce } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import './group-select.scss';

// interface IGroupSelect {
//   list?: IGroupItem[];
//   value?: string | number;
//   readonly?: boolean;
//   placeholder?: string;
// }

export interface IGroupItem {
  children?: IGroupItem[];
  fatherName?: string;
  id: string;
  name: string;
}

export default defineComponent({
  props: {
    list: {
      default: () => [],
      type: [] as PropType<IGroupItem[]>,
    },
    value: {
      default: '',
      type: [String, Number],
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: window.i18n.t('选择'),
    },
  },
  emits: ['clear', 'change'],
  setup(props, { emit }) {
    const selectPanelRef = ref(null);
    const selectWapRef = ref(null);
    const keyword = ref('');
    const popoverInstance = ref(null);
    const isShow = ref(false);
    const activeGroupId = ref('');
    const activeGroup = ref<IGroupItem>(null);
    const activeItem = ref<IGroupItem>(null);
    const activeId = ref('');
    const filterList = computed(() => {
      if (!keyword.value) return props.list;
      return props.list.filter(item =>
        item?.children?.some(child => child.name.toLocaleLowerCase().includes(keyword.value.toLocaleLowerCase()))
      );
    });
    const activeList = computed(() => {
      return filterList.value.find(item => item.id === activeGroupId.value)?.children || [];
    });

    const { t } = useI18n();

    watch(
      () => props.value,
      v => {
        activeId.value = v as string;
      },
      { immediate: true }
    );
    watch(
      () => props.list,
      (v: IGroupItem[]) => {
        if (v.length) {
          activeGroup.value = props.list.filter(item => item?.children?.some(child => child.id === activeId.value))[0];
          activeGroupId.value = activeGroup.value?.id;
          activeItem.value = activeGroup.value?.children.find(item => item.id === activeId.value);
          if (activeGroup.value?.name) {
            activeItem.value.fatherName = activeGroup.value.name;
          }
        }
      },
      { immediate: true }
    );

    // 清除popover实例
    const destroyPopoverInstance = (show: boolean) => {
      popoverInstance.value?.close();
      popoverInstance.value = null;
      isShow.value = show;
    };

    const handleKeywordChange = debounce(
      () => {
        handleGroupMouseenter(filterList.value[0]);
      },
      300,
      false
    );

    const handleGroupMouseenter = (item: IGroupItem) => {
      activeGroupId.value = item?.id || '';
      activeGroup.value = item;
    };
    const handleSelect = (item: IGroupItem) => {
      destroyPopoverInstance(false);
      if (activeId.value === item.id) return;
      activeId.value = item.id;
      activeItem.value = item;
      activeItem.value.fatherName = activeGroup.value.name;
      handleChange(item.id);
    };

    const handleClear = () => {
      activeId.value = '';
      activeItem.value = null;
      activeGroupId.value = '';
      activeGroup.value = null;
      destroyPopoverInstance(false);
      emit('clear');
    };
    const handleChange = (v: string) => {
      emit('change', v);
    };

    return {
      isShow,
      activeItem,
      selectWapRef,
      selectPanelRef,
      activeGroupId,
      activeId,
      keyword,
      activeList,
      filterList,
      handleSelect,
      handleGroupMouseenter,
      handleKeywordChange,
      handleClear,
      t,
    };
  },
  render() {
    return (
      <div class={['group-select-component', { 'is-readonly': this.readonly }]}>
        <Popover
          ref='selectWapRef'
          width={480}
          extCls='group-select-component-popover'
          v-slots={{
            default: (
              <div
                class={['select-wrap', { 'is-focus': this.isShow }, { 'is-hover': !this.readonly }]}
                data-set='select-wrap'
              >
                <div class='select-name'>
                  {this.activeItem?.name ? (
                    <span class='name'>
                      {this.activeItem.name}
                      <span class='father-name'>（{this.activeItem?.fatherName || ''}）</span>
                    </span>
                  ) : (
                    <span class='placeholder'>{this.placeholder}</span>
                  )}
                </div>
                {!this.readonly && (
                  <span
                    class='icon-monitor sel-icon icon-mc-close-fill'
                    onClick={e => {
                      e.stopPropagation();
                      this.handleClear();
                    }}
                  />
                )}
                <span
                  class={['icon-monitor', 'sel-icon', 'icon-arrow-down']}
                  onClick={e => e.stopPropagation()}
                />
              </div>
            ),
            content: (
              <div ref='selectPanelRef'>
                <div class='group-select-panel'>
                  <Input
                    class='panel-search'
                    v-model={this.keyword}
                    v-slots={{
                      prefix: (
                        <Search
                          width={14}
                          height={14}
                        />
                      ),
                    }}
                    behavior='simplicity'
                    placeholder={this.t('输入关键字')}
                    prefixIcon='bk-icon icon-search'
                    onInput={this.handleKeywordChange}
                  />
                  {this.filterList.length > 0 ? (
                    <div class='panel-list'>
                      {this.filterList.length > 0 && (
                        <ul class='panel-item'>
                          {this.filterList.map(item => (
                            <li
                              key={item.id}
                              class={['list-item', { 'item-active': item.id === this.activeGroupId }]}
                              onMouseenter={() => this.handleGroupMouseenter(item)}
                            >
                              {item.name}
                              <i class='icon-monitor icon-arrow-right arrow-icon' />
                            </li>
                          ))}
                        </ul>
                      )}
                      {this.activeList.length > 0 && (
                        <ul class='panel-item child-item'>
                          {this.activeList.map(
                            item =>
                              item.name.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) && (
                                <li
                                  key={item.id}
                                  class={['list-item', { 'item-active': item.id === this.activeId }]}
                                  onClick={() => this.handleSelect(item)}
                                >
                                  {item.name.slice(
                                    0,
                                    item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase())
                                  )}
                                  <span style='color: #FF9C00'>
                                    {item.name.slice(
                                      item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()),
                                      item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) +
                                        this.keyword.length
                                    )}
                                  </span>
                                  {item.name.slice(
                                    item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) +
                                      this.keyword.length,
                                    item.name.length
                                  )}
                                </li>
                              )
                          )}
                        </ul>
                      )}
                    </div>
                  ) : (
                    <div class='panel-list'>
                      <div style='width: 100%;'>
                        <Exception
                          class='exception-wrap-item exception-part'
                          description={this.t('暂无数据')}
                          scene='part'
                          type='empty'
                        >
                          {' '}
                        </Exception>
                      </div>
                    </div>
                  )}
                  {this.$slots.extension && <div class='select-extension'>{this.$slots.extension}</div>}
                </div>
              </div>
            ),
          }}
          arrow={false}
          boundary='window'
          placement='bottom'
          theme='light common-monitor'
          trigger='click'
        />
      </div>
    );
  },
});
