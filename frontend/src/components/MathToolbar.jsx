const GROUPS = [
  {
    label: "Algebra",
    syms: ["√", "²", "³", "⁴", "±", "×", "÷", "≠", "≈", "≤", "≥", "∞", "π", "α", "β", "θ"],
  },
  {
    label: "Geometry",
    syms: ["∠", "△", "⊥", "∥", "≅", "~", "°", "□", "⊙", "↔", "→", "⃗"],
  },
  {
    label: "Proof",
    syms: ["∴", "∵", "⇒", "⟹", "∈", "∉", "∩", "∪"],
  },
  {
    label: "Fractions",
    syms: ["½", "⅓", "⅔", "¼", "¾", "⅛", "⅜"],
  },
];

export default function MathToolbar({ textareaRef, value, onChange }) {
  const insert = (sym) => {
    const el = textareaRef?.current;
    const cur = value || "";
    if (!el) {
      onChange(cur + sym);
      return;
    }
    const start = el.selectionStart ?? cur.length;
    const end   = el.selectionEnd   ?? cur.length;
    const next  = cur.slice(0, start) + sym + cur.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.selectionStart = el.selectionEnd = start + sym.length;
      el.focus();
    });
  };

  return (
    <div className="rounded-lg border border-blue-900 bg-gray-900 p-2.5 space-y-2">
      <p className="text-xs font-semibold text-blue-400 uppercase tracking-wide">∑ Math Symbols — click to insert at cursor</p>
      {GROUPS.map((g) => (
        <div key={g.label} className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-gray-600 w-16 shrink-0">{g.label}</span>
          {g.syms.map((sym) => (
            <button
              key={sym}
              type="button"
              onClick={() => insert(sym)}
              className="px-2 py-1 rounded bg-gray-800 hover:bg-blue-900 text-gray-200 hover:text-blue-100 text-sm font-mono transition-colors border border-gray-700 hover:border-blue-700 select-none"
            >
              {sym}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
