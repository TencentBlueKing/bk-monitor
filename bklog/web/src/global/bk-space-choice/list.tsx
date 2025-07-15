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
import { defineComponent, ref, computed } from 'vue';
import { RecycleScroller } from 'vue-virtual-scroller';

import useStore from '../../hooks/use-store';
import { SPACE_TYPE_MAP } from '../../store/constant';

import './list.scss';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';

export enum ETagsType {
  BCS = 'bcs',
  BKCC = 'bkcc',
  BKCI = 'bkci',
  BKSAAS = 'bksaas',
  MONITOR = 'monitor',
}

export interface ITagsItem {
  id: string;
  name: string;
  type: ETagsType;
}

export interface IListItem {
  id: number | string;
  name: string;
  space_code?: string;
  space_type_id?: string;
  space_id?: string;
  tags?: ITagsItem[];
  children?: IListItem[];
  is_hidden_tag?: boolean;
  space_uid?: string;
  type?: string;
  commonListLength?: number; // 用于标识常用业务列表的长度
}

export type ThemeType = 'dark' | 'light';

// const DEFAULT_BIZ_ID = 'DEFAULT_BIZ_ID';

export default defineComponent({
  name: 'BizList',
  props: {
    checked: {
      type: [Number, String],
      default: undefined,
      required: true, // 强制要求传递
    },
    canSetDefaultSpace: {
      type: Boolean,
      default: true,
    },
    list: {
      type: Array as () => IListItem[],
      default: () => [],
    },
    theme: {
      type: String as () => ThemeType,
      default: 'dark',
      validator: (val: string) => ['dark', 'light'].includes(val),
    },
    commonList: {
      type: Array as () => IListItem[],
      default: () => [],
    },
  },
  emits: ['handleClickOutSide', 'handleClickMenuItem', 'openDialog'],
  setup(props, { emit }) {
    const store = useStore();
    const defaultSpace = ref<IListItem | null>(null); // 当前弹窗中选中的业务
    const isSetBizIdDefault = ref(true); // 设为默认or取消默认
    const defaultBizId = computed(() => store.getters.defaultBizId); // 当前默认业务ID
    // const defaultBizIdApiId = computed(() => store.getters.defaultBizIdApiId); // 当前默认业务的API ID

    // 获取用户配置的默认业务ID
    // const getUserConfigId = () => {
    //   userConfigMixin
    //     .handleGetUserConfig(DEFAULT_BIZ_ID)
    //     .then((res: number) => {
    //       if (res) {
    //         store.commit('SET_APP_STATE', {
    //           defaultBizIdApiId: userConfigMixin.storeId,
    //         });
    //       }
    //     })
    //     .catch(e => {
    //       console.log(e);
    //     });
    // };

    // 点击设置/取消默认
    const handleDefaultBizIdDialog = (e: MouseEvent, data: IListItem, isSetDefault: boolean) => {
      e.stopPropagation();
      defaultSpace.value = null;
      setTimeout(() => {
        defaultSpace.value = data;
        isSetBizIdDefault.value = isSetDefault;
        emit('openDialog', defaultSpace.value, isSetBizIdDefault.value); // 打开弹窗
        emit('handleClickOutSide'); // 关闭下拉框
      });
    };

    // 选中业务项时触发
    const handleSelected = (item: IListItem) => {
      emit('handleClickMenuItem', item);
    };

    // 初始化时获取用户配置ID
    // if (!defaultBizIdApiId.value) {
    //   getUserConfigId();
    // }

    // 渲染函数
    return () => (
      <div class={['biz-list-wrap', props.theme]}>
        {props.list.length > 0 ? (
          // 滚动加载
          <RecycleScroller
            class={['list-scroller']}
            scopedSlots={{
              default: ({ item, index }: { item: IListItem; index: number }) => (
                <div
                  key={item.id || item.name + index}
                  class={['list-group', props.theme]}
                >
                  <div
                    key={item.id || index}
                    class={[
                      item.type === 'group-title' ? 'list-group-title' : 'list-item',
                      props.theme,
                      { checked: item.space_uid === props.checked },
                      props.commonList.length > 0 && index === props.commonList.length ? 'last-common-item' : '',
                    ]}
                    onClick={() => handleSelected(item)}
                  >
                    <span class='list-item-left'>
                      <span class='list-item-name'>{item.name}</span>
                      <span class={['list-item-id', props.theme]}>
                        {/* 显示业务ID或空间ID */}
                        {item.type != 'group-title' ? `(#${item.space_id})` : ''}
                      </span>
                      {/* 如果当前业务是默认业务，显示“默认”标签 */}
                      {props.canSetDefaultSpace && defaultBizId.value && Number(defaultBizId.value) === item.id && (
                        <span class='item-default-icon'>
                          <span class='item-default-text'>默认</span>
                        </span>
                      )}
                    </span>
                    {/* 显示标签 */}
                    {!item.is_hidden_tag && (
                      <span class='list-item-right'>
                        {item.tags?.map?.(tag => (
                          <span
                            key={tag.id}
                            style={{ ...SPACE_TYPE_MAP[tag.id]?.[props.theme] }}
                            class='list-item-tag'
                          >
                            {SPACE_TYPE_MAP[tag.id]?.name}
                          </span>
                        ))}
                      </span>
                    )}
                    {/* 设为默认/取消默认按钮 */}
                    {props.canSetDefaultSpace && (
                      <div class='set-default-button'>
                        {defaultBizId.value && Number(defaultBizId.value) === Number(item.id) ? (
                          <div
                            class={`btn-style-${props.theme} remove`}
                            onClick={e => handleDefaultBizIdDialog(e as MouseEvent, item, false)}
                          >
                            取消默认
                          </div>
                        ) : (
                          <div
                            class={`btn-style-${props.theme}`}
                            onClick={e => handleDefaultBizIdDialog(e as MouseEvent, item, true)}
                          >
                            设为默认
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ),
            }}
            buffer={200} /* 提前加载200px以外的内容 */
            item-size={32}
            items={Array.isArray(props.list) ? props.list : []}
          />
        ) : (
          // 无数据时显示异常提示
          <bk-exception
            style='height: 300px;  display: flex; justify-content: center; align-items: center;'
            scene='part'
            type='search-empty'
          />
        )}
      </div>
    );
  },
});
