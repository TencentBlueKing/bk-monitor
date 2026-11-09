/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { compile } from '@inlang/paraglide-js';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import config from '../project.inlang/paraglide.config.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
await compile({ ...config, project: resolve(root, 'project.inlang'), outdir: resolve(root, config.outdir) });
