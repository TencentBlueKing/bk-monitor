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
import { type PropType, defineComponent, reactive, ref, watch } from 'vue';

import { TagInput } from 'bkui-vue';
import { listUsersUser } from 'monitor-api/modules/model';
import { debounce, random } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import './member-selector.scss';

export default defineComponent({
  name: 'MemberSelector',
  props: {
    value: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    api: {
      type: String,
      default: '',
    },
    userGroups: {
      type: Array,
      default: () => [],
    },
    useGroup: {
      type: Boolean,
      default: false,
    },
    onChange: {
      type: Function as PropType<(v: string[]) => void>,
      default: () => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    const localValue = ref([]);
    const lcoalList = ref([]);
    const params = reactive({
      app_code: 'bk-magicbox',
      page: 1,
      page_size: 20,
      fuzzy_lookups: '',
    });
    const trigger = ref<'focus' | 'search'>('focus');
    const groupsMap = new Map();
    const usersMap = new Map();
    const key = ref(random(8));
    const debounceHandleInput = debounce(handleInput, 300, false);
    init();
    watch(
      () => props.userGroups,
      userGroups => {
        setUserGroups(userGroups);
      },
      { deep: true }
    );
    watch(
      () => props.value,
      v => {
        localValue.value = v;
        setUsersMap(localValue.value);
      },
      {
        immediate: true,
      }
    );
    function init() {
      setUserGroups(props.userGroups);
    }
    /**
     * @description 回填时获取用户信息
     * @param users
     */
    async function setUsersMap(users: string[]) {
      const noData = [];
      users.forEach(u => {
        if (!groupsMap.has(u) && !usersMap.has(u)) {
          noData.push(u);
        }
      });
      const curParams = JSON.parse(JSON.stringify(params));
      curParams.fuzzy_lookups = noData.join(',');
      curParams.page = 1;
      getUserList(curParams).then(data => {
        (data as any[]).forEach(item => {
          const obj = {
            ...item,
            idd: item.id,
            id: item.username,
            name: item.display_name,
          };
          usersMap.set(obj.id, obj);
          key.value = random(8);
        });
      });
    }
    /**
     * @description 获取用户组数据
     * @param userGroups
     */
    function setUserGroups(userGroups) {
      if (userGroups.length) {
        userGroups.forEach(item => {
          if (item.id === 'group') {
            const children = item.children.map(c => {
              const obj = {
                ...c,
                name: c.display_name,
              };
              groupsMap.set(obj.id, obj);
              return obj;
            });
            lcoalList.value = children;
          }
        });
      }
    }
    /**
     * @description 获取用户下拉列表
     * @param users
     */
    function setUsers(users) {
      lcoalList.value = users.map(item => {
        const obj = {
          ...item,
          idd: item.id,
          id: item.username,
          name: item.display_name,
        };
        usersMap.set(obj.id, obj);
        return obj;
      });
    }
    /**
     * @description 输入
     * @param v
     */
    async function handleInput(v) {
      // trigger.value = 'search';
      params.fuzzy_lookups = v;
      const data = await getUserList(params);
      setUsers(data);
    }
    function handleFocus() {
      // console.log(v);
    }
    function handleBlur() {
      key.value = random(8);
      setUserGroups(props.userGroups);
    }

    async function getUserList(params: Record<string, any>) {
      return await listUsersUser(params, {
        needCancel: true,
      })
        .then(res => res?.results || [])
        .catch(() => []);
    }

    function handleChange(v) {
      localValue.value = v;
      props.onChange(localValue.value);
    }

    function tpl(node) {
      return (
        <div class='user-item-wrap'>
          {(() => {
            if (node.type === 'group') {
              return <span class='icon-monitor icon-mc-user-group' />;
            }
            if (
              node.logo &&
              typeof node.logo === 'string' &&
              /^(https?|HTTPS?):\/\/[^\s/$.?#].[^\s]*$/.test(node.logo)
            ) {
              return (
                <img
                  class='user-logo'
                  alt=''
                  src={node.logo}
                />
              );
            }
            return <span class='icon-monitor icon-mc-user-one' />;
          })()}
          <span class='user-name'>{node.type === 'group' ? node.name : `${node.id} (${node.name})`}</span>
        </div>
      );
    }
    function tagTpl(node) {
      const obj = groupsMap.get(node.id) || usersMap.get(node.id);
      if (!obj) return undefined;
      return (
        <div class='user-item-tag'>
          {(() => {
            if (obj.type === 'group') {
              return <span class='icon-monitor icon-mc-user-group' />;
            }
            if (obj.logo && typeof obj.logo === 'string' && /^(https?|HTTPS?):\/\/[^\s/$.?#].[^\s]*$/.test(obj.logo)) {
              return (
                <img
                  class='user-logo'
                  alt=''
                  src={obj.logo}
                />
              );
            }
            return <span class='icon-monitor icon-mc-user-one' />;
          })()}
          <span class='user-name'>{obj.type === 'group' ? obj.name : `${obj.id} (${obj.name})`}</span>
        </div>
      );
    }
    return {
      lcoalList,
      localValue,
      usersMap,
      key,
      trigger,
      t,
      tpl,
      tagTpl,
      handleChange,
      debounceHandleInput,
      handleFocus,
      handleBlur,
    };
  },
  render() {
    return (
      <TagInput
        key={this.key}
        class='member-selector-component'
        popoverProps={{
          extCls: 'member-selector-component-tag-input-pop',
        }}
        allowCreate={true}
        allowNextFocus={true}
        contentWidth={320}
        filterCallback={(_filterVal, _filterKey, data) => data}
        isAsyncList={true}
        list={this.lcoalList}
        modelValue={this.localValue}
        placeholder={this.t('选择通知对象')}
        tagTpl={this.tagTpl}
        tpl={this.tpl}
        trigger={this.trigger}
        useGroup={this.useGroup}
        onBlur={this.handleBlur}
        onFocus={this.handleFocus}
        onInput={this.debounceHandleInput}
        onUpdate:modelValue={v => this.handleChange(v)}
      />
    );
  },
});
