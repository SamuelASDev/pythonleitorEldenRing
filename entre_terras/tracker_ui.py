"""Desktop control panel for the journey, boss history and in-game display."""
from copy import deepcopy
from datetime import datetime
import csv
import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from entre_terras.global_hotkeys import GlobalHotkeys, validate_hotkeys
from entre_terras.tracker_runtime import CaptureWorker
from entre_terras.tracker_state import DEFAULTS, HOTKEY_LABELS, validate_settings
from entre_terras.vision import BASE_DIR

BG = "#10151d"
SURFACE = "#18212d"
TEXT = "#edf1f5"
MUTED = "#a7b4c5"
GOLD = "#dfbd7e"


class ScrollPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, padding=(4, 6, 10, 6))
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._resize)
        self.canvas.bind("<Configure>", self._resize)
        self.winfo_toplevel().bind("<MouseWheel>", self._wheel, add="+")

    def _resize(self, event=None):
        self.canvas.itemconfigure(self.window, width=max(1, self.canvas.winfo_width()), height=max(self.canvas.winfo_height(), self.body.winfo_reqheight()))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        if self.winfo_ismapped() and not isinstance(event.widget, (ttk.Spinbox, ttk.Combobox)):
            self.canvas.yview_scroll(-int(event.delta / 120), "units")


