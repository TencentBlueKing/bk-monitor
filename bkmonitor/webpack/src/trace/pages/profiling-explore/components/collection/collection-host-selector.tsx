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
import { type PropType, defineComponent } from 'vue';

import createIpSelector from '../../../../components/monitor-ip-selector/vue3.x';

import type { createCollectionHostServices } from '../../services/collection-hosts';
import type { CollectionHost } from '../../types/collection';

import '@blueking/ip-selector/dist/styles/vue2.6.x.css';

const BkIpSelector = createIpSelector({ version: '4', serviceConfigError: false });
const config = {
  panelList: ['staticTopo', 'manualInput'],
  nameStyle: 'kebabCase',
  unqiuePanelValue: false,
  hostTableDefaultSelectAllMode: false,
  hostTableRenderColumnList: ['ip', 'ipv6', 'cloudArea', 'alive', 'osName'],
};

export default defineComponent({
  name: 'CollectionHostSelector',
  props: {
    hosts: { type: Array as PropType<CollectionHost[]>, required: true },
    service: { type: Object as PropType<ReturnType<typeof createCollectionHostServices>>, required: true },
  },
  emits: { change: (_hosts: CollectionHost[]) => true, close: () => true },
  render() {
    return (
      <BkIpSelector
        config={config}
        keepHostFieldOutput={true}
        mode='dialog'
        service={this.service}
        showDialog={true}
        showView={true}
        value={{ host_list: this.hosts }}
        onChange={value => this.$emit('change', value.host_list)}
        onClose-dialog={() => this.$emit('close')}
      />
    );
  },
});
