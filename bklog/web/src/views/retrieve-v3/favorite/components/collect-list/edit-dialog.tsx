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

import { computed, defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useFavorite } from '../../hooks/use-favorite';
import { IFavoriteItem, IGroupItem } from '../../types';
import { getGroupNameRules } from '../../utils';
import AddGroup from './add-group';

import './edit-dialog.scss';

export default defineComponent({
  name: 'EditDialog',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    data: {
      type: Object as () => IFavoriteItem,
      default: () => ({}),
    },
    activeFavoriteID: {
      type: Number,
    },
    favoriteList: {
      type: Array as () => IGroupItem[],
      default: () => [],
    },
  },
  emits: ['cancel', 'refresh-group'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const formRef = ref(null);
    const selectRef = ref(null);
    const store = useStore();
    /** 当前空间id */
    const spaceUid = computed(() => store.state.spaceUid);
    const isUnionSearch = computed(() => props.data.index_set_type === 'union');
    const groupNameMap = {
      unknown: t('未分组'),
      private: t('个人收藏'),
    };

    const groupList = ref([]);
    const favoriteData = ref<IFavoriteItem>({});
    // 可见状态为公共的时候显示的收藏组
    const publicGroupList = ref([]);
    const isClickFavoriteEdit = ref(false);
    const isDisableSelect = ref(false);
    const loading = ref(false);

    // 使用自定义 hook 管理状态
    const { getFavoriteData, requestGroupList, handleUpdateFavorite } = useFavorite();

    /** 获取组列表 */
    const handleRequestGroupList = async () => {
      requestGroupList(spaceUid.value, res => {
        groupList.value = res.data.map(item => ({
          ...item,
          name: groupNameMap[item.group_type] ?? item.name,
        }));
        const len = groupList.value.length;
        publicGroupList.value = groupList.value.slice(1, len);
      });
    };

    /** 当前选中分组的favorites */
    const currentGroupFavorite = computed(() => {
      const favorites = props.favoriteList.find(item => item.group_id === props.data.group_id)?.favorites || [];
      return favorites.filter(item => item.favorite_id !== props.data.favorite_id);
    });
    /** 分组名的规则 */
    const ruleData = computed(() => getGroupNameRules(currentGroupFavorite.value, 'name'));

    /** 根据visible_type 展示对应的分组名 */
    const showGroupList = computed(() => {
      return favoriteData.value.visible_type === 'public' ? publicGroupList.value : groupList.value;
    });
    const indexItem = computed(() => store.state.indexItem);

    const handleCancel = () => {
      emit('cancel', !props.isShow);
    };
    const currentParamsValue = computed(() => {
      return isClickFavoriteEdit.value ? Object.assign({}, favoriteData.value, indexItem.value) : favoriteData.value;
    });

    /** 修改收藏 */
    const updateFavorite = (item: IFavoriteItem) => {
      handleUpdateFavorite(item, data => {
        emit('refresh-group', data);
        handleCancel();
      });
    };

    const handleSubmitFormData = () => {
      formRef.value.validate().then(() => {
        updateFavorite(currentParamsValue.value);
      });
    };
    /** 刷新 */
    const handleRefreshGroup = () => {
      handleRequestGroupList();
    };
    /** 弹框value值改变时的handle */
    const handleValueChange = async (value: boolean) => {
      if (value) {
        loading.value = true;
        isClickFavoriteEdit.value = props.data.id === props.activeFavoriteID;
        await getFavoriteData(props.data.id, favoriteData.value);
        await handleRequestGroupList();
        loading.value = false;
        isDisableSelect.value = favoriteData.value.visible_type === 'private';
      }
    };
    /** 展示的索引集，当为多索引集时，展示index_set_names字段，反之展示index_set_name */
    const indexSetName = () => {
      const { index_set_name: indexSetName, index_set_names: indexSetNames } = favoriteData.value;
      return !isUnionSearch.value ? indexSetName : (indexSetNames || []).join(',');
    };

    /** 成功添加分组 */
    const handleAddSubmit = (id: number) => {
      handleRefreshGroup();
      favoriteData.value.group_id = id;
      selectRef.value?.close();
    };

    return () => (
      <bk-dialog
        width={640}
        ext-cls='add-collect-dialog'
        auto-close={false}
        header-position='left'
        ok-text={t('保存')}
        render-directive={'if'}
        title={t('编辑收藏')}
        value={props.isShow}
        on-cancel={handleCancel}
        on-confirm={handleSubmitFormData}
        on-value-change={handleValueChange}
      >
        <bk-form
          ref={formRef}
          v-bkloading={{ isLoading: loading.value }}
          form-type='vertical'
          {...{
            props: {
              model: favoriteData.value,
              rules: ruleData.value,
            },
          }}
        >
          <bk-form-item
            label={t('收藏名称')}
            property='name'
            required={true}
          >
            <bk-input
              value={favoriteData.value.name}
              onInput={val => (favoriteData.value.name = val)}
            ></bk-input>
          </bk-form-item>
          <bk-form-item
            label={t('所属分组')}
            required={true}
          >
            <bk-select
              ref={selectRef}
              clearable={false}
              searchable={true}
              value={favoriteData.value.group_id}
              onChange={val => (favoriteData.value.group_id = val)}
            >
              {showGroupList.value.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                ></bk-option>
              ))}
              <div
                style={{ cursor: 'pointer' }}
                slot='extension'
              >
                <AddGroup
                  rules={ruleData.value}
                  on-submit={id => handleAddSubmit(id)}
                />
              </div>
            </bk-select>
          </bk-form-item>
          <bk-form-item label={t('索引集')}>
            <bk-input
              disabled={true}
              value={indexSetName()}
            ></bk-input>
          </bk-form-item>
          <bk-form-item label={t('查询语句')}>
            <bk-input
              disabled={true}
              type='textarea'
              value={favoriteData.value.query_string}
            ></bk-input>
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
  },
});