class ControlPanel:
    def __init__(self, root, journey, store, reference, debug=False, enable_tray=True):
        self.root, self.journey, self.store = root, journey, store
        self.events = queue.Queue()
        self.closed = False
        self.pending_settings = None
        self.settings_token = 0
        self.runtime_status = "Conectando ao jogo"
        self.shortcut_status = "Registrando atalhos..."
        self.score = 0.
        self.connected = False
        self._loading_form = True
        self.root.title("Entre Terras • Contador de mortes")
        self.root.geometry("1000x790")
        self.root.minsize(900, 700)
        self.root.configure(bg=BG)
        self.tray = None
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        if (BASE_DIR / "assets/entre-terras.ico").exists():
            self.root.iconbitmap(str(BASE_DIR / "assets/entre-terras.ico"))
        self.root.bind("<Unmap>", self._on_minimize)
        self._styles()
        self._build()
        self.hotkeys = GlobalHotkeys(self.events)
        self.hotkeys.configure(journey.settings["hotkeys"], "initial")
        self.worker = CaptureWorker(self.events, reference, journey.settings, journey.data["paused"], debug)
        self._load_form(journey.settings)
        self._loading_form = False
        self.refresh()
        if enable_tray:
            from entre_terras.desktop_integration import TrayIcon
            self.tray = TrayIcon(self.events)
        self.root.after(80, self.poll)
        if store.warning:
            self.root.after(300, lambda: messagebox.showwarning("Recuperação dos dados", store.warning, parent=root))

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10), borderwidth=0)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Card.TLabel", background=SURFACE)
        style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
        style.configure("Value.TLabel", background=SURFACE, foreground=GOLD, font=("Segoe UI", 38, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("TButton", background="#263345", foreground=TEXT, padding=(14, 8))
        style.map("TButton", background=[("active", "#35475f"), ("disabled", "#202a38")], foreground=[("disabled", "#738196")])
        style.configure("Accent.TButton", background=GOLD, foreground="#171b22", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#f0d49e"), ("disabled", "#655d4c")])
        style.configure("TEntry", fieldbackground="#202c3b", foreground=TEXT, insertcolor=TEXT, padding=7, bordercolor="#35475b", lightcolor="#35475b", darkcolor="#35475b")
        style.configure("TSpinbox", fieldbackground="#202c3b", foreground=TEXT, arrowsize=16, padding=5)
        style.configure("TCombobox", fieldbackground="#202c3b", foreground=TEXT, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#202c3b")], foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, padding=5)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TNotebook", background=BG, tabmargins=(0, 8, 0, 12), bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED, padding=(18, 10), bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.map("TNotebook.Tab", background=[("selected", "#2c3b4d")], foreground=[("selected", GOLD)])
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=34)
        style.configure("Treeview.Heading", background="#253244", foreground=MUTED, padding=8)
        style.configure("Vertical.TScrollbar", background="#34445a", troughcolor=BG, bordercolor=BG, lightcolor="#34445a", darkcolor="#34445a", arrowcolor=MUTED)
        style.map("Treeview", background=[("selected", "#35475b")], foreground=[("selected", "#fff5dd")])
        self.root.option_add("*TCombobox*Listbox.background", SURFACE)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)

    def _build(self):
        shell = ttk.Frame(self.root, padding=(26, 20))
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 12))
        identity = ttk.Frame(header)
        identity.pack(side="left")
        ttk.Label(identity, text="ENTRE TERRAS", font=("Segoe UI", 22, "bold"), foreground=GOLD).pack(anchor="w")
        ttk.Label(identity, text="Sua jornada, uma tentativa por vez.", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Button(header, text="Encerrar", command=self.close).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Minimizar", command=self.hide_window).pack(side="right")
        toolbar = ttk.Frame(shell)
        toolbar.pack(fill="x", pady=(0, 8))
        self.health_var = tk.StringVar(value="Conectando")
        ttk.Label(toolbar, textvariable=self.health_var, foreground=MUTED).pack(side="left")
        self.pause_var = tk.StringVar()
        ttk.Button(toolbar, textvariable=self.pause_var, command=lambda: self.action("pause")).pack(side="right")
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True)
        dashboard_scroll = ScrollPage(self.tabs)
        self.dashboard = dashboard_scroll.body
        self.history_page = ttk.Frame(self.tabs, padding=(4, 6))
        overlay_scroll = ScrollPage(self.tabs)
        self.overlay_page = overlay_scroll.body
        settings_scroll = ScrollPage(self.tabs)
        self.settings_page = settings_scroll.body
        for page, title in ((dashboard_scroll, "Jornada"), (self.history_page, "Chefes e histórico"), (overlay_scroll, "Texto no jogo"), (settings_scroll, "Atalhos e detecção")):
            self.tabs.add(page, text=title)
        self._dashboard()
        self._history()
        self._overlay()
        self._settings()
        footer = ttk.Frame(shell)
        footer.pack(side="bottom", fill="x", pady=(12, 0), before=self.tabs)
        self.notice_var = tk.StringVar(value="Pronto. Contagens e histórico são salvos automaticamente.")
        ttk.Label(footer, textvariable=self.notice_var, style="Muted.TLabel", wraplength=600).pack(side="left")
        self.save_button = ttk.Button(footer, text="Salvar configurações", style="Accent.TButton", command=self.apply_settings)
        self.save_button.pack(side="right")

    def _dashboard(self):
        row = ttk.Frame(self.dashboard)
        row.pack(fill="x")
        row.columnconfigure((0, 1), weight=1, uniform="cards")
        self.total_var = tk.StringVar()
        self.boss_count_var = tk.StringVar()
        self.boss_title_var = tk.StringVar()
        for index, title, value in ((0, "TOTAL DA JORNADA", self.total_var), (1, "CHEFE ATIVO", self.boss_count_var)):
            card = ttk.Frame(row, style="Card.TFrame", padding=20)
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 8) if index == 0 else (8, 0))
            ttk.Label(card, text=title, style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=value, style="Value.TLabel").pack(anchor="w", pady=(4, 0))
            if index == 0:
                ttk.Label(card, text="Independente das sessões de chefes", style="CardMuted.TLabel").pack(anchor="w")
            else:
                ttk.Label(card, textvariable=self.boss_title_var, style="CardMuted.TLabel", wraplength=350).pack(anchor="w")
            controls = ttk.Frame(card, style="Card.TFrame")
            controls.pack(fill="x", pady=(16, 0))
            target = "total" if index == 0 else "boss"
            for text, operation in (("−1", "down"), ("+1", "up"), ("Zerar", "reset")):
                ttk.Button(controls, text=text, command=lambda a=f"{target}_{operation}": self.action(a, confirm=True)).pack(side="left", padx=(0, 5))
            ttk.Button(controls, text="Editar", command=lambda t=target: self.edit_count(t)).pack(side="left")
        section = ttk.Frame(self.dashboard)
        section.pack(fill="x", pady=(24, 0))
        ttk.Label(section, text="Uma luta de cada vez", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(section, text="Mortes detectadas somam ao geral e ao chefe ativo. Correções manuais alteram apenas o alvo escolhido.", style="Muted.TLabel", wraplength=870).pack(anchor="w", pady=(6, 14))
        start = ttk.Frame(section)
        start.pack(fill="x")
        self.new_boss_var = tk.StringVar()
        ttk.Label(start, text="Nome do chefe").pack(side="left", padx=(0, 10))
        name = ttk.Entry(start, textvariable=self.new_boss_var)
        name.pack(side="left", fill="x", expand=True)
        name.bind("<Return>", lambda event: self.start_boss())
        self.start_button = ttk.Button(start, text="Iniciar sessão", style="Accent.TButton", command=self.start_boss)
        self.start_button.pack(side="left", padx=(10, 0))
        actions = ttk.Frame(section)
        actions.pack(fill="x", pady=(14, 0))
        self.victory_button = ttk.Button(actions, text="Chefe vencido • salvar", style="Accent.TButton", command=lambda: self.finish_boss(True))
        self.victory_button.pack(side="left")
        self.archive_button = ttk.Button(actions, text="Arquivar sem vitória", command=lambda: self.finish_boss(False))
        self.archive_button.pack(side="left", padx=10)
        ttk.Button(actions, text="Abrir pasta dos dados", command=self.open_data).pack(side="right")
        self.summary_var = tk.StringVar()
        ttk.Label(section, textvariable=self.summary_var, style="Muted.TLabel").pack(anchor="w", pady=(20, 0))
        ttk.Label(section, text="Minimizar ou fechar a janela envia o painel para a bandeja. Para sair, use Encerrar.", style="Muted.TLabel", wraplength=860).pack(anchor="w", pady=(10, 0))

    def _history(self):
        ttk.Label(self.history_page, text="Cada chefe tem sua própria história", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self.history_page, text="Encerrar uma luta preserva as mortes. Editar um registro não altera o contador geral.", style="Muted.TLabel").pack(anchor="w", pady=(6, 15))
        table = ttk.Frame(self.history_page)
        table.pack(fill="both", expand=True)
        columns = ("name", "deaths", "result", "started", "ended", "pinned")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for key, title, width in zip(columns, ("Chefe", "Mortes", "Situação", "Início", "Encerramento", "No jogo"), (200, 65, 110, 140, 140, 70)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55, stretch=key == "name")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda event: self.edit_history())
        actions = ttk.Frame(self.history_page)
        actions.pack(fill="x", pady=(15, 0))
        for text, command in (("Editar registro", self.edit_history), ("Fixar / retirar do jogo", self.toggle_pin), ("Exportar CSV", self.export_history)):
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=(0, 8))
        ttk.Label(self.history_page, text="Você pode fixar até 6 chefes do histórico abaixo do chefe ativo. O total geral permanece sempre no topo.", style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=(12, 0))

    def _overlay(self):
        self.form = {}
        ttk.Label(self.overlay_page, text="Do seu jeito, dentro do jogo", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self.overlay_page, text="O total geral ocupa a primeira linha. Use os campos entre chaves para inserir as contagens.", style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=(6, 16))
        for key, label, hint in (("total_template", "Linha do contador geral", "Campo obrigatório: {total}  •  Exemplo: Jornada = {total}"), ("boss_template", "Linha de cada chefe", "Campos: {nome}, {mortes}  •  Exemplo: {nome} = {mortes}")):
            ttk.Label(self.overlay_page, text=label).pack(anchor="w", pady=(8, 5))
            self.form[key] = tk.StringVar()
            ttk.Entry(self.overlay_page, textvariable=self.form[key]).pack(fill="x")
            ttk.Label(self.overlay_page, text=hint, style="Muted.TLabel").pack(anchor="w", pady=(4, 8))
        for key, text in (("show_boss", "Mostrar chefe ativo e registros fixados"), ("show_status", "Mostrar status de captura / pausa")):
            self.form[key] = tk.BooleanVar()
            ttk.Checkbutton(self.overlay_page, text=text, variable=self.form[key]).pack(anchor="w")
        ttk.Label(self.overlay_page, text="PRÉVIA DO TEXTO", foreground=GOLD).pack(anchor="w", pady=(18, 8))
        self.preview = tk.Text(self.overlay_page, height=6, bg="#090e15", fg=GOLD, font=("Consolas", 13), relief="flat", padx=16, pady=12, wrap="word", state="disabled")
        self.preview.pack(fill="both", expand=True)

    def _settings(self):
        self.hotkey_vars = {}
        self.settings_page.columnconfigure(0, weight=3)
        self.settings_page.columnconfigure(1, weight=2)
        left = ttk.Frame(self.settings_page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 25))
        right = ttk.Frame(self.settings_page)
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(left, text="Atalhos globais", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(left, text="Funcionam com o jogo em foco. Vazio = desativado.", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 14))
        for index, (action, label) in enumerate(HOTKEY_LABELS.items(), 2):
            ttk.Label(left, text=label).grid(row=index, column=0, sticky="w", padx=(0, 12), pady=5)
            self.hotkey_vars[action] = tk.StringVar()
            ttk.Entry(left, textvariable=self.hotkey_vars[action], width=23).grid(row=index, column=1, sticky="ew", pady=5)
        ttk.Label(left, text="Ex.: Ctrl+Alt+F8, Ctrl+Shift+PageUp\nAtalhos de zerar e vencer executam imediatamente.\nGeral e chefe possuem atalhos separados.", style="Muted.TLabel", wraplength=440).grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.hotkey_status_var = tk.StringVar()
        ttk.Label(left, textvariable=self.hotkey_status_var, foreground=GOLD, wraplength=450).grid(row=11, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Label(right, text="Detecção", style="Heading.TLabel").pack(anchor="w", pady=(0, 8))
        self.form["capture"] = tk.StringVar()
        ttk.Label(right, text="Captura").pack(anchor="w", pady=(6, 4))
        ttk.Combobox(right, textvariable=self.form["capture"], values=("rtss", "dxgi"), state="readonly", width=22).pack(fill="x")
        specs = (("monitor", "Monitor (somente DXGI)", 0, 16, 1), ("fps", "Consultas por segundo", 1, 15, 1), ("threshold", "Semelhança mínima", .5, .95, .01), ("confirmation_frames", "Quadros para confirmar", 2, 5, 1), ("clear_seconds", "Segundos sem texto para rearmar", 1, 10, .5))
        for key, label, low, high, step in specs:
            self.form[key] = tk.StringVar()
            ttk.Label(right, text=label).pack(anchor="w", pady=(10, 4))
            ttk.Spinbox(right, textvariable=self.form[key], from_=low, to=high, increment=step, width=22).pack(fill="x")
        ttk.Button(right, text="Restaurar padrões", command=lambda: self._load_form(DEFAULTS)).pack(fill="x", pady=(18, 0))
        for variable in list(self.form.values()) + list(self.hotkey_vars.values()):
            variable.trace_add("write", self.form_changed)

    def _load_form(self, settings):
        for key, variable in self.form.items():
            variable.set(settings[key])
        for key, variable in self.hotkey_vars.items():
            variable.set(settings["hotkeys"][key])

    def form_changed(self, *_):
        if not self._loading_form:
            self.notice_var.set("Configurações alteradas. Clique em Salvar configurações para aplicar.")
        self.update_preview()

    def update_preview(self):
        if not hasattr(self, "preview"):
            return
        try:
            settings = deepcopy(self.journey.settings)
            for key in ("total_template", "boss_template", "show_boss", "show_status"):
                settings[key] = self.form[key].get()
            settings = validate_settings(settings)
            data = deepcopy(self.journey.data)
            data["settings"] = settings
            from entre_terras.tracker_state import Journey
            preview = Journey(data)
            if not preview.active and not any(s["pinned"] for s in data["sessions"]):
                sample = preview.start("Margit")
                sample["deaths"] = 7
                text = preview.overlay(self.runtime_status) + "\n\nExemplo de chefe; nenhuma sessão foi criada."
            else:
                text = preview.overlay(self.runtime_status)
        except (ValueError, KeyError, tk.TclError) as error:
            text = f"Confira o formato: {error}"
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def save(self):
        try:
            self.store.save(self.journey)
        except (OSError, ValueError) as error:
            self.notice_var.set(f"Não foi possível salvar: {error}. Os valores permanecem nesta janela.")
            return False
        self.notice_var.set("Salvo automaticamente às " + datetime.now().strftime("%H:%M:%S"))
        return True

    def changed(self, notice=None):
        saved = self.save()
        if notice and saved:
            self.notice_var.set(notice)
        self.refresh()
        self.worker.configure(self.journey.settings, self.journey.data["paused"])

    def refresh(self):
        data = self.journey.data
        active = self.journey.active
        self.total_var.set(str(data["total"]))
        self.boss_count_var.set(str(active["deaths"]) if active else "—")
        self.boss_title_var.set(active["name"] if active else "Nenhuma sessão em andamento")
        self.pause_var.set("Retomar detecção" if data["paused"] else "Pausar detecção")
        for button in (self.victory_button, self.archive_button):
            button.configure(state="normal" if active else "disabled")
        self.start_button.configure(state="disabled" if active else "normal")
        won = sum(s["status"] == "won" for s in data["sessions"])
        ended = sum(s["status"] != "active" for s in data["sessions"])
        self.summary_var.set(f"{won} chefes vencidos   •   {ended} sessões arquivadas   •   Histórico preservado entre execuções")
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for session in reversed(data["sessions"]):
            def date(value):
                if not value:
                    return "—"
                try:
                    return datetime.fromisoformat(value).strftime("%d/%m/%y %H:%M")
                except ValueError:
                    return value
            self.tree.insert("", "end", iid=session["id"], values=(session["name"], session["deaths"], {"active": "Em andamento", "won": "Vencido", "archived": "Arquivado"}[session["status"]], date(session["started"]), date(session["ended"]), "Sim" if session["pinned"] else "—"))
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        self.update_preview()
        self.worker.set_overlay(self.journey.overlay(self.runtime_status))

    def action(self, action, confirm=False):
        try:
            if action == "pause":
                self.journey.data["paused"] = not self.journey.data["paused"]
            elif action == "victory":
                self.finish_boss(True)
                return
            else:
                target, operation = action.split("_")
                if target == "boss":
                    if not self.journey.active:
                        raise ValueError("Inicie uma sessão de chefe para usar este controle.")
                    target = self.journey.active["id"]
                if operation == "reset":
                    if confirm and not messagebox.askyesno("Zerar contagem", "Zerar apenas este contador? Os demais serão preservados.", parent=self.root):
                        return
                    self.journey.set_count(target, 0)
                else:
                    self.journey.adjust(target, 1 if operation == "up" else -1)
            self.changed()
        except ValueError as error:
            if confirm:
                messagebox.showinfo("Contador", str(error), parent=self.root)
            else:
                self.notice_var.set(str(error))

    def edit_count(self, target):
        if target == "boss":
            if not self.journey.active:
                messagebox.showinfo("Chefe ativo", "Inicie uma sessão primeiro.", parent=self.root)
                return
            target = self.journey.active["id"]
        current = self.journey.data["total"] if target == "total" else self.journey.active["deaths"]
        number = simpledialog.askinteger("Corrigir contagem", "Novo número de mortes (somente este contador):", initialvalue=current, minvalue=0, parent=self.root)
        if number is not None:
            self.journey.set_count(target, number)
            self.changed()

    def start_boss(self):
        try:
            self.journey.start(self.new_boss_var.get())
            self.new_boss_var.set("")
            self.changed()
        except ValueError as error:
            messagebox.showinfo("Iniciar sessão", str(error), parent=self.root)

    def finish_boss(self, won):
        try:
            session = self.journey.finish(won)
            self.changed(f"{session['name']}: {session['deaths']} mortes. Sessão salva no histórico.")
        except ValueError as error:
            self.notice_var.set(str(error))

    def selected_session(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Histórico", "Selecione um registro na lista.", parent=self.root)
            return None
        return next(s for s in self.journey.data["sessions"] if s["id"] == selected[0])

    def edit_history(self):
        session = self.selected_session()
        if session is None:
            return
        name = simpledialog.askstring("Editar registro", "Nome do chefe:", initialvalue=session["name"], parent=self.root)
        if name is None:
            return
        try:
            name = self.journey.clean_name(name)
        except ValueError as error:
            messagebox.showerror("Nome inválido", str(error), parent=self.root)
            return
        number = simpledialog.askinteger("Editar registro", "Mortes deste chefe (não altera o total geral):", initialvalue=session["deaths"], minvalue=0, parent=self.root)
        if number is not None:
            session["name"] = name
            self.journey.set_count(session["id"], number)
            self.changed()

    def toggle_pin(self):
        session = self.selected_session()
        if session is None:
            return
        if session["status"] == "active":
            messagebox.showinfo("Mostrar no jogo", "O chefe ativo já aparece no contador. Você pode fixá-lo depois de encerrar a sessão.", parent=self.root)
            return
        if not session["pinned"] and sum(s["pinned"] for s in self.journey.data["sessions"]) >= 6:
            messagebox.showinfo("Mostrar no jogo", "Retire um dos 6 registros fixados antes de adicionar outro.", parent=self.root)
            return
        session["pinned"] = not session["pinned"]
        self.changed()

    def export_history(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Exportar histórico", defaultextension=".csv", initialfile="historico-chefes.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output, delimiter=";")
                writer.writerow(("Chefe", "Mortes", "Situação", "Início", "Encerramento"))
                for session in self.journey.data["sessions"]:
                    # Avoid spreadsheet formula execution for user-entered names.
                    name = session["name"]
                    if name.startswith(("=", "+", "-", "@")):
                        name = "'" + name
                    writer.writerow((name, session["deaths"], session["status"], session["started"], session["ended"] or ""))
            self.notice_var.set("Histórico exportado.")
        except OSError as error:
            messagebox.showerror("Exportação", str(error), parent=self.root)

    def open_data(self):
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        os.startfile(self.store.path.parent)

    def apply_settings(self):
        if self.pending_settings is not None:
            return
        try:
            settings = deepcopy(self.journey.settings)
            for key, variable in self.form.items():
                value = variable.get()
                if key in ("fps", "monitor", "confirmation_frames"):
                    value = int(value)
                elif key in ("threshold", "clear_seconds"):
                    value = float(value.replace(",", "."))
                settings[key] = value
            settings["hotkeys"] = {key: variable.get().strip() for key, variable in self.hotkey_vars.items()}
            settings = validate_settings(settings)
            validate_hotkeys(settings["hotkeys"])
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Confira as configurações", str(error), parent=self.root)
            return
        self.pending_settings = settings
        self.settings_token += 1
        self.save_button.configure(state="disabled")
        self.hotkeys.configure(settings["hotkeys"], self.settings_token)

    def poll(self):
        if self.closed:
            return
        latest_health = None
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "death":
                if self.journey.record_death():
                    self.changed()
            elif event[0] == "tray":
                if event[1] == "show":
                    self.show_window()
                elif event[1] == "pause":
                    self.action("pause")
                elif event[1] == "quit":
                    self.close()
                    return
            elif event[0] == "hotkey":
                if self.root.grab_current() is None:
                    self.action(event[1])
            elif event[0] == "health":
                latest_health = event
            elif event[0] == "hotkeys_result":
                _, token, success, message = event
                self.shortcut_status = message
                self.hotkey_status_var.set(message)
                if token != "initial":
                    self.save_button.configure(state="normal")
                    if success and self.pending_settings is not None:
                        self.journey.data["settings"] = self.pending_settings
                        self.changed()
                    elif not success:
                        messagebox.showerror("Atalhos indisponíveis", message + "\nAs configurações anteriores foram mantidas.", parent=self.root)
                    self.pending_settings = None
                elif not success:
                    self.notice_var.set("Atalhos não foram ativados. Escolha outras combinações em Atalhos e detecção.")
        if latest_health:
            _, self.runtime_status, self.score, self.connected = latest_health
            capture = self.journey.settings["capture"].upper()
            self.health_var.set(f"{capture}  •  {self.runtime_status[:85]}  •  semelhança {self.score:.2f}")
            self.worker.set_overlay(self.journey.overlay(self.runtime_status if len(self.runtime_status) < 60 else "Aguardando captura do jogo"))
        self.root.after(80, self.poll)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        if self.tray is not None:
            self.root.withdraw()
        else:
            self.root.iconify()

    def _on_minimize(self, event):
        if event.widget == self.root and self.root.state() == "iconic" and self.tray is not None:
            self.root.after_idle(self.hide_window)

    def close(self):
        if self.closed:
            return
        if not self.save():
            if not messagebox.askyesno("Dados não salvos", "Não foi possível salvar. Encerrar mesmo assim?", parent=self.root):
                return
        self.closed = True
        self.hotkeys.close()
        self.worker.close()
        if self.tray is not None:
            self.tray.close()
        self.root.destroy()
