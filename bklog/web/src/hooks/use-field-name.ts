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
export default ({ store }) => {
    // 用于筛选并展示别名的情况
    const getFieldName = (name: string) => {
        if (store.state.showFieldAlias) {
            const field = store.state.indexFieldInfo.fields.filter(item => item.field_name === name)
            return field[0].query_alias || name
        }
        return name
    }
    // 用于只返回字段名数组的情况
    const getFieldNames = (fildes: any) => {
        if (store.state.showFieldAlias) {
            return fildes.map(fieldInfo => fieldInfo.query_alias || fieldInfo.field_name);
        } else {
            return fildes.map(fieldInfo => fieldInfo.field_name);
        }
    }
    // 用于返回拼接字段名的情况
    const getConcatenatedFieldName = (fildes: any) => {
        const { field_name: id, field_alias: alias, query_alias: query } = fildes;
        if (store.state.showFieldAlias && query) {
            return { id, name: `${query}(${alias || id})` };
        }
        return { id, name: alias ? `${id}(${alias})` : id };
    }
    return {
        getFieldName,
        getFieldNames,
        getConcatenatedFieldName
    }
}