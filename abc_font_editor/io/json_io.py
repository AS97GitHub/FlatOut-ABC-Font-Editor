"""Import / export of glyph data as JSON."""
import json
import struct

from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)
from PyQt6.QtCore import Qt


class JsonMixin:
    """JSON import/export for :class:`ABCFontEditor`."""

    def export_json(self):
        if not self.glyphs:
            self.show_warning("No Data", "Load a .abc file first.")
            return
    
        class ExportDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Export Coordinate Format")
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
                self.setStyleSheet("background-color: #202020; color: white;")
                self.setFixedSize(200, 70)
                layout = QVBoxLayout()
    
                label = QLabel("Choose coordinate export format:")
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                label.setStyleSheet("color: white;")
                layout.addWidget(label)
    
                btn_row = QHBoxLayout()
                self.uv_btn = QPushButton("UV (0.0–1.0)")
                self.px_btn = QPushButton("Pixel")
                for btn in (self.uv_btn, self.px_btn):
                    btn.setStyleSheet("QPushButton { background-color: #333333; color: white; } QPushButton:hover { background-color: #444444; } QPushButton:disabled { background-color: #2a2a2a; color: #666666; }")
                    btn.setFixedWidth(85)
                    btn_row.addWidget(btn)
                layout.addLayout(btn_row)
    
                self.selection = None
                self.uv_btn.clicked.connect(lambda: self.choose("uv"))
                self.px_btn.clicked.connect(lambda: self.choose("pixel"))
    
                self.setLayout(layout)
    
            def choose(self, mode):
                self.selection = mode
                self.accept()
    
        dlg = ExportDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.selection is None:
            return
    
        use_uv = dlg.selection == "uv"
    
        export_path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "", "JSON Files (*.json)")
        if not export_path:
            return
    
        output = []
        # Add parameter descriptions
        output.append({
            "_note": {
                "_hex": "is for reference only and is not used during import",
                "_uv_xy_start_end": "UV coordinates (0.0-1.0) for texture mapping",
                "_px_xy_start_end": "Pixel coordinates for texture mapping",
                "_padding_left": "Left padding width before glyph (can be negative for kerning)",
                "_glyph_width": "Width of the glyph/symbol in pixels",
                "_cell_width": "Total width allocated for the glyph cell",
                "_row_hint": "Tool artifact - texture row index stored as float16",
                "_chars": "Characters that map to this glyph through the ABC character map",
                "_codepoints": "Unicode codepoints that map to this glyph"
            }
        })
        # Add global parameters
        output.append({
            "global": {
                "glyph_height": self.glyph_height,
                "unknown_data_h1": self.unknown_data_h1,
                "unknown_data_h2": self.unknown_data_h2,
                "line_height": self.line_height,
                "charmap_max_codepoint": getattr(self, "charmap_max_codepoint", 0),
                "charmap_count": getattr(self, "charmap_count", 0),
                "charmap_nonzero_count": sum(1 for v in getattr(self, "charmap", []) if v),
                "glyph_record_count": getattr(self, "glyph_record_count", len(self.glyphs)),
                "trailing_data_hex": getattr(self, "trailing_data", b"").hex(" ")
            }
        })
        CHARS_LIMIT = 40
        for g in self.glyphs:
            chars_list = g.get("chars", [])
            codepoints_list = g.get("codepoints", [])
            if len(chars_list) > CHARS_LIMIT:
                chars_val = f"({len(chars_list)} chars total, omitted)"
                cp_val = f"({len(codepoints_list)} codepoints total, omitted)"
            else:
                # Replace control chars, surrogates with U+XXXX notation
                safe_chars = []
                for ch in chars_list:
                    cp = ord(ch)
                    if cp < 0x20 or cp == 0x7F or (0xD800 <= cp <= 0xDFFF):
                        safe_chars.append(f"U+{cp:04X}")
                    elif cp == 0x20:
                        safe_chars.append("Space")
                    else:
                        safe_chars.append(ch)
                chars_val = safe_chars
                cp_val = [f"U+{cp:04X}" for cp in codepoints_list]
            item = {
                "index": g["index"],
                "row_hint": g.get("row_hint", 0),  # tool artifact - texture row index as float16
                "chars": chars_val,
                "codepoints": cp_val,
            }
            if use_uv:
                item["uv_x_start"] = g["uv_x_start"]
                item["uv_y_start"] = g["uv_y_start"]
                item["uv_x_end"] = g["uv_x_end"]
                item["uv_y_end"] = g["uv_y_end"]
            else:
                item["px_x_start"] = g["px_x_start"]
                item["px_y_start"] = g["px_y_start"]
                item["px_x_end"] = g["px_x_end"]
                item["px_y_end"] = g["px_y_end"]
            item["padding_left"] = g["padding_left"]
            item["glyph_width"] = g["glyph_width"]
            item["cell_width"] = g["cell_width"]
            output.append(item)
    
        def compact_json(obj, indent=4, _level=0):
            """Serialize JSON with indent, but keep 'chars' and 'codepoints' arrays inline."""
            pad = " " * indent * _level
            inner_pad = " " * indent * (_level + 1)
            if isinstance(obj, list):
                if not obj:
                    return "[]"
                items = [compact_json(v, indent, _level + 1) for v in obj]
                return "[\n" + inner_pad + (",\n" + inner_pad).join(items) + "\n" + pad + "]"
            elif isinstance(obj, dict):
                if not obj:
                    return "{}"
                parts = []
                for k, v in obj.items():
                    key_str = json.dumps(k, ensure_ascii=False)
                    if k in ("chars", "codepoints") and isinstance(v, list):
                        # Inline: ["x"] or [32]
                        val_str = "[" + ", ".join(json.dumps(i, ensure_ascii=False) for i in v) + "]"
                    else:
                        val_str = compact_json(v, indent, _level + 1)
                    parts.append(f"{key_str}: {val_str}")
                return "{\n" + inner_pad + (",\n" + inner_pad).join(parts) + "\n" + pad + "}"
            else:
                return json.dumps(obj, ensure_ascii=False)

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(compact_json(output))
                f.write("\n")
        except Exception as e:
            self.show_error("Error", f"Failed to write JSON file:\n{str(e)}")
            return

        self.show_info("Export Complete", f"Exported to:\n{export_path}")

    def import_json(self):
        if not self.abc_path or not self.original_data:
            self.show_warning("Error", "Load an .abc file first.")
            return

        json_path, _ = QFileDialog.getOpenFileName(self, "Import JSON", "", "JSON Files (*.json *.JSON)")
        if not json_path:
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                imported = json.load(f)
        except Exception as e:
            self.show_error("Error", f"Failed to read JSON:\n{str(e)}")
            return

        # Validate JSON structure
        if not isinstance(imported, list):
            self.show_error("Error", "Invalid JSON structure: expected a list of glyphs.")
            return

        if not imported:
            self.show_error("Error", "JSON file is empty or contains no valid glyphs.")
            return

        data = bytearray(self.original_data)
        offset = self.offset_dec
        stride = 24

        # Find and validate global data in imported JSON
        global_data = None
        for entry in imported:
            if isinstance(entry, dict) and "global" in entry:
                global_data = entry["global"]
                break
        
        # Validate and update header data if found
        if global_data:
            if not isinstance(global_data, dict):
                self.show_error("Error", "Invalid global data structure in JSON.")
                return
            
            # Check for nested structure
            if "header" in global_data:
                self.show_error("Error", "Invalid JSON structure: move header fields from 'global.header' to 'global'")
                return

            # Check for required header fields
            required_fields = {"glyph_height", "unknown_data_h1", "unknown_data_h2", "line_height"}
            if not any(field in global_data for field in required_fields):
                self.show_error("Error", "Invalid JSON: missing required header fields in 'global'")
                return
                
            try:
                if "glyph_height" in global_data:
                    struct.pack_into("<f", data, 4, float(global_data["glyph_height"]))
                if "unknown_data_h1" in global_data:
                    struct.pack_into("<f", data, 8, float(global_data["unknown_data_h1"]))
                if "unknown_data_h2" in global_data:
                    struct.pack_into("<f", data, 12, float(global_data["unknown_data_h2"]))
                if "line_height" in global_data:
                    struct.pack_into("<f", data, 16, float(global_data["line_height"]))
            except (ValueError, TypeError) as e:
                self.show_error("Error", f"Invalid header data values: {str(e)}")
                return
                
        try:
            valid_glyphs = 0
            for glyph in imported:
                # Skip service records like _note or glyph_count
                if not isinstance(glyph, dict):
                    continue
                    
                if "index" not in glyph:
                    continue
                    
                # Validate glyph index
                try:
                    glyph_index = int(glyph["index"])
                    if glyph_index < 0:
                        continue
                except (ValueError, TypeError):
                    continue
                    
                # Now offset points to first glyph, so we calculate position directly
                i = offset + glyph_index * stride
                if i + stride > len(data):
                    continue

                # Validate coordinate data
                has_uv = any(key.startswith("uv_") for key in glyph.keys())
                has_px = any(key.startswith("px_") for key in glyph.keys())
                
                if not (has_uv or has_px):
                    continue
                    
                try:
                    if has_uv:
                        x0 = float(glyph["uv_x_start"])
                        y0 = float(glyph["uv_y_start"])
                        x1 = float(glyph["uv_x_end"])
                        y1 = float(glyph["uv_y_end"])
                    else:  # has_px
                        x0 = float(glyph["px_x_start"]) / self.texture_size[0]
                        y0 = float(glyph["px_y_start"]) / self.texture_size[1]
                        x1 = float(glyph["px_x_end"]) / self.texture_size[0]
                        y1 = float(glyph["px_y_end"]) / self.texture_size[1]
                except (ValueError, TypeError, KeyError):
                    continue

                # Validate and write glyph data
                try:
                    row_hint = int(glyph.get("row_hint", struct.unpack_from("<H", data, i)[0]))
                    cell_width = int(glyph.get("cell_width", struct.unpack_from("<H", data, i + 22)[0]))
                    width_px = int(glyph.get("glyph_width", struct.unpack_from("<H", data, i + 20)[0]))
                    padding_left_val = int(glyph.get("padding_left", struct.unpack_from("<h", data, i + 18)[0]))
                    
                    struct.pack_into("<H", data, i, row_hint)
                    struct.pack_into("<H", data, i + 22, cell_width)
                    struct.pack_into("<ffff", data, i + 2, x0, y0, x1, y1)
                    struct.pack_into("<hH", data, i + 18, padding_left_val, width_px)
                    
                    valid_glyphs += 1
                except (ValueError, TypeError, struct.error):
                    continue

            if valid_glyphs == 0:
                self.show_warning("Warning", "No valid glyphs found in JSON file.")
                return

            self.original_data = bytes(data)
            self.refresh_abc_from_memory(dirty=True)
            self.show_info("Success", f"ABC updated in memory.\nUpdated glyphs: {valid_glyphs}\nUse Save .abc to write the file.")

        except Exception as e:
            self.show_error("Error", f"Failed to apply changes:\n{str(e)}")
