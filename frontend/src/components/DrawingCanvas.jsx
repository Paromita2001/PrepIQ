import { useRef, useState, useEffect } from "react";

const COLORS = [
  { label: "White",  hex: "#e5e7eb" },
  { label: "Red",    hex: "#f87171" },
  { label: "Blue",   hex: "#60a5fa" },
  { label: "Green",  hex: "#4ade80" },
  { label: "Yellow", hex: "#fbbf24" },
];

const TOOLS = [
  { id: "pen",    icon: "✏️", title: "Freehand Pen" },
  { id: "line",   icon: "╱",  title: "Straight Line" },
  { id: "rect",   icon: "□",  title: "Rectangle" },
  { id: "circle", icon: "○",  title: "Circle / Ellipse" },
  { id: "eraser", icon: "⌫",  title: "Eraser" },
];

const WIDTHS = [
  { size: 1, dot: 3 },
  { size: 2, dot: 5 },
  { size: 4, dot: 8 },
];

const BG = "#111827";

export default function DrawingCanvas({ initialData, onChange }) {
  const canvasRef  = useRef(null);
  const [tool,  setTool]  = useState("pen");
  const [color, setColor] = useState("#e5e7eb");
  const [width, setWidth] = useState(2);
  const isDrawing  = useRef(false);
  const startPos   = useRef({ x: 0, y: 0 });
  const snapshot   = useRef(null);   // canvas snapshot for shape preview
  const history    = useRef([]);     // for undo

  /* ── helpers ── */
  const ctx = () => canvasRef.current?.getContext("2d");

  const getPos = (e) => {
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const src    = e.touches?.[0] || e;
    return {
      x: (src.clientX - rect.left) * (canvas.width  / rect.width),
      y: (src.clientY - rect.top)  * (canvas.height / rect.height),
    };
  };

  const pushHistory = () => {
    const c = canvasRef.current;
    history.current.push(ctx().getImageData(0, 0, c.width, c.height));
    if (history.current.length > 40) history.current.shift();
  };

  const notify = () => onChange?.(canvasRef.current.toDataURL("image/png"));

  /* ── init + restore ── */
  useEffect(() => {
    const canvas = canvasRef.current;
    const c = canvas.getContext("2d");
    c.fillStyle = BG;
    c.fillRect(0, 0, canvas.width, canvas.height);

    if (initialData) {
      const img = new Image();
      img.onload = () => c.drawImage(img, 0, 0);
      img.src    = initialData;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── draw events ── */
  const onDown = (e) => {
    e.preventDefault();
    const pos = getPos(e);
    pushHistory();
    snapshot.current = ctx().getImageData(0, 0, canvasRef.current.width, canvasRef.current.height);
    startPos.current = pos;
    isDrawing.current = true;

    if (tool === "pen" || tool === "eraser") {
      const c = ctx();
      c.beginPath();
      c.moveTo(pos.x, pos.y);
    }
  };

  const onMove = (e) => {
    if (!isDrawing.current) return;
    e.preventDefault();
    const pos = getPos(e);
    const c   = ctx();

    c.lineCap    = "round";
    c.lineJoin   = "round";
    c.lineWidth  = tool === "eraser" ? width * 6 : width;
    c.strokeStyle = tool === "eraser" ? BG : color;

    if (tool === "pen" || tool === "eraser") {
      c.lineTo(pos.x, pos.y);
      c.stroke();
      return;
    }

    /* shape tools: restore snapshot then draw preview */
    c.putImageData(snapshot.current, 0, 0);
    c.strokeStyle = color;
    c.lineWidth   = width;
    c.beginPath();

    const sx = startPos.current.x, sy = startPos.current.y;

    if (tool === "line") {
      c.moveTo(sx, sy);
      c.lineTo(pos.x, pos.y);
    } else if (tool === "rect") {
      c.strokeRect(sx, sy, pos.x - sx, pos.y - sy);
    } else if (tool === "circle") {
      const rx = Math.abs(pos.x - sx) / 2;
      const ry = Math.abs(pos.y - sy) / 2;
      c.ellipse(sx + (pos.x - sx) / 2, sy + (pos.y - sy) / 2, rx, ry, 0, 0, 2 * Math.PI);
    }
    c.stroke();
  };

  const onUp = (e) => {
    if (!isDrawing.current) return;
    e.preventDefault();
    isDrawing.current = false;
    notify();
  };

  /* ── actions ── */
  const undo = () => {
    if (!history.current.length) return;
    ctx().putImageData(history.current.pop(), 0, 0);
    notify();
  };

  const clear = () => {
    pushHistory();
    const canvas = canvasRef.current;
    const c = ctx();
    c.clearRect(0, 0, canvas.width, canvas.height);
    c.fillStyle = BG;
    c.fillRect(0, 0, canvas.width, canvas.height);
    onChange?.(null);
  };

  return (
    <div className="rounded-lg border border-purple-900 bg-gray-900 p-3 space-y-2.5">
      {/* Title row */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-purple-400 uppercase tracking-wide">
          📐 Drawing Tool — geometry, ray diagrams, circuits
        </p>
        <div className="flex gap-2">
          <button onClick={undo}  className="text-xs px-2.5 py-1 rounded bg-gray-800 border border-gray-700 text-gray-400 hover:text-white transition-colors">↩ Undo</button>
          <button onClick={clear} className="text-xs px-2.5 py-1 rounded bg-gray-800 border border-gray-700 text-red-400  hover:text-red-300 transition-colors">✕ Clear</button>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Tool buttons */}
        <div className="flex gap-1">
          {TOOLS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTool(t.id)}
              title={t.title}
              className={`w-9 h-9 rounded text-sm border transition-colors ${
                tool === t.id
                  ? "bg-purple-700 border-purple-500 text-white"
                  : "bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500"
              }`}
            >
              {t.icon}
            </button>
          ))}
        </div>

        <div className="w-px h-6 bg-gray-700" />

        {/* Colors */}
        <div className="flex gap-1.5">
          {COLORS.map((c) => (
            <button
              key={c.hex}
              onClick={() => setColor(c.hex)}
              title={c.label}
              className={`w-6 h-6 rounded-full border-2 transition-all ${
                color === c.hex ? "border-white scale-125" : "border-transparent opacity-70 hover:opacity-100"
              }`}
              style={{ backgroundColor: c.hex }}
            />
          ))}
        </div>

        <div className="w-px h-6 bg-gray-700" />

        {/* Stroke width */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500">Size</span>
          {WIDTHS.map((w) => (
            <button
              key={w.size}
              onClick={() => setWidth(w.size)}
              className={`w-8 h-8 rounded flex items-center justify-center border transition-colors ${
                width === w.size ? "bg-purple-800 border-purple-600" : "bg-gray-800 border-gray-700"
              }`}
            >
              <div
                className="rounded-full bg-gray-200"
                style={{ width: w.dot, height: w.dot }}
              />
            </button>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={680}
        height={340}
        className="w-full rounded-lg touch-none"
        style={{ cursor: tool === "eraser" ? "cell" : "crosshair", background: BG }}
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={onUp}
        onMouseLeave={onUp}
        onTouchStart={onDown}
        onTouchMove={onMove}
        onTouchEnd={onUp}
      />
      <p className="text-xs text-gray-600">
        Tip: Use <strong className="text-gray-500">Line</strong> for angles &amp; construction lines · <strong className="text-gray-500">Circle</strong> for arcs · <strong className="text-gray-500">Rect</strong> for circuit boxes.
        Drawing is saved with your answer.
      </p>
    </div>
  );
}
