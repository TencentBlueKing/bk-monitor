import { SPACE_TYPE_MAP } from './utils';

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import type { ILocalSpaceList } from './typing';

export const tipsContent = (list: { id: string; name: string; tags: ILocalSpaceList['tags'] }[]) => {
  return (
    <div
      style={{
        maxWidth: '500px',
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '2px',
        fontSize: '12px',
      }}
    >
      {list.map((item, index) => {
        return (
          <span
            key={index}
            style={{ marginRight: '4px' }}
          >
            <span>{`${item.name}${item.id ? `(${item.id})` : ''}`}</span>
            {item.tags?.map?.(tag => (
              <span
                key={tag.id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '22px',
                  padding: '0 10px',
                  marginLeft: '4px',
                  whiteSpace: 'nowrap',
                  border: '1px solid transparent',
                  borderRadius: '2px',
                  ...(SPACE_TYPE_MAP[tag.id]?.dark || SPACE_TYPE_MAP.default.dark),
                }}
              >
                {SPACE_TYPE_MAP[tag.id]?.name || window.i18n.t('未知')}
              </span>
            ))}
            {index !== list.length - 1 && ','}
          </span>
        );
      })}
    </div>
  );
};
