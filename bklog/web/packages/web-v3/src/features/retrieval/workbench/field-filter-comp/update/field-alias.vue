<!--
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
-->

<script setup lang="ts">
import { ServicesInstance } from '@/platform/services';

import { computed, ref, watch } from 'vue';
import {
  Drawer as TDrawer,
  BaseTable as TTable,
  Input as TInput,
  Button as TButton,
  Tooltip as TTooltip,
} from 'tdesign-vue-next';
import type { BaseTableCol } from 'tdesign-vue-next';
import BklogLoading from '@/shared/ui/loading';
import { toWorkerMessage } from '@/shared/lib/worker-message';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import { useRoute } from 'vue-router';
import { overlayRegistry } from '@/shared/global/overlay/overlay-registry.js';
import { Z_INDEX_LAYERS } from '@/shared/global/overlay/z-index-manager.js';

import { RetrieveEvent } from '@/features/retrieval/retrieve-helper';
import useRetrieveEvent from '@/shared/composables/use-retrieve-event';

interface AliasField {
  field_name: string;
  field_type: string;
  query_alias?: string;
  alias_name?: string;
  is_built_in?: boolean;
  is_objectKey?: boolean;
  expand?: boolean;
  aliasErr?: string;
  children?: AliasField[];
  [key: string]: unknown;
}
interface AliasSetting {
  field_name: string;
  query_alias?: string;
  path_type: string;
}

const store = useStore();
const route = useRoute();
const { t } = useLocale();
const emit = defineEmits(['handle-popover-hide', 'handlePopoverHide']);
const showSlider = ref(false);
const drawerZIndex = ref(Z_INDEX_LAYERS.DRAWER);
const sliderLoading = ref(false);
const confirmLoading = ref(false);
const formData = ref<AliasField[]>([]);
const fields = computed<AliasField[]>(() => store.getters.rawFieldList as AliasField[]);
const columns = computed<BaseTableCol[]>(() => [
  { colKey: 'fieldName', title: t('字段名') },
  { colKey: 'alias', title: t('别名') },
]);
const handleOpenSidebar = async () => {
  drawerZIndex.value = overlayRegistry.nextZIndex();
  showSlider.value = true;
  emit('handle-popover-hide');
  addObject();
};

watch(showSlider, (visible) => {
  if (visible) drawerZIndex.value = overlayRegistry.nextZIndex();
});

const { addEvent } = useRetrieveEvent();
addEvent(RetrieveEvent.ALIAS_CONFIG_OPEN, (val) => {
  if (val) {
    handleOpenSidebar();
  }
});
// 提交
const submit = async () => {
  try {
    await checkQueryAlias();
    const aliasSettings = formData.value
      .filter((item) => !item.is_objectKey)
      .reduce<AliasSetting[]>((acc, item) => {
        if (item.field_type !== 'object') {
          acc.push({
            field_name: item.field_name,
            query_alias: item.query_alias,
            path_type: item.field_type,
          });
        } else if (item.children) {
          const childrenFields = item.children.map((child) => ({
            field_name: child.field_name,
            query_alias: child.query_alias,
            path_type: child.field_type,
          }));
          acc.push(...childrenFields);
        }
        return acc;
      }, [])
      .filter((item) => item.query_alias);
    const res = await ServicesInstance.retrieve.updateFieldsAlias({
      params: {
        index_set_id: route.params.indexId,
      },
      data: {
        alias_settings: aliasSettings,
      },
    });

    if (res.code === 0) {
      showSlider.value = false;
      store.dispatch('requestIndexSetFieldInfo');
    }
  } catch (error) {
    console.error('Submit failed:', error);
  }
};
const handleCancel = () => {
  formData.value = [];
  showSlider.value = false;
};
const closeSlider = () => {
  formData.value = [];
};

