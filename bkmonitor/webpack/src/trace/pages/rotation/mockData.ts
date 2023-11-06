import { RotationTabTypeEnum } from './typings/common';

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
export const fixedMockData = {
  name: 'dad',
  category: 'regular',
  labels: [],
  duty_arranges: [
    {
      id: 1,
      duty_time: [
        {
          work_type: 'weekly',
          work_days: [1, 2, 3],
          work_time: ['12:02--12:02', '03:00--03:00']
        }
      ],
      duty_users: [
        [
          {
            type: 'group',
            id: 'xxxx',
            display_name: '运维人员',
            logo: ''
          },
          {
            type: 'group',
            id: 'xxxx',
            display_name: '产品人员',
            logo: ''
          }
        ]
      ]
    },
    {
      id: 2,
      duty_time: [
        {
          work_type: 'monthly',
          work_days: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
          work_time: ['01:00--01:00', '02:00--02:00']
        }
      ],
      duty_users: [
        [
          {
            type: 'group',
            id: 'xxxx',
            display_name: '运维人员',
            logo: ''
          },
          {
            type: 'group',
            id: 'asasdasd',
            display_name: '测试人员',
            logo: ''
          }
        ]
      ]
    },
    {
      id: 3,
      duty_time: [
        {
          work_type: 'date_range',
          work_date_range: ['2023-10-03--2023-11-21'],
          work_time: ['02:00--02:00']
        }
      ],
      duty_users: [
        [
          {
            type: 'group',
            id: 'xxxx',
            display_name: '开发人员',
            logo: ''
          },
          {
            type: 'group',
            id: 'sasdasasdasd',
            display_name: '主负责人',
            logo: ''
          }
        ]
      ]
    }
  ],
  effective_time: '2023-10-11 00:00:00',
  end_time: ''
};

export const replaceMockData = {
  name: 'a',
  category: 'handoff',
  labels: [],
  duty_arranges: [
    {
      id: 1,
      duty_time: [
        {
          is_custom: true,
          work_type: 'weekly',
          work_days: [2, 4],
          work_time: ['12:00--12:00', '02:00--02:00']
        },
        {
          is_custom: true,
          work_type: 'weekly',
          work_days: [2, 4],
          work_time: ['12:01--12:01', '04:00--04:00']
        },
        {
          is_custom: true,
          work_type: 'weekly',
          work_days: [2, 4],
          work_time: ['02:00--02:00']
        }
      ],
      duty_users: [
        [
          {
            type: 'group',
            id: 'xxxxx',
            display_name: '产品人员',
            logo: ''
          },
          {
            type: 'group',
            id: 'xxxxxx',
            display_name: '运维人员',
            logo: ''
          }
        ],
        [
          {
            type: 'group',
            id: 'xxxxx',
            display_name: '开发人员',
            logo: ''
          },
          {
            type: 'group',
            id: 'operator',
            display_name: '主负责人',
            logo: ''
          }
        ],
        [
          {
            type: 'group',
            id: 'xxxxxx',
            display_name: '运维人员',
            logo: ''
          }
        ]
      ],
      group_type: 'specified',
      group_number: 1
    }
  ],
  effective_time: '2023-10-03 00:00:00',
  end_time: ''
};

export const mockRequest = (type: RotationTabTypeEnum) => {
  return new Promise(res => {
    return res(type === RotationTabTypeEnum.REGULAR ? fixedMockData : replaceMockData);
  });
};
