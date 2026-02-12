"""Streaming ASCII art dari video dan webcam.

Aplikasi ini membaca frame video atau webcam, mengonversi ke grayscale,
menskalakan sesuai rasio karakter, lalu memetakan ke karakter ASCII dan
menampilkan secara real-time di terminal.
"""

import os
import sys
import time
from typing import List, Tuple, Optional
import shutil

_FACE_CASCADE = None


def resize_pixels(pixels: List[List[int]], new_width: int, ratio: float = 0.43) -> List[List[int]]:
    """Purpose
    Mengubah ukuran matriks piksel 2D ke lebar baru, menyesuaikan tinggi
    dengan rasio karakter monospaced.
    
    Parameters
    pixels: Matriks piksel 2D bernilai 0–255.
    new_width: Lebar baru untuk ASCII art.
    ratio: Rasio tinggi-karakter terhadap lebar (default 0.43).
    
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
    new_height = max(1, int(orig_h * scale * ratio))
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
    Menerapkan Floyd–Steinberg dithering pada piksel grayscale untuk menjaga detail di lebar kecil.
    
    Parameters
    pixels: Matriks piksel 2D bernilai 0–255.
    levels: Jumlah tingkat kuantisasi sesuai panjang charset.
    
    Return value
    Matriks piksel 2D yang telah didither.
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


def map_to_ascii(
    pixels: List[List[int]],
    charset: str = " .:-=+*#%@",
    gamma: float = 1.0,
    invert: bool = False,
    dither: bool = False,
) -> List[str]:
    """Purpose
    Memetakan nilai 0–255 ke karakter ASCII dan menghasilkan baris teks.
    
    Parameters
    pixels: Matriks piksel 2D bernilai 0–255.
    charset: String palet karakter dari terang ke gelap.
    
    Return value
    List baris string ASCII art.
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


def frame_to_pixels(frame) -> List[List[int]]:
    """Purpose
    Mengonversi frame numpy (BGR) dari OpenCV menjadi matriks 2D grayscale.
    
    Parameters
    frame: Array numpy frame BGR dari OpenCV.
    
    Return value
    Matriks piksel 2D bernilai 0–255.
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("Memerlukan 'opencv-python'. Instal dengan: pip install opencv-python") from e
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    rows: List[List[int]] = []
    for y in range(h):
        rows.append(list(gray[y, :]))
    return rows


def enhance_gray_array(gray):
    """Purpose
    Meningkatkan kejelasan citra grayscale dan mengembalikan array numpy.
    
    Parameters
    gray: Array numpy grayscale 2D.
    
    Return value
    Array numpy grayscale 2D yang telah ditingkatkan.
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return gray
    clahe = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    smooth = cv2.bilateralFilter(eq, d=5, sigmaColor=60, sigmaSpace=60)
    blur = cv2.GaussianBlur(smooth, (0, 0), sigmaX=1.2)
    sharp = cv2.addWeighted(smooth, 1.8, blur, -0.8, 0)
    edges = cv2.Canny(eq, 40, 120)
    edges = cv2.GaussianBlur(edges, (0, 0), sigmaX=1.0)
    sharp = cv2.addWeighted(sharp, 1.0, edges, 0.25, 0)
    return sharp


def enhance_gray(gray) -> List[List[int]]:
    """Purpose
    Meningkatkan kejelasan citra grayscale dengan CLAHE dan penajaman ringan.
    
    Parameters
    gray: Array numpy grayscale 2D.
    
    Return value
    Matriks piksel 2D bernilai 0–255 setelah peningkatan.
    """
    sharp = enhance_gray_array(gray)
    h, w = sharp.shape
    out: List[List[int]] = []
    for y in range(h):
        out.append(list(sharp[y, :]))
    return out


def get_face_cascade():
    """Purpose
    Mengambil cascade classifier wajah dan menyimpannya untuk dipakai ulang.
    
    Parameters
    None
    
    Return value
    CascadeClassifier atau None jika tidak tersedia.
    """
    global _FACE_CASCADE
    try:
        import cv2  # type: ignore
    except Exception:
        return None
    if _FACE_CASCADE is None:
        path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            return None
        _FACE_CASCADE = cascade
    return _FACE_CASCADE


