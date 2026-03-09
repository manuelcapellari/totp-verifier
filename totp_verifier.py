import base64
import binascii
import io
import json
import os
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2
import fitz  # PyMuPDF
import numpy as np
import pyotp
import segno
from PIL import Image, ImageGrab, ImageTk
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


APP_GEOMETRY = "1200x860"
PDF_RENDER_DPI_LEVELS = [144, 220, 300]
IMAGE_READ_FLAGS = cv2.IMREAD_COLOR

APP_ICON_FILE = "totp_verifier_icon.ico"
SETTINGS_FILE_NAME = "totp_verifier_settings.json"
LANGUAGE_FILE_NAME = "totp_verifier_language.json"


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_external_path(filename: str) -> Path:
    return get_app_dir() / filename


def get_resource_path(filename: str) -> Path:
    external = get_external_path(filename)
    if external.exists():
        return external

    bundled = get_resource_dir() / filename
    return bundled


CONFIG_FILE = get_external_path(SETTINGS_FILE_NAME)
LANGUAGE_FILE = get_external_path(LANGUAGE_FILE_NAME)
ICON_PATH = get_resource_path(APP_ICON_FILE)


DEFAULT_STRINGS = {
    "app_title": "TOTP Verifier / QR Generator",
    "status_ready": "Bereit. Es werden keine Secrets gespeichert.",
    "source_empty": "Quelle: -",
    "status_reset": "Zurückgesetzt. Es wurden keine Secrets gespeichert.",
    "status_settings_saved": "Einstellungen gespeichert.",

    "tab_verify": "Verifizieren / Einlesen",
    "tab_generate": "QR erzeugen / PDF",

    "group_read": "Secret / QR einlesen",
    "label_totp_secret": "TOTP Secret:",
    "btn_generate_from_secret": "Code aus Secret erzeugen",
    "btn_open_qr_image_pdf": "QR aus Bild/PDF öffnen",
    "btn_capture_screen": "QR vom Bildschirm erfassen",
    "btn_reset": "Zurücksetzen",
    "group_current_code": "Aktueller TOTP-Code",
    "label_status": "Status:",
    "group_qr_info": "QR- / OTP-Informationen",
    "remaining_seconds": "Gültig für noch {seconds} Sekunden",

    "group_generate": "QR / PDF erzeugen",
    "group_preview": "QR Vorschau",
    "label_username": "Benutzername:",
    "label_password": "Kennwort:",
    "label_secret": "TOTP Secret:",
    "label_issuer": "Issuer:",
    "label_account_name": "Account Name:",
    "label_digits": "Digits:",
    "label_period": "Period:",
    "label_algorithm": "Algorithmus:",
    "group_pdf_options": "PDF Optionen",
    "chk_print_username": "Benutzername drucken",
    "chk_print_password": "Kennwort drucken",
    "chk_print_totp_label": "TOTP Token Text drucken",
    "chk_print_secret": "Secret zusätzlich als Text drucken",
    "chk_date_header": "Erstellungsdatum in Kopfzeile",
    "chk_date_footer": "Erstellungsdatum in Fußzeile",
    "chk_mask_password": "Kennwort im PDF maskieren",
    "chk_unlock_advanced": "Erweiterte TOTP-Parameter bearbeiten",
    "btn_generate_qr": "QR erzeugen",
    "btn_save_png": "QR als PNG speichern",
    "btn_export_pdf": "Als PDF ausgeben",
    "btn_save_checkbox_settings": "Einstellungen speichern",
    "preview_empty": "Noch kein QR erzeugt",

    "dialog_open_image_pdf_title": "Bild oder PDF mit QR-Code auswählen",
    "filetype_supported": "Unterstützte Dateien",
    "filetype_images": "Bilddateien",
    "filetype_pdf": "PDF-Dateien",
    "filetype_all": "Alle Dateien",
    "dialog_save_png_title": "QR-Code als PNG speichern",
    "dialog_save_pdf_title": "PDF speichern",
    "filetype_png": "PNG-Datei",
    "filetype_pdf_single": "PDF-Datei",

    "pdf_no_pages": "Die PDF enthält keine Seiten.",
    "pdf_page_prompt_title": "PDF Seite wählen",
    "pdf_page_prompt_text": "Die PDF hat {count} Seiten.\nAuf welcher Seite befindet sich der QR-Code?",
    "pdf_selection_cancelled": "PDF-Auswahl abgebrochen.",

    "msg_secret_loaded": "TOTP-Secret erfolgreich übernommen.",
    "msg_qr_loaded": "QR-Code erfolgreich eingelesen.",
    "msg_multiple_qr": "{count} QR-Inhalte erkannt. Der erste passende Eintrag wird verwendet.",
    "msg_screenshot_cancelled": "Screenshot-Erfassung abgebrochen.",
    "msg_qr_generated": "QR-Code erfolgreich erzeugt.",
    "msg_qr_saved": "QR-Code gespeichert: {path}",
    "msg_pdf_saved": "PDF erfolgreich erstellt: {path}",

    "err_no_qr": "Kein QR-Code erkannt.",
    "err_image_load": "Bild konnte nicht geladen werden.",
    "err_pdf_no_qr_page": "Auf der gewählten PDF-Seite wurde kein QR-Code erkannt.",
    "err_invalid_pdf_page": "Ungültige PDF-Seite.",
    "err_empty_secret": "Kein Secret angegeben.",
    "err_invalid_secret": "Ungültiges TOTP-Secret (Base32).",
    "err_empty_content": "Leerer Inhalt.",
    "err_no_otpauth": "QR-Code enthält keinen otpauth-Inhalt.",
    "err_no_secret_in_qr": "Im QR-Code wurde kein Secret gefunden.",
    "err_only_totp_supported": "Nur TOTP wird unterstützt. HOTP kann angezeigt, aber nicht berechnet werden.",
    "err_algorithm_unsupported": "Nicht unterstützter Algorithmus: {algorithm}",
    "err_otp_type_unsupported": "Nicht unterstützter OTP-Typ: {otp_type}",
    "err_secret_process": "Secret konnte nicht verarbeitet werden: {error}",
    "err_settings_save": "Einstellungen konnten nicht gespeichert werden: {error}",
    "err_screenshot_process": "Screenshot konnte nicht verarbeitet werden: {error}",
    "err_qr_generate": "QR konnte nicht erzeugt werden: {error}",
    "err_png_save": "PNG konnte nicht gespeichert werden: {error}",
    "err_pdf_export": "PDF konnte nicht erstellt werden: {error}",

    "info_otp_type": "OTP-Typ",
    "info_label": "Label",
    "info_issuer": "Issuer",
    "info_account": "Account",
    "info_algorithm": "Algorithmus",
    "info_digits": "Digits",
    "info_period": "Period",
    "info_counter": "Counter",
    "info_secret": "Secret",
    "info_raw": "Rohinhalt",
    "info_more_qr": "Weitere erkannte QR-Inhalte",
    "value_dash": "-",

    "pdf_title": "TOTP Registrierungsblatt",
    "pdf_created": "Erstellt: {created}",
    "pdf_created_footer": "Erstellt am {created}",
    "pdf_totp_label": "TOTP Token",
    "pdf_field_username": "Benutzername:",
    "pdf_field_password": "Kennwort:",
    "pdf_field_totp_secret": "TOTP Token Secret:",

    "source_prefix": "Quelle:",
    "source_manual": "Manuelle Eingabe",
    "source_pdf": "PDF-Datei",
    "source_image": "Bilddatei",
    "source_screenshot": "Bildschirmaufnahme",
    "source_page": "Seite",
}


