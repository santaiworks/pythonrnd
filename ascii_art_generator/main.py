"""Aplikasi konversi gambar menjadi ASCII art.

Aplikasi ini fokus pada kesederhanaan: tanpa dependency eksternal untuk data
contoh dengan format PGM (P2). Jika Pillow tersedia, Anda bisa memproses PNG/JPG.
"""

from typing import List, Tuple
import os
import shutil


def read_pgm(path: str) -> Tuple[List[List[int]], int, int]:
    """Purpose
    Membaca file gambar grayscale berformat PGM ASCII (P2) dan mengembalikan
    matriks piksel beserta lebar dan tinggi.
    
    Parameters
    path: Lokasi file PGM (format P2, ASCII).
    
    Return value
    (pixels, width, height) di mana pixels adalah list 2D berisi nilai 0–255.
    """
    tokens: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.extend(line.split())
    if not tokens or tokens[0] != "P2":
        raise ValueError("File PGM harus berformat ASCII P2")
    idx = 1
    width = int(tokens[idx]); idx += 1
    height = int(tokens[idx]); idx += 1
    maxval = int(tokens[idx]); idx += 1
    if maxval <= 0:
        raise ValueError("Nilai maxval tidak valid pada PGM")
    expected = width * height
    values = list(map(int, tokens[idx:idx + expected]))
    if len(values) != expected:
        raise ValueError("Jumlah piksel tidak sesuai dimensi PGM")
    pixels: List[List[int]] = []
    for r in range(height):
        row = values[r * width:(r + 1) * width]
        pixels.append(row)
    return pixels, width, height


def resize_pixels(pixels: List[List[int]], new_width: int) -> List[List[int]]:
    """Purpose
    Mengubah ukuran matriks piksel secara sederhana (nearest-neighbor) agar
    cocok untuk render ASCII pada lebar tertentu.
    
    Parameters
    pixels: Matriks piksel 2D bernilai 0–255.
    new_width: Lebar baru yang diinginkan untuk ASCII art.
    
    Return value
    Matriks piksel 2D yang telah diubah ukurannya.
    """
    if new_width < 1:
        raise ValueError("new_width minimal 1")
    orig_h = len(pixels)
    orig_w = len(pixels[0]) if orig_h > 0 else 0
    if orig_w == 0 or orig_h == 0:
        return []
    scale = new_width / float(orig_w)
    new_height = max(1, int(orig_h * scale * 0.43))
    resized: List[List[int]] = []
    for y in range(new_height):
        src_y = min(orig_h - 1, int(y / new_height * orig_h))
        row: List[int] = []
        for x in range(new_width):
            src_x = min(orig_w - 1, int(x / new_width * orig_w))
            row.append(pixels[src_y][src_x])
        resized.append(row)
    return resized


def dither_pixels(pixels: List[List[int]], levels: int) -> List[List[int]]:
    """Purpose
    Menerapkan Floyd–Steinberg dithering pada piksel grayscale untuk menjaga
    detail pada resolusi kecil.
    
    Parameters
    pixels: Matriks piksel 2D bernilai 0–255.
    levels: Jumlah tingkat kuantisasi sesuai panjang charset.
    
    Return value
    Matriks piksel 2D yang sudah didither dalam rentang 0–255.
    """
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    if h == 0 or w == 0 or levels < 2:
        return pixels
    step = 255.0 / float(levels - 1)
    out = [row[:] for row in pixels]
    def clamp(v: float) -> int:
        if v < 0: return 0
        if v > 255: return 255
        return int(v)
    for y in range(h):
        for x in range(w):
            old = out[y][x]
            new = round(old / step) * step
            out[y][x] = clamp(new)
            err = old - new
            if x + 1 < w:
                out[y][x + 1] = clamp(out[y][x + 1] + err * 7 / 16)
            if y + 1 < h:
                if x - 1 >= 0:
                    out[y + 1][x - 1] = clamp(out[y + 1][x - 1] + err * 3 / 16)
                out[y + 1][x] = clamp(out[y + 1][x] + err * 5 / 16)
                if x + 1 < w:
                    out[y + 1][x + 1] = clamp(out[y + 1][x + 1] + err * 1 / 16)
    return out


def get_terminal_width(default_width: int = 80) -> int:
    """Purpose
    Mengambil lebar terminal secara aman dengan fallback nilai default.
    
    Parameters
    default_width: Nilai lebar jika tidak dapat mendeteksi terminal.
    
    Return value
    Lebar terminal dalam jumlah kolom karakter.
    """
    try:
        ts = shutil.get_terminal_size(fallback=(default_width, 24))
        return int(ts.columns)
    except Exception:
        return default_width


