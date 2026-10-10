"""Generator napisów / Subtitle Generator — GUI."""
import os
import queue
import threading
import tkinter as tk
import traceback
from tkinter import filedialog
from tkinter import font as tkfont

import customtkinter as ctk

try:  # przeciąganie plików do okna; bez tej biblioteki program działa, tylko bez drag & drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None

import core
import i18n
from i18n import t

# ---------------------------------------------------------------- paleta (jasny, ciemny)

BG = ("#F4F5F7", "#16181C")
CARD = ("#FFFFFF", "#1F2227")
CARD_BORDER = ("#E5E7EB", "#2B2F36")
INSET = ("#F8F9FA", "#1A1C20")
TEXT = ("#1F2328", "#E3E5E8")
MUTED = ("#6B7280", "#8D949E")
ACCENT = ("#2F6FEB", "#3B7BEF")
ACCENT_HOVER = ("#285FCB", "#3069D4")
CONTROL = ("#EEF0F3", "#2A2E35")
CONTROL_HOVER = ("#E4E7EB", "#323741")
SELECTED = ("#FFFFFF", "#3C424C")
BORDER = ("#D5D9DF", "#3B4049")
CHECK_BORDER = ("#C3C8D0", "#4A505A")
DANGER_BG = ("#FBEAEA", "#3A2426")
DANGER_HOVER = ("#F6DCDC", "#45292B")
DANGER_TEXT = ("#B42323", "#F3A6A3")


def apply_theme(root):
    # zaokrąglenia rysowane wielokątami są ~20% szybsze od domyślnych „font_shapes” przy zmianie rozmiaru okna
    from customtkinter.windows.widgets.core_rendering import DrawEngine

    DrawEngine.preferred_drawing_method = "polygon_shapes"
    th = ctk.ThemeManager.theme
    th["CTkFont"]["family"] = tkfont.nametofont("TkDefaultFont", root).actual("family")  # Segoe UI / SF / Cantarell…
    th["CTk"]["fg_color"] = BG
    th["CTkFrame"].update(fg_color=CARD, top_fg_color=INSET, border_color=CARD_BORDER, corner_radius=12)
    th["CTkLabel"]["text_color"] = TEXT
    th["CTkButton"].update(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=("#FFFFFF", "#FFFFFF"),
                           border_color=BORDER, corner_radius=8)
    th["CTkCheckBox"].update(fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=CHECK_BORDER, border_width=2,
                             checkmark_color=("#FFFFFF", "#FFFFFF"), text_color=TEXT, corner_radius=5)
    th["CTkSegmentedButton"].update(fg_color=CONTROL, selected_color=SELECTED, selected_hover_color=SELECTED,
                                    unselected_color=CONTROL, unselected_hover_color=CONTROL_HOVER,
                                    text_color=TEXT, border_width=3, corner_radius=8)
    th["CTkOptionMenu"].update(fg_color=CONTROL, button_color=CONTROL, button_hover_color=CONTROL_HOVER,
                               text_color=TEXT, corner_radius=8)
    th["DropdownMenu"].update(fg_color=CARD, hover_color=CONTROL, text_color=TEXT)
    th["CTkEntry"].update(fg_color=("#FFFFFF", "#191B1F"), border_color=BORDER, border_width=1,
                          text_color=TEXT, placeholder_text_color=MUTED, corner_radius=8)
    th["CTkTextbox"].update(fg_color=INSET, border_color=BORDER, border_width=1, text_color=TEXT, corner_radius=8,
                            scrollbar_button_color=CONTROL_HOVER, scrollbar_button_hover_color=BORDER)
    th["CTkProgressBar"].update(fg_color=CONTROL, progress_color=ACCENT)
    th["CTkComboBox"].update(fg_color=("#FFFFFF", "#191B1F"), border_color=BORDER, border_width=1,
                             button_color=CONTROL, button_hover_color=CONTROL_HOVER, text_color=TEXT, corner_radius=8)


def mono_family():
    """Czytelna czcionka o stałej szerokości dostępna w systemie."""
    available = set(tkfont.families())
    for name in ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "JetBrains Mono", "DejaVu Sans Mono", "Ubuntu Mono"):
        if name in available:
            return name
    return tkfont.nametofont("TkFixedFont").actual("family")


def font(size=13, weight="normal"):
    return ctk.CTkFont(size=size, weight=weight)


UI_LANGS = {"PL": "pl", "EN": "en"}
LABEL_COL = 140  # szerokość kolumny etykiet w karcie tłumaczenia


def mode_color(pair):
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


