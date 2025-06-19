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
import useStore from '../../hooks/use-store';
import UserConfigMixin from '../../mixins/userStoreConfig';
import { SPACE_TYPE_MAP } from '../../store/constant';
import './list.scss';

const userConfigMixin = new UserConfigMixin();

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
}

export type ThemeType = 'dark' | 'light';

const DEFAULT_BIZ_ID = 'DEFAULT_BIZ_ID';

export default defineComponent({
  name: 'BizList',
  props: {
    checked: {
      type: [Number, String],
      default: undefined,
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
  },
  setup(props, { emit }) {
    // console.log('props.checked', props.checked);
    const store = useStore();
    const defaultSpace = ref<IListItem | null>(null);
    const setDefaultBizIdLoading = ref(false);
    const isSetBizIdDefault = ref(true);

    const defaultBizId = computed(() => store.getters.defaultBizId);
    const defaultBizIdApiId = computed(() => store.getters.defaultBizIdApiId);
    // 获取当前用户的配置id
    const getUserConfigId = () => {
      userConfigMixin
        .handleGetUserConfig(DEFAULT_BIZ_ID)
        .then((res: number) => {
          if (res) {
            store.commit('SET_APP_STATE', {
              defaultBizIdApiId: userConfigMixin.storeId,
            });
          }
        })
        .catch(e => {
          console.log(e);
        });
    };
    
    // 默认id处理
    const handleDefaultId = async () => {
      setDefaultBizIdLoading.value = true;
      const bizId = isSetBizIdDefault.value ? Number(defaultSpace.value?.id) : 'undefined';
      userConfigMixin
        .handleSetUserConfig(DEFAULT_BIZ_ID, `${bizId}`, defaultBizIdApiId.value || 0)
        .then(result => {
          if (result) {
            store.commit('SET_APP_STATE', {
              defaultBizId: bizId,
            });
          }
        })
        .catch(e => {
          console.log(e);
        })
        .finally(() => {
          setDefaultBizIdLoading.value = false;
          defaultSpace.value = null;
        });
    };

    // 打开弹窗
    const handleDefaultBizIdDialog = (e: MouseEvent, data: IListItem, isSetDefault: boolean) => {
      e.stopPropagation();
      emit('handleClickOutSide');  /* 关闭下拉框 */
      defaultSpace.value = null;
      setTimeout(() => {
        defaultSpace.value = data;
        isSetBizIdDefault.value = isSetDefault;
      });
    };

    // 点击菜单项时调用该方法
    const handleSelected = (item: IListItem, type = 'general') => {
      emit('handleClickMenuItem', item, type);
    };

    // 初始化
    if (!defaultBizIdApiId.value) {
      getUserConfigId();
    }

    return () => (
      <div class={['biz-list-wrap', props.theme]}>
        {props.list.length ? (
          props.list.map((item, i) => (
            <div
              key={item.id || item.name + i}
              class={['list-group', props.theme, { 'no-name': !item.name }]}
            >
              <div
                key={item.id || i}
                class={['list-item', props.theme, { checked: item.space_uid === props.checked }]}
                onClick={() => handleSelected(item, 'general')}
              >
                <span class='list-item-left'>
                  <span class='list-item-name'>{item.name}</span>
                  <span class={['list-item-id', props.theme]}>
                    ({item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code})
                  </span>
                  {props.canSetDefaultSpace && defaultBizId.value && Number(defaultBizId.value) === item.id && (
                    <span class='item-default-icon'>
                      <span class='item-default-text'>默认</span>
                    </span>
                  )}
                </span>
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
          ))
        ) : (
          <bk-exception
            class='no-data'
            scene='part'
            type='search-empty'
          />
        )}
        <bk-dialog
          width={480}
          ext-cls='confirm-dialog__set-default'
          footer-position='center'
          mask-close={false}
          value={!!defaultSpace.value}
          transfer
          onUpdate:modelValue={val => {
            if (!val) {
              defaultSpace.value = null;
            }
          }}
        >
          <div class='confirm-dialog__hd'>
            {isSetBizIdDefault.value ? '是否将该业务设为默认业务？' : '是否取消默认业务？'}
          </div>
          <div class='confirm-dialog__bd'>
            业务名称：<span class='confirm-dialog__bd-name'>{defaultSpace.value?.name || ''}</span>
          </div>
          <div class='confirm-dialog__ft'>
            {isSetBizIdDefault.value
              ? '设为默认后，每次进入监控平台将会默认选中该业务'
              : '取消默认业务后，每次进入监控平台将会默认选中最近使用的业务而非当前默认业务'}
          </div>
          <div slot='footer'>
            <bk-button
              class='btn-confirm'
              loading={setDefaultBizIdLoading.value}
              theme='primary'
              onClick={handleDefaultId}
            >
              确认
            </bk-button>
            <bk-button
              class='btn-cancel'
              onClick={() => {
                defaultSpace.value = null;
              }}
            >
              取消
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  },
});