@dataclass
class OTPPayload:
    raw_text: str
    otp_type: str
    label: str
    issuer: str
    account_name: str
    secret: str
    algorithm: str
    digits: int
    period: int
    counter: Optional[int]


class QRDecodeError(Exception):
    pass


class OTPParseError(Exception):
    pass


class LanguageManager:
    def __init__(self):
        self.strings = dict(DEFAULT_STRINGS)

        if LANGUAGE_FILE.exists():
            try:
                with open(LANGUAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    for key, value in data.items():
                        if key in self.strings and isinstance(value, str):
                            self.strings[key] = value
            except Exception:
                pass

    def tr(self, key: str, **kwargs) -> str:
        text = self.strings.get(key, DEFAULT_STRINGS.get(key, key))
        try:
            return text.format(**kwargs)
        except Exception:
            return text


class SettingsManager:
    DEFAULTS = {
        "pdf_include_username": True,
        "pdf_include_password": True,
        "pdf_include_totp_label": True,
        "pdf_include_secret_text": False,
        "pdf_include_created_date_header": True,
        "pdf_include_created_date_footer": False,
        "pdf_mask_password": False,
    }

    @classmethod
    def load(cls) -> dict:
        if not CONFIG_FILE.exists():
            return dict(cls.DEFAULTS)

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            settings = dict(cls.DEFAULTS)
            settings.update({k: bool(v) for k, v in data.items() if k in cls.DEFAULTS})
            return settings
        except Exception:
            return dict(cls.DEFAULTS)

    @classmethod
    def save(cls, settings: dict) -> None:
        safe = {k: bool(v) for k, v in settings.items() if k in cls.DEFAULTS}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(safe, f, indent=2, ensure_ascii=False)


def make_default_export_filename(username: str, ext: str) -> str:
    username = (username or "").strip()
    date_str = datetime.now().strftime("%d%m%Y")

    if not username:
        return f"totp_{date_str}{ext}"

    safe = username
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        safe = safe.replace(ch, "_")
    safe = safe.replace("@", "_")
    safe = safe.replace(" ", "_")

    while "__" in safe:
        safe = safe.replace("__", "_")

    safe = safe.strip("._")
    if not safe:
        safe = "totp"

    return f"{safe}_{date_str}{ext}"


class QRUtils:
    @staticmethod
    def _detect_qr_with_opencv(image_bgr: np.ndarray) -> List[str]:
        detector = cv2.QRCodeDetector()
        results: List[str] = []

        try:
            ok, decoded_info, _points, _ = detector.detectAndDecodeMulti(image_bgr)
            if ok and decoded_info:
                for item in decoded_info:
                    if item and item.strip():
                        results.append(item.strip())
        except Exception:
            pass

        if not results:
            single_text, _points, _ = detector.detectAndDecode(image_bgr)
            if single_text and single_text.strip():
                results.append(single_text.strip())

        if not results:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            scales = [1.0, 1.5, 2.0]
            for scale in scales:
                resized = cv2.resize(
                    gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                )
                _, thresh = cv2.threshold(
                    resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )
                text, _points, _ = detector.detectAndDecode(thresh)
                if text and text.strip():
                    results.append(text.strip())
                    break

        deduped: List[str] = []
        seen = set()
        for item in results:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    @staticmethod
    def _decode_or_raise(image_bgr: np.ndarray, lang: LanguageManager) -> List[str]:
        results = QRUtils._detect_qr_with_opencv(image_bgr)
        if not results:
            raise QRDecodeError(lang.tr("err_no_qr"))
        return results

    @staticmethod
    def decode_qr_from_image_file(path: str, lang: LanguageManager) -> List[str]:
        image = cv2.imread(path, IMAGE_READ_FLAGS)
        if image is None:
            raise QRDecodeError(lang.tr("err_image_load"))
        return QRUtils._decode_or_raise(image, lang)

    @staticmethod
    def decode_qr_from_pil_image(image: Image.Image, lang: LanguageManager) -> List[str]:
        rgb = image.convert("RGB")
        arr = np.array(rgb)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return QRUtils._decode_or_raise(bgr, lang)

    @staticmethod
    def get_pdf_page_count(path: str) -> int:
        doc = fitz.open(path)
        try:
            return len(doc)
        finally:
            doc.close()

    @staticmethod
    def decode_qr_from_pdf_page(
        path: str, page_number_1_based: int, lang: LanguageManager
    ) -> List[str]:
        doc = fitz.open(path)
        try:
            page_index = page_number_1_based - 1
            if page_index < 0 or page_index >= len(doc):
                raise QRDecodeError(lang.tr("err_invalid_pdf_page"))

            page = doc.load_page(page_index)
            all_results: List[str] = []

            for dpi in PDF_RENDER_DPI_LEVELS:
                matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                image_bytes = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                try:
                    hits = QRUtils.decode_qr_from_pil_image(pil_image, lang)
                    for hit in hits:
                        if hit not in all_results:
                            all_results.append(hit)
                except QRDecodeError:
                    continue

            if not all_results:
                raise QRDecodeError(lang.tr("err_pdf_no_qr_page"))

            return all_results
        finally:
            doc.close()


class OTPUtils:
    @staticmethod
    def normalize_secret(secret: str) -> str:
        return "".join(secret.strip().split()).upper()

    @staticmethod
    def validate_base32_secret(secret: str, lang: LanguageManager) -> None:
        normalized = OTPUtils.normalize_secret(secret)
        if not normalized:
            raise OTPParseError(lang.tr("err_empty_secret"))

        try:
            padded = normalized + "=" * ((8 - len(normalized) % 8) % 8)
            base64.b32decode(padded, casefold=True)
        except binascii.Error as exc:
            raise OTPParseError(lang.tr("err_invalid_secret")) from exc

    @staticmethod
    def build_payload_from_secret(secret: str, lang: LanguageManager) -> OTPPayload:
        normalized = OTPUtils.normalize_secret(secret)
        OTPUtils.validate_base32_secret(normalized, lang)

        return OTPPayload(
            raw_text=normalized,
            otp_type="totp",
            label="",
            issuer="",
            account_name="",
            secret=normalized,
            algorithm="SHA1",
            digits=6,
            period=30,
            counter=None,
        )

    @staticmethod
    def parse_otpauth_uri(uri: str, lang: LanguageManager) -> OTPPayload:
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme != "otpauth":
            raise OTPParseError(lang.tr("err_no_otpauth"))

        otp_type = parsed.netloc.lower().strip()
        if otp_type not in {"totp", "hotp"}:
            raise OTPParseError(lang.tr("err_otp_type_unsupported", otp_type=otp_type))

        label = urllib.parse.unquote(parsed.path.lstrip("/"))
        query = urllib.parse.parse_qs(parsed.query)

        secret = OTPUtils.normalize_secret(query.get("secret", [""])[0])
        if not secret:
            raise OTPParseError(lang.tr("err_no_secret_in_qr"))

        OTPUtils.validate_base32_secret(secret, lang)

        issuer = query.get("issuer", [""])[0]
        algorithm = query.get("algorithm", ["SHA1"])[0].upper()
        digits = int(query.get("digits", ["6"])[0])
        period = int(query.get("period", ["30"])[0])

        counter_raw = query.get("counter", [None])[0]
        counter = int(counter_raw) if counter_raw not in (None, "") else None

        account_name = label
        if ":" in label:
            maybe_issuer, maybe_account = label.split(":", 1)
            if not issuer:
                issuer = maybe_issuer.strip()
            account_name = maybe_account.strip()

        return OTPPayload(
            raw_text=uri,
            otp_type=otp_type,
            label=label,
            issuer=issuer,
            account_name=account_name,
            secret=secret,
            algorithm=algorithm,
            digits=digits,
            period=period,
            counter=counter,
        )

    @staticmethod
    def payload_from_text(raw_text: str, lang: LanguageManager) -> OTPPayload:
        stripped = raw_text.strip()
        if not stripped:
            raise OTPParseError(lang.tr("err_empty_content"))

        if stripped.lower().startswith("otpauth://"):
            return OTPUtils.parse_otpauth_uri(stripped, lang)

        return OTPUtils.build_payload_from_secret(stripped, lang)

    @staticmethod
    def totp_from_payload(payload: OTPPayload, lang: LanguageManager) -> pyotp.TOTP:
        if payload.otp_type != "totp":
            raise OTPParseError(lang.tr("err_only_totp_supported"))

        import hashlib

        digest = getattr(hashlib, payload.algorithm.lower(), None)
        if digest is None:
            raise OTPParseError(
                lang.tr("err_algorithm_unsupported", algorithm=payload.algorithm)
            )

        return pyotp.TOTP(
            s=payload.secret,
            digits=payload.digits,
            digest=digest,
            interval=payload.period,
        )

    @staticmethod
    def current_code(payload: OTPPayload, lang: LanguageManager) -> str:
        return OTPUtils.totp_from_payload(payload, lang).now()

    @staticmethod
    def seconds_remaining(payload: OTPPayload) -> int:
        if payload.period <= 0:
            return 0
        now = int(time.time())
        remaining = payload.period - (now % payload.period)
        return remaining if remaining != payload.period else payload.period

    @staticmethod
    def build_otpauth_uri(
        secret: str,
        issuer: str,
        account_name: str,
        digits: int,
        period: int,
        algorithm: str,
        lang: LanguageManager,
    ) -> str:
        normalized = OTPUtils.normalize_secret(secret)
        OTPUtils.validate_base32_secret(normalized, lang)

        label = account_name.strip()
        issuer_clean = issuer.strip()
        if issuer_clean:
            label = f"{issuer_clean}:{label}"

        query = {
            "secret": normalized,
            "issuer": issuer_clean,
            "digits": str(digits),
            "period": str(period),
            "algorithm": algorithm.upper(),
        }

        return "otpauth://totp/{}?{}".format(
            urllib.parse.quote(label),
            urllib.parse.urlencode(query),
        )


class QRCodeGenerator:
    @staticmethod
    def create_qr_png_bytes(text: str, scale: int = 8) -> bytes:
        qr = segno.make(text)
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=scale, border=2)
        return buf.getvalue()

    @staticmethod
    def save_qr_png(text: str, path: str, scale: int = 8) -> None:
        qr = segno.make(text)
        qr.save(path, kind="png", scale=scale, border=2)


