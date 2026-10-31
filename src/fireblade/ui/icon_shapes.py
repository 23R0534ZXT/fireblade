"""Small vector icons: no external fonts, assets or image libraries."""
import math
from PySide6.QtCore import QPoint,QRect,Qt
from PySide6.QtGui import QColor,QPolygon


def paint_shape(painter,box,shape,level,levels,color):
    painter.save();r=box.adjusted(2,2,-2,-2);cx,cy=r.center().x(),r.center().y()
    painter.setPen(Qt.NoPen);painter.setBrush(color)
    if shape=='squares':painter.drawRect(r)
    elif shape=='triangles':painter.drawPolygon(QPolygon([QPoint(cx,r.top()),r.bottomRight(),r.bottomLeft()]))
    elif shape=='diamonds':painter.drawPolygon(QPolygon([QPoint(cx,r.top()),QPoint(r.right(),cy),QPoint(cx,r.bottom()),QPoint(r.left(),cy)]))
    elif shape=='flags':
        painter.setPen(color);painter.drawLine(r.left(),r.top(),r.left(),r.bottom())
        painter.drawPolygon(QPolygon([r.topLeft(),r.topRight(),QPoint(r.right()-3,cy),QPoint(r.left(),cy)]))
    elif shape=='ratings':
        for i in range(levels):
            width=max(1,r.width()//levels);h=max(2,round(r.height()*(i+1)/levels))
            painter.setBrush(color if i<=level else QColor('#cccccc'));painter.drawRect(r.left()+i*width,r.bottom()-h,width-1,h)
    elif shape=='stars':
        radius=min(r.width(),r.height())/2
        polygon=QPolygon([QPoint(round(cx+radius*(1 if i%2==0 else .42)*math.sin(i*math.pi/5)),round(cy-radius*(1 if i%2==0 else .42)*math.cos(i*math.pi/5))) for i in range(10)])
        painter.setPen(QColor('#777777'));painter.setBrush(Qt.NoBrush);painter.drawPolygon(polygon)
        painter.setClipRect(QRect(r.left(),r.top(),round(r.width()*level/(levels-1)),r.height()),Qt.IntersectClip)
        painter.setPen(Qt.NoPen);painter.setBrush(color);painter.drawPolygon(polygon)
    painter.restore()
