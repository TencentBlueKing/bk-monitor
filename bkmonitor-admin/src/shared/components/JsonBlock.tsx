interface JsonBlockProps {
  value: unknown;
}

export function JsonBlock({ value }: JsonBlockProps) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}
