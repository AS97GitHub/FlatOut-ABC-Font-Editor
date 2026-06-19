"""Interactive QGraphics items used to draw glyph rectangles and labels."""
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsRectItem
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtCore import Qt, QPointF


class GlyphRectItem(QGraphicsRectItem):
    def __init__(self, rect, normal_pen, hover_pen, hover_brush):
        super().__init__(rect)
        self.normal_pen = normal_pen
        self.hover_pen = hover_pen
        self.hover_brush = hover_brush
        self.setPen(self.normal_pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hoverEnterEvent(self, event):
        self.setPen(self.hover_pen)
        self.setBrush(self.hover_brush)
        self.setZValue(10)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(self.normal_pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setZValue(0)
        super().hoverLeaveEvent(event)


class GlyphLabelItem(QGraphicsItem):
    def __init__(self, text, font):
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.path = QPainterPath()
        self.path.addText(QPointF(0, font.pointSizeF() + 2), font, text)
        self.bounds = self.path.boundingRect().adjusted(-2, -2, 2, 2)
        self.outline_pen = QPen(QColor(0, 0, 0), 1.5)
        self.outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.outline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.fill_brush = QBrush(QColor(255, 255, 255))
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def boundingRect(self):
        return self.bounds

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(self.outline_pen)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawPath(self.path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.fill_brush)
        painter.drawPath(self.path)