class CheckGrid(tk.Canvas):
    """Siatka pól wyboru narysowana na jednej kanwie.

    32 osobne CTkCheckBoxy to 32 kanwy przerysowywane przy każdej zmianie rozmiaru okna — główne źródło
    lagowania. Tu jest jedna kanwa, która przy zmianie rozmiaru nic nie przerysowuje."""

    def __init__(self, master, items, variables, columns=4):
        super().__init__(master, highlightthickness=0, bd=0, cursor="hand2")
        self.items, self.vars, self.columns = items, variables, columns
        self.disabled = set()
        self.scale = ctk.ScalingTracker.get_widget_scaling(master)
        family = ctk.ThemeManager.theme["CTkFont"]["family"]
        self.font = tkfont.Font(family=family, size=-round(13 * self.scale))
        for v in variables.values():
            v.trace_add("write", lambda *_: self.draw())
        self.mode = None
        self.draw()

    def draw(self):
        sc, self.mode = self.scale, ctk.get_appearance_mode()
        self.delete("all")
        self.configure(bg=mode_color(INSET))
        box, gap, pad_x, row_h = round(18 * sc), round(9 * sc), round(12 * sc), round(26 * sc)
        col_w = max(self.font.measure(text) for _, text in self.items) + box + gap + pad_x
        rows = -(-len(self.items) // self.columns)
        top = round(8 * sc)
        for i, (code, text) in enumerate(self.items):
            x = pad_x + (i % self.columns) * col_w
            y = top + (i // self.columns) * row_h
            off = code in self.disabled
            on = self.vars[code].get() and not off
            tag = f"item_{code}"
            self._rounded(x, y + (row_h - box) / 2, box, round(5 * sc),
                          fill=mode_color(ACCENT) if on else mode_color(CONTROL if off else INSET),
                          outline=mode_color(ACCENT) if on else mode_color(CONTROL_HOVER if off else CHECK_BORDER),
                          width=max(1, round(1.5 * sc)), tags=tag)
            if on:
                cy = y + row_h / 2
                self.create_line(x + box * .25, cy, x + box * .43, cy + box * .18, x + box * .76, cy - box * .2,
                                 fill="#FFFFFF", width=max(2, round(2 * sc)), capstyle="round", joinstyle="round",
                                 tags=tag)
            self.create_text(x + box + gap, y + row_h / 2, text=text, anchor="w", font=self.font,
                             fill=mode_color(MUTED if off else TEXT), tags=tag)
            # niewidoczny prostokąt — klikalny cały wiersz, nie tylko litery
            self.create_rectangle(x - 4, y, x + col_w - pad_x, y + row_h, outline="", fill="", tags=tag)
            self.tag_bind(tag, "<Button-1>", lambda _, c=code: self.toggle(c))
        self.configure(width=self.columns * col_w + pad_x, height=rows * row_h + 2 * top)

    def _rounded(self, x, y, size, r, **kw):
        x2, y2 = x + size, y + size
        pts = [x + r, y, x2 - r, y, x2, y, x2, y + r, x2, y2 - r, x2, y2, x2 - r, y2, x + r, y2, x, y2, x, y2 - r,
               x, y + r, x, y]
        self.create_polygon(pts, smooth=True, **kw)

    def toggle(self, code):
        if code not in self.disabled:
            self.vars[code].set(not self.vars[code].get())

    def set_disabled(self, codes):
        if set(codes) != self.disabled:
            self.disabled = set(codes)
            self.draw()

    def sync_mode(self):
        if ctk.get_appearance_mode() != self.mode:
            self.draw()


class Tooltip:
    """Dymek z tekstem po najechaniu kursorem (np. pełna ścieżka pliku)."""

    def __init__(self, widget, text, delay=400):
        self.widget, self.text, self.delay, self.tip, self.job = widget, text, delay, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _):
        self._hide()
        self.job = self.widget.after(self.delay, self._show)

    def _show(self):
        scale = ctk.ScalingTracker.get_widget_scaling(self.widget)
        x, y = self.widget.winfo_pointerx() + round(12 * scale), self.widget.winfo_pointery() + round(18 * scale)
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.wm_geometry(f"+{x}+{y}")
        border = tk.Frame(self.tip, bg=mode_color(BORDER))
        border.pack()
        tk.Label(border, text=self.text, bg=mode_color(CARD), fg=mode_color(TEXT), justify="left",
                 font=tkfont.Font(family=ctk.ThemeManager.theme["CTkFont"]["family"], size=-round(12 * scale)),
                 padx=round(8 * scale), pady=round(4 * scale)).pack(padx=1, pady=1)

    def _hide(self, _=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ExistsDialog(ctk.CTkToplevel):
    """Plik wynikowy już istnieje: Nadpisz / Zapisz jako kopię / Pomiń (+ „dla wszystkich”)."""

    def __init__(self, master, path, on_answer):
        super().__init__(master)
        self.withdraw()  # pokażemy dopiero po ustawieniu na środku okna programu (inaczej mignie w rogu ekranu)
        self.on_answer, self.answered = on_answer, False
        self.title(t("exists_title"))
        self.resizable(False, False)
        if os.name == "nt":  # CTkToplevel też nadpisuje ikonę po ~200 ms
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
            self.after(300, lambda: os.path.exists(ico) and self.iconbitmap(ico))
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", lambda: self.answer("skip"))
        ctk.CTkLabel(self, text=t("exists_msg", path=os.path.normpath(path)), justify="left", wraplength=520).pack(
            anchor="w", padx=24, pady=(20, 10))
        self.all = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text=t("apply_all"), variable=self.all, checkbox_width=18, checkbox_height=18,
                        font=font(12)).pack(anchor="w", padx=24, pady=(0, 16))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 20))
        ctk.CTkButton(row, text=t("save_copy"), command=lambda: self.answer("copy")).pack(side="right")
        for key in ("overwrite", "skip"):
            ctk.CTkButton(row, text=t(key), fg_color="transparent", border_width=1, text_color=TEXT,
                          hover_color=CONTROL, command=lambda k=key: self.answer(k)).pack(side="right", padx=(0, 8))
        self.after(10, self._center)

    def _center(self):
        m = self.master
        self.update_idletasks()
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_reqwidth()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self.grab_set()

    def answer(self, choice):
        if not self.answered:
            self.answered = True
            self.on_answer(choice, self.all.get())
            self.destroy()


