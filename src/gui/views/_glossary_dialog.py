"""Add / Edit dialog for a single GlossaryTerm."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.models import GlossaryMode, GlossaryTerm

PACKS = ["AI/ML", "Programming", "Math", "Custom"]
MODES = [m.value for m in GlossaryMode]


class GlossaryDialog(QDialog):
    """Modal dialog to create or edit a :class:`GlossaryTerm`.

    Pass an existing term to pre-populate the fields (edit mode).
    Call :meth:`get_term` after ``exec()`` returns ``Accepted``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        term: GlossaryTerm | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Term" if term else "Add Term")
        self.setMinimumWidth(360)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.english_input = QLineEdit()
        self.english_input.setPlaceholderText("e.g. gradient descent")
        form.addRow("English term:", self.english_input)

        self.vietnamese_input = QLineEdit()
        self.vietnamese_input.setPlaceholderText("e.g. giảm dần độ dốc")
        form.addRow("Vietnamese:", self.vietnamese_input)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(MODES)
        form.addRow("Mode:", self.mode_combo)

        self.pack_combo = QComboBox()
        self.pack_combo.addItems(PACKS)
        form.addRow("Pack:", self.pack_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if term:
            self._populate(term)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_term(self) -> GlossaryTerm:
        """Return the term built from the current field values."""
        return GlossaryTerm(
            english=self.english_input.text().strip(),
            vietnamese=self.vietnamese_input.text().strip(),
            mode=GlossaryMode(self.mode_combo.currentText()),
            pack=self.pack_combo.currentText(),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate(self, term: GlossaryTerm) -> None:
        self.english_input.setText(term.english)
        self.vietnamese_input.setText(term.vietnamese)
        idx = self.mode_combo.findText(term.mode.value)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        idx = self.pack_combo.findText(term.pack)
        if idx >= 0:
            self.pack_combo.setCurrentIndex(idx)

    def _on_accept(self) -> None:
        if self.english_input.text().strip():
            self.accept()
