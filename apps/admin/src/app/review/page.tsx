'use client';

import { useEffect, useState } from 'react';

import { adminApi, mediaUrl, ReviewItem } from '../../lib/api';

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setItems(await adminApi.queue());
    } catch (e: any) {
      setError(e.message || 'Failed to load queue');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const decide = async (id: string, outcome: 'publish' | 'reject') => {
    setBusyId(id);
    try {
      await adminApi.decide(id, outcome);
      await load();
    } catch (e: any) {
      setError(e.message || 'Decision failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Review queue</h1>
      <p className="mt-2 text-[var(--muted)]">
        Approve food-related images or reject unrelated / prohibited content.
      </p>
      {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}

      <div className="mt-8 space-y-6">
        {items.length === 0 ? (
          <p className="text-[var(--muted)]">Queue is empty.</p>
        ) : (
          items.map((item) => {
            const image = mediaUrl(item.recipe?.image_url);
            const labels = item.detections?.map((d) => d.label).join(', ') || 'none';
            return (
              <div
                key={item.id}
                className="grid gap-5 rounded-lg border border-[var(--line)] bg-[var(--surface)] p-5 md:grid-cols-[200px_1fr]"
              >
                <div className="overflow-hidden rounded-md bg-[var(--bg)]">
                  {image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={image} alt={item.recipe?.title || 'Recipe'} className="h-48 w-full object-cover" />
                  ) : (
                    <div className="flex h-48 items-center justify-center text-sm text-[var(--muted)]">No image</div>
                  )}
                </div>
                <div>
                  <h2 className="text-xl font-semibold">{item.recipe?.title || 'Untitled'}</h2>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    @{item.recipe?.author?.username || 'cook'} · priority {item.priority}
                  </p>
                  <p className="mt-3 text-sm">{item.recipe?.description}</p>
                  <p className="mt-3 text-sm">
                    <span className="text-[var(--muted)]">YOLO labels:</span> {labels}
                  </p>
                  <div className="mt-5 flex gap-3">
                    <button
                      disabled={busyId === item.id}
                      onClick={() => decide(item.id, 'publish')}
                      className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      Approve
                    </button>
                    <button
                      disabled={busyId === item.id}
                      onClick={() => decide(item.id, 'reject')}
                      className="rounded-md border border-[var(--line)] px-4 py-2 text-sm font-semibold disabled:opacity-60"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
