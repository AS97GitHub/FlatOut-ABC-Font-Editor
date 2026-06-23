"""Dialog-driven editing of glyphs, symbols and global parameters."""
import re
import struct

from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout,
)
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt


class EditingMixin:
    """Add / edit / delete glyphs and edit global header parameters."""

    def add_symbol(self):
        if not self.abc_path or not self.original_data:
            self.show_error("Error", "Load an .abc file first.")
            return

        dlg = self.create_dialog()
        dlg.setWindowTitle("Add Symbol / Glyph Index")
        dlg.setStyleSheet("background-color: #202020; color: white;")
        dlg.setFixedWidth(470)
        dlg.setFixedHeight(440)
        layout = QVBoxLayout(dlg)

        LABEL_W = 68  # adjust to move input fields left/right

        sep = QLabel("── Character mapping ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        symbol_row = QHBoxLayout()
        symbol_lbl = QLabel("Symbol 1:")
        symbol_lbl.setFixedWidth(LABEL_W)
        symbol_lbl.setStyleSheet("margin-left: 14px;")
        symbol_row.addWidget(symbol_lbl)
        symbol_input = QLineEdit()
        symbol_input.setPlaceholderText("Optional: A or U+0041 or 0x41 or 65")
        symbol_input.setStyleSheet("background-color: #333; color: white;")
        symbol_row.addWidget(symbol_input)
        layout.addLayout(symbol_row)

        symbol2_row = QHBoxLayout()
        symbol2_lbl = QLabel("Symbol 2:")
        symbol2_lbl.setFixedWidth(LABEL_W)
        symbol2_lbl.setStyleSheet("margin-left: 14px;")
        symbol2_row.addWidget(symbol2_lbl)
        symbol2_input = QLineEdit()
        symbol2_input.setPlaceholderText("Optional: B or U+0042 or 0x42 or 66")
        symbol2_input.setStyleSheet("background-color: #333; color: white;")
        symbol2_row.addWidget(symbol2_input)
        layout.addLayout(symbol2_row)

        COPY_LABEL_W = 95  # adjust to move input fields left/right (For "Copy glyph index:" only)

        sep = QLabel("── Copy from existing glyph ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        copy_row = QHBoxLayout()
        copy_lbl = QLabel("Copy glyph index:")
        copy_lbl.setFixedWidth(COPY_LABEL_W)
        copy_row.addWidget(copy_lbl)
        copy_index_input = QSpinBox()
        copy_index_input.setRange(0, max(0, getattr(self, "glyph_record_count", len(self.glyphs)) - 1))
        copy_index_input.setValue(0)
        copy_index_input.setStyleSheet("QSpinBox { background-color: #333; color: white; }")
        copy_row.addWidget(copy_index_input)
        layout.addLayout(copy_row)

        sep = QLabel("── Glyph coordinates ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        def make_rect_row(label_text, placeholder, indent=0):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(LABEL_W)
            lbl.setIndent(indent)
            row.addWidget(lbl)
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet("background-color: #333; color: white;")
            row.addWidget(inp)
            layout.addLayout(row)
            return inp

        rect_x0_input = make_rect_row("Start X:", "Optional, e.g. 0", 32)
        rect_y0_input = make_rect_row("Start Y:", "Optional, e.g. 0", 32)
        rect_x1_input = make_rect_row("End X:",   "Optional, e.g. 64", 36)
        rect_y1_input = make_rect_row("End Y:",   "Optional, e.g. 32", 36)

        sep = QLabel("── Glyph metrics ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        metrics_pad_input  = make_rect_row("Pad Left:",    "Optional, e.g. 0 (pixels, can be negative)", 23)
        metrics_gw_input   = make_rect_row("Glyph Width:", "Optional, e.g. 64",  0)
        metrics_cw_input   = make_rect_row("Cell Width:",  "Optional, e.g. 64",   11)

        hint = QLabel("Tip: leave Symbol fields empty to add a glyph record without any character mapping.")
        hint.setStyleSheet("color: #aaa;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        old_charmap = list(getattr(self, "charmap", []))

        # Parse both symbols
        codepoints_to_add = []
        for sym_text, label in [(symbol_input.text().strip(), "Symbol 1"), (symbol2_input.text().strip(), "Symbol 2")]:
            if not sym_text:
                continue
            try:
                cp = self.parse_single_codepoint(sym_text)
            except ValueError:
                self.show_warning("Invalid Symbol", f"Invalid {label} value.")
                return
            if cp is None or not (0 <= cp <= 0xFFFF):
                self.show_warning("Invalid Symbol", f"ABC charmap supports codepoints 0–65535 ({label}).")
                return
            if cp < len(old_charmap) and old_charmap[cp] != 0:
                self.show_warning("Already Exists", f"{label} is already mapped to glyph index {old_charmap[cp]}.")
                return
            codepoints_to_add.append(cp)

        # Deduplicate
        seen = set()
        unique_codepoints = []
        for cp in codepoints_to_add:
            if cp not in seen:
                seen.add(cp)
                unique_codepoints.append(cp)
        codepoints_to_add = unique_codepoints

        old_record_count = getattr(self, "glyph_record_count", len(self.glyphs))
        source_index = copy_index_input.value()
        if source_index < 0 or source_index >= old_record_count:
            self.show_error("Invalid Index", "Copy glyph index is outside the glyph table.")
            return

        old_records_start = getattr(self, "charmap_end", 22) + 2
        old_records_end = old_records_start + old_record_count * 24
        if old_records_end > len(self.original_data):
            self.show_error("Error", "ABC glyph table exceeds file size.")
            return

        old_records = [
            self.original_data[old_records_start + i * 24:old_records_start + (i + 1) * 24]
            for i in range(old_record_count)
        ]

        new_record = bytearray(old_records[source_index])
        rect_raw = [rect_x0_input.text().strip(), rect_y0_input.text().strip(),
                    rect_x1_input.text().strip(), rect_y1_input.text().strip()]
        rect_filled = [v for v in rect_raw if v]

        if rect_filled:
            if any(not v for v in rect_raw):
                self.show_warning("Invalid Rect", "Fill all four pixel rect fields: Start X, Start Y, End X, End Y.")
                return
            try:
                px_x0, px_y0, px_x1, px_y1 = [int(v) for v in rect_raw]
            except ValueError:
                self.show_warning("Invalid Rect", "Pixel rect values must be integer numbers.")
                return
            texture_width, texture_height = self.texture_size
            if texture_width <= 0 or texture_height <= 0 or px_x1 <= px_x0 or px_y1 <= px_y0:
                self.show_warning("Invalid Rect", "Pixel rect must be a valid rectangle: End X > Start X and End Y > Start Y.")
                return
            x0 = px_x0 / texture_width
            y0 = px_y0 / texture_height
            x1 = px_x1 / texture_width
            y1 = px_y1 / texture_height
            struct.pack_into("<ffff", new_record, 2, x0, y0, x1, y1)

            glyph_width = px_x1 - px_x0
            struct.pack_into("<hHH", new_record, 18, 0, glyph_width, glyph_width)

        metrics_raw = [metrics_pad_input.text().strip(), metrics_gw_input.text().strip(), metrics_cw_input.text().strip()]
        metrics_filled = [v for v in metrics_raw if v]

        if metrics_filled:
            if any(not v for v in metrics_raw):
                self.show_warning("Invalid Metrics", "Fill all three metric fields: Pad Left, Glyph Width, Cell Width.")
                return
            try:
                padding_left, glyph_width, cell_width = [int(v) for v in metrics_raw]
            except ValueError:
                self.show_warning("Invalid Metrics", "Metric values must be integer numbers.")
                return
            if not (-32768 <= padding_left <= 32767 and 0 <= glyph_width <= 65535 and 0 <= cell_width <= 65535):
                self.show_warning("Invalid Metrics", "Metric values are outside the supported range.")
                return
            struct.pack_into("<hHH", new_record, 18, padding_left, glyph_width, cell_width)

        new_charmap = old_charmap[:]
        for cp in codepoints_to_add:
            if cp >= len(new_charmap):
                new_charmap.extend([0] * (cp + 1 - len(new_charmap)))
        if len(new_charmap) > 0x10000:
            self.show_error("Invalid Symbol", "ABC header cannot store a charmap larger than 65535 entries.")
            return

        new_index = old_record_count
        for cp in codepoints_to_add:
            new_charmap[cp] = new_index
        new_record_count = old_record_count + 1
        new_header = bytearray(self.original_data[:22])
        struct.pack_into("<H", new_header, 20, len(new_charmap) - 1)

        output = bytearray(new_header)
        output.extend(struct.pack(f"<{len(new_charmap)}H", *new_charmap))
        output.extend(struct.pack("<H", new_record_count))
        for record in old_records:
            output.extend(record)
        output.extend(new_record)
        output.extend(self.original_data[old_records_end:])

        old_size = len(self.original_data)
        self.original_data = bytes(output)
        self.refresh_abc_from_memory(dirty=True)

        if codepoints_to_add:
            sym_parts = []
            for cp in codepoints_to_add:
                display_char = chr(cp) if cp >= 32 else f"U+{cp:04X}"
                sym_parts.append(f"{display_char} (U+{cp:04X})")
            symbol_line = "Added symbols: " + ", ".join(sym_parts)
        else:
            symbol_line = "Added glyph index only"
        self.show_info(
            "Glyph Added",
            f"{symbol_line}\n"
            f"New glyph index: {new_index}\n"
            f"Copied from index: {source_index}\n"
            f"Size in memory: {old_size} -> {len(output)} bytes\n"
            "Use Save .abc to write the file."
        )

    def edit_global_params(self):
        if not self.original_data:
            self.show_error("No Data", "Load a .abc file first.")
            return

        dlg = self.create_dialog()
        dlg.setWindowTitle("Global Parameters")
        dlg.setStyleSheet("background-color: #202020; color: white;")
        dlg.setFixedWidth(340)
        dlg.setFixedHeight(158)
        layout = QVBoxLayout(dlg)

        LABEL_W = 72  # adjust to move input fields left/right

        fields = [
            ("Glyph Height",  "glyph_height",      4,  8,  0),
            ("Unknown H1",    "unknown_data_h1",    8,  12,  1),
            ("Unknown H2",    "unknown_data_h2",    12, 16,  1),
            ("Line height",   "line_height",    16, 20,  11),
        ]

        inputs = {}
        for label, attr, start, end, indent in fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(LABEL_W)
            lbl.setIndent(indent)
            row.addWidget(lbl)
            val = getattr(self, attr, struct.unpack("<f", self.original_data[start:end])[0])
            inp = QLineEdit(f"{val:.6g}")
            inp.setStyleSheet("background-color: #333; color: white;")
            row.addWidget(inp)
            layout.addLayout(row)
            inputs[attr] = (inp, start, end)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        layout.addWidget(btns)

        def on_accept():
            new_data = bytearray(self.original_data)
            for attr, (inp, start, end) in inputs.items():
                try:
                    value = float(inp.text().strip())
                except ValueError:
                    self.show_error("Invalid Value", f"'{inp.text()}' is not a valid number.")
                    return
                struct.pack_into("<f", new_data, start, value)
                setattr(self, attr, value)
            self.original_data = bytes(new_data)
            self.dirty = True
            dlg.accept()

        btns.accepted.connect(on_accept)
        btns.rejected.connect(dlg.reject)
        dlg.exec()

    def edit_glyph(self, glyph):
        if not self.original_data:
            return

        dlg = self.create_dialog()
        dlg.setWindowTitle(f"Edit Glyph {glyph['index']}")
        dlg.setStyleSheet("background-color: #202020; color: white;")
        dlg.setFixedWidth(470)
        dlg.setFixedHeight(574)
        layout = QVBoxLayout(dlg)

        LABEL_W = 72  # adjust this to move input fields left/right
        UV_LABEL_W = 41

        sep = QLabel("── Edit glyph coordinates ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        def make_px_uv_row(axis_label, px_val, axis_label_uv, uv_val, px_indent=0, uv_indent=0):
            row = QHBoxLayout()
            ax_lbl = QLabel(axis_label)
            ax_lbl.setFixedWidth(LABEL_W)
            ax_lbl.setIndent(px_indent)
            row.addWidget(ax_lbl)
            px_inp = QLineEdit(str(px_val))
            px_inp.setStyleSheet("background-color: #333; color: white;")
            row.addWidget(px_inp)
            uv_lbl = QLabel(axis_label_uv)
            uv_lbl.setFixedWidth(UV_LABEL_W)
            uv_lbl.setIndent(uv_indent)
            row.addWidget(uv_lbl)
            uv_inp = QLineEdit(f"{uv_val:.9f}")
            uv_inp.setStyleSheet("background-color: #333; color: white;")
            row.addWidget(uv_inp)
            layout.addLayout(row)
            return px_inp, uv_inp

        px_x0_input, uv_x0_input = make_px_uv_row("Start X (Pixel):", glyph['px_x_start'], "Start U:", glyph['uv_x_start'], 0, 4)
        px_y0_input, uv_y0_input = make_px_uv_row("Start Y (Pixel):", glyph['px_y_start'], "Start V:", glyph['uv_y_start'], 0, 5)
        px_x1_input, uv_x1_input = make_px_uv_row("End X (Pixel):",   glyph['px_x_end'],   "End U:", glyph['uv_x_end'], 4, 8)
        px_y1_input, uv_y1_input = make_px_uv_row("End Y (Pixel):",   glyph['px_y_end'],   "End V:", glyph['uv_y_end'], 4, 9)

        hint = QLabel("If pixel values are changed, they take priority over UV.")
        hint.setStyleSheet("color: #aaa;")
        layout.addWidget(hint)

        LABEL_W = 68  # adjust this to move input fields left/right

        sep = QLabel("── Edit glyph metrics ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        def make_metric_row(label_text, val, indent=0):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(LABEL_W)
            lbl.setIndent(indent)
            row.addWidget(lbl)
            inp = QLineEdit(str(val))
            inp.setStyleSheet("background-color: #333; color: white;")
            row.addWidget(inp)
            layout.addLayout(row)
            return inp

        metrics_pad_input = make_metric_row("Pad Left:",    glyph['padding_left'], 23)
        metrics_gw_input  = make_metric_row("Glyph Width:", glyph['glyph_width'], 0)
        metrics_cw_input  = make_metric_row("Cell Width:",  glyph['cell_width'], 11)

        hint = QLabel("Padding and size affect glyph layout.")
        hint.setStyleSheet("color: #aaa;")
        layout.addWidget(hint)

        sep = QLabel("── Glyph metadata ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        unknown_row = QHBoxLayout()
        unknown_lbl = QLabel("Row hint:")
        unknown_lbl.setFixedWidth(LABEL_W)
        unknown_lbl.setStyleSheet("margin-left: 16px;")
        unknown_row.addWidget(unknown_lbl)
        unknown_input = QLineEdit(str(glyph.get("row_hint", 0)))
        unknown_input.setStyleSheet("background-color: #333; color: white;")
        unknown_row.addWidget(unknown_input)
        layout.addLayout(unknown_row)

        hint = QLabel("Optional field. Does not affect rendering.")
        hint.setStyleSheet("color: #aaa;")
        layout.addWidget(hint)

        sep = QLabel("── Glyph character preview ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        chars = glyph.get("chars", [])
        codepoints = glyph.get("codepoints", [])

        MAX_PREVIEW = 10

        def chars_to_str(lst):
            """Show printable characters only; skip control chars (U+0000-U+001F, U+007F) and surrogates."""
            if not lst:
                return "(none)"
            parts = []
            for ch in lst:
                cp = ord(ch)
                if cp == 0x20:
                    parts.append("Space")
                elif cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF):
                    pass  # skip control/surrogate chars — shown in codepoints only
                else:
                    parts.append(ch)
            return " ".join(parts) if parts else "(only control chars)"

        def codepoints_to_str(lst):
            if not lst:
                return "(none)"
            normal = [cp for cp in lst if cp >= 0x20 and cp != 0x7F and not (0xD800 <= cp <= 0xDFFF)]
            control = [cp for cp in lst if cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF)]
            parts = [f"U+{cp:04X}" for cp in normal]
            if control:
                ctrl_str = "  [control: " + " ".join(f"U+{cp:04X}" for cp in control) + "]"
                parts.append(ctrl_str)
            return " ".join(parts) if parts else "(none)"

        def open_full_dialog(title, codepoints_list):
            fd = self.create_dialog(dlg)
            fd.setWindowTitle(title)
            fd.setStyleSheet("background-color: #202020; color: white;")
            fd.setFixedWidth(360)
            fd.setFixedHeight(500)
            fl = QVBoxLayout(fd)

            # Summary
            total = len(codepoints_list)
            ctrl_count = sum(1 for cp in codepoints_list if cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF))
            summary_lbl = QLabel(f"Total: {total}  ·  Printable: {total - ctrl_count}  ·  Control: {ctrl_count}")
            summary_lbl.setStyleSheet("color: #aaa;")
            fl.addWidget(summary_lbl)

            # Filter
            filter_row = QHBoxLayout()
            filter_input = QLineEdit()
            filter_input.setPlaceholderText("Filter: char, U+0041, 65…")
            filter_input.setStyleSheet("background-color: #333; color: white;")
            filter_row.addWidget(filter_input, stretch=1)
            ctrl_cb = QCheckBox("Hide control")
            ctrl_cb.setStyleSheet("color: white;")
            ctrl_cb.setChecked(True)
            filter_row.addWidget(ctrl_cb)
            fl.addLayout(filter_row)

            # Table
            tbl = QTableWidget()
            tbl.setColumnCount(4)
            tbl.setHorizontalHeaderLabels(["Dec", "Unicode", "Char", "Type"])
            tbl.setStyleSheet(
                "QTableWidget { background-color: #2a2a2a; color: white; gridline-color: #444; }"
                "QHeaderView::section { background-color: #333; color: white; padding: 4px; }"
            )
            tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            tbl.verticalHeader().setVisible(False)
            fl.addWidget(tbl)

            count_lbl = QLabel()
            count_lbl.setStyleSheet("color: #888;")
            fl.addWidget(count_lbl)

            # Build rows data
            rows_data = []
            for cp in codepoints_list:
                uni = f"U+{cp:04X}"
                is_ctrl = cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF)
                if cp == 0x20:
                    char_str = "Space"
                    type_str = "Printable"
                elif is_ctrl:
                    char_str = ""
                    type_str = "Control"
                elif 0xD800 <= cp <= 0xDFFF:
                    char_str = ""
                    type_str = "Surrogate"
                else:
                    try:
                        char_str = chr(cp)
                    except (ValueError, OverflowError):
                        char_str = ""
                    type_str = "Printable"
                rows_data.append((cp, uni, char_str, type_str, is_ctrl))

            def apply_filter():
                needle = filter_input.text().strip().lower()
                tbl.setRowCount(0)
                visible = 0
                for cp, uni, char_str, type_str, is_ctrl in rows_data:
                    if ctrl_cb.isChecked() and is_ctrl:
                        continue
                    haystack = f"{cp} {uni} {char_str} {type_str}".lower()
                    if needle and needle not in haystack:
                        continue
                    row = tbl.rowCount()
                    tbl.insertRow(row)
                    for col, text in enumerate((str(cp), uni, char_str, type_str)):
                        item = QTableWidgetItem(text)
                        if is_ctrl:
                            item.setForeground(QColor(0x88, 0x88, 0x88))
                        tbl.setItem(row, col, item)
                    visible += 1
                count_lbl.setText(f"Showing {visible} of {total} entries")

            filter_input.textChanged.connect(apply_filter)
            ctrl_cb.stateChanged.connect(lambda: apply_filter())
            apply_filter()

            close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close_btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; } QPushButton:disabled { background-color: #2a2a2a; color: #666666; }")
            close_btn.rejected.connect(fd.reject)
            fl.addWidget(close_btn)
            fd.exec()

        # For chars preview: take first MAX_PREVIEW printable chars (skip control/surrogates)
        def is_printable(ch):
            cp = ord(ch)
            return not (cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF))

        printable_chars = [ch for ch in chars if is_printable(ch)]
        chars_preview = printable_chars[:MAX_PREVIEW]
        has_more_printable = len(printable_chars) > MAX_PREVIEW

        # For codepoints preview: first MAX_PREVIEW normal ones; if none — show control ones
        normal_cps = [cp for cp in codepoints if cp >= 0x20 and cp != 0x7F and not (0xD800 <= cp <= 0xDFFF)]
        control_cps = [cp for cp in codepoints if cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF)]
        if normal_cps:
            codepoints_preview = normal_cps[:MAX_PREVIEW]
        else:
            codepoints_preview = control_cps[:MAX_PREVIEW]
        has_more_codepoints = len(normal_cps) > MAX_PREVIEW

        # Chars row
        chars_row = QHBoxLayout()
        chars_label = QLabel(f"Chars: {chars_to_str(chars_preview)}"
                             + (" …" if has_more_printable else ""))
        chars_label.setStyleSheet("color: #aaa;")
        chars_label.setWordWrap(True)
        chars_label.setMinimumWidth(300)
        chars_row.addWidget(chars_label, stretch=1)
        layout.addLayout(chars_row)

        # Codepoints row
        codepoints_row = QHBoxLayout()
        codepoints_label = QLabel(f"Codepoints: {codepoints_to_str(codepoints_preview)}"
                                  + (" …" if has_more_codepoints else ""))
        codepoints_label.setStyleSheet("color: #aaa;")
        codepoints_label.setWordWrap(True)
        codepoints_label.setMinimumWidth(300)
        codepoints_row.addWidget(codepoints_label, stretch=1)
        if len(codepoints) > MAX_PREVIEW:
            show_cp_btn = QPushButton("Show all")
            show_cp_btn.setFixedWidth(70)
            show_cp_btn.setStyleSheet("background-color: #333; color: white;")
            def _show_all_cp(_, full=codepoints):
                open_full_dialog(
                    f"Codepoints — Glyph {glyph['index']}",
                    full
                )
            show_cp_btn.clicked.connect(_show_all_cp)
            codepoints_row.addWidget(show_cp_btn)
        layout.addLayout(codepoints_row)

        # ── Char management section ──────────────────────────────────────
        sep = QLabel("── Manage symbols mapped to this glyph ──")
        sep.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(sep)

        def make_dark_input(placeholder):
            w = QLineEdit()
            w.setPlaceholderText(placeholder)
            pal = w.palette()
            pal.setColor(QPalette.ColorRole.Base, QColor(0x33, 0x33, 0x33))
            pal.setColor(QPalette.ColorRole.Text, QColor(0xFF, 0xFF, 0xFF))
            pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(0x88, 0x88, 0x88))
            w.setPalette(pal)
            w.setStyleSheet("background-color: #333; color: white;")
            return w

        LABEL_W = 85  # adjust this to move input fields left/right

        add_char_row = QHBoxLayout()
        add_lbl = QLabel("Add symbol:")
        add_lbl.setFixedWidth(LABEL_W)
        add_lbl.setStyleSheet("margin-left: 16px;")
        add_char_row.addWidget(add_lbl)
        add_char_input = make_dark_input("Char, U+XXXX, 0xXXXX or decimal")
        add_char_row.addWidget(add_char_input)
        layout.addLayout(add_char_row)

        replace_char_row = QHBoxLayout()
        replace_lbl = QLabel("Replace symbol:")
        replace_lbl.setFixedWidth(LABEL_W)
        replace_char_row.addWidget(replace_lbl)
        replace_old_input = make_dark_input("Old: char, U+XXXX or decimal")
        replace_char_row.addWidget(replace_old_input)
        replace_char_row.addWidget(QLabel("→"))
        replace_new_input = make_dark_input("New: char, U+XXXX or decimal")
        replace_char_row.addWidget(replace_new_input)
        layout.addLayout(replace_char_row)

        char_hint = QLabel(
            "Add: maps a new codepoint to this glyph.\n"
            "Replace: remaps old → new (removes old mapping)."
        )
        char_hint.setStyleSheet("color: #aaa;")
        layout.addWidget(char_hint)
        # ────────────────────────────────────────────────────────────────

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # ── Validate and apply char changes first ────────────────────────
        charmap_changed = False
        new_charmap = list(getattr(self, "charmap", []))
        glyph_index = glyph["index"]

        add_sym_text = add_char_input.text().strip()
        if add_sym_text:
            try:
                add_cp = self.parse_single_codepoint(add_sym_text)
            except ValueError:
                self.show_warning("Invalid Symbol", "Invalid value in 'Add symbol'.")
                return
            if add_cp is None or not (0 <= add_cp <= 0xFFFF):
                self.show_warning("Invalid Symbol", "Add symbol: codepoint must be 0–65535.")
                return
            if add_cp < len(new_charmap) and new_charmap[add_cp] != 0:
                self.show_warning("Already Exists",
                    f"Codepoint U+{add_cp:04X} is already mapped to glyph {new_charmap[add_cp]}.")
                return
            if add_cp >= len(new_charmap):
                new_charmap.extend([0] * (add_cp + 1 - len(new_charmap)))
            if len(new_charmap) > 0x10000:
                self.show_error("Invalid Symbol", "Charmap would exceed 65535 entries.")
                return
            new_charmap[add_cp] = glyph_index
            charmap_changed = True

        replace_old_text = replace_old_input.text().strip()
        replace_new_text = replace_new_input.text().strip()
        if replace_old_text or replace_new_text:
            if not replace_old_text or not replace_new_text:
                self.show_warning("Replace Symbol", "Both 'Old' and 'New' fields must be filled for Replace.")
                return
            try:
                old_cp = self.parse_single_codepoint(replace_old_text)
                new_cp = self.parse_single_codepoint(replace_new_text)
            except ValueError:
                self.show_warning("Invalid Symbol", "Invalid value in Replace symbol fields.")
                return
            if old_cp is None or not (0 <= old_cp <= 0xFFFF):
                self.show_warning("Invalid Symbol", "Replace old: codepoint must be 0–65535.")
                return
            if new_cp is None or not (0 <= new_cp <= 0xFFFF):
                self.show_warning("Invalid Symbol", "Replace new: codepoint must be 0–65535.")
                return
            if old_cp >= len(new_charmap) or new_charmap[old_cp] == 0:
                self.show_warning("Not Found",
                    f"Old codepoint U+{old_cp:04X} is not mapped in this ABC file.")
                return
            if new_charmap[old_cp] != glyph_index:
                self.show_warning("Wrong Glyph",
                    f"U+{old_cp:04X} is mapped to glyph {new_charmap[old_cp]}, not glyph {glyph_index}.")
                return
            if new_cp < len(new_charmap) and new_charmap[new_cp] != 0:
                self.show_warning("Already Exists",
                    f"New codepoint U+{new_cp:04X} is already mapped to glyph {new_charmap[new_cp]}.")
                return
            # Free old, map new
            new_charmap[old_cp] = 0
            if new_cp >= len(new_charmap):
                new_charmap.extend([0] * (new_cp + 1 - len(new_charmap)))
            if len(new_charmap) > 0x10000:
                self.show_error("Invalid Symbol", "Charmap would exceed 65535 entries.")
                return
            new_charmap[new_cp] = glyph_index
            charmap_changed = True

        if charmap_changed:
            # Trim trailing zeros
            while len(new_charmap) > 1 and new_charmap[-1] == 0:
                new_charmap.pop()
            new_header = bytearray(self.original_data[:22])
            struct.pack_into("<H", new_header, 20, len(new_charmap) - 1)
            old_charmap_count = getattr(self, "charmap_count", len(new_charmap))
            charmap_end = 22 + old_charmap_count * 2
            rest = self.original_data[charmap_end:]
            output = bytearray(new_header)
            output.extend(struct.pack(f"<{len(new_charmap)}H", *new_charmap))
            output.extend(rest)
            self.original_data = bytes(output)
            self.refresh_abc_from_memory(dirty=True)
            # Re-resolve record_offset after charmap change
        # ─────────────────────────────────────────────────────────────────

        try:
            px_values = [px_x0_input.text().strip(), px_y0_input.text().strip(),
                         px_x1_input.text().strip(), px_y1_input.text().strip()]
            uv_values = [uv_x0_input.text().strip(), uv_y0_input.text().strip(),
                         uv_x1_input.text().strip(), uv_y1_input.text().strip()]
            metric_values = [metrics_pad_input.text().strip(), metrics_gw_input.text().strip(), metrics_cw_input.text().strip()]

            if len(metric_values) != 3:
                raise ValueError("Internal error: metrics fields missing.")
            padding_left, glyph_width, cell_width = [int(v) for v in metric_values]
            row_hint = int(unknown_input.text().strip(), 0)

            original_px = [str(glyph['px_x_start']), str(glyph['px_y_start']),
                           str(glyph['px_x_end']),   str(glyph['px_y_end'])]
            if px_values != original_px:
                try:
                    px_x0, px_y0, px_x1, px_y1 = [int(v) for v in px_values]
                except ValueError:
                    raise ValueError("Pixel rect values must be integer numbers.")
                if px_x1 <= px_x0 or px_y1 <= px_y0:
                    raise ValueError("Pixel rect must be a positive rectangle.")
                x0 = px_x0 / self.texture_size[0]
                y0 = px_y0 / self.texture_size[1]
                x1 = px_x1 / self.texture_size[0]
                y1 = px_y1 / self.texture_size[1]
            else:
                try:
                    x0, y0, x1, y1 = [float(v) for v in uv_values]
                except ValueError:
                    raise ValueError("UV rect values must be float numbers.")

            if not (0 <= row_hint <= 0xFFFF):
                raise ValueError("Row hint must be in range 0–65535.")
            if not (-32768 <= padding_left <= 32767 and 0 <= glyph_width <= 0xFFFF and 0 <= cell_width <= 0xFFFF):
                raise ValueError("Metrics out of range: Pad Left −32768–32767, Glyph/Cell Width 0–65535.")
        except ValueError as e:
            self.show_error("Invalid Glyph Data", str(e))
            return

        record_offset = self.offset_dec + glyph["index"] * 24
        if record_offset + 24 > len(self.original_data):
            self.show_error("Error", "Glyph record offset exceeds file size.")
            return

        data = bytearray(self.original_data)
        struct.pack_into("<H", data, record_offset, row_hint)
        struct.pack_into("<ffff", data, record_offset + 2, x0, y0, x1, y1)
        struct.pack_into("<hHH", data, record_offset + 18, padding_left, glyph_width, cell_width)
        self.original_data = bytes(data)
        self.dirty = True
        self.extract_glyphs(self.offset_dec, manual=self.manual_offset)

    def delete_symbols(self):
        if not self.abc_path or not self.original_data:
            self.show_error("Error", "Load an .abc file first.")
            return

        dlg = self.create_dialog()
        dlg.setWindowTitle("Delete Symbols")
        dlg.setStyleSheet("background-color: #202020; color: white;")
        dlg.resize(520, 360)
        layout = QVBoxLayout(dlg)

        label = QLabel("Symbols/codepoints to delete:")
        label.setStyleSheet("color: white;")
        layout.addWidget(label)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText("Examples: ABC 0-9 U+0410-U+042F 0x20AC")
        text_edit.setMaximumHeight(80)
        text_edit.setStyleSheet("background-color: #333; color: white;")
        layout.addWidget(text_edit)

        hint = QLabel("Direct text, U+XXXX, 0xXXXX, decimal values, and ranges are supported.")
        hint.setStyleSheet("color: #aaa;")
        layout.addWidget(hint)

        index_label = QLabel("Glyph indexes to delete:")
        index_label.setStyleSheet("color: white;")
        layout.addWidget(index_label)

        index_edit = QTextEdit()
        index_edit.setPlaceholderText("Examples: 12 15 20-30")
        index_edit.setMaximumHeight(80)
        index_edit.setStyleSheet("background-color: #333; color: white;")
        layout.addWidget(index_edit)

        index_hint = QLabel("Glyph index as shown in the preview and JSON export.")
        index_hint.setStyleSheet("color: #aaa;")
        layout.addWidget(index_hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; }")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        codepoints_to_delete = self.parse_symbol_delete_text(text_edit.toPlainText())
        glyph_indexes_to_delete = self.parse_index_delete_text(index_edit.toPlainText())
        if not codepoints_to_delete and not glyph_indexes_to_delete:
            self.show_warning("No Input", "Enter symbols/codepoints or glyph indexes to delete.")
            return

        old_charmap = list(getattr(self, "charmap", []))
        old_record_count = getattr(self, "glyph_record_count", len(self.glyphs))
        old_records_start = getattr(self, "charmap_end", 22) + 2
        old_records_end = old_records_start + old_record_count * 24
        if old_records_end > len(self.original_data):
            self.show_error("Error", "ABC glyph table exceeds file size.")
            return

        mapped_deleted = [
            codepoint for codepoint in codepoints_to_delete
            if codepoint < len(old_charmap) and old_charmap[codepoint] != 0
        ]
        valid_index_deleted = {
            index for index in glyph_indexes_to_delete
            if 0 <= index < old_record_count
        }

        if not mapped_deleted and not valid_index_deleted:
            message = "No entered symbols or glyph indexes are mapped in this ABC file."
            self.show_warning("No Matches", message)
            return

        # Build the set of glyph indices to remove:
        # from codepoints: whatever glyph index those codepoints map to
        # from explicit index list: directly
        glyph_indices_from_symbols = {old_charmap[cp] for cp in mapped_deleted}
        indices_to_delete = glyph_indices_from_symbols | valid_index_deleted

        # All glyph indices that survive
        keep_old_indices = sorted(
            i for i in range(old_record_count) if i not in indices_to_delete
        )
        index_map = {old_index: new_index for new_index, old_index in enumerate(keep_old_indices)}

        old_records = [
            self.original_data[old_records_start + i * 24:old_records_start + (i + 1) * 24]
            for i in range(old_record_count)
        ]

        # Rebuild charmap: zero out deleted codepoints, remap remaining indices
        new_charmap = old_charmap[:]
        for cp in mapped_deleted:
            new_charmap[cp] = 0
        for i, value in enumerate(new_charmap):
            if value in indices_to_delete:
                new_charmap[i] = 0
            elif value in index_map:
                new_charmap[i] = index_map[value]

        while len(new_charmap) > 1 and new_charmap[-1] == 0:
            new_charmap.pop()

        new_record_count = len(keep_old_indices)
        new_header = bytearray(self.original_data[:22])
        struct.pack_into("<H", new_header, 20, len(new_charmap) - 1)

        output = bytearray(new_header)
        output.extend(struct.pack(f"<{len(new_charmap)}H", *new_charmap))
        output.extend(struct.pack("<H", new_record_count))
        for old_index in keep_old_indices:
            output.extend(old_records[old_index])
        output.extend(self.original_data[old_records_end:])

        old_size = len(self.original_data)
        self.original_data = bytes(output)
        self.refresh_abc_from_memory(dirty=True)

        removed_glyphs = old_record_count - new_record_count
        removed_bytes = old_size - len(output)
        self.show_info(
            "Symbols Deleted",
            f"Removed mapped symbols: {len(mapped_deleted)}\n"
            f"Removed requested indexes: {len(valid_index_deleted)}\n"
            f"Removed glyph records: {removed_glyphs}\n"
            f"Size in memory: {old_size} -> {len(output)} bytes ({removed_bytes} bytes saved)\n"
            "Use Save .abc to write the file."
        )