def detect_faces(gray) -> List[Tuple[int, int, int, int]]:
    """Purpose
    Mendeteksi wajah pada citra grayscale.
    
    Parameters
    gray: Array numpy grayscale 2D.
    
    Return value
    List tuple (x, y, w, h) untuk setiap wajah.
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return []
    cascade = get_face_cascade()
    if cascade is None:
        return []
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]


def enhance_faces(gray, strong: bool = False):
    """Purpose
    Meningkatkan kontras pada area wajah agar lebih jelas di ASCII.
    
    Parameters
    gray: Array numpy grayscale 2D.
    strong: Aktifkan peningkatan yang lebih agresif.
    
    Return value
    Array numpy grayscale 2D dengan wajah yang ditonjolkan.
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return gray
    faces = detect_faces(gray)
    if not faces:
        return gray
    out = gray.copy()
    h, w = out.shape
    for x, y, fw, fh in faces:
        pad = int(0.2 * max(fw, fh))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + fw + pad)
        y1 = min(h, y + fh + pad)
        roi = out[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        if strong:
            clahe = cv2.createCLAHE(clipLimit=3.4, tileGridSize=(6, 6))
        else:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6))
        roi_eq = clahe.apply(roi)
        roi_smooth = cv2.bilateralFilter(roi_eq, d=5, sigmaColor=50, sigmaSpace=50)
        roi_blur = cv2.GaussianBlur(roi_smooth, (0, 0), sigmaX=0.9 if not strong else 0.7)
        roi_sharp = cv2.addWeighted(roi_smooth, 1.5 if not strong else 1.8, roi_blur, -0.5 if not strong else -0.8, 0)
        roi_final = cv2.convertScaleAbs(roi_sharp, alpha=1.15 if not strong else 1.25, beta=6 if not strong else 10)
        blend = 0.55 if not strong else 0.7
        roi_mix = cv2.addWeighted(roi, 1.0 - blend, roi_final, blend, 0)
        out[y0:y1, x0:x1] = roi_mix
    return out


def process_gray(gray, clarity: bool = False, face: bool = False, face_strong: bool = False) -> List[List[int]]:
    """Purpose
    Memproses grayscale dengan clarity dan face enhancement jika diaktifkan.
    
    Parameters
    gray: Array numpy grayscale 2D.
    clarity: Aktifkan peningkatan kejelasan global.
    face: Aktifkan deteksi wajah dan peningkatan lokal.
    face_strong: Aktifkan peningkatan wajah yang lebih agresif.
    
    Return value
    Matriks piksel 2D bernilai 0–255.
    """
    try:
        import cv2  # type: ignore
    except Exception:
        return [list(row) for row in gray]
    work = gray
    if clarity:
        work = enhance_gray_array(work)
    if face or face_strong:
        work = enhance_faces(work, strong=face_strong)
    h, w = work.shape
    out: List[List[int]] = []
    for y in range(h):
        out.append(list(work[y, :]))
    return out


def get_terminal_width(default_width: int = 80) -> int:
    """Purpose
    Mengambil lebar terminal dengan fallback nilai default.
    
    Parameters
    default_width: Nilai fallback jika gagal mendeteksi.
    
    Return value
    Lebar terminal (kolom).
    """
    try:
        ts = shutil.get_terminal_size(fallback=(default_width, 24))
        return int(ts.columns)
    except Exception:
        return default_width


def render_ascii(lines: List[str]) -> str:
    """Purpose
    Menggabungkan baris ASCII menjadi satu string siap cetak.
    
    Parameters
    lines: List baris ASCII.
    
    Return value
    String gabungan dengan newline.
    """
    return "\n".join(lines)


def print_frame(lines: List[str]) -> None:
    """Purpose
    Mencetak ASCII art ke terminal dengan membersihkan layar terlebih dahulu.
    
    Parameters
    lines: List baris ASCII.
    
    Return value
    None
    """
    sys.stdout.write("\x1b[H\x1b[2J")
    sys.stdout.write(render_ascii(lines) + "\n")
    sys.stdout.flush()


