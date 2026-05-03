"""Aba Status: nível, contexto de localização, contadores, captured_at."""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)


class StatusTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(Qt.AlignTop)

        self.player_box = QGroupBox("Jogador")
        form = QFormLayout(self.player_box)
        self.lbl_level = QLabel("—")
        self.lbl_xp_next = QLabel("—")
        self.lbl_skills = QLabel("—")
        self.lbl_pos = QLabel("—")
        self.lbl_interior = QLabel("—")
        self.lbl_in_space = QLabel("—")
        form.addRow("Nível:", self.lbl_level)
        form.addRow("XP até próximo nível:", self.lbl_xp_next)
        form.addRow("Skills com rank:", self.lbl_skills)
        form.addRow("Posição (X, Y, Z):", self.lbl_pos)
        form.addRow("Interior:", self.lbl_interior)
        form.addRow("No espaço:", self.lbl_in_space)
        layout.addWidget(self.player_box)

        self.capture_box = QGroupBox("Captura")
        cap_form = QFormLayout(self.capture_box)
        self.lbl_captured = QLabel("—")
        self.lbl_source = QLabel("—")
        self.lbl_quests = QLabel("—")
        self.lbl_inventory = QLabel("—")
        self.lbl_containers = QLabel("—")
        cap_form.addRow("Capturado em:", self.lbl_captured)
        cap_form.addRow("Log:", self.lbl_source)
        cap_form.addRow("Quests (flags / no journal):", self.lbl_quests)
        cap_form.addRow("Itens no inventário:", self.lbl_inventory)
        cap_form.addRow("Containers dumpados:", self.lbl_containers)
        layout.addWidget(self.capture_box)

        layout.addStretch()

    def update_data(self, parsed: dict, _here: str) -> None:
        if not parsed:
            return

        level = parsed.get("player_level")
        self.lbl_level.setText(str(level) if level else "(não capturado)")
        xp = parsed.get("player_xp_for_next_level")
        self.lbl_xp_next.setText(str(xp) if xp else "(não capturado)")
        skills = parsed.get("skills", [])
        n_owned = sum(1 for s in skills if s["rank"] > 0)
        self.lbl_skills.setText(f"{n_owned} / {len(skills)}")

        pos = parsed.get("player_pos") or {}
        if pos:
            self.lbl_pos.setText(
                f"({pos.get('X', '?')}, {pos.get('Y', '?')}, {pos.get('Z', '?')})"
            )
        else:
            self.lbl_pos.setText("(não capturado)")

        is_int = parsed.get("player_is_interior")
        self.lbl_interior.setText("sim" if is_int else "não" if is_int is False
                                   else "(não capturado)")
        is_sp = parsed.get("player_is_in_space")
        self.lbl_in_space.setText("sim" if is_sp else "não" if is_sp is False
                                   else "(não capturado)")

        self.lbl_captured.setText(parsed.get("captured_at", "—"))
        self.lbl_source.setText(parsed.get("source_log", "—"))
        flags = parsed.get("quests_flags", [])
        n_on = sum(1 for q in flags if q["on"])
        n_disp = sum(1 for q in parsed.get("quests_objectives", [])
                      if q.get("displayed"))
        self.lbl_quests.setText(f"{len(flags)} flags ({n_on} On) • {n_disp} no journal")

        inventory = parsed.get("inventory", [])
        self.lbl_inventory.setText(str(len(inventory)))
        if inventory:
            c = Counter(i["container"] for i in inventory)
            parts = ", ".join(f"{k} ({n})" for k, n in sorted(c.items()))
            self.lbl_containers.setText(parts)
        else:
            self.lbl_containers.setText("—")
