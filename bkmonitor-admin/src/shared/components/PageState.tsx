import { Card, CardContent } from './ui/card';

interface PageStateProps {
  title: string;
  description?: string;
}

export function PageState({ title, description }: PageStateProps) {
  return (
    <Card>
      <CardContent className="flex min-h-28 flex-col items-center justify-center gap-2 py-8 text-center">
        <strong>{title}</strong>
        {description ? <span className="text-sm text-muted-foreground">{description}</span> : null}
      </CardContent>
    </Card>
  );
}