def stream_video_ascii(path: str, width: int = 80, fps_limit: Optional[float] = None, charset: str = " .:-=+*#%@", gamma: float = 1.0, invert: bool = False, dither: bool = False, clarity: bool = False, face: bool = False, face_strong: bool = False) -> None:
    """Purpose
    Membaca file video dan menampilkan ASCII art setiap frame di terminal.
    
    Parameters
    path: Path file video.
    width: Lebar ASCII art.
    fps_limit: Batas FPS untuk throttling (None artinya mengikuti video).
    charset: Palet karakter dari terang ke gelap.
    face: Aktifkan deteksi wajah untuk menonjolkan area wajah.
    face_strong: Peningkatan wajah yang lebih agresif.
    
    Return value
    None
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("Memerlukan 'opencv-python'. Instal dengan: pip install opencv-python") from e
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Tidak dapat membuka video: {path}")
    delay = 0.0
    if fps_limit and fps_limit > 0:
        delay = 1.0 / fps_limit
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            try:
                import cv2  # type: ignore
            except Exception:
                pass
            gray = None
            try:
                import cv2  # type: ignore
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            except Exception:
                pass
            if gray is not None:
                pixels = process_gray(gray, clarity=clarity, face=face, face_strong=face_strong)
            else:
                pixels = frame_to_pixels(frame)
            resized = resize_pixels(pixels, width)
            lines = map_to_ascii(resized, charset=charset, gamma=gamma, invert=invert, dither=dither)
            print_frame(lines)
            if delay > 0:
                time.sleep(delay)
    finally:
        cap.release()


def stream_webcam_ascii(camera_index: int = 0, width: int = 80, fps_limit: float = 24.0, charset: str = " .:-=+*#%@", gamma: float = 1.0, invert: bool = False, dither: bool = False, clarity: bool = True, fit: bool = False, face: bool = False, face_strong: bool = False) -> None:
    """Purpose
    Menangkap webcam secara real-time dan menampilkan ASCII art di terminal.
    
    Parameters
    camera_index: Indeks kamera (default 0).
    width: Lebar ASCII art.
    fps_limit: Batas FPS untuk throttling.
    charset: Palet karakter dari terang ke gelap.
    face: Aktifkan deteksi wajah untuk menonjolkan area wajah.
    face_strong: Peningkatan wajah yang lebih agresif.
    
    Return value
    None
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise RuntimeError("Memerlukan 'opencv-python'. Instal dengan: pip install opencv-python") from e
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Tidak dapat membuka kamera index {camera_index}")
    delay = 1.0 / max(1e-6, fps_limit)
    if fit:
        tw = get_terminal_width(80)
        width = max(20, tw - 2)
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            try:
                import cv2  # type: ignore
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            except Exception:
                gray = None
            if gray is not None:
                pixels = process_gray(gray, clarity=clarity, face=face, face_strong=face_strong)
            else:
                pixels = frame_to_pixels(frame)
            resized = resize_pixels(pixels, width)
            lines = map_to_ascii(resized, charset=charset, gamma=gamma, invert=invert, dither=dither)
            print_frame(lines)
            time.sleep(delay)
    finally:
        cap.release()


def main() -> None:
    """Purpose
    Entry point CLI: jalankan streaming ASCII dari video atau webcam.
    
    Parameters
    None
    
    Return value
    None
    """
    import argparse
    parser = argparse.ArgumentParser(description="Streaming ASCII dari video/webcam.")
    parser.add_argument("-v", "--video", type=str, default="", help="Path file video (kosong untuk webcam)")
    parser.add_argument("-c", "--camera", type=int, default=0, help="Indeks webcam jika video kosong")
    parser.add_argument("-w", "--width", type=int, default=80, help="Lebar ASCII art")
    parser.add_argument("--fps", type=float, default=24.0, help="Batas FPS untuk streaming")
    parser.add_argument("--charset", type=str, default=" .:-=+*#%@", help="Palet karakter atau kata kunci: simple|dense")
    parser.add_argument("--gamma", type=float, default=0.9, help="Koreksi gamma untuk kontras (default 0.9)")
    parser.add_argument("--invert", action="store_true", help="Balik terang-gelap sebelum pemetaan")
    parser.add_argument("--dither", action="store_true", help="Aktifkan dithering agar detail lebih jelas")
    parser.add_argument("--clarity", action="store_true", help="Tingkatkan kejelasan (CLAHE + sharpen)")
    parser.add_argument("--fit", action="store_true", help="Sesuaikan lebar dengan lebar terminal")
    parser.add_argument("--face", action="store_true", help="Deteksi wajah dan tingkatkan area wajah")
    parser.add_argument("--face-strong", action="store_true", help="Mode wajah lebih agresif")
    args = parser.parse_args()
    if args.video:
        path = args.video
        if not os.path.isabs(path):
            script_dir = os.path.dirname(__file__)
            rp = os.path.join(script_dir, path)
            if os.path.exists(rp):
                path = rp
        cs = args.charset
        if cs.lower() == "simple":
            cs = " .:-=+*#%@"
        elif cs.lower() == "dense":
            cs = " .'`^\",:;Il!i~+_-?][}{1)(|\\/*tfjrxnczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
        stream_video_ascii(path, width=args.width, fps_limit=args.fps, charset=cs, gamma=args.gamma, invert=args.invert, dither=args.dither, clarity=args.clarity, face=args.face, face_strong=args.face_strong)
    else:
        cs = args.charset
        if cs.lower() == "simple":
            cs = " .:-=+*#%@"
        elif cs.lower() == "dense":
            cs = " .'`^\",:;Il!i~+_-?][}{1)(|\\/*tfjrxnczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
        stream_webcam_ascii(camera_index=args.camera, width=args.width, fps_limit=args.fps, charset=cs, gamma=args.gamma, invert=args.invert, dither=args.dither, clarity=args.clarity, fit=args.fit, face=args.face, face_strong=args.face_strong)


if __name__ == "__main__":
    main()

