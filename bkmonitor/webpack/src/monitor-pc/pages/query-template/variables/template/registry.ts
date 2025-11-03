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

import type { SelectableValue } from './types/select';

export interface RegistryItem {
  aliasIds?: string[]; // when the ID changes, we may want backwards compatibility ('current' => 'last')
  description?: string;
  /**
   * Some extensions should not be user selectable
   *  like: 'all' and 'any' matchers;
   */
  excludeFromPicker?: boolean;
  id: string; // Unique Key -- saved in configs

  name: string; // Display Name, can change without breaking configs
}

export interface RegistryItemWithOptions<TOptions = any> extends RegistryItem {
  /**
   * Default options used if nothing else is specified
   */
  defaultOptions?: TOptions;

  /**
   * Convert the options to a string
   */
  getOptionsDisplayText?: (options: TOptions) => string;
}

interface RegistrySelectInfo {
  current: Array<SelectableValue<string>>;
  options: Array<SelectableValue<string>>;
}

export class Registry<T extends RegistryItem> {
  private byId = new Map<string, T>();
  private initialized = false;
  private ordered: T[] = [];

  setInit = (init: () => T[]) => {
    if (this.initialized) {
      throw new Error('Registry already initialized');
    }
    this.init = init;
  };
  constructor(private init?: () => T[]) {
    this.init = init;
  }
  get(id: string): T {
    const v = this.getIfExists(id);
    if (!v) {
      throw new Error(`"${id}" not found in: ${this.list().map(v => v.id)}`);
    }
    return v;
  }

  getIfExists(id: string | undefined): T | undefined {
    if (!this.initialized) {
      this.initialize();
    }

    if (id) {
      return this.byId.get(id);
    }

    return undefined;
  }

  initialize() {
    if (this.init) {
      for (const ext of this.init()) {
        this.register(ext);
      }
    }
    this.sort();
    this.initialized = true;
  }

  isEmpty(): boolean {
    if (!this.initialized) {
      this.initialize();
    }

    return this.ordered.length === 0;
  }

  /**
   * Return a list of values by ID, or all values if not specified
   */
  list(ids?: string[]): T[] {
    if (!this.initialized) {
      this.initialize();
    }

    if (ids) {
      const found: T[] = [];
      for (const id of ids) {
        const v = this.getIfExists(id);
        if (v) {
          found.push(v);
        }
      }
      return found;
    }

    return this.ordered;
  }

  register(ext: T) {
    if (this.byId.has(ext.id)) {
      throw new Error('Duplicate Key:' + ext.id);
    }

    this.byId.set(ext.id, ext);
    this.ordered.push(ext);

    if (ext.aliasIds) {
      for (const alias of ext.aliasIds) {
        if (!this.byId.has(alias)) {
          this.byId.set(alias, ext);
        }
      }
    }

    if (this.initialized) {
      this.sort();
    }
  }

  selectOptions(current?: string[], filter?: (ext: T) => boolean): RegistrySelectInfo {
    if (!this.initialized) {
      this.initialize();
    }

    const select: RegistrySelectInfo = {
      options: [],
      current: [],
    };

    const currentOptions: Record<string, SelectableValue<string>> = {};
    if (current) {
      for (const id of current) {
        currentOptions[id] = {};
      }
    }

    for (const ext of this.ordered) {
      if (ext.excludeFromPicker) {
        continue;
      }
      if (filter && !filter(ext)) {
        continue;
      }

      const option = {
        value: ext.id,
        label: ext.name,
        description: ext.description,
      };

      select.options.push(option);
      if (currentOptions[ext.id]) {
        currentOptions[ext.id] = option;
      }
    }

    if (current) {
      // this makes sure we preserve the order of ids
      select.current = Object.values(currentOptions);
    }

    return select;
  }

  sort() {
    // TODO sort the list
  }
}
