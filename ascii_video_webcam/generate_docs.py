"""Generator dokumentasi HTML untuk proyek ASCII Video/Webcam.
"""

import ast
from typing import List, Dict, Any


def parse_functions(path: str) -> List[Dict[str, Any]]:
    """Purpose
    Mengurai fungsi dalam file Python dan mengambil nama, docstring, serta potongan kode.
    
    Parameters
    path: Lokasi file Python yang akan diparse.
    
    Return value
    List dict berisi informasi fungsi: name, doc, code.
    """
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    lines = source.splitlines()
    out: List[Dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node) or ""
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno) - 1
            code = "\n".join(lines[start:end + 1])
            out.append({"name": node.name, "doc": doc, "code": code})
    return out


def build_html(title: str, overview: str, how_it_works: str, functions: List[Dict[str, Any]]) -> str:
    """Purpose
    Menyusun HTML sederhana berisi ringkasan aplikasi, cara kerja, dan detail fungsi.
    
    Parameters
    title: Judul dokumentasi.
    overview: Ringkasan masalah yang diselesaikan aplikasi.
    how_it_works: Penjelasan tingkat tinggi alur kerja.
    functions: Informasi fungsi (name, doc, code).
    
    Return value
    String HTML final siap tulis ke file.
    """
    css = """
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; line-height: 1.6; }
      h1 { font-size: 24px; margin-bottom: 8px; }
      h2 { font-size: 20px; margin-top: 24px; }
      pre { background: #f5f5f5; padding: 12px; overflow: auto; }
      .fn { border-left: 4px solid #ccc; padding-left: 12px; margin-bottom: 16px; }
      .meta { color: #333; }
      details { margin-top: 8px; }
    </style>
    """
    parts: List[str] = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>{}</title>{}</head><body>".format(title, css),
        "<h1>{}</h1>".format(title),
        "<h2>Application Overview</h2>",
        "<p class='meta'>{}</p>".format(overview),
        "<h2>How It Works</h2>",
        "<p class='meta'>{}</p>".format(how_it_works),
        "<h2>CLI Options</h2>",
        "<ul>",
        "<li><b>-v, --video</b>: Path file video</li>",
        "<li><b>-c, --camera</b>: Indeks webcam (default 0)</li>",
        "<li><b>-w, --width</b>: Lebar ASCII art</li>",
        "<li><b>--fps</b>: Batas FPS streaming</li>",
        "<li><b>--charset</b>: Pilih 'simple' atau 'dense', atau string karakter custom</li>",
        "<li><b>--gamma</b>: Koreksi gamma untuk kontras (contoh 0.8–1.2)</li>",
        "<li><b>--invert</b>: Balik terang-gelap</li>",
        "<li><b>--dither</b>: Aktifkan dithering untuk detail di lebar kecil</li>",
        "<li><b>--clarity</b>: Tingkatkan kejelasan (CLAHE + sharpen)</li>",
        "<li><b>--fit</b>: Sesuaikan lebar otomatis dengan lebar terminal</li>",
        "<li><b>--face</b>: Deteksi wajah dan tingkatkan area wajah</li>",
        "<li><b>--face-strong</b>: Mode wajah lebih agresif</li>",
        "</ul>",
        "<h2>Functions</h2>",
    ]
    for fn in functions:
        parts.append("<div class='fn'>")
        parts.append("<h3>{}</h3>".format(fn["name"]))
        if fn["doc"]:
            parts.append("<pre>{}</pre>".format(fn["doc"]))
        parts.append("<details><summary>Code Snippet</summary>")
        parts.append("<pre>{}</pre>".format(fn["code"]))
        parts.append("</details>")
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def generate_docs(main_path: str = "main.py", output_path: str = "docs.html") -> str:
    """Purpose
    Menghasilkan docs.html dari main.py.
    
    Parameters
    main_path: Path file sumber utama.
    output_path: Path file HTML output.
    
    Return value
    Path file HTML yang dihasilkan.
    """
    functions = parse_functions(main_path)
    overview = (
        "Aplikasi mengubah video/webcam menjadi ASCII art real-time di terminal. "
        "Menggunakan OpenCV untuk menangkap frame dan pemetaan sederhana ke karakter ASCII."
    )
    how_it_works = (
        "Ambil frame → konversi grayscale → resize sesuai rasio karakter → peta ke karakter ASCII → cetak. "
        "Video menggunakan VideoCapture path, webcam menggunakan indeks kamera."
    )
    html = build_html("ASCII Video/Webcam Docs", overview, how_it_works, functions)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


if __name__ == "__main__":
    path = generate_docs()
    print(f"Dokumentasi dibuat: {path}")