class Card(ctk.CTkFrame):
    """Sekcja z tytułem."""

    def __init__(self, master, title):
        super().__init__(master, border_width=1)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=title, font=font(14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(14, 8))


class App(ctk.CTk, *([TkinterDnD.DnDWrapper] if TkinterDnD else [])):
    def __init__(self):
        super().__init__()
        self._set_icon()
        apply_theme(self)
        self.geometry("1120x850")
        self.minsize(980, 760)
        self.q = queue.Queue()
        self.cfg = core.load_config()
        i18n.set_lang(self.cfg.get("ui_lang"))
        self.keys = core.api_keys(self.cfg)
        self.paths = []
        self.running = False
        self.outputs = []  # pliki zapisane w ostatnim uruchomieniu
        self.engine_code = self.cfg.get("engine", "cli")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.dnd = self._enable_drop()
        self.build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll)

    # ------------------------------------------------------------ budowa okna

    def build(self, log_text=""):
        self.title(t("title"))
        self.body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.body.grid(row=0, column=0, sticky="nsew")
        b = self.body
        b.grid_columnconfigure((0, 1), weight=1, uniform="col")
        b.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(b, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(18, 12))
        ctk.CTkLabel(head, text=t("title"), font=font(22, "bold")).pack(side="left")
        lang = ctk.CTkSegmentedButton(head, values=list(UI_LANGS), command=self.on_ui_lang, width=90)
        lang.set(i18n.LANG.upper())
        lang.pack(side="right")

        left = ctk.CTkFrame(b, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(24, 8))
        right = ctk.CTkFrame(b, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 24))
        left.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        self._files_card(left).grid(row=0, column=0, sticky="ew")
        self._stt_card(left).grid(row=1, column=0, sticky="ew", pady=12)
        self._format_card(left).grid(row=2, column=0, sticky="ew")
        self.log_box = ctk.CTkTextbox(left, height=90, corner_radius=12,
                                      font=ctk.CTkFont(family=mono_family(), size=12))
        self.log_box.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        self.log_box.insert("end", log_text)
        self.log_box.configure(state="disabled")
        left.grid_rowconfigure(3, weight=1)
        self._translate_card(right).grid(row=0, column=0, sticky="nsew")

        bottom = ctk.CTkFrame(b, fg_color="transparent")
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=24, pady=(14, 18))
        bottom.grid_columnconfigure(0, weight=1)
        self.go = ctk.CTkButton(bottom, text="", height=42, font=font(15, "bold"), command=self.on_go)
        self.go.grid(row=0, column=0, sticky="ew")
        self.open_btn = self._secondary(bottom, t("open_folder"), self.open_folder, width=150)
        self.open_btn.configure(height=42)
        self.open_btn.grid(row=0, column=1, padx=(10, 0))
        self.bar = ctk.CTkProgressBar(bottom, height=8)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        if not self.running and not getattr(self, "started", False):
            # niewidoczny (kolor tła), dopóki nie ruszy pierwsze zadanie — miejsce zostaje, układ nie skacze
            self.bar.configure(fg_color=BG, progress_color=BG)
        self.status = ctk.CTkLabel(bottom, text="", text_color=MUTED, font=font(12), anchor="w", height=18)
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self._set_running(self.running)

        self._render_files()
        self.refresh_info()

    def _set_icon(self):
        assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        try:
            if os.name == "nt":
                # CustomTkinter ustawia własną ikonę ~200 ms po starcie — nadpisujemy ją później
                self.after(300, lambda: self.iconbitmap(os.path.join(assets, "icon.ico")))
            else:
                self._icon = tk.PhotoImage(file=os.path.join(assets, "icon.png"))
                self.iconphoto(True, self._icon)
        except (tk.TclError, OSError):
            pass  # brak pliku ikony nie może zablokować programu

    def _enable_drop(self):
        """Pliki (i foldery) upuszczone gdziekolwiek na okno trafiają na listę."""
        if not TkinterDnD:
            return False
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
        except Exception:
            return False
        self.dnd_bind("<<DropEnter>>", lambda e: (self._drop_highlight(True), e.action)[1])
        self.dnd_bind("<<DropLeave>>", lambda e: (self._drop_highlight(False), e.action)[1])
        self.dnd_bind("<<Drop>>", self.on_drop)
        return True

    def _drop_highlight(self, on):
        self.files_card.configure(border_color=ACCENT if on else CARD_BORDER, border_width=2 if on else 1)

    def on_drop(self, event):
        self._drop_highlight(False)
        self.add_paths(self.tk.splitlist(event.data))
        return event.action

    def add_paths(self, paths):
        """Dodaje pliki; z folderu — wszystkie obsługiwane pliki w nim (bez podfolderów)."""
        supported = core.MEDIA_EXT + (".srt",)
        for p in paths:
            items = sorted(os.path.join(p, f) for f in os.listdir(p)) if os.path.isdir(p) else [p]
            for f in items:
                if os.path.isfile(f) and f.lower().endswith(supported):
                    if f not in self.paths:
                        self.paths.append(f)
                elif not os.path.isdir(p):
                    self.log(t("unsupported", name=os.path.basename(f)))
        self._render_files()

    def on_ui_lang(self, label):
        """Zmiana języka interfejsu: zapisz stan, przebuduj okno."""
        self._collect()
        self.cfg["ui_lang"] = UI_LANGS[label]
        core.save_config(self.cfg)
        i18n.set_lang(self.cfg["ui_lang"])
        log_text = self.log_box.get("1.0", "end-1c")
        self.body.destroy()
        self.build(log_text)

    # ------------------------------------------------------------ sekcje

    def _secondary(self, master, text, command, width=90):
        return ctk.CTkButton(master, text=text, width=width, command=command, fg_color="transparent",
                             border_width=1, text_color=TEXT, hover_color=CONTROL)

    def _files_card(self, master):
        c = self.files_card = Card(master, t("files"))
        self.file_list = ctk.CTkFrame(c, corner_radius=8)
        self.file_list.grid(row=1, column=0, columnspan=3, sticky="ew", padx=18)
        self.file_list.grid_columnconfigure(0, weight=1)
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.grid(row=2, column=0, columnspan=3, sticky="w", padx=18, pady=(10, 16))
        ctk.CTkButton(row, text=t("add_files"), width=130, command=self.add).pack(side="left")
        self._secondary(row, t("clear"), self.clear).pack(side="left", padx=8)
        return c

    def _stt_card(self, master):
        c = Card(master, t("stt"))
        self.speech_map = {t("auto"): None, **{core.lang_name(code): code for code in core.LANGUAGES}}
        ctk.CTkLabel(c, text=t("speech_lang")).grid(row=1, column=0, sticky="w", padx=18, pady=5)
        self.speech = ctk.CTkOptionMenu(c, values=list(self.speech_map), width=220, dynamic_resizing=False,
                                        command=self._autosave)
        saved = self.cfg.get("speech", "auto")
        code = None if saved in (None, "auto") else core.resolve_language(saved)
        self.speech.set(core.lang_name(code) if code in core.LANGUAGES else t("auto"))
        self.speech.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(c, text=t("model")).grid(row=2, column=0, sticky="w", padx=18, pady=5)
        self.model = ctk.CTkSegmentedButton(c, values=core.WHISPER_MODELS,
                                            command=lambda _: (self.refresh_info(), self._autosave()))
        self.model.set(self.cfg.get("model", "large-v3"))
        self.model.grid(row=2, column=1, sticky="w", padx=10, pady=5)
        self.stt_info = ctk.CTkLabel(c, text="", text_color=MUTED, font=font(12), justify="left", wraplength=440)
        self.stt_info.grid(row=3, column=0, columnspan=3, sticky="w", padx=18, pady=(4, 16))
        return c

    def _format_card(self, master):
        c = Card(master, t("format"))
        ctk.CTkLabel(c, text=t("chars")).grid(row=1, column=0, sticky="w", padx=18, pady=5)
        self.chars = ctk.CTkOptionMenu(c, values=[str(n) for n in (32, 37, 40, 42, 45, 50)], width=90,
                                       command=self._autosave)
        self.chars.set(str(self.cfg.get("chars", 42)))
        self.chars.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(c, text=t("lines")).grid(row=2, column=0, sticky="w", padx=18, pady=(5, 16))
        self.lines = ctk.CTkSegmentedButton(c, values=["1", "2", "3"], command=self._autosave)
        self.lines.set(str(self.cfg.get("lines", 2)))
        self.lines.grid(row=2, column=1, sticky="w", padx=10, pady=(5, 16))
        return c

    def _translate_card(self, master):
        c = Card(master, t("translation"))
        col = int(LABEL_COL * ctk.ScalingTracker.get_widget_scaling(self))  # minsize nie skaluje się sam
        c.grid_columnconfigure(0, minsize=col)
        ctk.CTkLabel(c, text=t("translator")).grid(row=1, column=0, sticky="w", padx=18, pady=5)
        labels = self._engine_labels()
        self.engine = ctk.CTkOptionMenu(c, values=list(labels.values()), command=self.on_engine,
                                        width=280, dynamic_resizing=False)
        self.engine.set(labels.get(self.engine_code, labels["cli"]))
        self.engine.grid(row=1, column=1, columnspan=2, sticky="w", padx=10, pady=5)
        # pola zależne od silnika (klucz / model / adres) — tylko to, czego dany silnik potrzebuje
        self.fields = ctk.CTkFrame(c, fg_color="transparent", corner_radius=0)
        self.fields.grid(row=2, column=0, columnspan=3, sticky="ew", padx=2)  # nie zasłaniaj obramowania karty
        self.fields.grid_columnconfigure(0, minsize=col - 2)
        self.fields.grid_columnconfigure(1, weight=1)
        self.tr_info = ctk.CTkLabel(c, text="", text_color=MUTED, font=font(12), justify="left", wraplength=440)
        self.tr_info.grid(row=3, column=0, columnspan=3, sticky="w", padx=18, pady=(2, 10))

        ctk.CTkLabel(c, text=t("translate_to"), font=font(13, "bold")).grid(
            row=4, column=0, columnspan=3, sticky="w", padx=18, pady=(4, 6))
        grid = ctk.CTkFrame(c, corner_radius=8)
        grid.grid(row=5, column=0, columnspan=3, sticky="ew", padx=18)
        grid.grid_anchor("nw")
        c.grid_rowconfigure(8, weight=1)  # wolne miejsce dostaje pole kontekstu
        self.targets = {}
        chosen = set(self.cfg.get("targets", []))
        langs = sorted(core.LANGUAGES, key=lambda code: (code not in ("pl", "en", "de"), core.lang_name(code)))
        for code in langs:
            self.targets[code] = tk.BooleanVar(value=code in chosen)
        self.check_grid = CheckGrid(grid, [(code, core.lang_name(code)) for code in langs], self.targets)
        self.check_grid.grid(row=0, column=0, sticky="nw", padx=6, pady=6)

        self.other = ctk.CTkEntry(c, placeholder_text=t("other_langs"))
        self._on_edit(self.other, self._autosave)
        if self._other_value(self.cfg.get("other", "")):
            self.other.insert(0, self.cfg["other"])
        self.other.grid(row=6, column=0, columnspan=3, sticky="ew", padx=18, pady=(12, 4))

        ctk.CTkLabel(c, text=t("context"), text_color=MUTED, font=font(12)).grid(
            row=7, column=0, columnspan=3, sticky="w", padx=18, pady=(10, 4))
        self.context = ctk.CTkTextbox(c, height=70, activate_scrollbars=False)  # mniej kanw = płynniejsza zmiana rozmiaru
        self.context.insert("1.0", self.cfg.get("context", ""))
        self.context.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=18, pady=(0, 16))
        self.context.bind("<KeyRelease>", self._autosave, add="+")
        for v in self.targets.values():
            v.trace_add("write", self._autosave)
        self._build_fields()
        self._apply_engine_limits()
        return c

    # ------------------------------------------------------------ tłumacz i klucze

    @staticmethod
    def _engine_labels():
        return {**core.ENGINES, "ollama": t("ollama_local"), "custom": t("custom_api")}

    def on_engine(self, label):
        self.engine_code = next(k for k, v in self._engine_labels().items() if v == label)
        self._build_fields()
        self._apply_engine_limits()
        self.refresh_info()
        self._autosave()

    def _apply_engine_limits(self):
        """DeepL tłumaczy tylko na swoje języki: reszta listy i pole „Inne języki” są wtedy nieaktywne."""
        deepl = self.engine_code == "deepl"
        self.check_grid.set_disabled([c for c, (_, _, d) in core.LANGUAGES.items() if deepl and not d])
        # „readonly”, nie „disabled”: kliknięcie zablokowanego pola w CTkEntry zamieniałoby tekst podpowiedzi
        # w „wpisaną” wartość (nie da się go wtedy skasować)
        self.other.configure(state="readonly" if deepl else "normal",
                             fg_color=CONTROL if deepl else ("#FFFFFF", "#191B1F"))

    def _build_fields(self):
        """Pola silnika w kolejności: adres serwera → klucz → model (lista modeli zależy od dwóch pierwszych)."""
        for w in self.fields.winfo_children():
            w.destroy()
        engine, row = self.engine_code, 0
        self.settings, self.key, self.model_box = {}, None, None
        fields = core.ENGINE_FIELDS.get(engine, ())

        def add_row(label, widget):
            nonlocal row
            ctk.CTkLabel(self.fields, text=label).grid(row=row, column=0, sticky="w", padx=16, pady=5)
            widget.grid(row=row, column=1, sticky="ew", padx=(10, 18), pady=5)
            row += 1

        if "url" in fields:
            w = ctk.CTkEntry(self.fields, placeholder_text=t("url_placeholder"))
            w.insert(0, core.engine_setting(self.cfg, engine, "url"))
            self._on_edit(w, self._store_settings)
            w.bind("<FocusOut>", lambda _: self._fetch_models(), add="+")
            self.settings["url"] = w
            add_row(t("server_url"), w)
        name = core.ENGINE_KEY.get(engine)
        if name:
            label = {"anthropic": t("key_anthropic"), "deepl": t("key_deepl")}.get(name, t("key"))
            hint = t("key_optional") if name == "custom" else t("key_placeholder")
            self.key = ctk.CTkEntry(self.fields, show="•", placeholder_text=hint)
            if self.keys.get(name):
                self.key.insert(0, self.keys[name])
            self._on_edit(self.key, self._store_key)
            add_row(label, self.key)
        if "model" in fields:
            value = core.engine_setting(self.cfg, engine, "model")
            # lista rozwijana uzupełniana w tle modelami z API; nazwę można też wpisać ręcznie
            self.model_box = ctk.CTkComboBox(self.fields, values=[value] if value else [],
                                             command=lambda _: self._store_settings())
            self.model_box.set(value)
            self._on_edit(self.model_box, self._store_settings)
            self.settings["model"] = self.model_box
            add_row(t("model"), self.model_box)
            self._fetch_models()

        if self.fields.winfo_children():  # pusta ramka CTk zachowałaby domyślne 200 px wysokości
            self.fields.grid()
        else:
            self.fields.grid_remove()

    def _fetch_models(self):
        """Pobiera listę modeli w tle (klucz / adres mogły się zmienić)."""
        if not self.model_box:
            return
        engine, keys, settings = self.engine_code, dict(self.keys), dict(self.cfg)
        self.models_id = getattr(self, "models_id", 0) + 1
        req = self.models_id
        threading.Thread(target=lambda: self.q.put(("models", (req, core.list_models(engine, keys, settings)))),
                         daemon=True).start()

    def _set_models(self, req, models):
        if req != self.models_id or not self.model_box or not models:
            return
        self.model_box.configure(values=models)
        if not self.model_box.get().strip():  # nic nie wybrano — weź pierwszy (najnowszy) model
            self.model_box.set(models[0])
            self._store_settings()

    def _on_edit(self, widget, callback):
        for event in ("<KeyRelease>", "<FocusOut>", "<<Paste>>"):  # wklejenie myszą nie daje KeyRelease
            widget.bind(event, lambda _: self.after(50, callback), add="+")

    def _store_settings(self):
        """Model / adres serwera — do config.json (to nie są sekrety)."""
        for field, w in self.settings.items():
            self.cfg[f"{self.engine_code}_{field}"] = w.get().strip()
        core.save_config(self.cfg)
        self.refresh_info()

    def _store_key(self):
        """Klucz trafia od razu do systemowego magazynu haseł, więc jest pamiętany między uruchomieniami."""
        name = core.ENGINE_KEY.get(self.engine_code)
        if not name or not self.key:
            return
        value = self.key.get().strip()
        if value == self.keys.get(name, ""):
            return
        try:
            core.set_key(name, value)
        except RuntimeError as e:
            self.log(str(e))
        self.keys[name] = value  # w tej sesji działa nawet bez magazynu
        self.refresh_info()
        # nowy klucz → nowa lista modeli (z opóźnieniem, żeby nie pytać API przy każdym znaku)
        if getattr(self, "_models_job", None):
            self.after_cancel(self._models_job)
        self._models_job = self.after(700, self._fetch_models)

    def refresh_info(self):
        engine, keys, model, settings = self.engine_code, dict(self.keys), self.model.get(), dict(self.cfg)
        self.tr_info.configure(text=t("checking"))
        self.info_id = getattr(self, "info_id", 0) + 1
        req = self.info_id

        def work():  # engine_info uruchamia `claude --version`, więc poza wątkiem GUI
            self.q.put(("info", (req, core.stt_info(model), core.engine_info(engine, keys, settings))))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ pliki

    def add(self):
        types = [(t("media_types"), " ".join("*" + e for e in core.MEDIA_EXT + (".srt",))), (t("all_files"), "*.*")]
        self.add_paths(filedialog.askopenfilenames(title=t("choose_files"), filetypes=types))

    def clear(self):
        self.paths.clear()
        self._render_files()

    def _render_files(self):
        for w in self.file_list.winfo_children():
            w.destroy()
        if not self.paths:
            ctk.CTkLabel(self.file_list, text=t("files_empty_dnd" if self.dnd else "files_empty"),
                         text_color=MUTED, font=font(12)).grid(
                row=0, column=0, pady=22)
            return
        last = len(self.paths) - 1
        for i, p in enumerate(self.paths):
            pad = (8 if i == 0 else 0, 8 if i == last else 0)
            name = ctk.CTkLabel(self.file_list, text=os.path.basename(p), anchor="w")
            name.grid(row=i, column=0, sticky="ew", padx=(14, 0), pady=pad)
            Tooltip(name, os.path.normpath(p))
            ctk.CTkLabel(self.file_list, text="SRT" if p.lower().endswith(".srt") else "media",
                         text_color=MUTED, font=font(12), width=50).grid(row=i, column=1, pady=pad)
            ctk.CTkButton(self.file_list, text="✕", width=28, height=24, fg_color="transparent",
                          text_color=MUTED, hover_color=CONTROL_HOVER,
                          command=lambda p=p: (self.paths.remove(p), self._render_files())).grid(
                row=i, column=2, padx=(0, 6), pady=pad)

    # ------------------------------------------------------------ log / kolejka

    def log(self, msg):
        self.q.put(("log", msg))

    def poll(self):
        self.check_grid.sync_mode()  # przełączenie jasny/ciemny w systemie
        while not self.q.empty():
            kind, val = self.q.get()
            if kind == "log":
                self.log_box.configure(state="normal")
                self.log_box.insert("end", val + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            elif kind == "progress":
                self._show_progress(*val)
            elif kind == "info" and val[0] == self.info_id:  # starsze, wolniejsze odpowiedzi pomijamy
                self.stt_info.configure(text=val[1])
                self.tr_info.configure(text=val[2])
            elif kind == "ask_exists":
                path, reply = val
                ExistsDialog(self, path, reply)
            elif kind == "models":
                self._set_models(*val)
            elif kind == "output":
                self.outputs.append(val)
                self.open_btn.configure(state="normal")
            elif kind == "done":
                self._set_running(False)
        self.after(100, self.poll)

    # ------------------------------------------------------------ praca

    def _autosave(self, *_):
        """Zapis ustawień chwilę po zmianie (wybór języków, modeli, formatu, kontekstu…)."""
        if getattr(self, "_save_job", None):
            self.after_cancel(self._save_job)
        self._save_job = self.after(500, self._save_now)

    def _save_now(self):
        self._save_job = None
        try:
            self._collect()
            core.save_config(self.cfg)
        except (tk.TclError, AttributeError):
            pass  # okno w trakcie przebudowy

    def on_close(self):
        self._save_now()
        core.CANCEL.set()  # zatrzymaj ewentualną pracę w tle
        self.destroy()

    def _collect(self):
        """Stan formularza → self.cfg (bez kluczy — te są w magazynie haseł)."""
        speech = self.speech_map[self.speech.get()]
        self.cfg.update(
            speech=speech or "auto", model=self.model.get(), engine=self.engine_code,
            targets=[c for c, v in self.targets.items() if v.get()], other=self._other_value(self.other.get()),
            chars=int(self.chars.get()), lines=int(self.lines.get()),
            context=self.context.get("1.0", "end").strip(),
        )

    @staticmethod
    def _other_value(text):
        """Wpisane „Inne języki” — bez tekstu podpowiedzi, gdyby kiedyś trafił do pola lub ustawień."""
        text = text.strip()
        hints = [v for k in ("other_langs",) for v in i18n.S[k]] + ["Inne języki (tylko Claude)", "Other languages (Claude only)"]
        return "" if any(text.startswith(h.split(",")[0]) for h in hints) else text

    def _targets(self):
        chosen = [c for c, v in self.targets.items() if v.get() and c not in self.check_grid.disabled]
        if self.engine_code != "deepl":
            chosen += [core.resolve_language(x) for x in self._other_value(self.other.get()).split(",") if x.strip()]
        return tuple(dict.fromkeys(chosen))

    def start(self):
        if not self.paths:
            self.log(t("add_first"))
            return
        self._collect()
        core.save_config(self.cfg)
        opts = core.Options(
            language=self.speech_map[self.speech.get()], model=self.model.get(), targets=self._targets(),
            engine=self.engine_code, context=self.cfg["context"], chars=self.cfg["chars"],
            lines=self.cfg["lines"], keys=dict(self.keys), settings=dict(self.cfg), on_exists=self._ask_exists,
        )
        self._exists_all = None  # odpowiedź „dla wszystkich” obowiązuje do końca tego zadania
        self._exists_lock = threading.Lock()
        core.CANCEL.clear()
        self.outputs = []
        self.started = True
        self.bar.configure(fg_color=CONTROL)
        self._set_running(True)
        threading.Thread(target=self.work, args=(list(self.paths), opts), daemon=True).start()

    def on_go(self):
        if not self.running:
            self.start()
        elif not core.CANCEL.is_set():
            core.CANCEL.set()  # wątek pracy zatrzyma się w najbliższym punkcie kontrolnym
            self.go.configure(text=t("stopping"), state="disabled")

    def _set_running(self, running):
        self.running = running
        if running:
            self.go.configure(text=t("stop"), state="normal", fg_color=DANGER_BG, hover_color=DANGER_HOVER,
                              text_color=DANGER_TEXT)
        else:
            self.go.configure(text=t("generate"), state="normal", fg_color=ACCENT, hover_color=ACCENT_HOVER,
                              text_color=("#FFFFFF", "#FFFFFF"))
        self.open_btn.configure(state="normal" if self.outputs else "disabled")

    def open_folder(self):
        """Jeden folder wyjściowy → otwórz go. Kilka (pliki z różnych folderów) → menu z listą folderów."""
        folders = {}
        for path in self.outputs:  # folder → ostatni zapisany w nim plik
            folders[os.path.normpath(os.path.dirname(path))] = path
        if len(folders) == 1:
            self._reveal(next(iter(folders.values())))
            return
        scale = ctk.ScalingTracker.get_widget_scaling(self)  # natywne menu nie skaluje się samo
        menu = tk.Menu(self, tearoff=0, font=tkfont.Font(family=ctk.ThemeManager.theme["CTkFont"]["family"],
                                                         size=-round(13 * scale)))
        for folder, path in folders.items():
            menu.add_command(label=folder, command=lambda p=path: self._reveal(p))
        x, y = self.open_btn.winfo_rootx(), self.open_btn.winfo_rooty()
        menu.update_idletasks()
        menu.tk_popup(x, y - menu.winfo_reqheight() - 4)

    @staticmethod
    def _reveal(path):
        """Pokazuje plik w menedżerze plików (zaznaczony, gdzie się da)."""
        import subprocess
        import sys

        if not os.path.exists(path):
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])

    def _ask_exists(self, path):
        """Wołane z wątku pracy: pyta w oknie głównym i czeka na odpowiedź (pytania po kolei)."""
        with self._exists_lock:
            if self._exists_all:
                return self._exists_all
            answered, result = threading.Event(), {}

            def reply(choice, for_all):
                result["choice"] = choice
                if for_all:
                    self._exists_all = choice
                answered.set()

            self.q.put(("ask_exists", (path, reply)))
            while not answered.wait(0.2):
                core.check_cancel()
            return result["choice"]

    def _show_progress(self, value, text):
        """value None = etap bez znanego postępu (ładowanie / pobieranie modelu) → animowany pasek."""
        if value is None:
            if self.bar.cget("mode") != "indeterminate":
                self.bar.configure(mode="indeterminate")
                self.bar.start()
        else:
            if self.bar.cget("mode") != "determinate":
                self.bar.stop()
                self.bar.configure(mode="determinate")
            # przy 0 CTk rysuje kropkę na początku paska — wtedy wypełnienie w kolorze tła
            self.bar.configure(progress_color=ACCENT if value > 0.005 else CONTROL)
            self.bar.set(value)
        self.status.configure(text=text)

    def work(self, files, opts):
        n = len(files)
        try:
            # najpierw wszystkie pytania o istniejące pliki — potem praca bez przerw
            plans = []
            for i, path in enumerate(files):
                stage = t("stage_checking") + (f" ({i + 1}/{n})" if n > 1 else "")
                self.q.put(("progress", (None, stage)))
                plans.append(core.plan_outputs(path, opts, self.log,
                                               lambda v, s=None, st=stage: self.q.put(("progress", (None, f"{st} · {s}" if s else st)))))
            for i, path in enumerate(files):
                self.log(f"=== {os.path.basename(path)}")
                prefix = os.path.basename(path) + (f" ({i + 1}/{n})" if n > 1 else "")

                def progress(v, stage=None, i=i, prefix=prefix):  # postęp pliku → postęp całej kolejki
                    overall = None if v is None else (i + v) / n
                    pct = "" if v is None else f"{v:.0%}"
                    self.q.put(("progress", (overall, " · ".join(x for x in (prefix, stage, pct) if x))))

                progress(0, "")
                core.process_file(path, opts, self.log, progress, saved=lambda out: self.q.put(("output", out)),
                                  plan=plans[i])
            self.q.put(("progress", (1.0, t("done"))))
            self.log(t("done"))
        except core.Cancelled:
            self.log(t("cancelled"))
            self.q.put(("progress", (0, t("cancelled"))))
        except Exception as e:
            self.log(t("error", err=e))
            self.log(traceback.format_exc())
        finally:
            self.q.put(("done", None))


if __name__ == "__main__":
    if os.name == "nt":  # własna ikona na pasku zadań zamiast ikony Pythona
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("maclask.SubtitleGenerator")
    ctk.set_appearance_mode("system")
    App().mainloop()
