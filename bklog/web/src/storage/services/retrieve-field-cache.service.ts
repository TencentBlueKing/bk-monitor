/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import {
  retrieveFieldRepository,
  type RetrieveFieldMetaEntity,
  type RetrieveFieldWidthEntity,
} from '../repositories/retrieve-field.repository';
import { createRetrieveFieldMeta, type RetrieveFieldMetaPayload } from '../utils/retrieve-field-meta';

type FieldMetaCache = RetrieveFieldMetaPayload & {
  scope: string;
  updatedAt: number;
};

export type FieldWidthSnapshot = {
  serverMaxLength?: number;
  computedWidth?: number;
  minWidth?: number;
  userWidth?: number;
  source?: string;
};

const DEFAULT_SCOPE = 'default';
const getScope = (scope?: string | number) => String(scope || DEFAULT_SCOPE);

const toMetaCache = (scope: string, entity: RetrieveFieldMetaEntity): FieldMetaCache => ({
  scope,
  rawPayload: entity.rawPayload,
  normalizedPayload: entity.normalizedPayload,
  rawFields: entity.rawFields,
  rawFieldList: entity.rawFieldList,
  aliasFieldList: entity.aliasFieldList,
  fieldTree: entity.fieldTree,
  fieldNameIndex: entity.fieldNameIndex,
  queryAliasIndex: entity.queryAliasIndex,
  widthHints: entity.widthHints ?? {},
  updatedAt: entity.updatedAt,
});

class RetrieveFieldCacheService {
  private metaMemory = new Map<string, FieldMetaCache>();
  private widthMemory = new Map<string, Record<string, FieldWidthSnapshot>>();

  setMeta(scope: string | number, payload: Record<string, any>) {
    const cacheScope = getScope(scope);
    const meta = createRetrieveFieldMeta(payload);
    const cacheValue: FieldMetaCache = {
      ...meta,
      scope: cacheScope,
      updatedAt: Date.now(),
    };
    this.metaMemory.set(cacheScope, cacheValue);
    if (Object.keys(meta.widthHints).length) {
      this.patchWidths(
        cacheScope,
        Object.keys(meta.widthHints).reduce(
          (output, fieldName) => {
            output[fieldName] = {
              ...meta.widthHints[fieldName],
              source: 'server',
            };
            return output;
          },
          {} as Record<string, FieldWidthSnapshot>,
        ),
      );
    }
    retrieveFieldRepository.setMeta(cacheScope, meta).catch(error => {
      console.warn('[retrieve-field-cache] persist meta failed', error);
    });
    return cacheValue;
  }

  getMetaSync(scope: string | number) {
    return this.metaMemory.get(getScope(scope));
  }

  async getMeta(scope: string | number) {
    const cacheScope = getScope(scope);
    const memory = this.metaMemory.get(cacheScope);
    if (memory) return memory;

    const entity = await retrieveFieldRepository.getMeta(cacheScope);
    if (!entity) return undefined;
    const cacheValue = toMetaCache(cacheScope, entity);
    this.metaMemory.set(cacheScope, cacheValue);
    return cacheValue;
  }

  getFieldList(scope: string | number, showAlias = true) {
    const meta = this.getMetaSync(scope);
    if (!meta) return [];
    return showAlias ? meta.aliasFieldList : meta.rawFieldList;
  }

  getFieldTree(scope: string | number) {
    return this.getMetaSync(scope)?.fieldTree ?? [];
  }

  getFieldNameIndex(scope: string | number) {
    return this.getMetaSync(scope)?.fieldNameIndex ?? {};
  }

  getQueryAliasIndex(scope: string | number) {
    return this.getMetaSync(scope)?.queryAliasIndex ?? {};
  }

  patchWidths(scope: string | number, widths: Record<string, FieldWidthSnapshot> = {}) {
    const cacheScope = getScope(scope);
    const current = this.widthMemory.get(cacheScope) ?? {};
    const next = { ...current };
    Object.keys(widths).forEach(fieldName => {
      next[fieldName] = {
        ...(next[fieldName] ?? {}),
        ...widths[fieldName],
      };
    });
    this.widthMemory.set(cacheScope, next);
    retrieveFieldRepository
      .setWidths(cacheScope, widths as Record<string, Partial<RetrieveFieldWidthEntity>>)
      .catch(error => {
        console.warn('[retrieve-field-cache] persist widths failed', error);
      });
    return next;
  }

