"""Rendering of the texture pixmap, glyph rectangles and index labels."""
from PyQt6.QtWidgets import QGraphicsPixmapItem
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPen
from PyQt6.QtCore import Qt, QRectF

from .glyph_item import GlyphLabelItem, GlyphRectItem


class RendererMixin:
    """Draws the scene contents for :class:`ABCFontEditor`."""

    def _add_outlined_index_label(self, text, font, x, y):
        """Index label: white fill with black outline for readability on texture."""
        label = GlyphLabelItem(text, font)
        label.setPos(x, y)
        self.scene.addItem(label)

    def refresh_view(self):
        self.scene.clear()
        
        if hasattr(self, 'pixmap') and self.pixmap is not None and not self.pixmap.isNull():
            self.pix_item = QGraphicsPixmapItem(self.pixmap)

            self.pix_item.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation
                if self.smooth_texture_cb.isChecked()
                else Qt.TransformationMode.FastTransformation
            )

            self.scene.addItem(self.pix_item)
        else:
            self.pix_item = None

        # Draw glyphs regardless of texture presence
        if self.glyphs:
            pen = QPen(QColor(0, 150, 0), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            hover_pen = QPen(QColor(120, 255, 120), 2, Qt.PenStyle.SolidLine)
            hover_pen.setCosmetic(True)

            hover_brush = QBrush(QColor(120, 255, 120, 45))
            font = QFont()
            font.setFamilies(["Arial", "Liberation Sans", "DejaVu Sans"])
            font.setPointSize(8)
            font.setBold(True)

            for g in self.glyphs:
                x0 = int(g["uv_x_start"] * self.texture_size[0])
                y0 = int(g["uv_y_start"] * self.texture_size[1])
                x1 = int(g["uv_x_end"] * self.texture_size[0])
                y1 = int(g["uv_y_end"] * self.texture_size[1])
                rect = QRectF(x0, y0, x1 - x0, y1 - y0)
                self.scene.addItem(GlyphRectItem(rect, pen, hover_pen, hover_brush))

                index_text = str(g["index"])
                chars = g.get("chars") or []
                if chars:
                    cp0 = ord(chars[0])
                    if cp0 == 0x20:
                        ch = "Spc"
                    elif cp0 < 0x20 or cp0 == 0x7F:
                        ch = f"U+{cp0:04X}"
                    else:
                        ch = chars[0]
                    candidate = f"{g['index']}:{ch}"
                    metrics = QFontMetrics(font)
                    glyph_width = x1 - x0
                    text_width = metrics.horizontalAdvance(candidate)
                    print(
                        f"glyph={g['index']} "
                        f"glyph_width={glyph_width} "
                        f"text_width={text_width} "
                        f"text='{candidate}'"
                    )
                    if text_width + 4 <= glyph_width:
                        index_text = candidate
                    self._add_outlined_index_label(index_text, font, x0 + 1, y0 + 1)
