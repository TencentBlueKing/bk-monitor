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
import { computed, defineComponent, nextTick, onMounted, PropType, reactive, ref, TransitionGroup, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { listUsersUser } from '@api/modules/model';
import { getReceiver } from '@api/modules/notice_group';
import { Loading, Popover } from 'bkui-vue';
import { debounce, random } from 'lodash';

import './member-select.scss';

interface DateItem {
  id: string;
  type: 'group' | 'user';
  logo?: string;
  display_name?: string;
}

export interface TagItemModel {
  id: string;
  logo?: string;
  display_name?: string;
  username: string;
  type: 'group' | 'user';
}

type FilterMethod = (list: TagItemModel[], val: string) => TagItemModel[];

export default defineComponent({
  name: 'MemberSelect',
  props: {
    showType: {
      type: String as PropType<'avatar' | 'tag'>,
      default: 'avatar'
    },
    modelValue: {
      type: Array as PropType<DateItem[]>,
      default: () => []
    },
    filterMethod: {
      type: Function as PropType<FilterMethod>,
      default: undefined
    },
    hasDefaultGroup: {
      type: Boolean,
      default: false
    },
    defaultGroup: {
      type: Array as PropType<TagItemModel[]>,
      default: () => []
    },
    placeholder: {
      type: String,
      default: ''
    },
    tagTpl: {
      type: Function as PropType<(item: TagItemModel, index: number) => JSX.Element | JSX.Element[]>,
      default: undefined
    }
  },
  emits: ['update:modelValue', 'change', 'selectEnd', 'drop'],
  setup(props, { emit }) {
    const { t } = useI18n();
    // ------------------ 用户数据----------------------
    const memberSelectRef = ref();
    const loading = ref(false);
    /** 用户和用户组列表  */
    const userAndGroupList = reactive<{ group: TagItemModel[]; user: TagItemModel[] }>({
      group: [],
      user: []
    });
    /** 映射表，用于通过唯一值获取详情 */
    const userAndGroupMap = reactive(new Map<string, TagItemModel>());
    /** 用户搜索关键字映射表，用于接口缓存 */
    const userSearchMap = new Map();
    const debounceGetUserList = debounce(getUserList, 300);
    watch(
      () => props.defaultGroup,
      val => {
        setGroup(val);
      },
      {
        immediate: true
      }
    );
    /** 获取用户组 */
    function getReceiverGroup() {
      getReceiver().then(data => {
        setGroup(data);
      });
    }
    /**
     * 用户组格式转化以及添加映射表
     * @param group 用户组
     */
    function setGroup(group) {
      const children = group.find(item => item.id === 'group')?.children || [];
      userAndGroupList.group = children.map(item => {
        const obj: TagItemModel = {
          id: item.id,
          type: 'group',
          username: item.display_name,
          display_name: item.display_name
        };
        !userAndGroupMap.has(obj.id) && userAndGroupMap.set(obj.id, obj);
        return obj;
      });
    }
    /** 获取用户列表 */
    async function getUserList(keyword = '', page = 1, pageSize = 20) {
      const key = `${keyword}_${page}_${pageSize}`;
      if (userSearchMap.has(key)) {
        setUser(userSearchMap.get(key));
        return;
      }
      loading.value = true;
      listUsersUser(
        {
          app_code: 'bk-magicbox',
          page,
          page_size: pageSize,
          fuzzy_lookups: keyword
        },
        {
          needCancel: true
        }
      )
        .then(res => {
          setUser(res.results);
          userSearchMap.set(key, res.results);
        })
        .finally(() => {
          loading.value = false;
        });
    }
    /**
     * 用户列表格式转化以及添加映射表
     * @param users 用户列表
     */
    function setUser(users) {
      userAndGroupList.user = users.map(item => {
        const obj: TagItemModel = {
          id: item.username,
          type: 'user',
          logo: item.logo,
          username: item.username,
          display_name: item.display_name
        };
        !userAndGroupMap.has(obj.username) && userAndGroupMap.set(obj.username, obj);
        return obj;
      });
    }

    /** 编辑态下把用户添加到映射表 */
    function setUserMap(tags: DateItem[]) {
      tags.forEach(tag => {
        const item: TagItemModel = {
          ...tag,
          username: tag.id
        };
        if (item.type === 'user' && !userAndGroupMap.has(item.username)) {
          userAndGroupMap.set(item.username, item);
        }
      });
    }

    // ----------------标签---------------------
    const tags = reactive<DateItem[]>([]);
    watch(
      () => props.modelValue,
      val => {
        tags.splice(0, tags.length, ...val);
        setUserMap(tags);
      },
      { immediate: true, deep: true }
    );

    /** 点击容器，把输入框显示在最后 */
    function handleWrapClick() {
      !popoverShow.value && debounceGetUserList(inputValue.value);
      resetInputPosition(tags.length);
    }
    /** 再点击的Tag后增加输入框 */
    function handleTagClick(e: Event, index: number) {
      e.stopPropagation();
      resetInputPosition(index + 1);
      debounceGetUserList();
    }
    /** 删除tag */
    function handleCloseTag(e: Event, index: number) {
      e.stopPropagation();
      tags.splice(index, 1);
      handleEmitData();
      emitSelectEnd();
    }
    /** 渲染用户logo */
    function renderUserLogo(tag: TagItemModel) {
      if (tag?.type === 'group') {
        return <span class='icon-monitor icon-mc-user-group'></span>;
      }
      if (tag?.logo && typeof tag.logo === 'string' && /^(https?|HTTPS?):\/\/[^\s/$.?#].[^\s]*$/.test(tag.logo)) {
        return (
          <img
            class='user-logo'
            src={tag.logo}
            alt=''
          ></img>
        );
      }
      return <span class='icon-monitor icon-mc-user-one'></span>;
    }
    /** 根据不同的显示方式类型渲染tag */
    function renderTagItemContent(name: string, ind: number) {
      const tag = userAndGroupMap.get(name);
      if (props.tagTpl) return props.tagTpl(tag, ind);
      if (props.showType === 'avatar') {
        return [renderUserLogo(tag), <span class='user-name'>{tag?.username}</span>];
      }
      return [
        <span class='icon-monitor icon-mc-tuozhuai'></span>,
        <span class='user-name'>{tag?.username}</span>,
        <span
          class='icon-monitor icon-mc-close'
          onClick={e => handleCloseTag(e, ind)}
        ></span>
      ];
    }

    /** 唯一拖拽id */
    const dragUid = random(8, true);
    /** 标签拖拽 */
    function handleDragstart(e: DragEvent, index: number) {
      e.dataTransfer.setData('index', String(index));
      e.dataTransfer.setData('uid', String(dragUid));
      resetInputPosition(-1);
    }
    function handleDragover(e: DragEvent) {
      e.preventDefault();
    }
    function handleDrop(e: DragEvent, index: number) {
      const uid = Number(e.dataTransfer.getData('uid'));
      if (uid !== dragUid) return;
      const startIndex = Number(e.dataTransfer.getData('index'));
      const tag = tags[startIndex];
      tags.splice(startIndex, 1);
      tags.splice(index, 0, tag);
      handleEmitData();
      emit('drop', startIndex, index);
    }

    // --------------输入框--------------
    const inputRef = ref();
    const textTestRef = ref();
    /** 输入框的索引 */
    const inputIndex = ref(-1);
    /** 输入框的值 */
    const inputValue = ref('');
    const inputWidth = ref(8);
    /**
     * 重置输入框显示位置
     * @param index 需要显示的位置
     */
    function resetInputPosition(index) {
      inputIndex.value = index;
      if (index === -1) {
        inputValue.value = '';
        popoverShow.value = false;
        return;
      }
      popoverShow.value = true;
      setInputFocus();
    }
    /** 输入框聚焦 */
    function setInputFocus() {
      nextTick(() => {
        inputRef.value?.focus?.();
      });
    }
    /** 输入框按键事件 */
    function handleInputKeyDown(e: KeyboardEvent) {
      // 如果输入框没有值，特定的按键会有特定的效果
      if (!inputValue.value) {
        if (e.key === 'Backspace' && inputIndex.value > 0) {
          // 删除前面的tag
          tags.splice(inputIndex.value - 1, 1);
          resetInputPosition(inputIndex.value - 1);
          handleEmitData();
        } else if (e.key === 'ArrowLeft' && inputIndex.value > 0) {
          // 输入框向前移动一格
          resetInputPosition(inputIndex.value - 1);
        } else if (e.key === 'ArrowRight' && inputIndex.value < tags.length) {
          // 输入框向后移动一格
          resetInputPosition(inputIndex.value + 1);
        }
      }
    }
    function handleInput(e: Event) {
      inputValue.value = (e.target as HTMLInputElement).value;
      debounceGetUserList(inputValue.value);
      nextTick(() => {
        inputWidth.value = textTestRef.value.offsetWidth;
      });
    }
    function renderInputContent() {
      return (
        <Popover
          trigger='click'
          theme='light'
          extCls='member-select-popover component'
          arrow={false}
          placement='bottom-start'
          is-show={popoverShow.value}
          onAfterHidden={handleAfterHidden}
        >
          {{
            content: () => renderPopoverContent(),
            default: () => (
              <input
                key={`${inputIndex.value}_input`}
                ref='inputRef'
                class='input'
                style={{ width: `${inputWidth.value}px` }}
                value={inputValue.value}
                onClick={e => e.stopPropagation()}
                onInput={handleInput}
                onKeydown={e => handleInputKeyDown(e)}
              />
            )
          }}
        </Popover>
      );
    }

    // ----------------弹窗--------------------
    const popoverShow = ref(false);
    const popoverWrapRef = ref();
    /** 弹窗选择列表 */
    const selectList = computed<TagItemModel[]>(() => {
      if (props.filterMethod) {
        return props.filterMethod([...userAndGroupList.group, ...userAndGroupList.user], inputValue.value);
      }
      return inputValue.value ? userAndGroupList.user : [...userAndGroupList.group, ...userAndGroupList.user];
    });
    function handleAfterHidden({ isShow }) {
      popoverShow.value = isShow;
      resetInputPosition(-1);
      emitSelectEnd();
    }
    /**
     * 选择事件
     * @param item 选择项
     */
    function handleSelect(e: Event, item: TagItemModel) {
      e.stopPropagation();
      inputValue.value = '';
      const index = tags.findIndex(tag => tag.id === item.id);
      if (index === -1) {
        // 新增
        tags.splice(inputIndex.value, 0, { type: item.type, id: item.id });
        resetInputPosition(inputIndex.value + 1);
      } else {
        // 删除
        tags.splice(index, 1);
        if (index < inputIndex.value) {
          resetInputPosition(inputIndex.value - 1);
        } else {
          setInputFocus();
        }
      }
      handleEmitData();
    }
    function renderPopoverContent() {
      return (
        <Loading loading={loading.value}>
          <div
            class='member-select-popover-wrap'
            ref='popoverWrapRef'
          >
            {selectList.value.map(item => (
              <div
                class='select-item'
                onClick={e => handleSelect(e, item)}
              >
                <div class='label-wrap'>
                  {renderUserLogo(item)}
                  <span class='name'>{item.username}</span>
                </div>
                {tags.some(tag => tag.id === item.id) && <span class='icon-monitor icon-mc-check-small'></span>}
              </div>
            ))}
            {!selectList.value.length && (
              <div class='empty-text'>
                <span>{t('无数据')}</span>
              </div>
            )}
          </div>
        </Loading>
      );
    }

    /** 用户每次选择操作都会触发 */
    function handleEmitData() {
      emit('change', tags);
      emit('update:modelValue', tags);
    }

    /** 用户选择操作结束后触发 */
    function emitSelectEnd() {
      emit('selectEnd', tags);
    }

    onMounted(() => {
      !props.hasDefaultGroup && getReceiverGroup();
      debounceGetUserList();
    });

    return {
      t,
      userSearchMap,
      userAndGroupList,
      memberSelectRef,
      tags,
      handleWrapClick,
      handleTagClick,
      renderTagItemContent,
      handleDragstart,
      handleDragover,
      handleDrop,
      inputRef,
      textTestRef,
      inputIndex,
      inputValue,
      inputWidth,
      resetInputPosition,
      handleInputKeyDown,
      renderInputContent,
      popoverShow,
      popoverWrapRef,
      selectList,
      handleSelect
    };
  },
  render() {
    return (
      <div
        ref='memberSelectRef'
        class='member-select-component'
        onClick={this.handleWrapClick}
      >
        <div class='prefix'>{this.$slots.prefix?.()}</div>
        <div class={['member-select-wrapper', `${this.showType}-type`]}>
          {this.tags.length ? (
            <TransitionGroup name={this.showType === 'tag' ? 'flip-list' : ''}>
              {this.tags.map((tag, ind) => (
                <div
                  class='list-item'
                  key={tag.id}
                >
                  {this.inputIndex === 0 && ind === 0 && this.renderInputContent()}
                  <div
                    key={`${tag.id}_value`}
                    class={['tag-item', `${this.showType}-type`]}
                    onClick={e => this.handleTagClick(e, ind)}
                    draggable={this.showType === 'tag'}
                    onDragstart={e => this.handleDragstart(e, ind)}
                    onDragover={e => this.handleDragover(e)}
                    onDrop={e => this.handleDrop(e, ind)}
                  >
                    {this.renderTagItemContent(tag.id, ind)}
                  </div>
                  {this.inputIndex === ind + 1 && this.renderInputContent()}
                </div>
              ))}
            </TransitionGroup>
          ) : (
            [
              this.inputIndex > -1 && this.renderInputContent(),
              this.inputIndex === -1 && <div class='placeholder'>{this.placeholder || this.t('选择')}</div>
            ]
          )}
        </div>
        <span
          class='text-width-test'
          ref='textTestRef'
        >
          {this.inputValue}
        </span>
      </div>
    );
  }
});