// 展开对象按钮的回调
const expandObject = (row: AliasField, show: boolean) => {
  row.expand = show;
  const index = formData.value.findIndex((item) => item.field_name === row.field_name);

  if (show) {
    if (index !== -1) {
      formData.value.splice(index + 1, 0, ...(row.children ?? []));
    }
  } else {
    if (index !== -1) {
      const childrenCount = row.children ? row.children.length : 0;
      formData.value.splice(index + 1, childrenCount);
    }
  }
};
const aliasShow = (row: AliasField) => {
  if (row.is_built_in) {
    return true;
  }
  return !row.alias_name;
};
const addObject = () => {
  const deepFields: AliasField[] = structuredClone(
    toWorkerMessage(
      fields.value
        .filter((fields) => fields.field_type !== 'object')
        .map((item) => {
          return {
            ...item,
            aliasErr: '',
          };
        }),
    ),
  );
  const keyFieldList = deepFields.filter((field) => field.field_name.includes('.'));

  const objectFieldMap = new Map<string, AliasField>();
  fields.value.forEach((field) => {
    if (field.field_name.includes('.') || field.field_type === 'object') {
      const fieldNamePrefix = field.field_name.split('.')[0].replace(/^_+|_+$/g, '');
      if (!objectFieldMap.has(fieldNamePrefix)) {
        objectFieldMap.set(fieldNamePrefix, {
          field_name: fieldNamePrefix,
          field_type: 'object',
          is_built_in: true,
          children: undefined,
        });
      }
    }
  });
  keyFieldList.forEach((item) => {
    item.is_objectKey = true;
    const keyFieldPrefix = item.field_name.split('.')[0].replace(/^_+|_+$/g, '');
    const objectField = objectFieldMap.get(keyFieldPrefix);

    if (objectField) {
      if (!objectField.children) {
        objectField.children = [];
      }
      objectField.children.push(item);
    }
  });

  const normalFields = deepFields.filter(
    (field) => field.field_type !== '__virtual__' && !field.field_name.includes('.'),
  );

  // 将对象字段分为有子项和无子项两类
  const objectFields = Array.from(objectFieldMap.values());
  const objectFieldsWithChildren = objectFields.filter((field) => (field.children?.length ?? 0) > 0);
  const objectFieldsWithoutChildren = objectFields.filter((field) => !field.children || field.children.length === 0);

  formData.value = [...objectFieldsWithChildren, ...normalFields, ...objectFieldsWithoutChildren];
};
// 校验别名
const checkQueryAlias = () => {
  return new Promise<void>((resolve, reject) => {
    try {
      let result = true;
      formData.value.forEach((row) => {
        if (!checkQueryAliasItem(row)) {
          result = false;
        }
      });

      if (result) {
        resolve();
      } else {
        console.warn('QueryAlias校验错误');
        reject(result);
      }
    } catch (err) {
      console.warn('QueryAlias校验错误');
      reject(err);
    }
  });
};
const checkQueryAliasItem = (row: AliasField) => {
  const { field_name: fieldName, query_alias: queryAlias } = row;
  if (queryAlias) {
    // 设置了别名
    if (!/^(?!^\d)[\w]+$/gi.test(queryAlias)) {
      row.aliasErr = t('别名只支持【英文、数字、下划线】，并且不能以数字开头');

      return false;
    }
    if (queryAlias === fieldName) {
      row.aliasErr = t('别名与字段名重复');
      return false;
    }
    // if (
    //   globalsData.value.field_built_in.find(
    //     (item) => item.id === queryAlias.toLocaleLowerCase()
    //   )
    // ) {
    //   row.aliasErr = $t("别名不能与内置字段名相同");
    //   return false;
    // }
  }
  row.aliasErr = '';
  return true;
};
defineExpose({
  handleOpenSidebar,
});
</script>
<template>
  <div class="field-alias-v3">
    <div class="bklog-v3 field-alias-title" @click="handleOpenSidebar">
      <span class="bklog-icon bklog-wholesale-editor"></span>{{ t('批量编辑别名') }}
    </div>
    <TDrawer
      attach="body"
      :visible="showSlider"
      :z-index="drawerZIndex"
      :close-on-overlay-click="true"
      :close-btn="false"
      size="640px"
      drawer-class-name="field-alias-drawer"
      @close="handleCancel"
    >
      <template #header>
        <div class="alias-drawer-header">
          <button type="button" :aria-label="t('关闭')" @click="handleCancel">
            <span class="bklog-icon bklog-arrow-right" />
          </button>
          <span>{{ t('批量编辑变量别名') }}</span>
        </div>
      </template>
      <BklogLoading :loading="sliderLoading" class="sideslider-content">
        <TTable
          class="field-table field-alias-table"
          :data="formData"
          :columns="columns"
          :empty="t('暂无数据')"
          row-key="field_name"
          size="small"
          bordered
          resizable
        >
          <template #fieldName="{ row }">
            <TTooltip :content="aliasShow(row) ? row.field_name : row.alias_name">
              <div class="sideslider-field-name field-name-overflow-tips">
                <span
                  v-if="row.children?.length"
                  :class="['ext-btn bklog-icon bklog-arrow-down-filled', { rotate: !row.expand }]"
                  @click="expandObject(row, !row.expand)"
                />
                <div v-if="aliasShow(row)" class="field-name">
                  <span v-if="row.is_objectKey" class="bklog-icon bklog-subnode" />{{ row.field_name }}
                </div>
                <div v-else-if="row.is_built_in && row.alias_name" class="field-name">{{ row.alias_name }}</div>
              </div>
            </TTooltip>
          </template>
          <template #alias="{ row }">
            <div class="alias-container">
              <TTooltip v-if="row.field_type === 'object'" :content="t('object字段不支持编辑别名')"
                ><div class="ml8">--</div></TTooltip
              >
              <TInput
                v-else
                v-model="row.query_alias"
                class="alias-input"
                :placeholder="t('请输入')"
                @blur="checkQueryAliasItem(row)"
              />
              <TTooltip v-if="row.aliasErr" :content="row.aliasErr"
                ><i style="right: 8px" class="bk-icon icon-exclamation-circle-shape tooltips-icon"
              /></TTooltip>
            </div>
          </template>
        </TTable>
      </BklogLoading>
      <template #footer>
        <div class="submit-container">
          <TButton class="king-button mr10" :loading="confirmLoading" theme="primary" @click.stop.prevent="submit">{{
            t('保存')
          }}</TButton>
          <TButton theme="default" @click="handleCancel">{{ t('取消') }}</TButton>
        </div>
      </template>
    </TDrawer>
  </div>
