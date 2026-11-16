/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { fileURLToPath } from 'node:url';
// Same directory as V2 webpack output and Django's template search path.
export const productionOutput = fileURLToPath(new URL('../../../../static/dist/', import.meta.url));
