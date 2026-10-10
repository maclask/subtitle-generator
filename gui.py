"""Generator napisów / Subtitle Generator — GUI."""
import os
import queue
import threading
import traceback
from tkinter import filedialog
from tkinter import font as tkfont

import customtkinter as ctk

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


def apply_theme(root):
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


class Card(ctk.CTkFrame):
    """Sekcja z tytułem."""

    def __init__(self, master, title):
        super().__init__(master, border_width=1)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=title, font=font(14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(14, 8))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        apply_theme(self)
        self.geometry("1120x800")
        self.minsize(980, 720)
        self.q = queue.Queue()
        self.cfg = core.load_config()
        i18n.set_lang(self.cfg.get("ui_lang"))
        self.keys = core.api_keys(self.cfg)
        self.paths = []
        self.engine_code = self.cfg.get("engine", "cli")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.build()
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
        self.go = ctk.CTkButton(bottom, text=t("generate"), height=42, font=font(15, "bold"), command=self.start)
        self.go.grid(row=0, column=0, sticky="ew")
        self.bar = ctk.CTkProgressBar(bottom, height=6)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", pady=(12, 0))

        self._render_files()
        self.refresh_info()

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
        c = Card(master, t("files"))
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
        self.speech = ctk.CTkOptionMenu(c, values=list(self.speech_map), width=220, dynamic_resizing=False)
        saved = self.cfg.get("speech", "pl")
        code = None if saved in (None, "auto") else core.resolve_language(saved)
        self.speech.set(core.lang_name(code) if code in core.LANGUAGES else t("auto"))
        self.speech.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(c, text=t("model")).grid(row=2, column=0, sticky="w", padx=18, pady=5)
        self.model = ctk.CTkSegmentedButton(c, values=core.WHISPER_MODELS, command=lambda _: self.refresh_info())
        self.model.set(self.cfg.get("model", "large-v3"))
        self.model.grid(row=2, column=1, sticky="w", padx=10, pady=5)
        self.stt_info = ctk.CTkLabel(c, text="", text_color=MUTED, font=font(12), justify="left", wraplength=440)
        self.stt_info.grid(row=3, column=0, columnspan=3, sticky="w", padx=18, pady=(4, 16))
        return c

    def _format_card(self, master):
        c = Card(master, t("format"))
        ctk.CTkLabel(c, text=t("chars")).grid(row=1, column=0, sticky="w", padx=18, pady=5)
        self.chars = ctk.CTkOptionMenu(c, values=[str(n) for n in (32, 37, 40, 42, 45, 50)], width=90)
        self.chars.set(str(self.cfg.get("chars", 42)))
        self.chars.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(c, text=t("lines")).grid(row=2, column=0, sticky="w", padx=18, pady=(5, 16))
        self.lines = ctk.CTkSegmentedButton(c, values=["1", "2", "3"])
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
        grid.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=18)
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="lang")
        c.grid_rowconfigure(5, weight=1)
        self.targets = {}
        chosen = set(self.cfg.get("targets", []))
        langs = sorted(core.LANGUAGES, key=lambda code: (code not in ("pl", "en", "de"), core.lang_name(code)))
        for i, code in enumerate(langs):
            v = ctk.BooleanVar(value=code in chosen)
            ctk.CTkCheckBox(grid, text=core.lang_name(code), variable=v, checkbox_width=18, checkbox_height=18,
                            font=font(13)).grid(row=i // 4, column=i % 4, sticky="w", padx=12,
                                                pady=(10 if i < 4 else 3, 10 if i >= len(langs) - 4 else 3))
            self.targets[code] = v

        self.other = ctk.CTkEntry(c, placeholder_text=t("other_langs"))
        if self.cfg.get("other"):
            self.other.insert(0, self.cfg["other"])
        self.other.grid(row=6, column=0, columnspan=3, sticky="ew", padx=18, pady=(12, 4))

        ctk.CTkLabel(c, text=t("context"), text_color=MUTED, font=font(12)).grid(
            row=7, column=0, columnspan=3, sticky="w", padx=18, pady=(10, 4))
        self.context = ctk.CTkTextbox(c, height=70)
        self.context.insert("1.0", self.cfg.get("context", ""))
        self.context.grid(row=8, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 16))
        self._build_fields()
        return c

    # ------------------------------------------------------------ tłumacz i klucze

    @staticmethod
    def _engine_labels():
        return {**core.ENGINES, "ollama": t("ollama_local"), "custom": t("custom_api")}

    def on_engine(self, label):
        self.engine_code = next(k for k, v in self._engine_labels().items() if v == label)
        self._build_fields()
        self.refresh_info()

    def _build_fields(self):
        for w in self.fields.winfo_children():
            w.destroy()
        engine, row = self.engine_code, 0
        self.settings = {}
        for field in core.ENGINE_FIELDS.get(engine, ()):
            value = core.engine_setting(self.cfg, engine, field)
            if engine == "ollama" and field == "model":
                models = core.ollama_models(core.engine_setting(self.cfg, "ollama", "url"))
                w = ctk.CTkComboBox(self.fields, values=models or [""], command=lambda _: self._store_settings())
                w.set(value or (models[0] if models else ""))
            else:
                w = ctk.CTkEntry(self.fields, placeholder_text=t("url_placeholder") if field == "url" else "")
                if value:
                    w.insert(0, value)
            self._on_edit(w, self._store_settings)
            ctk.CTkLabel(self.fields, text=t("server_url") if field == "url" else t("model")).grid(
                row=row, column=0, sticky="w", padx=16, pady=5)
            w.grid(row=row, column=1, sticky="ew", padx=(10, 18), pady=5)
            self.settings[field] = w
            row += 1
        self.key = None
        name = core.ENGINE_KEY.get(engine)
        if name:
            label = {"anthropic": t("key_anthropic"), "deepl": t("key_deepl")}.get(name, t("key"))
            hint = t("key_optional") if name == "custom" else t("key_placeholder")
            self.key = ctk.CTkEntry(self.fields, show="•", placeholder_text=hint)
            if self.keys.get(name):
                self.key.insert(0, self.keys[name])
            self._on_edit(self.key, self._store_key)
            ctk.CTkLabel(self.fields, text=label).grid(row=row, column=0, sticky="w", padx=16, pady=5)
            self.key.grid(row=row, column=1, sticky="ew", padx=(10, 18), pady=5)
        if engine == "ollama" and not self.cfg.get("ollama_model"):
            self._store_settings()  # zapamiętaj pierwszy zainstalowany model jako domyślny

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
        for p in filedialog.askopenfilenames(title=t("choose_files"), filetypes=types):
            if p not in self.paths:
                self.paths.append(p)
        self._render_files()

    def clear(self):
        self.paths.clear()
        self._render_files()

    def _render_files(self):
        for w in self.file_list.winfo_children():
            w.destroy()
        if not self.paths:
            ctk.CTkLabel(self.file_list, text=t("files_empty"), text_color=MUTED, font=font(12)).grid(
                row=0, column=0, pady=22)
            return
        last = len(self.paths) - 1
        for i, p in enumerate(self.paths):
            pad = (8 if i == 0 else 0, 8 if i == last else 0)
            ctk.CTkLabel(self.file_list, text=os.path.basename(p), anchor="w").grid(
                row=i, column=0, sticky="ew", padx=(14, 0), pady=pad)
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
        while not self.q.empty():
            kind, val = self.q.get()
            if kind == "log":
                self.log_box.configure(state="normal")
                self.log_box.insert("end", val + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            elif kind == "progress":
                self.bar.set(val)
            elif kind == "info" and val[0] == self.info_id:  # starsze, wolniejsze odpowiedzi pomijamy
                self.stt_info.configure(text=val[1])
                self.tr_info.configure(text=val[2])
            elif kind == "done":
                self.go.configure(state="normal", text=t("generate"))
        self.after(100, self.poll)

    # ------------------------------------------------------------ praca

    def _collect(self):
        """Stan formularza → self.cfg (bez kluczy — te są w magazynie haseł)."""
        speech = self.speech_map[self.speech.get()]
        self.cfg.update(
            speech=speech or "auto", model=self.model.get(), engine=self.engine_code,
            targets=[c for c, v in self.targets.items() if v.get()], other=self.other.get().strip(),
            chars=int(self.chars.get()), lines=int(self.lines.get()),
            context=self.context.get("1.0", "end").strip(),
        )

    def _targets(self):
        chosen = [c for c, v in self.targets.items() if v.get()]
        chosen += [core.resolve_language(x) for x in self.other.get().split(",") if x.strip()]
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
            lines=self.cfg["lines"], keys=dict(self.keys), settings=dict(self.cfg),
        )
        self.go.configure(state="disabled", text=t("working"))
        threading.Thread(target=self.work, args=(list(self.paths), opts), daemon=True).start()

    def work(self, files, opts):
        try:
            for path in files:
                self.log(f"=== {os.path.basename(path)}")
                self.q.put(("progress", 0))
                core.process_file(path, opts, self.log, lambda v: self.q.put(("progress", v)))
            self.log(t("done"))
        except Exception as e:
            self.log(t("error", err=e))
            self.log(traceback.format_exc())
        finally:
            self.q.put(("done", None))


if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    App().mainloop()
