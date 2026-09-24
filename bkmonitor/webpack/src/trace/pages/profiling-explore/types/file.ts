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
import type { Aggregation, ProfileViewState, ServiceDetail } from './index';
import type { IWhereItem } from '@/components/retrieval-filter/typing';

export interface FileQueryState {
  aggregation: Aggregation;
  commonWhere: IWhereItem[];
  dataType: string;
  fileName: string;
  pendingTimeRange: boolean;
  profileId: string;
  view: ProfileViewState;
  where: IWhereItem[];
}

export interface ProfileFile {
  content: string;
  data_time: string;
  data_types: ServiceDetail['data_types'];
  file_md5: string;
  file_name: string;
  file_size: number;
  file_type: string;
  id: number;
  operator: string;
  origin_file_name: string;
  profile_id: string;
  query_end_time: null | number;
  query_start_time: null | number;
  status: ProfileFileStatus;
  uploaded_time: string;
}

export type ProfileFileStatus = 'parsing_failed' | 'parsing_succeed' | 'store_failed' | 'store_succeed' | 'uploaded';

export interface ProfileUploadItem {
  error: string;
  file: File;
  id: number;
  progress: number;
  status: 'canceled' | 'error' | 'success' | 'uploading';
}
