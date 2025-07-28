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
interface Config {
  onSuccess?: (registration: ServiceWorkerRegistration) => void;
  onUpdate?: (registration: ServiceWorkerRegistration) => void;
}

const isLocalhost = Boolean(
  window.location.hostname === 'localhost' ||
    window.location.hostname === '[::1]' ||
    /^127(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}$/.test(window.location.hostname)
);

const registerValidSW = (swUrl: string, config?: Config): void => {
  navigator.serviceWorker
    .register(swUrl)
    .then((registration: ServiceWorkerRegistration) => {
      registration.onupdatefound = (): void => {
        const installingWorker: null | ServiceWorker = registration.installing;
        if (!installingWorker) return;
        installingWorker.onstatechange = (): void => {
          if (installingWorker.state === 'installed') {
            if (navigator.serviceWorker.controller) {
              console.log('New content is available and will be used when all tabs for this page are closed.');
              config?.onUpdate?.(registration);
            } else {
              console.log('Content is cached in cache storage.');
              config?.onSuccess?.(registration);
            }
          }
        };
      };
    })
    .catch((error: Error) => {
      console.error('Error during service worker registration:', error);
    });
};

const checkValidServiceWorker = (swUrl: string, config?: Config): void => {
  fetch(swUrl)
    .then((response: Response) => {
      const contentType = response.headers.get('content-type');
      if (response.status === 404 || (contentType && !contentType.includes('javascript'))) {
        navigator.serviceWorker.ready.then((registration: ServiceWorkerRegistration) => {
          registration.unregister().then(() => {
            window.location.reload();
          });
        });
      } else {
        registerValidSW(swUrl, config);
      }
    })
    .catch(() => {
      console.log('No internet connection found. App is running in offline mode.');
    });
};

export const register = (config?: Config): void => {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      const swUrl = `${window.site_url}service-worker.js`;
      if (isLocalhost) {
        checkValidServiceWorker(swUrl, config);
        navigator.serviceWorker.ready.then(() => {
          console.log('This web app is being served cache-first by a service worker.');
        });
      } else {
        window.requestIdleCallback(() => {
          registerValidSW(swUrl, config);
        });
      }
    });
  }
};

export const immediateRegister = (config?: Config): void => {
  if ('serviceWorker' in navigator) {
    const swUrl = `${window.site_url}service-worker.js`;
    if (isLocalhost) {
      checkValidServiceWorker(swUrl, config);
      navigator.serviceWorker.ready.then(() => {
        console.log('This web app is being served cache-first by a service worker.');
      });
    } else {
      window.requestIdleCallback(() => {
        registerValidSW(swUrl, config);
      });
    }
  }
};

export const unregister = (): void => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then((registration: ServiceWorkerRegistration) => {
      registration.unregister();
    });
  }
};
