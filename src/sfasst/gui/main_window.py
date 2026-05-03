"""Janela principal do Starfield Assistant.

Layout:
- Toolbar superior: botão Refresh (roda scripts/run.sh), botão Recarregar
  (lê JSON), QLineEdit "Local atual" (--here).
- QTabWidget central: Quests / Skills / Research / Status.
- Dock inferior: log do pipeline (stdout/stderr quando o Refresh roda).
- Status bar: caminho do JSON carregado + timestamp.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget, QFileDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QStatusBar, QTabWidget, QToolBar, QWidget,
)

from sfasst._config import load_env, sfse_loader_path
from sfasst.gui.tabs.quests import QuestsTab
from sfasst.gui.tabs.research import ResearchTab
from sfasst.gui.tabs.skills import SkillsTab
from sfasst.gui.tabs.status import StatusTab

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_JSON = REPO_ROOT / "out" / "latest.json"
RUN_SCRIPT = REPO_ROOT / "scripts" / "run.sh"


class MainWindow(QMainWindow):
    json_loaded = Signal(dict, str)  # parsed_json, here_label

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Starfield Assistant")
        self.resize(1200, 800)

        self._parsed: dict[str, Any] = {}
        self._here: str = ""
        self._json_path: Path = DEFAULT_JSON
        self._process: QProcess | None = None

        # Debounce do campo "Local atual": recalcula 250ms após a última tecla.
        self._here_timer = QTimer(self)
        self._here_timer.setSingleShot(True)
        self._here_timer.setInterval(250)
        self._here_timer.timeout.connect(self._apply_here)

        self._build_toolbar()
        self._build_tabs()
        self._build_log_dock()
        self._build_status_bar()

        # Carregar JSON automaticamente se existir
        if self._json_path.exists():
            self._load_json(self._json_path)

    # ──────────────────────────────────────────────────────────────────
    # UI build
    # ──────────────────────────────────────────────────────────────────
    def _build_toolbar(self) -> None:
        tb = QToolBar("Ações")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_refresh = QAction("Refresh (rodar pipeline)", self)
        self.act_refresh.setShortcut("F5")
        self.act_refresh.setToolTip(
            "Roda scripts/run.sh: copia o log do jogo, parseia, cruza com "
            "inventário e regrava out/latest.json. Rode 'bat dump' no jogo antes."
        )
        self.act_refresh.triggered.connect(self._on_refresh)
        tb.addAction(self.act_refresh)

        self.act_reload = QAction("Recarregar JSON", self)
        self.act_reload.setShortcut("Ctrl+R")
        self.act_reload.setToolTip("Apenas relê out/latest.json (sem rodar pipeline)")
        self.act_reload.triggered.connect(lambda: self._load_json(self._json_path))
        tb.addAction(self.act_reload)

        self.act_open = QAction("Abrir JSON…", self)
        self.act_open.triggered.connect(self._on_open_json)
        tb.addAction(self.act_open)

        tb.addSeparator()

        self.act_launch = QAction("Iniciar jogo (SFSE)", self)
        self.act_launch.setToolTip(
            "Lança sfse_loader.exe (resolvido a partir de STARFIELD_GAME_LOG "
            "ou STARFIELD_SFSE_LOADER no .env). Detached — não bloqueia."
        )
        self.act_launch.triggered.connect(self._on_launch_sfse)
        tb.addAction(self.act_launch)

        tb.addSeparator()

        tb.addWidget(QLabel("  Local atual: "))
        self.here_edit = QLineEdit()
        self.here_edit.setPlaceholderText("ex.: cydonia, neon, akila, lodge")
        self.here_edit.setMaximumWidth(220)
        self.here_edit.setClearButtonEnabled(True)
        # textChanged dispara a cada caractere (e ao clicar no X que limpa).
        # Usa debounce pra não recalcular a cada tecla — só 250ms após parar.
        self.here_edit.textChanged.connect(lambda _: self._here_timer.start())
        tb.addWidget(self.here_edit)

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tab_quests = QuestsTab()
        self.tab_skills = SkillsTab()
        self.tab_research = ResearchTab()
        self.tab_status = StatusTab()

        self.tabs.addTab(self.tab_quests, "Quests")
        self.tabs.addTab(self.tab_skills, "Skills")
        self.tabs.addTab(self.tab_research, "Research")
        self.tabs.addTab(self.tab_status, "Status")

        for tab in (self.tab_quests, self.tab_skills,
                    self.tab_research, self.tab_status):
            self.json_loaded.connect(tab.update_data)

        self.setCentralWidget(self.tabs)

    def _build_log_dock(self) -> None:
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(10000)
        dock = QDockWidget("Log do pipeline", self)
        dock.setWidget(self.log)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        dock.hide()  # só aparece quando refresh é disparado
        self._log_dock = dock

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("(sem JSON carregado)")
        sb.addWidget(self._status_label)

    # ──────────────────────────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────────────────────────
    def _apply_here(self) -> None:
        new_here = self.here_edit.text().strip()
        if new_here != self._here:
            self._here = new_here
            if self._parsed:
                self.json_loaded.emit(self._parsed, self._here)

    def _on_open_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir parsed.json",
            str(REPO_ROOT / "out"), "JSON (*.json)"
        )
        if path:
            self._load_json(Path(path))

    def _load_json(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(
                self, "JSON não encontrado",
                f"Não achei {path}.\n\nRode o pipeline (botão Refresh) ou "
                f"abra um JSON diferente."
            )
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON inválido", str(e))
            return
        self._parsed = data
        self._json_path = path
        self.json_loaded.emit(data, self._here)
        captured = data.get("captured_at", "?")
        self._status_label.setText(f"{path}  •  capturado em {captured}")

    def _on_refresh(self) -> None:
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Aguarde", "Pipeline já está rodando.")
            return
        if not RUN_SCRIPT.exists():
            QMessageBox.critical(self, "Pipeline não encontrado", str(RUN_SCRIPT))
            return

        self._log_dock.show()
        self.log.clear()
        self.log.appendPlainText(f"$ {RUN_SCRIPT}\n")
        self.act_refresh.setEnabled(False)

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_output)
        self._process.finished.connect(self._on_proc_finished)
        env = self._process.processEnvironment()
        # garantir que python encontra o pacote
        env.insert("PYTHONPATH", str(REPO_ROOT / "src"))
        self._process.setProcessEnvironment(env)
        self._process.setWorkingDirectory(str(REPO_ROOT))
        self._process.start("bash", [str(RUN_SCRIPT)])

    def _on_proc_output(self) -> None:
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data().decode(
            "utf-8", errors="replace"
        )
        self.log.insertPlainText(data)
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )

    def _on_launch_sfse(self) -> None:
        cfg = load_env()
        loader = sfse_loader_path(cfg)
        if loader is None:
            QMessageBox.warning(
                self, "sfse_loader.exe não encontrado",
                "Não consegui resolver o caminho do sfse_loader.\n\n"
                "Configure STARFIELD_GAME_LOG no .env (e o loader é "
                "derivado da raiz do jogo) ou defina explicitamente "
                "STARFIELD_SFSE_LOADER apontando pro .exe."
            )
            return
        ok = QProcess.startDetached(str(loader), [], str(loader.parent))
        if not ok:
            QMessageBox.critical(
                self, "Falha ao lançar",
                f"QProcess não conseguiu iniciar:\n{loader}\n\n"
                "Em WSL, certifique-se que o interop com Windows está ativo "
                "(arquivos .exe em /mnt/c devem ser executáveis transparentemente)."
            )
            return
        self.statusBar().showMessage(f"Lançado: {loader.name}", 5000)

    def _on_proc_finished(self, code: int, _status: object) -> None:
        self.act_refresh.setEnabled(True)
        if code == 0:
            self.log.appendPlainText(f"\n[pipeline ok — exit 0]")
            self._load_json(self._json_path)
        else:
            self.log.appendPlainText(f"\n[pipeline falhou — exit {code}]")
        self._process = None
