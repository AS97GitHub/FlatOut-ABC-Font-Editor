"""Shared message dialogs and the charmap table dialog."""
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt


class DialogsMixin:
    """Reusable dialogs (errors, warnings, info, charmap table)."""

    def create_dialog(self, parent=None):
        dlg = QDialog(parent or self)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        return dlg

    def show_error(self, title, message):
        """Helper method to show error dialogs consistently"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setModal(True)
        msg_box.raise_()
        msg_box.activateWindow()
        btn = msg_box.button(QMessageBox.StandardButton.Ok)
        if btn:
            btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        msg_box.exec()

    def show_warning(self, title, message):
        """Helper method to show warning dialogs consistently"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setModal(True)
        msg_box.raise_()
        msg_box.activateWindow()
        btn = msg_box.button(QMessageBox.StandardButton.Ok)
        if btn:
            btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        msg_box.exec()

    def show_info(self, title, message):
        """Helper method to show info dialogs consistently"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setModal(True)
        msg_box.raise_()
        msg_box.activateWindow()
        btn = msg_box.button(QMessageBox.StandardButton.Ok)
        if btn:
            btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        msg_box.exec()

    def show_charmap_table(self):
        if not getattr(self, "charmap", None):
            self.show_warning("No Data", "Load a .abc file first.")
            return

        dlg = self.create_dialog()
        dlg.setWindowTitle("Charmap")
        dlg.setStyleSheet("background-color: #202020; color: white;")
        dlg.resize(520, 560)
        layout = QVBoxLayout(dlg)

        mapped_count = sum(1 for v in self.charmap if v)
        summary = QLabel(
            f"Codepoints 0–{self.charmap_max_codepoint} · "
            f"mapped: {mapped_count} · glyph records: {getattr(self, 'glyph_record_count', 0)}"
        )
        summary.setStyleSheet("color: #aaa;")
        layout.addWidget(summary)

        filter_row = QHBoxLayout()
        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter: char, U+0041, 65, glyph 12…")
        filter_input.setStyleSheet("background-color: #333; color: white;")
        filter_row.addWidget(filter_input, stretch=1)
        mapped_only_cb = QCheckBox("Mapped only")
        mapped_only_cb.setStyleSheet("color: white;")
        mapped_only_cb.setChecked(True)
        filter_row.addWidget(mapped_only_cb)
        layout.addLayout(filter_row)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Dec", "Unicode", "Char", "Glyph"])
        table.setStyleSheet(
            "QTableWidget { background-color: #2a2a2a; color: white; gridline-color: #444; }"
            "QHeaderView::section { background-color: #333; color: white; padding: 4px; }"
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table)

        rows = []
        for codepoint, glyph_index in enumerate(self.charmap):
            char = self._format_codepoint_char(codepoint)
            rows.append((codepoint, f"U+{codepoint:04X}", char, str(glyph_index)))

        def apply_filter():
            needle = filter_input.text().strip().lower()
            table.setRowCount(0)
            visible = 0
            for codepoint, uni, char, glyph_s in rows:
                if mapped_only_cb.isChecked() and glyph_s == "0":
                    continue
                haystack = f"{codepoint} {uni} {char} {glyph_s}".lower()
                if needle and needle not in haystack:
                    continue
                row = table.rowCount()
                table.insertRow(row)
                for col, text in enumerate((str(codepoint), uni, char, glyph_s)):
                    item = QTableWidgetItem(text)
                    if col == 3 and glyph_s == "0":
                        item.setForeground(QColor(0x88, 0x88, 0x88))
                    table.setItem(row, col, item)
                visible += 1
            count_label.setText(f"Showing {visible} of {len(rows)} entries")

        count_label = QLabel()
        count_label.setStyleSheet("color: #888;")
        layout.addWidget(count_label)

        filter_input.textChanged.connect(apply_filter)
        mapped_only_cb.stateChanged.connect(lambda: apply_filter())
        apply_filter()

        def on_row_clicked(row, col):
            glyph_item = table.item(row, 3)
            if not glyph_item:
                return
            try:
                glyph_index = int(glyph_item.text())
            except ValueError:
                return
            glyph = next((g for g in self.glyphs if g["index"] == glyph_index), None)
            if glyph:
                self.edit_glyph(glyph)

        table.cellClicked.connect(on_row_clicked)

        hint = QLabel("Click a row to edit the glyph.")
        hint.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()
