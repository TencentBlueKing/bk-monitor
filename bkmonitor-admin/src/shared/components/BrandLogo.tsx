interface BrandLogoProps {
  compact?: boolean;
}

export function BrandLogo({ compact = false }: BrandLogoProps) {
  return (
    <div className="brand">
      <img className="brand-mark" src="/logo-mark.png" alt="" aria-hidden="true" />
      {compact ? null : (
        <span>
          <strong>bkmonitor-admin</strong>
          <small>Monitor Admin</small>
        </span>
      )}
    </div>
  );
}
