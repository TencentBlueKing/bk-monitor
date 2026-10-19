/* eslint-disable */
import { prepareMicroAppRuntime } from './micro-app-runtime';

export const captureMicroAppRuntime = window.__POWERED_BY_BK_WEWEB__ ? prepareMicroAppRuntime(window) : undefined;

// @ts-expect-error
__webpack_public_path__ =
  process.env.NODE_ENV === 'production' ? `${window.static_url}trace/` : `http://${process.env.devUrl}/`;
