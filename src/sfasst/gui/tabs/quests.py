"""Aba Quests: tabela com colunas (Quest, Local, Bucket, Esforço, Proximidade,
Dica) + bloco "Rota Rápida" no topo. Filtros: bucket, busca."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from sfasst.cross import (
    BUCKET_LABELS, PROXIMITY_LABELS, analyze, render_route,
)

BUCKET_COLORS = {
    "ready": QColor(50, 130, 80),
    "almost": QColor(70, 110, 150),
    "in_progress": QColor(110, 110, 110),
    "stuck": QColor(150, 90, 60),
    "level_gated": QColor(140, 60, 60),
}

PROX_COLORS = {
    0: QColor(80, 160, 90),    # AQUI
    1: QColor(70, 130, 150),   # MESMO SISTEMA
    2: QColor(70, 110, 150),   # PERTO
    3: QColor(120, 110, 80),   # INTERMEDIÁRIO
    4: QColor(140, 80, 70),    # LONGE
    5: QColor(100, 100, 100),  # DESCONHECIDO
}


class QuestsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._all_analyses: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Filtros
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Bucket:"))
        self.bucket_combo = QComboBox()
        self.bucket_combo.addItem("(todos)", userData=None)
        for k, v in BUCKET_LABELS.items():
            self.bucket_combo.addItem(v, userData=k)
        self.bucket_combo.currentIndexChanged.connect(self._refilter)
        filt_row.addWidget(self.bucket_combo)

        filt_row.addSpacing(16)
        filt_row.addWidget(QLabel("Buscar:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("nome ou local")
        self.search_edit.textChanged.connect(self._refilter)
        filt_row.addWidget(self.search_edit, 1)

        layout.addLayout(filt_row)

        # Splitter: Rota Rápida em cima, tabela embaixo
        splitter = QSplitter(Qt.Vertical)

        self.route_view = QPlainTextEdit()
        self.route_view.setReadOnly(True)
        self.route_view.setMaximumHeight(200)
        self.route_view.setPlaceholderText(
            "Rota rápida aparece aqui quando você define o 'Local atual' na toolbar."
        )
        splitter.addWidget(self.route_view)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Quest", "Local", "Bucket", "Esforço",
             "Proximidade", "Nível req.", "Dica"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(6, QHeaderView.Stretch)
        for col in (1, 2, 3, 4, 5):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

    # ──────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────
    def update_data(self, parsed: dict, here: str) -> None:
        if not parsed:
            return
        analyses = analyze(parsed, player_level=parsed.get("player_level"),
                           here=here or None)
        self._all_analyses = [asdict(a) for a in analyses]

        # Rota rápida
        if here:
            route_lines = render_route(analyses, top=10)
            self.route_view.setPlainText("\n".join(route_lines) if route_lines
                                         else "(sem candidatas acionáveis)")
        else:
            self.route_view.setPlainText(
                "Defina 'Local atual' na toolbar pra ver rota rápida por proximidade."
            )

        self._refilter()

    # ──────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────
    def _refilter(self) -> None:
        bucket = self.bucket_combo.currentData()
        query = self.search_edit.text().strip().lower()

        filtered: list[dict] = []
        for a in self._all_analyses:
            if bucket and a["bucket"] != bucket:
                continue
            if query:
                hay = (a["display_name"] + " " + a["location"]).lower()
                if query not in hay:
                    continue
            filtered.append(a)

        self.table.setRowCount(len(filtered))
        for row, a in enumerate(filtered):
            self._fill_row(row, a)

    def _fill_row(self, row: int, a: dict) -> None:
        cells: list[QTableWidgetItem] = []

        cells.append(QTableWidgetItem(a["display_name"]))
        cells.append(QTableWidgetItem(a["location"] if a["location"] != "?"
                                       else "(?)"))
        bucket_label = BUCKET_LABELS.get(a["bucket"], a["bucket"])
        bucket_item = QTableWidgetItem(bucket_label)
        if (color := BUCKET_COLORS.get(a["bucket"])):
            bucket_item.setForeground(color)
        cells.append(bucket_item)
        cells.append(QTableWidgetItem(f"{a['total_cost']:.1f}"))

        ptier = a.get("proximity_tier", 5)
        prox_label = PROXIMITY_LABELS.get(ptier, "?")
        d = a.get("distance_ly")
        if d is not None and ptier in (2, 3, 4):
            prox_label = f"{prox_label} (~{d:.0f}u)"
        prox_item = QTableWidgetItem(prox_label)
        if (color := PROX_COLORS.get(ptier)):
            prox_item.setForeground(color)
        if a.get("at_here"):
            prox_item.setText(prox_label + " ★")
        cells.append(prox_item)

        lvl = a.get("level_required")
        cells.append(QTableWidgetItem(str(lvl) if lvl else "—"))
        cells.append(QTableWidgetItem(a.get("community_tip") or ""))

        for col, item in enumerate(cells):
            self.table.setItem(row, col, item)