</template>
<style lang="scss">
.field-alias-v3 {
  .field-alias-title {
    display: flex;
    align-items: center;
    font-size: 12px;
    color: #4d4f56;

    .bklog-wholesale-editor {
      margin-right: 4px;
      font-size: 12px;
    }
  }
}

.field-alias-drawer .sideslider-content {
  min-height: 394px;
  max-height: calc(-119px + 100vh);
  padding: 24px 24px 0;
  overflow-y: auto;

  .field-alias-table {
    .t-table__body td {
      padding: 0;

      .sideslider-field-name {
        padding: 0 8px;
      }

      .field-name-overflow-tips {
        .ext-btn {
          position: absolute;
          left: 0;
          font-size: 18px;
          cursor: pointer;
        }

        .bklog-subnode {
          font-size: 16px;
        }

        .rotate {
          transform: rotate(-90deg);
        }

        .field-name {
          margin: 15px 10px 15px 15px;
          line-height: 14px;
        }
      }

      .alias-container {
        position: relative;

        .ml8 {
          margin-left: 8px;
        }

        .tooltips-icon {
          position: absolute;
          top: 14px;
          z-index: var(--bklog-z-page);
          font-size: 16px;
          color: #ea3636;
          cursor: pointer;
        }
      }

      .alias-input {
        .t-input {
          height: 44px;
          border: 0;
          border-radius: 0;
          box-shadow: none;
        }
        input {
          height: 43px;
          border: none;
        }
      }
    }
  }
}
.field-alias-drawer {
  .t-drawer__header {
    height: 52px;
    min-height: 52px;
    padding: 0;
  }
  .t-drawer__body {
    overflow: hidden;
    padding: 0;
  }
  .t-drawer__footer {
    padding: 16px 24px;
  }
  .alias-drawer-header {
    display: flex;
    align-items: center;
    height: 52px;
    font-size: 16px;
    font-weight: normal;
    button {
      width: 30px;
      height: 52px;
      margin-right: 16px;
      border: 0;
      background: #3a84ff;
      color: white;
      cursor: pointer;
    }
  }
  .t-table__header th {
    background: #f0f1f5;
    height: 43px;
    color: #313238;
  }
  .submit-container {
    text-align: left;
    button {
      width: 88px;
    }
  }
}
</style>
