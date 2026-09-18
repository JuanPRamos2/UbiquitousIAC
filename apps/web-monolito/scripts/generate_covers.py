#!/usr/bin/env python3
"""Generate simple book-cover PNGs for the library seed."""
from pathlib import Path
import subprocess
import tempfile
import xml.sax.saxutils as sax

OUT = Path("/home/bold/Documents/Integracion/library/uploads")
OUT.mkdir(parents=True, exist_ok=True)

BOOKS = [
    ("9780134444245", "Cloud Computing", "Thomas Erl", "#0f4c81"),
    ("9780307474728", "Cien anos de soledad", "Garcia Marquez", "#7c2d12"),
    ("9780132350884", "Clean Code", "Robert C. Martin", "#14532d"),
    ("9780062316097", "Sapiens", "Yuval Noah Harari", "#1e1b4b"),
    ("9780307389732", "El amor en los tiempos del colera", "Garcia Marquez", "#9a3412"),
    ("9781501117015", "La casa de los espiritus", "Isabel Allende", "#831843"),
    ("9788437604572", "Rayuela", "Julio Cortazar", "#1e3a5f"),
    ("9780802133908", "Pedro Paramo", "Juan Rulfo", "#44403c"),
    ("9780451524935", "1984", "George Orwell", "#111827"),
    ("9780135957059", "The Pragmatic Programmer", "Hunt y Thomas", "#0e7490"),
    ("9781449373320", "Designing Data-Intensive Apps", "Martin Kleppmann", "#1d4ed8"),
    ("9781617293726", "Kubernetes in Action", "Marko Luksa", "#326ce5"),
    ("9781491929124", "Site Reliability Engineering", "Beyer y otros", "#b45309"),
    ("9781942788294", "The Phoenix Project", "Gene Kim", "#9f1239"),
    ("9780134757599", "Refactoring", "Martin Fowler", "#365314"),
    ("9780321125217", "Domain-Driven Design", "Eric Evans", "#4c1d95"),
    ("9788420412146", "Don Quijote de la Mancha", "Cervantes", "#713f12"),
    ("9780802130303", "Ficciones", "Jorge Luis Borges", "#1c1917"),
    ("9780385420174", "Como agua para chocolate", "Laura Esquivel", "#b91c1c"),
    ("9789681603021", "El laberinto de la soledad", "Octavio Paz", "#3f3f46"),
    ("9780553380163", "A Brief History of Time", "Stephen Hawking", "#0c4a6e"),
    ("9780374533557", "Thinking, Fast and Slow", "Daniel Kahneman", "#334155"),
    ("9780307887894", "The Lean Startup", "Eric Ries", "#0369a1"),
    ("9780735211292", "Atomic Habits", "James Clear", "#166534"),
    ("9780465050659", "The Design of Everyday Things", "Don Norman", "#6b21a8"),
    ("9780262033848", "Introduction to Algorithms", "Cormen y otros", "#1e293b"),
    ("9780132126953", "Computer Networks", "Tanenbaum", "#0f766e"),
    ("9781118063330", "Operating System Concepts", "Silberschatz", "#7f1d1d"),
    ("9780073523323", "Database System Concepts", "Silberschatz", "#1e40af"),
    ("9781593279288", "Python Crash Course", "Eric Matthes", "#ca8a04"),
]

def wrap(title, width=18):
    words = title.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:5] or [title[:width]]

for isbn, title, author, color in BOOKS:
    lines = wrap(title)
    text_nodes = []
    start_y = 130 - (len(lines) - 1) * 16
    for i, line in enumerate(lines):
        y = start_y + i * 32
        text_nodes.append(
            f'<text x="120" y="{y}" text-anchor="middle" font-family="Georgia, serif" font-size="20" font-weight="700" fill="#f8fafc">{sax.escape(line)}</text>'
        )
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="360" viewBox="0 0 240 360">
  <rect width="240" height="360" fill="{color}"/>
  <rect x="14" y="14" width="212" height="332" fill="none" stroke="#f8fafc" stroke-width="2" opacity="0.35"/>
  <rect x="0" y="0" width="12" height="360" fill="#000000" opacity="0.25"/>
  {"".join(text_nodes)}
  <line x1="40" y1="280" x2="200" y2="280" stroke="#f8fafc" stroke-width="1" opacity="0.4"/>
  <text x="120" y="310" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#e2e8f0">{sax.escape(author)}</text>
</svg>
'''
    svg_path = Path(tempfile.gettempdir()) / f"cover-{isbn}.svg"
    png_path = OUT / f"cover-{isbn}.png"
    svg_path.write_text(svg, encoding="utf-8")
    subprocess.check_call(["rsvg-convert", "-w", "480", "-h", "720", str(svg_path), "-o", str(png_path)])
    print(png_path.name, png_path.stat().st_size)

print("covers", len(list(OUT.glob("cover-*.png"))))
