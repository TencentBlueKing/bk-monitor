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
const MESSAGE_FIELD = 'popup_message';
const MESSAGE_THEME_LIST = ['error', 'warning'];
/**
 *
 * @param props { theme: string, message: Record<string, any>} | Record<string, any>
 * @returns Record<string, any>
 */
export const transformMessageProps = (params: Record<string, any>) => {
  let props = params;
  if (!props || typeof props !== 'object') return props;
  if (MESSAGE_FIELD in props) {
    props = {
      message: props,
    };
  }
  if (props.message && typeof props.message !== 'string' && MESSAGE_FIELD in props.message) {
    return {
      actions: [
        {
          id: 'assistant',
          disabled: !props.message.assistant,
        },
        {
          id: 'details',
          disabled: false,
        },
      ],
      message: {
        code: props.message.exc_code || props.message.code,
        overview: props.message.overview || props.message.overview,
        suggestion: props.message.suggestion || '',
        type: 'json',
        details: JSON.stringify({ ...props.message }),
        assistant: props.message.assistant || undefined,
      },
      theme: MESSAGE_THEME_LIST.includes(props.message.popup_message) ? props.message.popup_message : 'error',
      ellipsisLine: 2,
      ellipsisCopy: true,
      zIndex: 9999,
    };
  }
  return {
    ...props,
    zIndex: 9999,
  };
};
