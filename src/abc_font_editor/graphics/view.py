"""Zoom, navigation and view-event handling for the texture view."""
from PyQt6.QtGui import QPainter, QTransform
from PyQt6.QtCore import Qt, QRectF


class ViewMixin:
    """Zoom / fit / smoothing / click handling for :class:`ABCFontEditor`."""

    def update_glyph_count_label(self):
        n = len(self.glyphs)
        if hasattr(self, "charmap"):
            symbols = sum(1 for v in self.charmap if v)
            self.glyph_count_label.setText(f"Glyphs: {n} ({symbols} in charmap)")
        else:
            self.glyph_count_label.setText(f"Glyphs: {n}")

    def _zoom_percent(self):
        """Current zoom as a multiple of ZOOM_STEP_PERCENT (avoids float drift)."""
        return round(self.zoom * 100 / self.ZOOM_STEP_PERCENT) * self.ZOOM_STEP_PERCENT

    def _set_zoom_percent(self, percent):
        percent = max(
            self.ZOOM_MIN_PERCENT,
            min(self.ZOOM_MAX_PERCENT, round(percent / self.ZOOM_STEP_PERCENT) * self.ZOOM_STEP_PERCENT),
        )
        self.zoom = percent / 100.0
        self.zoom_label.setText(f"{percent}%")
        self.apply_zoom_transform()

    def apply_zoom_transform(self):
        if hasattr(self, "view"):
            self.view.setTransform(QTransform().scale(self.zoom, self.zoom))

    def fit_texture_view(self):
        if not hasattr(self, "pixmap"):
            self.show_warning("No Texture", "Load a texture first to fit the view.")
            return
        vw = max(self.view.viewport().width(), 1)
        vh = max(self.view.viewport().height(), 1)
        tw, th = self.texture_size
        scale = min(vw / tw, vh / th) * 0.98
        self._set_zoom_percent(round(scale * 100))
        self.view.centerOn(tw / 2, th / 2)

    def handle_view_click(self, event):
        if not self.glyphs:
            return

        scene_pos = self.view.mapToScene(event.position().toPoint())
        for glyph in reversed(self.glyphs):
            x0 = glyph["uv_x_start"] * self.texture_size[0]
            y0 = glyph["uv_y_start"] * self.texture_size[1]
            x1 = glyph["uv_x_end"] * self.texture_size[0]
            y1 = glyph["uv_y_end"] * self.texture_size[1]
            rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            if rect.contains(scene_pos):
                self.edit_glyph(glyph)
                return

    def toggle_smooth_texture(self, checked):
        if not hasattr(self, "pix_item") or self.pix_item is None:
            return

        mode = (
            Qt.TransformationMode.SmoothTransformation
            if checked
            else Qt.TransformationMode.FastTransformation
        )

        self.pix_item.setTransformationMode(mode)

        self.view.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            checked
        )

        self.view.viewport().update()

    def zoom_in(self):
        self._set_zoom_percent(self._zoom_percent() + self.ZOOM_STEP_PERCENT)
        self.update_glyph_count_label()

    def zoom_out(self):
        self._set_zoom_percent(self._zoom_percent() - self.ZOOM_STEP_PERCENT)
        self.update_glyph_count_label()
