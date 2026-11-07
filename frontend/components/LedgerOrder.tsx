export type Line = { name: string; qty: string; amount: number | null };

export type Proposal = {
  lines: Line[];
  total: number;
  status: "proposed" | "confirmed";
  questions?: string[];
};

type Labels = { order: string; total: string; confirmed: string };

export default function LedgerOrder({
  p = { lines: [], total: 0, status: "proposed" },
  labels = { order: "অর্ডার", total: "মোট", confirmed: "নিশ্চিত" },
}: {
  p?: Proposal;
  labels?: Labels;
}) {
  return (
    <div className="relative mt-[40px]">
      <div className="row text-sm text-[var(--ink-soft)]">{labels.order}</div>

      {p.lines.map((l, i) => (
        <div
          key={`${l.name}-${i}`}
          className="row grid grid-cols-[1fr_auto_4.5rem] gap-3 text-xl"
        >
          <span className="truncate">{l.name}</span>
          <span>{l.qty}</span>
          <span className="text-right tabular-nums">
            {l.amount === null ? "—" : `₹${l.amount}`}
          </span>
        </div>
      ))}

      {p.questions?.map((q) => (
        <div key={q} className="row truncate text-xl text-[var(--danger)]">
          ? {q}
        </div>
      ))}

      <div className="row relative grid grid-cols-[1fr_4.5rem] gap-3 border-t-4 border-double border-[var(--ink)] text-xl">
        <span>{labels.total}</span>
        <span className="text-right tabular-nums">{`₹${p.total}`}</span>
        {p.status === "confirmed" && (
          <div className="stamp absolute right-[6.5rem] top-[-2px]">{labels.confirmed}</div>
        )}
      </div>
    </div>
  );
}
