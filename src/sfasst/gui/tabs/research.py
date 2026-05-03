"""Aba Research: tabela de projetos com pré-requisitos e desbloqueios."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from sfasst.research_suggestions import (
    evaluate, load_projects, player_skill_ranks,
)


class ResearchTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._parsed: dict = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Categoria:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("(todas)")
        for c in ("Equipment", "Food and Drink", "Manufacturing",
                  "Outpost Development", "Pharmacology", "Weaponry"):
            self.cat_combo.addItem(c)
        self.cat_combo.currentIndexChanged.connect(self._refresh)
        filt_row.addWidget(self.cat_combo)

        filt_row.addSpacing(16)
        self.acc_only = QCheckBox("Só acessíveis agora")
        # QSettings persiste entre execuções e trocas de aba.
        self._settings = QSettings()
        self.acc_only.setChecked(
            self._settings.value("research/accessible_only", False, type=bool)
        )
        self.acc_only.toggled.connect(self._on_acc_toggled)
        filt_row.addWidget(self.acc_only)
        filt_row.addStretch()
        layout.addLayout(filt_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["", "Projeto", "Categoria", "Pré-requisitos", "Desbloqueia"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

    # ──────────────────────────────────────────────────────────────────
    def _on_acc_toggled(self, checked: bool) -> None:
        self._settings.setValue("research/accessible_only", checked)
        self._refresh()

    def update_data(self, parsed: dict, _here: str) -> None:
        self._parsed = parsed
        self._refresh()

    def _refresh(self) -> None:
        if not self._parsed:
            return
        projects = load_projects()
        ranks = player_skill_ranks(self._parsed)

        cat = self.cat_combo.currentText()
        if cat == "(todas)":
            cat = None

        rows: list[tuple] = []
        for p in projects:
            ok, miss = evaluate(p, ranks)
            if cat and p.category != cat:
                continue
            if self.acc_only.isChecked() and not ok:
                continue
            req_str = ", ".join(f"{n} {r}" for n, r in p.prereq_skills) or "—"
            rows.append((ok, miss, p, req_str))

        # acessíveis primeiro, dentro de cada grupo por tier+nome
        rows.sort(key=lambda r: (not r[0], r[2].category, r[2].tier, r[2].project))

        self.table.setRowCount(len(rows))
        for row, (ok, miss, p, req_str) in enumerate(rows):
            mark = "✓" if ok else "✗"
            mark_item = QTableWidgetItem(mark)
            mark_item.setForeground(QColor(80, 160, 90) if ok
                                    else QColor(150, 90, 60))
            mark_item.setTextAlignment(Qt.AlignCenter)

            cells = [
                mark_item,
                QTableWidgetItem(f"{p.project}  [T{p.tier}]"),
                QTableWidgetItem(p.category),
                QTableWidgetItem(req_str if ok
                                 else f"{req_str}  (falta: {', '.join(miss)})"),
                QTableWidgetItem(p.unlocks),
            ]
            for col, item in enumerate(cells):
                self.table.setItem(row, col, item)
