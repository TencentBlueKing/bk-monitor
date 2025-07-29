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
// Import Clipboard library
import Clipboard from 'clipboard/dist/clipboard.min.js';

interface ExtentElement {
  _vClipboard: any;
  _vClipboard_error: Function;
  _vClipboard_success: Function;
}
// Define VueClipboardConfig interface
interface VueClipboardConfig {
  appendToBody: boolean;
  autoSetContainer: boolean;
}

// Set default configuration
const defaultConfig: VueClipboardConfig = {
  autoSetContainer: false,
  appendToBody: true, // This fixes IE, see #50
};

// Define VueClipboard object
const VueClipboard = {
  install(Vue: any) {
    Vue.prototype.$clipboardConfig = defaultConfig;

    // Copy text function
    Vue.prototype.$copyText = function (text: string, container?: HTMLElement): Promise<Event> {
      return new Promise((resolve, reject) => {
        const fakeElement = document.createElement('button');
        const clipboard = new Clipboard(fakeElement, {
          text: () => text,
          action: () => 'copy',
          container: container instanceof HTMLElement ? container : document.body,
        });

        clipboard.on('success', (e: Event) => {
          clipboard.destroy();
          resolve(e);
        });

        clipboard.on('error', (e: Event) => {
          clipboard.destroy();
          reject(e);
        });

        if (defaultConfig.appendToBody) document.body.appendChild(fakeElement);
        fakeElement.click();
        if (defaultConfig.appendToBody) document.body.removeChild(fakeElement);
      });
    };

    // Clipboard directive
    Vue.directive('clipboard', {
      bind(el: ExtentElement & HTMLElement, binding: any) {
        if (binding.arg === 'success') {
          el._vClipboard_success = binding.value;
        } else if (binding.arg === 'error') {
          el._vClipboard_error = binding.value;
        } else {
          const clipboard = new Clipboard(el, {
            text: () => binding.value,
            action: () => (binding.arg === 'cut' ? 'cut' : 'copy'),
            container: defaultConfig.autoSetContainer ? el : undefined,
          });

          clipboard.on('success', (e: Event) => {
            const callback = el._vClipboard_success;
            callback?.(e);
          });

          clipboard.on('error', (e: Event) => {
            const callback = el._vClipboard_error;
            callback?.(e);
          });

          el._vClipboard = clipboard;
        }
      },

      update(el: ExtentElement & HTMLElement, binding: any) {
        if (binding.arg === 'success') {
          el._vClipboard_success = binding.value;
        } else if (binding.arg === 'error') {
          el._vClipboard_error = binding.value;
        } else {
          el._vClipboard.text = () => binding.value;
          el._vClipboard.action = () => (binding.arg === 'cut' ? 'cut' : 'copy');
        }
      },

      unbind(el: ExtentElement & HTMLElement, binding: any) {
        if (binding.arg === 'success') {
          delete el._vClipboard_success;
        } else if (binding.arg === 'error') {
          delete el._vClipboard_error;
        } else {
          el._vClipboard.destroy();
          delete el._vClipboard;
        }
      },
    });
  },
  config: defaultConfig,
};

// Export default VueClipboard
export default VueClipboard;
