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
import { type PropType, type UnwrapRef, computed, defineComponent, watch } from 'vue';
import { shallowRef } from 'vue';

import { Button, Checkbox, Dialog, Exception, Input, Message, Radio } from 'bkui-vue';
import _ from 'lodash';
import { shareFavorite } from 'monitor-api/modules/model';
import { ETagsType, SPACE_TYPE_MAP } from 'monitor-common/utils/biz';
import { useI18n } from 'vue-i18n';

import useFavoriteType from '../../../../../hooks/use-favorite-type';
import { useAppStore } from '@store/modules/app';

import type { IFavoriteGroup } from '../../../../../types';

import './share-favorite.scss';

export const makeMap = (list: Array<number> = []): Record<number, boolean> => {
  const map = Object.create(null);
  for (const item of list) {
    map[item] = true;
  }
  return map;
};

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
      required: true,
    },
    isShow: {
      type: Boolean,
    },
  },
  emits: ['close', 'success'],
  setup(props, context) {
    const store = useAppStore();
    const { t } = useI18n();
    const favoriteType = useFavoriteType();

    const spaceSearchKey = shallowRef('');
    const duplicateMode = shallowRef('skip');
    const shareBizIdList = shallowRef([]);
    const isSubmiting = shallowRef(false);

    const allBizList = computed(() => {
      return store.bizList.map(bizItem => {
        const tagList = [{ id: bizItem.space_type_id, name: bizItem.type_name, type: bizItem.space_type_id }];
        if (bizItem.space_type_id === 'bkci' && bizItem.space_code) {
          tagList.push({
            id: 'bcs',
            name: t('容器项目'),
            type: 'bcs',
          });
        }
        return {
          ...bizItem,
          tagList,
        };
      });
    });

    const renderBizList = shallowRef<UnwrapRef<typeof allBizList>>([]);
    const isBizSelectAll = computed(() => {
      const selectIdMap = makeMap(shareBizIdList.value);
      return _.every(renderBizList.value, item => selectIdMap[item.id]);
    });

    watch(
      () => props.isShow,
      () => {
        setTimeout(() => {
          spaceSearchKey.value = '';
          renderBizList.value = allBizList.value;
        });
      },
      {
        immediate: true,
      }
    );

    const handleSpaceSearch = _.throttle(() => {
      const keyword = spaceSearchKey.value.toLocaleLowerCase();
      renderBizList.value = _.filter(
        allBizList.value,
        bizItem =>
          bizItem.space_name.toLocaleLowerCase().indexOf(keyword) > -1 ||
          `${bizItem.id}`.includes(keyword) ||
          `${bizItem.space_id}`.toLocaleLowerCase().includes(keyword)
      );
    }, 300);

    const handleBizAllChange = (checked: boolean) => {
      if (checked) {
        shareBizIdList.value = renderBizList.value.map(item => item.id);
      } else {
        shareBizIdList.value = [];
      }
    };

    const handleSubmitEdit = async () => {
      isSubmiting.value = true;
      try {
        await shareFavorite({
          bk_biz_id: store.bizId,
          type: favoriteType.value,
          share_bk_biz_ids: shareBizIdList.value,
          duplicate_mode: duplicateMode.value,
          name: props.data.name,
          config: props.data.config,
        });
        context.emit('close');
        Message({
          theme: 'success',
          message: t('操作成功'),
        });
      } finally {
        isSubmiting.value = false;
      }
    };

    const handleClose = () => {
      context.emit('close');
    };

    return () => (
      <Dialog
        width={480}
        class='favorite-box-share-favorite-dialog'
        v-slots={{
          footer: () => (
            <>
              <Button
                loading={isSubmiting.value}
                theme='primary'
                onClick={handleSubmitEdit}
              >
                {t('确定')}
              </Button>
              <Button
                style='margin-left: 8px'
                onClick={handleClose}
              >
                {t('取消')}
              </Button>
            </>
          ),
        }}
        is-show={props.isShow}
        title={t('共享')}
        onClosed={handleClose}
      >
        <div class='space-wrapper'>
          <div class='space-search'>
            <Input
              v-model={spaceSearchKey.value}
              placeholder={t('搜索空间')}
              onInput={handleSpaceSearch}
            />
          </div>
          <div class='space-list'>
            <div class='space-item'>
              <Checkbox
                modelValue={isBizSelectAll.value}
                onChange={handleBizAllChange}
              >
                {t('全选')}
              </Checkbox>
            </div>
            <Checkbox.Group v-model={shareBizIdList.value}>
              {renderBizList.value.map(item => (
                <div
                  key={item.id}
                  class='space-item'
                >
                  <Checkbox label={item.id}>
                    {item.space_name}
                    <span
                      class='space-id'
                      v-overflow-tips
                    >
                      ({item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code})
                    </span>
                  </Checkbox>
                  <div class='space-tag-wrapper'>
                    {item.tagList.map(tag => (
                      <div
                        key={tag.id}
                        style={{ ...SPACE_TYPE_MAP[tag.id]?.light }}
                        class='space-tag'
                      >
                        {tag.name}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </Checkbox.Group>
            {spaceSearchKey.value && renderBizList.value.length < 1 && (
              <Exception
                style='margin-top: 60px'
                description={t('搜索为空')}
                scene='part'
                type='search-empty'
              />
            )}
          </div>
        </div>
        <div style='margin-top: 30px'>
          <div
            class='rename-title'
            v-bk-tooltips={t('该规则仅针对重名内容生效')}
          >
            {t('重命名规则')}
          </div>
          <div>
            <Radio.Group v-model={duplicateMode.value}>
              <Radio label='skip'>{t('不共享')}</Radio>
              <Radio label='copy'>{t('创建副本')}</Radio>
              <Radio label='overwrite'>{t('覆盖')}</Radio>
            </Radio.Group>
          </div>
        </div>
      </Dialog>
    );
  },
});
