export function formatBoolean(value: boolean | null | undefined): string {
  if (value === true) {
    return '是';
  }

  if (value === false) {
    return '否';
  }

  return '-';
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }

  return value.replace('T', ' ').replace(/\.\d+Z$/, '');
}

export function compactObject<T extends Record<string, unknown>>(input: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(input).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  ) as Partial<T>;
}
