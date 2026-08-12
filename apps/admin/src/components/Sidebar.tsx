import Link from 'next/link';

const links = [
  { href: '/', label: 'Overview' },
  { href: '/review', label: 'Review queue' },
];

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r border-[var(--line)] bg-[var(--surface)] p-6">
      <div className="mb-10">
        <div className="text-2xl font-semibold tracking-tight">FreshEats</div>
        <div className="mt-1 text-sm text-[var(--muted)]">Moderation</div>
      </div>
      <nav className="flex flex-col gap-2">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="rounded-md px-3 py-2 text-sm text-[var(--ink)] hover:bg-[var(--bg)]"
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