  setUserWidths(scope: string | number, fieldsWidth: Record<string, number> = {}) {
    const cacheScope = getScope(scope);
    if (!Object.keys(fieldsWidth ?? {}).length) {
      const current = this.widthMemory.get(cacheScope) ?? {};
      const next = Object.keys(current).reduce(
        (output, fieldName) => {
          const rest = { ...current[fieldName] };
          delete rest.userWidth;
          output[fieldName] = {
            ...rest,
            source: rest.source === 'user' ? undefined : rest.source,
          };
          return output;
        },
        {} as Record<string, FieldWidthSnapshot>,
      );
      this.widthMemory.set(cacheScope, next);
      retrieveFieldRepository
        .setWidths(cacheScope, next as Record<string, Partial<RetrieveFieldWidthEntity>>)
        .catch(error => {
          console.warn('[retrieve-field-cache] clear user widths failed', error);
        });
      return next;
    }

    const widths = Object.keys(fieldsWidth).reduce(
      (output, fieldName) => {
        const userWidth = Number(fieldsWidth[fieldName]);
        if (Number.isFinite(userWidth)) {
          output[fieldName] = { userWidth, source: 'user' };
        }
        return output;
      },
      {} as Record<string, FieldWidthSnapshot>,
    );
    return this.patchWidths(scope, widths);
  }

  setComputedWidths(scope: string | number, fields: Array<Record<string, any>> = []) {
    const widths = fields.reduce(
      (output, field) => {
        if (!field?.field_name) return output;
        output[field.field_name] = {
          computedWidth: Number.isFinite(Number(field.width)) ? Number(field.width) : undefined,
          minWidth: Number.isFinite(Number(field.minWidth)) ? Number(field.minWidth) : undefined,
          source: 'computed',
        };
        return output;
      },
      {} as Record<string, FieldWidthSnapshot>,
    );
    return this.patchWidths(scope, widths);
  }

  getWidthsSync(scope: string | number) {
    return this.widthMemory.get(getScope(scope)) ?? {};
  }

  async getWidths(scope: string | number) {
    const cacheScope = getScope(scope);
    const memory = this.widthMemory.get(cacheScope);
    if (memory) return memory;

    const rows = await retrieveFieldRepository.getWidths(cacheScope);
    const widths = Object.keys(rows).reduce(
      (output, fieldName) => {
        const row = rows[fieldName];
        output[fieldName] = {
          serverMaxLength: row.serverMaxLength,
          computedWidth: row.computedWidth,
          minWidth: row.minWidth,
          userWidth: row.userWidth,
          source: row.source,
        };
        return output;
      },
      {} as Record<string, FieldWidthSnapshot>,
    );
    this.widthMemory.set(cacheScope, widths);
    return widths;
  }

  getWidthConfig(scope: string | number) {
    const widths = this.getWidthsSync(scope);
    return Object.keys(widths).reduce(
      (output, fieldName) => {
        const width = widths[fieldName]?.userWidth ?? widths[fieldName]?.computedWidth;
        if (Number.isFinite(Number(width))) {
          output[fieldName] = Number(width);
        }
        return output;
      },
      {} as Record<string, number>,
    );
  }

  getUserWidthConfig(scope: string | number) {
    const widths = this.getWidthsSync(scope);
    return Object.keys(widths).reduce(
      (output, fieldName) => {
        const width = widths[fieldName]?.userWidth;
        if (Number.isFinite(Number(width))) {
          output[fieldName] = Number(width);
        }
        return output;
      },
      {} as Record<string, number>,
    );
  }

  clearScope(scope: string | number) {
    const cacheScope = getScope(scope);
    this.metaMemory.delete(cacheScope);
    this.widthMemory.delete(cacheScope);
    retrieveFieldRepository.clearMeta(cacheScope).catch(() => {});
    retrieveFieldRepository.clearWidths(cacheScope).catch(() => {});
  }
}

export const retrieveFieldCacheService = new RetrieveFieldCacheService();