def map_to_ascii(
    pixels: List[List[int]],
    charset: str = " .:-=+*#%@",
    gamma: float = 1.0,
    invert: bool = False,
    dither: bool = False,
) -> List[str]:
    """Purpose
    Memetakan nilai grayscale 0–255 menjadi karakter ASCII sesuai palet yang
    disediakan, lalu menghasilkan baris-baris teks.
    
    Parameters
    pixels: Matriks piksel 2D bernilai 0–255.
    charset: String palet karakter dari gelap ke terang.
    gamma: Koreksi gamma (1.0 berarti tanpa perubahan).
    invert: Membalik terang-gelap sebelum pemetaan.
    dither: Mengaktifkan dithering agar detail kecil lebih terjaga.
    
    Return value
    List baris string yang mewakili ASCII art.
    """
    if not pixels:
        return []
    if len(charset) < 2:
        raise ValueError("charset minimal 2 karakter")
    work = pixels
    if dither:
        work = dither_pixels(work, len(charset))
    lines: List[str] = []
    for row in work:
        line_chars = []
        for v in row:
            val = v / 255.0
            if invert:
                val = 1.0 - val
            if gamma > 0:
                val = pow(val, gamma)
            idx = int(val * (len(charset) - 1))
            if idx < 0:
                idx = 0
            if idx >= len(charset):
                idx = len(charset) - 1
            line_chars.append(charset[idx])
        lines.append("".join(line_chars))
    return lines


def save_ascii(lines: List[str], output_path: str) -> None:
    """Purpose
    Menyimpan ASCII art ke file teks.
    
    Parameters
    lines: List baris ASCII art.
    output_path: Lokasi file output teks.
    
    Return value
    None
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def image_to_ascii(
    input_path: str,
    output_path: str,
    width: int = 80,
    charset: str = " .:-=+*#%@",
    gamma: float = 1.0,
    invert: bool = False,
    dither: bool = False,
) -> str:
    """Purpose
    Pipeline yang mengubah gambar menjadi ASCII art. Mendukung PGM (P2) tanpa
    dependency, dan mencoba menggunakan Pillow untuk format lain bila tersedia.
    
    Parameters
    input_path: Lokasi file gambar (PGM P2 direkomendasikan untuk contoh).
    output_path: Lokasi file teks output ASCII.
    width: Lebar ASCII art yang diinginkan.
    charset: Palet karakter untuk pemetaan terang-gelap.
    gamma: Koreksi gamma untuk pengaturan kontras.
    invert: Membalik terang-gelap sebelum pemetaan.
    dither: Mengaktifkan dithering agar detail kecil lebih terjaga.
    
    Return value
    String ASCII art yang juga disimpan ke output_path.
    """
    ext = os.path.splitext(input_path.lower())[1]
    if ext == ".pgm":
        pixels, w, h = read_pgm(input_path)
        resized = resize_pixels(pixels, width)
    else:
        try:
            from PIL import Image, ImageOps  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Format non-PGM memerlukan Pillow. Instal 'Pillow' atau gunakan .pgm."
            ) from e
        img = Image.open(input_path).convert("L")
        w, h = img.size
        new_h = max(1, int(h * (width / float(w)) * 0.43))
        img = ImageOps.autocontrast(img)
        img = img.resize((width, new_h), resample=Image.BILINEAR)
        resized = [list(img.crop((0, y, width, y + 1)).getdata()) for y in range(new_h)]
    ascii_lines = map_to_ascii(resized, charset=charset, gamma=gamma, invert=invert, dither=dither)
    save_ascii(ascii_lines, output_path)
    return "\n".join(ascii_lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Konversi gambar ke ASCII art.")
    parser.add_argument(
        "-i", "--input", default="raisa.jpg", help="Path gambar (default: raisa.jpg)"
    )
    parser.add_argument(
        "-o", "--output", default="raisa_ascii.txt", help="Path output teks ASCII (default)"
    )
    parser.add_argument(
        "-w", "--width", type=int, default=80, help="Lebar ASCII art"
    )
    parser.add_argument(
        "--fit", action="store_true", default=True, help="Sesuaikan lebar dengan lebar terminal (default aktif)"
    )
    parser.add_argument(
        "--no-fit", action="store_false", dest="fit", help="Matikan penyesuaian lebar terminal"
    )
    parser.add_argument(
        "--gamma", type=float, default=1.0, help="Koreksi gamma (contoh 0.8 atau 1.2)"
    )
    parser.add_argument(
        "--invert", action="store_true", help="Balik terang-gelap sebelum pemetaan"
    )
    parser.add_argument(
        "--dither", action="store_true", help="Aktifkan dithering untuk detail di lebar kecil"
    )
    parser.add_argument(
        "--charset", type=str, default=" .:-=+*#%@", help="Palet karakter atau kata kunci: simple|dense"
    )
    args = parser.parse_args()
    script_dir = os.path.dirname(__file__)
    in_path = args.input
    if not os.path.isabs(in_path):
        rel_candidate = os.path.join(script_dir, in_path)
        if os.path.exists(rel_candidate):
            in_path = rel_candidate
    width = args.width
    if args.fit:
        term_w = get_terminal_width(80)
        width = max(20, term_w - 2)
    charset = args.charset
    if charset.lower() == "simple":
        charset = " .:-=+*#%@"
    elif charset.lower() == "dense":
        charset = " .'`^\",:;Il!i~+_-?][}{1)(|\\/*tfjrxnczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
    art = image_to_ascii(
        in_path,
        args.output,
        width,
        charset=charset,
        gamma=args.gamma,
        invert=args.invert,
        dither=args.dither,
    )
    print(art)

