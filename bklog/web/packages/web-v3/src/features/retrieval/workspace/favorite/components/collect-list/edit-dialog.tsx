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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useRetrieveStore } from '@/app/state/domains/retrieve-store';


import {
  Input as TInput,
  Textarea as TTextarea,
  Dialog as TDialog,
  Form as TForm,
  FormItem as TFormItem,
  Select as TSelect,
  Loading as TLoading,
} from 'tdesign-vue-next';
import type { FormInstanceFunctions } from 'tdesign-vue-next';
import { asDictionary } from '@/shared/utils/typed-record';

import { computed, defineComponent, ref } from 'vue';

import useLocale from '@/shared/composables/use-locale';


import { useFavorite } from '../../hooks/use-favorite';
import { IFavoriteItem, IGroupItem } from '../../types/index';
import { getGroupNameRules } from '../../utils/index';
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
  emits: ['cancel', 'refresh-group', 'refreshGroup'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const formRef = ref<FormInstanceFunctions | null>(null);
    const groupPopupVisible = ref(false);
    const store = useApplicationStore();
    /** 当前空间id */
    const spaceUid = computed(() => store.spaceUid);
    const isUnionSearch = computed(() => props.data.index_set_type === 'union');
    const groupNameMap = asDictionary({
      unknown: t('未分组'),
      private: t('个人收藏'),
    });

    const groupList = ref<Array<{ id: number; name: string; group_type: string }>>([]);
    const favoriteData = ref<IFavoriteItem>({ display_fields: [] });
    // 可见状态为公共的时候显示的收藏组
    const publicGroupList = ref<Array<{ id: number; name: string; group_type: string }>>([]);
    const isClickFavoriteEdit = ref(false);
    const isDisableSelect = ref(false);
    const loading = ref(false);

    // 使用自定义 hook 管理状态
    const { getFavoriteData, requestGroupList, handleUpdateFavorite } = useFavorite();

    /** 获取组列表 */
    const handleRequestGroupList = async () => {
      return requestGroupList(spaceUid.value, (res) => {
        groupList.value = res.data.map((item: { id: number; group_type: string; name: string }) => ({
          ...item,
          name: groupNameMap[item.group_type] ?? item.name,
        }));
        const len = groupList.value.length;
        publicGroupList.value = groupList.value.slice(1, len);
      });
    };

    /** 当前选中分组的favorites */
    const currentGroupFavorite = computed(() => {
      const favorites = props.favoriteList.find((item) => item.group_id === props.data.group_id)?.favorites || [];
      return favorites.filter((item) => item.favorite_id !== props.data.favorite_id);
    });
    /** 分组名的规则 */
    const ruleData = computed(() => getGroupNameRules(currentGroupFavorite.value, 'name'));

    /** 根据visible_type 展示对应的分组名 */
    const showGroupList = computed(() => {
      return favoriteData.value.visible_type === 'public' ? publicGroupList.value : groupList.value;
    });
    const indexItem = computed(() => store.indexItem);

    const handleCancel = () => {
      emit('cancel', !props.isShow);
    };
    const currentParamsValue = computed(() => {
      if (!isClickFavoriteEdit.value) return favoriteData.value;
      const merged = Object.assign({}, favoriteData.value, indexItem.value);
      // 场景化模式：使用 retrieveParams 中已转换的 table_id_conditions 和 scene_filter_values 覆盖
      if (store.isSceneMode) {
        const { table_id_conditions, scene_filter_values } = store.retrieveParams as Pick<
          IFavoriteItem,
          'table_id_conditions' | 'scene_filter_values'
        >;
        Object.assign(merged, { table_id_conditions, scene_filter_values });
      }
      return merged;
    });

    /** 修改收藏 */
    const updateFavorite = (item: IFavoriteItem) => {
      handleUpdateFavorite(item, (data) => {
        emit('refresh-group', data);
        handleCancel();
      });
    };

    const handleSubmitFormData = async () => {
      if ((await formRef.value?.validate()) === true) updateFavorite(currentParamsValue.value);
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
        await getFavoriteData(props.data.id!, favoriteData.value);
        await handleRequestGroupList();
        loading.value = false;
        isDisableSelect.value = favoriteData.value.visible_type === 'private';
      }
    };
    /** 展示的索引集/场景名，场景模式下显示场景名，索引集模式下显示索引集名 */
    const indexSetName = () => {
      const data = favoriteData.value;
      if (data.source_type === 'scene') {
        // 场景化收藏：从 sceneConfigList 中查找场景名称
        const sceneConfigs = useRetrieveStore().sceneConfigList ?? [];
        const sceneConfig = sceneConfigs.find((s: { type: string | undefined }) => s.type === data.scene_id);
        return sceneConfig?.label ?? data.scene_id ?? '';
      }
      const { index_set_name: indexSetName, index_set_names: indexSetNames } = data;
      return !isUnionSearch.value ? indexSetName : (indexSetNames || []).join(',');
    };

    /** 成功添加分组 */
    const handleAddSubmit = (id: number) => {
      handleRefreshGroup();
      favoriteData.value.group_id = id;
      groupPopupVisible.value = false;
    };

    return () => (
      <TDialog
        width={640}
        class='favorite-edit-dialog'
        attach='body'
        confirmBtn={t('保存')}
        header={t('编辑收藏')}
        visible={props.isShow}
        onClose={handleCancel}
        onConfirm={handleSubmitFormData}
        onOpened={() => handleValueChange(true)}
      >
        <TLoading loading={loading.value}>
          <TForm
            ref={formRef}
            labelAlign='top'
            {...{
              ...{
                data: favoriteData.value,
                rules: ruleData.value,
              },
            }}
          >
            <TFormItem label={t('收藏名称')} name='name' requiredMark={true}>
              <TInput
                value={favoriteData.value.name}
                onChange={(value) => (favoriteData.value.name = String(value ?? ''))}
              ></TInput>
            </TFormItem>
            <TFormItem label={t('所属分组')} requiredMark={true}>
              <TSelect
                panelBottomContent={() => (
                  <div style={{ cursor: 'pointer' }}>
                    <AddGroup rules={ruleData.value} onSubmit={(id) => handleAddSubmit(id)} />
                  </div>
                )}
                popupVisible={groupPopupVisible.value}
                onPopupVisibleChange={(value) => (groupPopupVisible.value = value)}
                clearable={false}
                filterable={true}
                value={favoriteData.value.group_id}
                options={showGroupList.value.map((item) => ({ ...item, value: item.id, label: item.name }))}
                onChange={(value) => {
                  if (typeof value === 'number' || value === undefined) favoriteData.value.group_id = value;
                }}
              ></TSelect>
            </TFormItem>
            <TFormItem label={favoriteData.value.source_type === 'scene' ? t('场景') : t('索引集')}>
              <TInput disabled={true} value={indexSetName()}></TInput>
            </TFormItem>
            <TFormItem label={t('查询语句')}>
              <TTextarea disabled={true} value={favoriteData.value.query_string}></TTextarea>
            </TFormItem>
          </TForm>
        </TLoading>
      </TDialog>
    );
  },
});
