"""Reading ABC files and (re)building the in-memory glyph table."""
import struct

from PyQt6.QtWidgets import QFileDialog


class ParserMixin:
    """Loads ABC binary data and extracts glyph records."""

    def load_abc(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open ABC", "", "ABC Files (*.abc *.ABC)")
        if not path:
            return
        self.abc_path = path
        try:
            with open(path, "rb") as f:
                self.original_data = f.read()
        except Exception as e:
            self.show_error("Error", f"Failed to read ABC file:\n{str(e)}")
            return

        # Determine table layout from header
        if len(self.original_data) < 22:
            self.show_warning("Error", "ABC file too small.")
            return
        header = self.original_data[:22]
        self.charmap_max_codepoint = int.from_bytes(header[20:22], "little")
        self.charmap_count = self.charmap_max_codepoint + 1
        self.charmap_offset = 22
        self.charmap_end = self.charmap_offset + self.charmap_count * 2
        self.auto_offset = self.charmap_end
        if self.charmap_end + 2 > len(self.original_data):
            self.show_warning("Error", "ABC character map exceeds file size.")
            return
        self.charmap = list(struct.unpack_from(f"<{self.charmap_count}H", self.original_data, self.charmap_offset))
        self.glyph_record_count = struct.unpack_from("<H", self.original_data, self.charmap_end)[0]
        self.glyph_to_chars = {}
        for codepoint, glyph_index in enumerate(self.charmap):
            if 0 <= glyph_index < self.glyph_record_count:
                self.glyph_to_chars.setdefault(glyph_index, []).append(codepoint)
        
        # Extract header data (bytes 4-19)
        self.glyph_height = struct.unpack("<f", self.original_data[4:8])[0]
        self.unknown_data_h1 = struct.unpack("<f", self.original_data[8:12])[0]
        self.unknown_data_h2 = struct.unpack("<f", self.original_data[12:16])[0]
        self.line_height = struct.unpack("<f", self.original_data[16:20])[0]
        self.offset_dec = self.charmap_end + 2  # First glyph offset
        self.manual_offset = False
        self.dirty = False
        self.extract_glyphs(self.offset_dec, manual=False)

        self.charmap_table_btn.setEnabled(True)
        self.global_params_btn.setEnabled(True)
        self.export_json_btn.setEnabled(True)
        self.import_json_btn.setEnabled(True)
        self.delete_symbols_btn.setEnabled(True)
        self.add_symbol_btn.setEnabled(True)
        self.save_abc_btn.setEnabled(True)

    def extract_glyphs(self, offset, manual=False):
        data = self.original_data
        auto_offset = getattr(self, 'auto_offset', None)
        if auto_offset is None or auto_offset + 24 > len(data):
            self.show_warning("Invalid Offset", "Offset exceeds file size.")
            return

        record_count = getattr(self, "glyph_record_count", None)

        # Determine start position for glyphs
        # Now offset points to first glyph, so we don't need to skip service block
        i = offset
        index = 0
        temp_glyphs = []
        while i + 24 <= len(data):
            if record_count is not None and index >= record_count:
                break
            entry = data[i:i+24]
            if len(entry) < 24:
                break
            try:
                # Correct structure: row_hint (2 bytes), UV coordinates (16 bytes), padding/width/cell_width (6 bytes)
                row_hint = struct.unpack("<H", entry[:2])[0]
                x0, y0, x1, y1 = struct.unpack("<ffff", entry[2:18])
                padding_left, width, cell_width = struct.unpack("<hHH", entry[18:24])
            except struct.error:
                break

            TOLERANCE = 0.02
            if not (0.0 <= x0 <= 1.0 + TOLERANCE and 0.0 <= x1 <= 1.0 + TOLERANCE and
                    0.0 <= y0 <= 1.0 + TOLERANCE and 0.0 <= y1 <= 1.0 + TOLERANCE):
                i += 24
                index += 1
                continue

            hex_repr = " ".join(f"{b:02X}" for b in entry)
            glyph = {
                "index": index,
                "cell_width": cell_width,
                "row_hint": row_hint,  # tool artifact - texture row index as float16
                "chars": [chr(c) for c in self.glyph_to_chars.get(index, [])],
                "codepoints": self.glyph_to_chars.get(index, []),
                "uv_x_start": x0, "uv_y_start": y0, "uv_x_end": x1, "uv_y_end": y1,
                "px_x_start": int(x0 * self.texture_size[0]),
                "px_y_start": int(y0 * self.texture_size[1]),
                "px_x_end": int(x1 * self.texture_size[0]),
                "px_y_end": int(y1 * self.texture_size[1]),
                "padding_left": padding_left,
                "glyph_width": width,
                "hex": hex_repr
            }
            temp_glyphs.append(glyph)
            i += 24
            index += 1

        self.trailing_data = data[i:]

        if temp_glyphs:
            self.glyphs = temp_glyphs
            self.update_glyph_count_label()
            self.refresh_view()
        else:
            self.show_warning("No Glyphs", "No valid glyphs found at this offset.")

    def refresh_abc_from_memory(self, dirty=False):
        header = self.original_data[:22]
        self.charmap_max_codepoint = int.from_bytes(header[20:22], "little")
        self.charmap_count = self.charmap_max_codepoint + 1
        self.charmap_offset = 22
        self.charmap_end = self.charmap_offset + self.charmap_count * 2
        self.auto_offset = self.charmap_end
        self.charmap = list(struct.unpack_from(f"<{self.charmap_count}H", self.original_data, self.charmap_offset))
        self.glyph_record_count = struct.unpack_from("<H", self.original_data, self.charmap_end)[0]
        self.glyph_to_chars = {}
        for codepoint, glyph_index in enumerate(self.charmap):
            if 0 <= glyph_index < self.glyph_record_count:
                self.glyph_to_chars.setdefault(glyph_index, []).append(codepoint)

        self.glyph_height = struct.unpack("<f", self.original_data[4:8])[0]
        self.unknown_data_h1 = struct.unpack("<f", self.original_data[8:12])[0]
        self.unknown_data_h2 = struct.unpack("<f", self.original_data[12:16])[0]
        self.line_height = struct.unpack("<f", self.original_data[16:20])[0]
        self.offset_dec = self.charmap_end + 2
        self.manual_offset = False
        self.dirty = dirty
        self.save_abc_btn.setEnabled(True)
        self.extract_glyphs(self.offset_dec, manual=False)
