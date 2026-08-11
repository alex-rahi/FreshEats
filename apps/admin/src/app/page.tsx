import { adminApi } from '../lib/api';

export default async function DashboardPage() {
  let stats = {
    pending_reviews: 0,
    published_today: 0,
    rejected_today: 0,
    total_recipes: 0,
    total_users: 0,
  };
  let error: string | null = null;

  try {
    stats = await adminApi.stats();
  } catch (e: any) {
    error = e.message || 'Backend unreachable — start the API on :8000';
  }

  const cards = [
    { label: 'Pending review', value: stats.pending_reviews },
    { label: 'Published', value: stats.published_today },
    { label: 'Rejected', value: stats.rejected_today },
    { label: 'Total recipes', value: stats.total_recipes },
    { label: 'Users', value: stats.total_users },
  ];

  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
      <p className="mt-2 text-[var(--muted)]">
        Uncertain YOLO results land in the review queue before publishing.
      </p>
      {error ? (
        <p className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-lg border border-[var(--line)] bg-[var(--surface)] p-5">
            <div className="text-sm text-[var(--muted)]">{card.label}</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight">{card.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
