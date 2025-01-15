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
<template>
  <article class="import-configuration-upload">
    <section class="upload">
      <upload
        action="rest/v2/export_import/upload_package/"
        :on-upload-success="handleSuccess"
        :on-upload-error="handleError"
        :headers="headers"
      />
    </section>
  </article>
</template>
<script>
import { getCookie } from 'monitor-common/utils/utils';

import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import Upload from '../components/upload';

export default {
  name: 'ImportConfigurationUpload',
  components: {
    Upload,
  },
  data() {
    return {
      headers: [
        {
          name: 'X-Requested-With',
          value: 'XMLHttpRequest',
        },
        {
          name: 'X-CSRFToken',
          value: window.csrf_token || getCookie(this.$store.getters.csrfCookieName),
        },
      ],
    };
  },
  created() {
    this.updateNavData(this.$t('route-导入配置'));
  },
  methods: {
    updateNavData(name = '') {
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, [{ name, id: '' }]);
    },
    handleSuccess(res) {
      this.$router.push({
        name: 'import-configuration',
        params: {
          importData: res.data,
        },
      });
    },
    handleError(err) {
      console.log(err);
    },
  },
};
</script>
<style lang="scss" scoped>
.upload {
  display: flex;
  justify-content: center;
  margin-top: 74px;
}
</style>
