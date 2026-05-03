"""Aba Skills: tabela de skills + painel de prioridades + painel de árvores."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from sfasst.skill_priorities import render as render_priorities
from sfasst.skill_suggestions import load_skills, MAX_RANK


class SkillsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._parsed: dict = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Filtros
        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel("Árvore:"))
        self.tree_combo = QComboBox()
        for label in ("(todas)", "Combat", "Physical", "Science", "Social", "Tech"):
            self.tree_combo.addItem(label)
        self.tree_combo.currentIndexChanged.connect(self._refresh)
        filt_row.addWidget(self.tree_combo)

        filt_row.addSpacing(16)
        self.owned_only = QCheckBox("Só skills com rank > 0")
        # QSettings persiste o estado entre execuções (e portanto também
        # entre trocas de aba — cada toggle é gravado imediatamente).
        self._settings = QSettings()
        self.owned_only.setChecked(
            self._settings.value("skills/owned_only", False, type=bool)
        )
        self.owned_only.toggled.connect(self._on_owned_toggled)
        filt_row.addWidget(self.owned_only)
        filt_row.addStretch()

        layout.addLayout(filt_row)

        # Splitter: skills table à esquerda, prioridades à direita
        splitter = QSplitter(Qt.Horizontal)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Skill", "Árvore", "Rank", "Próximo unlock"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        splitter.addWidget(self.table)

        self.priorities_view = QPlainTextEdit()
        self.priorities_view.setReadOnly(True)
        self.priorities_view.setPlaceholderText(
            "Top prioridades aparecem aqui depois do JSON ser carregado."
        )
        splitter.addWidget(self.priorities_view)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, 1)

    # ──────────────────────────────────────────────────────────────────
    def _on_owned_toggled(self, checked: bool) -> None:
        self._settings.setValue("skills/owned_only", checked)
        self._refresh()

    def update_data(self, parsed: dict, _here: str) -> None:
        self._parsed = parsed
        self._refresh()

    def _refresh(self) -> None:
        if not self._parsed:
            return
        catalog = load_skills()
        player_ranks: dict[str, int] = {
            s["form_id"].upper(): s["rank"]
            for s in self._parsed.get("skills", [])
        }
        tree_filter = self.tree_combo.currentText()
        if tree_filter == "(todas)":
            tree_filter = None
        owned = self.owned_only.isChecked()

        rows: list[tuple[str, str, int, str]] = []
        for fid, skill in catalog.items():
            cur = player_ranks.get(fid, 0)
            if tree_filter and skill.tree != tree_filter:
                continue
            if owned and cur == 0:
                continue
            next_unlock = (
                skill.unlocks[cur] if cur < MAX_RANK and cur < len(skill.unlocks)
                else "(rank máximo)"
            )
            rows.append((skill.name, skill.tree, cur, next_unlock))

        rows.sort(key=lambda r: (r[1], -r[2], r[0]))

        self.table.setRowCount(len(rows))
        for row, (name, tree, rank, unlock) in enumerate(rows):
            stars = "★" * rank + "☆" * (MAX_RANK - rank)
            items = [
                QTableWidgetItem(name),
                QTableWidgetItem(tree),
                QTableWidgetItem(f"{stars}  ({rank})"),
                QTableWidgetItem(unlock),
            ]
            if rank > 0:
                items[2].setForeground(QColor(220, 200, 80))
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        # Prioridades (texto pré-renderizado, sem reproduzir lógica)
        try:
            txt = render_priorities(self._parsed, top=10,
                                     tree_filter=tree_filter)
        except Exception as e:  # defensivo
            txt = f"erro renderizando prioridades: {e}"
        self.priorities_view.setPlainText(txt)
