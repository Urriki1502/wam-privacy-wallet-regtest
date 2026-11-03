"""Production Q06 BIP39 backup onboarding UI for WAM Fusion.

Implements the 12-word grid, verification and success screens using the
existing Fusion design system. No wallet authority, no plaintext persistence.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
    QLineEdit, QPushButton, QCheckBox, QStackedWidget, QScrollArea,
)

from .bip39_locale import t
from .fusion_ui import label, panel, action, fusion_palette


class _WordCard(QFrame):
    def __init__(self, number, word, parent=None):
        super().__init__(parent)
        self.setObjectName("FusionInset")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        number_label = QLabel(f"{number}")
        number_label.setObjectName("FusionMuted")
        number_label.setStyleSheet("font-size:11px;font-weight:600;")
        word_label = QLabel(word)
        word_label.setObjectName("FusionCardValue")
        word_label.setStyleSheet("font-size:17px;font-weight:600;")
        word_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(number_label)
        layout.addWidget(word_label)
        self.setMinimumWidth(140)


class Bip39BackupPage(QWidget):
    """Full onboarding backup page: grid → verification → success."""

    verify_requested = Signal(list, list)
    deferred_requested = Signal()
    continue_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phrase_words = []
        self._challenge_positions = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # --- Phrase grid page ---
        self._phrase_page = QWidget()
        self._phrase_page.setObjectName("FusionInner")
        pl = QVBoxLayout(self._phrase_page)
        pl.setContentsMargins(4, 4, 12, 16)
        pl.setSpacing(18)

        pl.addWidget(label(t("backup_title"), "PageTitle"))
        pl.addWidget(label(t("backup_subtitle")))
        warning = label(t("backup_warning"), "Warning")
        pl.addWidget(warning)

        grid_card, gcl = panel(t("phrase_grid_title"))
        self._grid = QGridLayout()
        self._grid.setSpacing(12)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 1)
        gcl.addLayout(self._grid)
        pl.addWidget(grid_card)

        controls = QHBoxLayout()
        controls.addStretch()
        self._written_check = QCheckBox(t("written_checkbox"))
        controls.addWidget(self._written_check)
        controls.addSpacing(16)
        self._back_up_now = action(t("back_up_now"), "check", primary=True)
        self._back_up_now.setEnabled(False)
        self._back_up_now.clicked.connect(self._on_back_up_now)
        controls.addWidget(self._back_up_now)
        self._back_up_later = action(t("back_up_later"), "backup")
        self._back_up_later.clicked.connect(self._on_back_up_later)
        controls.addWidget(self._back_up_later)
        pl.addLayout(controls)
        pl.addStretch()

        self._stack.addWidget(self._phrase_page)

        # --- Verification page ---
        self._verify_page = QWidget()
        self._verify_page.setObjectName("FusionInner")
        vl = QVBoxLayout(self._verify_page)
        vl.setContentsMargins(4, 4, 12, 16)
        vl.setSpacing(18)

        vl.addWidget(label(t("verify_title"), "PageTitle"))
        vl.addWidget(label(t("verify_subtitle")))

        verify_card, vcl = panel(t("verify_title"))
        self._verify_inputs = []
        self._verify_layout = QGridLayout()
        self._verify_layout.setSpacing(14)
        vcl.addLayout(self._verify_layout)
        vl.addWidget(verify_card)

        self._verify_error = label("", "FusionGold")
        self._verify_error.hide()
        vl.addWidget(self._verify_error)

        vcontrols = QHBoxLayout()
        vcontrols.addStretch()
        self._verify_back_up_later = action(t("back_up_later"), "backup")
        self._verify_back_up_later.clicked.connect(self._on_back_up_later)
        vcontrols.addWidget(self._verify_back_up_later)
        self._verify_button = action(t("verify"), "check", primary=True)
        self._verify_button.clicked.connect(self._on_verify)
        vcontrols.addWidget(self._verify_button)
        vl.addLayout(vcontrols)
        vl.addStretch()

        self._stack.addWidget(self._verify_page)

        # --- Success page ---
        self._success_page = QWidget()
        self._success_page.setObjectName("FusionInner")
        sl = QVBoxLayout(self._success_page)
        sl.setContentsMargins(4, 4, 12, 16)
        sl.setSpacing(18)
        sl.addStretch()
        sl.addWidget(label(t("success_title"), "PageTitle"), alignment=Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(label(t("success_subtitle")), alignment=Qt.AlignmentFlag.AlignCenter)
        self._continue_button = action(t("continue"), "check", primary=True)
        self._continue_button.clicked.connect(self.continue_requested.emit)
        sl.addWidget(self._continue_button, alignment=Qt.AlignmentFlag.AlignCenter)
        sl.addStretch()
        self._stack.addWidget(self._success_page)

        self._written_check.toggled.connect(self._back_up_now.setEnabled)

    def set_phrase(self, words):
        """Show the 12-word grid and prepare a verification challenge."""
        self._clear_grid()
        self._phrase_words = list(words)
        if len(self._phrase_words) != 12:
            raise ValueError("Q06_BACKUP_PAGE_PHRASE_LEN_DENIED")
        # 3 columns x 4 rows, numbered 1..12 left-to-right, top-to-bottom.
        for i, word in enumerate(self._phrase_words):
            card = _WordCard(i + 1, word)
            self._grid.addWidget(card, i // 3, i % 3)
        self._written_check.setChecked(False)
        self._back_up_now.setEnabled(False)
        self._challenge_positions = self._pick_challenge()
        self._build_verify_inputs(self._challenge_positions)
        self._verify_error.hide()
        self._stack.setCurrentWidget(self._phrase_page)

    def set_deferred_mode(self):
        """Skip the grid; user must verify to resume an interrupted backup."""
        self._phrase_words = []
        self._clear_grid()
        self._challenge_positions = self._pick_challenge()
        self._build_verify_inputs(self._challenge_positions)
        self._verify_error.hide()
        self._stack.setCurrentWidget(self._verify_page)

    def _clear_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _pick_challenge(self, count=3):
        import random
        return sorted(random.sample(range(1, 13), count))

    def _build_verify_inputs(self, positions):
        # Clear old inputs.
        for edit in self._verify_inputs:
            edit.deleteLater()
        self._verify_inputs.clear()
        while self._verify_layout.count():
            item = self._verify_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, pos in enumerate(positions):
            prompt = label(t("verify_prompt").format(position=pos), "FusionCardTitle")
            edit = QLineEdit()
            edit.setMaxLength(32)
            edit.setPlaceholderText(t("word_label").lower())
            edit.returnPressed.connect(self._on_verify)
            self._verify_inputs.append(edit)
            self._verify_layout.addWidget(prompt, i, 0)
            self._verify_layout.addWidget(edit, i, 1)

    def _on_back_up_now(self):
        if not self._written_check.isChecked():
            return
        self._stack.setCurrentWidget(self._verify_page)

    def _on_back_up_later(self):
        self.clear_phrase()
        self.deferred_requested.emit()

    def _on_verify(self):
        answers = [edit.text().strip() for edit in self._verify_inputs]
        if not all(answers):
            self._verify_error.setText(t("verify_error"))
            self._verify_error.show()
            return
        self.verify_requested.emit(self._challenge_positions, answers)

    def show_verification_error(self):
        self._verify_error.setText(t("verify_error"))
        self._verify_error.show()
        for edit in self._verify_inputs:
            edit.clear()
        self._challenge_positions = self._pick_challenge()
        self._build_verify_inputs(self._challenge_positions)

    def show_success(self):
        self.clear_phrase()
        self._verify_error.hide()
        self._stack.setCurrentWidget(self._success_page)

    def clear_phrase(self):
        self._phrase_words = []
        self._clear_grid()
        self._written_check.setChecked(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_back_up_later()
            return
        super().keyPressEvent(event)
