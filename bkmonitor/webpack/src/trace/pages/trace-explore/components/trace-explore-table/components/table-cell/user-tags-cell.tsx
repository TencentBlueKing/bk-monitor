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

import { type PropType, defineComponent, shallowRef, watchEffect } from 'vue';

import { getBkUserDisplayNameInstance, getUserComponentConfig } from 'monitor-pc/common/user-display-name';

import TagsCell from './tags-cell';

import type { ExploreTableColumn, ExploreTableColumnTypeEnum, TableCellRenderContext } from '../../typing';

export default defineComponent({
  name: 'UserTagsCell',
  props: {
    /** 当前列配置信息 */
    column: {
      type: Object as PropType<ExploreTableColumn<ExploreTableColumnTypeEnum.USER_TAGS>>,
    },
    /** 当前需要渲染的数据 */
    tags: {
      type: Array as PropType<string[]>,
    },
    /** 当前列 id */
    colId: {
      type: String,
    },
    /** 当前行数据 id */
    rowId: {
      type: String,
    },
    /** table 单元格渲染上下文信息 */
    renderCtx: {
      type: Object as PropType<TableCellRenderContext>,
      default: () => ({}),
    },
  },
  setup(props) {
    const userDisplayNameList = shallowRef<string[]>([]);

    // 获取负责人显示名称
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    watchEffect(async () => {
      const displayNameConfig = getUserComponentConfig();
      const list = props?.tags || [];
      if (list.length && displayNameConfig.apiBaseUrl && displayNameConfig.tenantId) {
        const displayNames = await getBkUserDisplayNameInstance()
          // @ts-ignore
          .getMultipleUsersDisplayName(list)
          .then(v => v?.split(',') || list)
          .catch(() => list);
        userDisplayNameList.value = displayNames;
      } else {
        userDisplayNameList.value = list;
      }
    });

    return { userDisplayNameList };
  },
  render() {
    return (
      <TagsCell
        class='explore-user-tags-col'
        colId={this.colId}
        column={this.column as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>}
        renderCtx={this.renderCtx}
        rowId={this.rowId}
        tags={this.userDisplayNameList}
      />
    );
  },
});