class PDFExporter:
    @staticmethod
    def export_totp_pdf(
        output_path: str,
        username: str,
        password: str,
        totp_secret: str,
        otpauth_uri: str,
        created_at: datetime,
        settings: dict,
        lang: LanguageManager,
    ) -> None:
        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        left_margin = 20 * mm
        right_margin = width - 20 * mm
        top_y = height - 20 * mm

        created_text = created_at.strftime("%d.%m.%Y %H:%M:%S")

        if settings.get("pdf_include_created_date_header", True):
            c.setFont("Helvetica", 9)
            c.drawRightString(
                right_margin,
                height - 10 * mm,
                lang.tr("pdf_created", created=created_text),
            )

        c.setFont("Helvetica-Bold", 16)
        c.drawString(left_margin, top_y, lang.tr("pdf_title"))

        y = top_y - 18 * mm

        label_x = left_margin
        value_x = left_margin + 52 * mm
        row_height = 9 * mm

        c.setFont("Helvetica", 11)

        rows = []

        if settings.get("pdf_include_username", True):
            rows.append((lang.tr("pdf_field_username"), username))

        if settings.get("pdf_include_password", True):
            pw_out = password
            if settings.get("pdf_mask_password", False):
                pw_out = "*" * len(password)
            rows.append((lang.tr("pdf_field_password"), pw_out))

        if settings.get("pdf_include_secret_text", False):
            rows.append((lang.tr("pdf_field_totp_secret"), totp_secret))

        for label, value in rows:
            c.drawString(label_x, y, label)
            c.drawString(value_x, y, value)
            y -= row_height

        if settings.get("pdf_include_totp_label", True):
            y -= 2 * mm
            c.drawString(label_x, y, lang.tr("pdf_totp_label"))
            y -= 10 * mm
        else:
            y -= 4 * mm

        png_bytes = QRCodeGenerator.create_qr_png_bytes(otpauth_uri, scale=8)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(png_bytes)
            tmp_path = tmp.name

        try:
            qr_size = 60 * mm
            qr_x = left_margin
            qr_y = y - qr_size
            c.drawImage(
                tmp_path,
                qr_x,
                qr_y,
                width=qr_size,
                height=qr_size,
                preserveAspectRatio=True,
                mask="auto",
            )
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        if settings.get("pdf_include_created_date_footer", False):
            c.setFont("Helvetica", 9)
            c.drawCentredString(
                width / 2,
                10 * mm,
                lang.tr("pdf_created_footer", created=created_text),
            )

        c.showPage()
        c.save()


