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

/* eslint-disable no-unused-vars */

// 任务状态枚举
export enum TaskStatus {
  PENDING_APPROVAL = -3, // 待审批
  APPROVED = -2, // 审批通过
  REJECTED = -1, // 审批拒绝
  CREATED = 0, // 已创建
  RUNNING = 1, // 执行中
  STOPPED = 2, // 停止
  FAILED = 3, // 执行失败
  COMPLETED = 4, // 执行完成
  CREATE_FAILED = 5, // 创建失败
  CLAIM_TIMEOUT = 6, // 认领超时
  EXECUTION_TIMEOUT = 7, // 执行超时
  CLAIMING = 8, // 认领中
  DELETED = 9, // 已删除
  CREATING = 10, // 创建中
  STARTING = 11, // 启动中
}

// 任务阶段枚举
export enum TaskScene {
  BEFORE_LOGIN = 1, // 登录前
  AFTER_LOGIN = 4, // 登录后
}