class ScreenCaptureOverlay(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.25)
        self.configure(bg="black")

        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.result_bbox: Optional[Tuple[int, int, int, int]] = None

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")

        self.canvas = tk.Canvas(self, cursor="cross", bg="gray", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.rect = None

        self.bind("<Escape>", self._cancel)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def start(self) -> Optional[Tuple[int, int, int, int]]:
        self.deiconify()
        self.lift()
        self.grab_set()
        self.focus_force()
        self.wait_window()
        return self.result_bbox

    def _on_press(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.end_x = event.x_root
        self.end_y = event.y_root

        if self.rect is not None:
            self.canvas.delete(self.rect)

        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2
        )

    def _on_drag(self, event):
        self.end_x = event.x_root
        self.end_y = event.y_root

        if self.rect is not None:
            self.canvas.coords(
                self.rect,
                self.start_x,
                self.start_y,
                self.end_x,
                self.end_y,
            )

    def _on_release(self, event):
        self.end_x = event.x_root
        self.end_y = event.y_root

        left = min(self.start_x, self.end_x)
        top = min(self.start_y, self.end_y)
        right = max(self.start_x, self.end_x)
        bottom = max(self.start_y, self.end_y)

        if right - left < 10 or bottom - top < 10:
            self.result_bbox = None
        else:
            self.result_bbox = (left, top, right, bottom)

        self.grab_release()
        self.destroy()

    def _cancel(self, _event=None):
        self.result_bbox = None
        self.grab_release()
        self.destroy()


class TOTPVerifierApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.lang = LanguageManager()
        self.root.title(self.lang.tr("app_title"))
        self.root.geometry(APP_GEOMETRY)
        self.root.minsize(1080, 760)

        self.settings = SettingsManager.load()

        self.current_payload: Optional[OTPPayload] = None
        self.current_source: str = ""
        self.qr_results: List[str] = []
        self.generated_qr_photo = None
        self.generated_otpauth_uri = ""
        self.window_icon_image = None

        self.secret_var = tk.StringVar()
        self.code_var = tk.StringVar(value="-")
        self.remaining_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value=self.lang.tr("status_ready"))
        self.source_var = tk.StringVar(value=self.lang.tr("source_empty"))

        self.gen_username_var = tk.StringVar()
        self.gen_password_var = tk.StringVar()
        self.gen_secret_var = tk.StringVar()
        self.gen_issuer_var = tk.StringVar()
        self.gen_account_var = tk.StringVar()
        self.gen_digits_var = tk.StringVar(value="6")
        self.gen_period_var = tk.StringVar(value="30")
        self.gen_algorithm_var = tk.StringVar(value="SHA1")

        self.chk_unlock_advanced = tk.BooleanVar(value=False)

        self.chk_pdf_include_username = tk.BooleanVar(
            value=self.settings["pdf_include_username"]
        )
        self.chk_pdf_include_password = tk.BooleanVar(
            value=self.settings["pdf_include_password"]
        )
        self.chk_pdf_include_totp_label = tk.BooleanVar(
            value=self.settings["pdf_include_totp_label"]
        )
        self.chk_pdf_include_secret_text = tk.BooleanVar(
            value=self.settings["pdf_include_secret_text"]
        )
        self.chk_pdf_include_created_date_header = tk.BooleanVar(
            value=self.settings["pdf_include_created_date_header"]
        )
        self.chk_pdf_include_created_date_footer = tk.BooleanVar(
            value=self.settings["pdf_include_created_date_footer"]
        )
        self.chk_pdf_mask_password = tk.BooleanVar(
            value=self.settings["pdf_mask_password"]
        )

        self._set_window_icon()
        self._build_ui()
        self._configure_styles()
        self._schedule_refresh()

    def _set_window_icon(self):
        try:
            if ICON_PATH.exists():
                try:
                    self.root.iconbitmap(default=str(ICON_PATH))
                except Exception:
                    pass

                try:
                    img = Image.open(ICON_PATH)
                    self.window_icon_image = ImageTk.PhotoImage(img)
                    self.root.iconphoto(True, self.window_icon_image)
                except Exception:
                    pass
        except Exception:
            pass

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.map(
                "Disabled.TEntry",
                fieldbackground=[("disabled", "#f0f0f0")],
                foreground=[("disabled", "#808080")],
            )
        except tk.TclError:
            pass

    def _build_ui(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab_verify = ttk.Frame(notebook)
        tab_generate = ttk.Frame(notebook)

        notebook.add(tab_verify, text=self.lang.tr("tab_verify"))
        notebook.add(tab_generate, text=self.lang.tr("tab_generate"))

        self._build_verify_tab(tab_verify)
        self._build_generate_tab(tab_generate)

    def _build_verify_tab(self, parent):
        container = ttk.Frame(parent, padding=12)
        container.pack(fill="both", expand=True)

        top = ttk.LabelFrame(container, text=self.lang.tr("group_read"), padding=10)
        top.pack(fill="x", pady=(0, 10))

        ttk.Label(top, text=self.lang.tr("label_totp_secret")).grid(
            row=0, column=0, sticky="w"
        )

        secret_entry = ttk.Entry(top, textvariable=self.secret_var, width=60)
        secret_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        secret_entry.focus_set()

        ttk.Button(
            top,
            text=self.lang.tr("btn_generate_from_secret"),
            command=self.load_from_manual_secret,
        ).grid(row=0, column=2, sticky="ew")

        button_row = ttk.Frame(top)
        button_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        for col in range(3):
            button_row.columnconfigure(col, weight=1)

        ttk.Button(
            button_row,
            text=self.lang.tr("btn_open_qr_image_pdf"),
            command=self.load_from_image_or_pdf,
        ).grid(row=0, column=0, padx=4, sticky="ew")

        ttk.Button(
            button_row,
            text=self.lang.tr("btn_capture_screen"),
            command=self.load_from_screenshot,
        ).grid(row=0, column=1, padx=4, sticky="ew")

        ttk.Button(
            button_row,
            text=self.lang.tr("btn_reset"),
            command=self.reset_all,
        ).grid(row=0, column=2, padx=4, sticky="ew")

        top.columnconfigure(1, weight=1)

        middle = ttk.Frame(container)
        middle.pack(fill="both", expand=True)
        middle.columnconfigure(0, weight=3)
        middle.columnconfigure(1, weight=2)
        middle.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(
            middle, text=self.lang.tr("group_current_code"), padding=10
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ttk.Label(
            left,
            textvariable=self.code_var,
            font=("Consolas", 30, "bold"),
            anchor="center",
        ).pack(fill="x", pady=(10, 10))

        ttk.Label(
            left,
            textvariable=self.remaining_var,
            font=("Segoe UI", 11),
        ).pack(anchor="center", pady=(0, 8))

        ttk.Label(
            left,
            textvariable=self.source_var,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", fill="x")

        ttk.Separator(left).pack(fill="x", pady=12)
        ttk.Label(left, text=self.lang.tr("label_status")).pack(anchor="w")

        ttk.Label(
            left,
            textvariable=self.status_var,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))

        right = ttk.LabelFrame(
            middle, text=self.lang.tr("group_qr_info"), padding=10
        )
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.info_text = tk.Text(right, wrap="word", height=24)
        self.info_text.grid(row=0, column=0, sticky="nsew")
        self.info_text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(
            right, orient="vertical", command=self.info_text.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.info_text["yscrollcommand"] = scrollbar.set

    def _build_generate_tab(self, parent):
        container = ttk.Frame(parent, padding=12)
        container.pack(fill="both", expand=True)

        left = ttk.LabelFrame(
            container, text=self.lang.tr("group_generate"), padding=10
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = ttk.LabelFrame(
            container, text=self.lang.tr("group_preview"), padding=10
        )
        right.pack(side="right", fill="both", expand=True)

        form = ttk.Frame(left)
        form.pack(fill="x")

        ttk.Label(form, text=self.lang.tr("label_username")).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.gen_username_var, width=48).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(form, text=self.lang.tr("label_password")).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.gen_password_var, width=48, show="*").grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(form, text=self.lang.tr("label_secret")).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.gen_secret_var, width=48).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(form, text=self.lang.tr("label_issuer")).grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.gen_issuer_var, width=48).grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(form, text=self.lang.tr("label_account_name")).grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.gen_account_var, width=48).grid(
            row=4, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Checkbutton(
            form,
            text=self.lang.tr("chk_unlock_advanced"),
            variable=self.chk_unlock_advanced,
            command=self._update_advanced_fields_state,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 4))

        ttk.Label(form, text=self.lang.tr("label_digits")).grid(row=6, column=0, sticky="w", pady=4)
        self.entry_digits = ttk.Entry(
            form, textvariable=self.gen_digits_var, width=48, style="Disabled.TEntry"
        )
        self.entry_digits.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(form, text=self.lang.tr("label_period")).grid(row=7, column=0, sticky="w", pady=4)
        self.entry_period = ttk.Entry(
            form, textvariable=self.gen_period_var, width=48, style="Disabled.TEntry"
        )
        self.entry_period.grid(row=7, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(form, text=self.lang.tr("label_algorithm")).grid(row=8, column=0, sticky="w", pady=4)
        self.entry_algorithm = ttk.Entry(
            form, textvariable=self.gen_algorithm_var, width=48, style="Disabled.TEntry"
        )
        self.entry_algorithm.grid(row=8, column=1, sticky="ew", padx=(8, 0), pady=4)

        form.columnconfigure(1, weight=1)

        opts = ttk.LabelFrame(left, text=self.lang.tr("group_pdf_options"), padding=10)
        opts.pack(fill="x", pady=(12, 0))

        checkboxes = [
            (self.lang.tr("chk_print_username"), self.chk_pdf_include_username),
            (self.lang.tr("chk_print_password"), self.chk_pdf_include_password),
            (self.lang.tr("chk_print_totp_label"), self.chk_pdf_include_totp_label),
            (self.lang.tr("chk_print_secret"), self.chk_pdf_include_secret_text),
            (self.lang.tr("chk_date_header"), self.chk_pdf_include_created_date_header),
            (self.lang.tr("chk_date_footer"), self.chk_pdf_include_created_date_footer),
            (self.lang.tr("chk_mask_password"), self.chk_pdf_mask_password),
        ]

        for i, (text, var) in enumerate(checkboxes):
            ttk.Checkbutton(
                opts,
                text=text,
                variable=var,
                command=self.save_checkbox_settings,
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=4)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(
            btns,
            text=self.lang.tr("btn_generate_qr"),
            command=self.generate_qr_preview,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            btns,
            text=self.lang.tr("btn_save_png"),
            command=self.save_generated_qr_png,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            btns,
            text=self.lang.tr("btn_export_pdf"),
            command=self.export_pdf,
        ).pack(side="left")

        ttk.Button(
            btns,
            text=self.lang.tr("btn_save_checkbox_settings"),
            command=self.save_checkbox_settings,
        ).pack(side="right")

        self.qr_preview_label = ttk.Label(
            right, text=self.lang.tr("preview_empty")
        )
        self.qr_preview_label.pack(fill="both", expand=True)

        self._update_advanced_fields_state()

    def _update_advanced_fields_state(self):
        if self.chk_unlock_advanced.get():
            self.entry_digits.configure(state="normal")
            self.entry_period.configure(state="normal")
            self.entry_algorithm.configure(state="normal")
        else:
            self.gen_digits_var.set("6")
            self.gen_period_var.set("30")
            self.gen_algorithm_var.set("SHA1")
            self.entry_digits.configure(state="disabled")
            self.entry_period.configure(state="disabled")
            self.entry_algorithm.configure(state="disabled")

    def _sync_payload_to_generator(self, payload: OTPPayload):
        self.gen_secret_var.set(payload.secret or "")
        self.gen_issuer_var.set(payload.issuer or "")
        self.gen_account_var.set(payload.account_name or "")
        self.gen_username_var.set(payload.account_name or "")

        if payload.digits:
            self.gen_digits_var.set(str(payload.digits))
        else:
            self.gen_digits_var.set("6")

        if payload.period:
            self.gen_period_var.set(str(payload.period))
        else:
            self.gen_period_var.set("30")

        if payload.algorithm:
            self.gen_algorithm_var.set(str(payload.algorithm).upper())
        else:
            self.gen_algorithm_var.set("SHA1")

        if not self.chk_unlock_advanced.get():
            self._update_advanced_fields_state()

    def current_settings_dict(self) -> dict:
        return {
            "pdf_include_username": self.chk_pdf_include_username.get(),
            "pdf_include_password": self.chk_pdf_include_password.get(),
            "pdf_include_totp_label": self.chk_pdf_include_totp_label.get(),
            "pdf_include_secret_text": self.chk_pdf_include_secret_text.get(),
            "pdf_include_created_date_header": self.chk_pdf_include_created_date_header.get(),
            "pdf_include_created_date_footer": self.chk_pdf_include_created_date_footer.get(),
            "pdf_mask_password": self.chk_pdf_mask_password.get(),
        }

    def save_checkbox_settings(self):
        try:
            SettingsManager.save(self.current_settings_dict())
            self.set_status(self.lang.tr("status_settings_saved"))
        except Exception as exc:
            self._show_error(self.lang.tr("err_settings_save", error=exc))

    def set_status(self, text: str):
        self.status_var.set(text)

    def set_info_text(self, text: str):
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", text)
        self.info_text.configure(state="disabled")

    def _format_source(self, source_text: str) -> str:
        return f"{self.lang.tr('source_prefix')} {source_text}"

    def load_from_manual_secret(self):
        try:
            payload = OTPUtils.build_payload_from_secret(
                self.secret_var.get(), self.lang
            )
            self._apply_payload(payload, source=self.lang.tr("source_manual"))
            self.set_status(self.lang.tr("msg_secret_loaded"))
        except Exception as exc:
            self._show_error(self.lang.tr("err_secret_process", error=exc))

    def load_from_image_or_pdf(self):
        path = filedialog.askopenfilename(
            title=self.lang.tr("dialog_open_image_pdf_title"),
            filetypes=[
                (self.lang.tr("filetype_supported"), "*.png *.jpg *.jpeg *.pdf"),
                (self.lang.tr("filetype_images"), "*.png *.jpg *.jpeg"),
                (self.lang.tr("filetype_pdf"), "*.pdf"),
                (self.lang.tr("filetype_all"), "*.*"),
            ],
        )
        if not path:
            return

        ext = Path(path).suffix.lower()

        try:
            if ext == ".pdf":
                page_count = QRUtils.get_pdf_page_count(path)
                if page_count <= 0:
                    raise QRDecodeError(self.lang.tr("pdf_no_pages"))

                page_no = 1
                if page_count > 1:
                    page_no = simpledialog.askinteger(
                        self.lang.tr("pdf_page_prompt_title"),
                        self.lang.tr("pdf_page_prompt_text", count=page_count),
                        parent=self.root,
                        minvalue=1,
                        maxvalue=page_count,
                        initialvalue=1,
                    )
                    if page_no is None:
                        self.set_status(self.lang.tr("pdf_selection_cancelled"))
                        return

                qr_texts = QRUtils.decode_qr_from_pdf_page(path, page_no, self.lang)
                source = f"{self.lang.tr('source_pdf')}: {path} ({self.lang.tr('source_page')} {page_no})"
                self._handle_qr_results(qr_texts, source=source)
            else:
                qr_texts = QRUtils.decode_qr_from_image_file(path, self.lang)
                source = f"{self.lang.tr('source_image')}: {path}"
                self._handle_qr_results(qr_texts, source=source)
        except Exception as exc:
            self._show_error(str(exc))

    def load_from_screenshot(self):
        self.root.withdraw()
        self.root.update_idletasks()

        try:
            overlay = ScreenCaptureOverlay(self.root)
            bbox = overlay.start()

            if not bbox:
                self.root.deiconify()
                self.root.lift()
                self.set_status(self.lang.tr("msg_screenshot_cancelled"))
                return

            image = ImageGrab.grab(bbox=bbox, all_screens=True)
            qr_texts = QRUtils.decode_qr_from_pil_image(image, self.lang)

            self.root.deiconify()
            self.root.lift()
            self._handle_qr_results(qr_texts, source=self.lang.tr("source_screenshot"))
        except Exception as exc:
            self.root.deiconify()
            self.root.lift()
            self._show_error(self.lang.tr("err_screenshot_process", error=exc))

    def _handle_qr_results(self, qr_texts: List[str], source: str):
        if not qr_texts:
            raise QRDecodeError(self.lang.tr("err_no_qr"))

        self.qr_results = qr_texts
        payload = OTPUtils.payload_from_text(qr_texts[0], self.lang)
        self._apply_payload(payload, source=source)

        if len(qr_texts) > 1:
            self.set_status(self.lang.tr("msg_multiple_qr", count=len(qr_texts)))
        else:
            self.set_status(self.lang.tr("msg_qr_loaded"))

    def _apply_payload(self, payload: OTPPayload, source: str):
        self.current_payload = payload
        self.current_source = source
        self.source_var.set(self._format_source(source))

        if payload.secret:
            self.secret_var.set(payload.secret)

        self._sync_payload_to_generator(payload)

        self._refresh_code_display()
        self._render_payload_details(payload)

    def _render_payload_details(self, payload: OTPPayload):
        dash = self.lang.tr("value_dash")

        lines = [
            f"{self.lang.tr('info_otp_type')}: {payload.otp_type}",
            f"{self.lang.tr('info_label')}: {payload.label or dash}",
            f"{self.lang.tr('info_issuer')}: {payload.issuer or dash}",
            f"{self.lang.tr('info_account')}: {payload.account_name or dash}",
            f"{self.lang.tr('info_algorithm')}: {payload.algorithm}",
            f"{self.lang.tr('info_digits')}: {payload.digits}",
            f"{self.lang.tr('info_period')}: {payload.period}",
            f"{self.lang.tr('info_counter')}: {payload.counter if payload.counter is not None else dash}",
            f"{self.lang.tr('info_secret')}: {payload.secret}",
            "",
            f"{self.lang.tr('info_raw')}:",
            payload.raw_text,
        ]

        if self.qr_results and len(self.qr_results) > 1:
            lines.append("")
            lines.append(f"{self.lang.tr('info_more_qr')}:")
            for idx, item in enumerate(self.qr_results[1:], start=2):
                lines.append(f"{idx}. {item}")

        self.set_info_text("\n".join(lines))

    def _refresh_code_display(self):
        if self.current_payload is None:
            self.code_var.set("-")
            self.remaining_var.set("-")
            return

        try:
            code = OTPUtils.current_code(self.current_payload, self.lang)
            remaining = OTPUtils.seconds_remaining(self.current_payload)
            self.code_var.set(self._format_code(code))
            self.remaining_var.set(
                self.lang.tr("remaining_seconds", seconds=remaining)
            )
        except Exception as exc:
            self.code_var.set("-")
            self.remaining_var.set("-")
            self.set_status(str(exc))

    @staticmethod
    def _format_code(code: str) -> str:
        if len(code) == 6:
            return f"{code[:3]} {code[3:]}"
        if len(code) == 8:
            return f"{code[:4]} {code[4:]}"
        return code

    def _schedule_refresh(self):
        self._refresh_code_display()
        self.root.after(1000, self._schedule_refresh)

    def _show_error(self, message: str):
        self.set_status(message)
        messagebox.showerror(self.lang.tr("app_title"), message)

    def reset_all(self):
        self.current_payload = None
        self.current_source = ""
        self.qr_results = []

        self.secret_var.set("")
        self.code_var.set("-")
        self.remaining_var.set("-")
        self.source_var.set(self.lang.tr("source_empty"))
        self.set_status(self.lang.tr("status_reset"))
        self.set_info_text("")

    def generate_qr_preview(self):
        try:
            secret = self.gen_secret_var.get()
            issuer = self.gen_issuer_var.get()
            account = self.gen_account_var.get() or self.gen_username_var.get()
            digits = int(self.gen_digits_var.get())
            period = int(self.gen_period_var.get())
            algorithm = self.gen_algorithm_var.get().upper().strip()

            otpauth_uri = OTPUtils.build_otpauth_uri(
                secret=secret,
                issuer=issuer,
                account_name=account,
                digits=digits,
                period=period,
                algorithm=algorithm,
                lang=self.lang,
            )
            self.generated_otpauth_uri = otpauth_uri

            png_bytes = QRCodeGenerator.create_qr_png_bytes(otpauth_uri, scale=8)
            pil_image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            pil_image = pil_image.resize((280, 280))
            self.generated_qr_photo = ImageTk.PhotoImage(pil_image)

            self.qr_preview_label.configure(image=self.generated_qr_photo, text="")
            self.set_status(self.lang.tr("msg_qr_generated"))
        except Exception as exc:
            self._show_error(self.lang.tr("err_qr_generate", error=exc))

    def save_generated_qr_png(self):
        try:
            if not self.generated_otpauth_uri:
                self.generate_qr_preview()
            if not self.generated_otpauth_uri:
                return

            suggested_name = make_default_export_filename(
                self.gen_username_var.get(), ".png"
            )

            path = filedialog.asksaveasfilename(
                title=self.lang.tr("dialog_save_png_title"),
                initialfile=suggested_name,
                defaultextension=".png",
                filetypes=[(self.lang.tr("filetype_png"), "*.png")],
            )
            if not path:
                return

            QRCodeGenerator.save_qr_png(self.generated_otpauth_uri, path, scale=8)
            self.set_status(self.lang.tr("msg_qr_saved", path=path))
        except Exception as exc:
            self._show_error(self.lang.tr("err_png_save", error=exc))

    def export_pdf(self):
        try:
            if not self.generated_otpauth_uri:
                self.generate_qr_preview()
            if not self.generated_otpauth_uri:
                return

            suggested_name = make_default_export_filename(
                self.gen_username_var.get(), ".pdf"
            )

            path = filedialog.asksaveasfilename(
                title=self.lang.tr("dialog_save_pdf_title"),
                initialfile=suggested_name,
                defaultextension=".pdf",
                filetypes=[(self.lang.tr("filetype_pdf_single"), "*.pdf")],
            )
            if not path:
                return

            PDFExporter.export_totp_pdf(
                output_path=path,
                username=self.gen_username_var.get(),
                password=self.gen_password_var.get(),
                totp_secret=OTPUtils.normalize_secret(self.gen_secret_var.get()),
                otpauth_uri=self.generated_otpauth_uri,
                created_at=datetime.now(),
                settings=self.current_settings_dict(),
                lang=self.lang,
            )
            self.set_status(self.lang.tr("msg_pdf_saved", path=path))
        except Exception as exc:
            self._show_error(self.lang.tr("err_pdf_export", error=exc))


def main():
    root = tk.Tk()
    TOTPVerifierApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()