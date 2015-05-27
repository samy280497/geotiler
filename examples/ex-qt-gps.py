#
# GeoTiler - library to create maps using tiles from a map provider
#
# Copyright (C) 2014-2015 by Artur Wroblewski <wrobell@pld-linux.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# This file incorporates work covered by the following copyright and
# permission notice (restored, based on setup.py file from
# https://github.com/stamen/modestmaps-py):
#
#   Copyright (C) 2007-2013 by Michal Migurski and other contributors
#   License: BSD
#

"""
Read data from GPS and show map centered at the position.

Use keys like '+', '-', 'n', 'p' to zoom in, zoom out and change map
provider.

Requirements:

- geotiler
- quamash
- PyQt 5
"""

import asyncio
import functools
import json
import logging
import redis
import sys
from collections import deque

from PIL.ImageQt import ImageQt

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, \
    QGraphicsPixmapItem, QGraphicsEllipseItem
from PyQt5.QtGui import QPixmap, QPen, QColor
from quamash import QEventLoop

import geotiler
from geotiler.cache import redis_downloader

logging.getLogger('geotiler').setLevel(logging.DEBUG)
logging.basicConfig()


def scroll_map(widget, pos):
    """
    Update map center with position and download new map image.

    :param map: Geotiler map object.
    :param pos: New center of the map (longitude, latitude).
    """
    map = widget.map
    widget.position = pos

    w1, h1 = widget.width() / 2, widget.height() / 2
    w2, h2 = map.size
    x, y = map.rev_geocode(widget.position)

    within = 0 <= x - w1 and x + w1 < w2 \
         and 0 <= y - h1 and y + h1 < h2
    if not within:
        map.center = pos
        widget.refresh_map.set()
        x, y = w2 / 2, h2 / 2

    widget.item.setOffset(w1 - x, h1 - y)


@asyncio.coroutine
def read_gps(queue):
    """
    Read postion from gpsd daemon and put it to positions queue.

    :param queue: Queue of GPS positions.
    """
    reader, writer = yield from asyncio.open_connection(port=2947)
    writer.write('?WATCH={"enable":true,"json":true}\n'.encode())
    while True:
        line = yield from reader.readline()
        data = json.loads(line.decode())
        if 'lon' in data:
            yield from queue.put((data['lon'], data['lat']))


@asyncio.coroutine
def refresh_map(widget):
    """
    Refresh map when map widget refresh event is set.

    This is asyncio coroutine.

    :param widget: Map widget.
    """
    event = widget.refresh_map
    map = widget.map

    # use redis to cache map tiles
    client = redis.Redis('localhost')
    downloader = redis_downloader(client)
    render_map = functools.partial(
        geotiler.render_map_async, downloader=downloader
    )

    while True:
        yield from event.wait()
        event.clear()

        img = yield from render_map(map)
        pixmap = QPixmap.fromImage(ImageQt(img))
        widget.item.setPixmap(pixmap)


@asyncio.coroutine
def locate(widget, queue):
    """
    Read position from the queue and update map position.

    This is asyncio coroutine.

    :param widget: Map widget.
    :param queue: Queue of GPS positions.
    """
    while True:
        pos = yield from queue.get()
        scroll_map(widget, pos)


class MapWindow(QGraphicsView):
    """
    Qt widget based on QGraphicsView to display map image and control map
    with keyboard.

    :var map: Map object.
    :var position: Current position on the map.
    """
    def __init__(self, map, *args):
        super().__init__(*args)
        self.map = map
        self.position = map.center

        self.providers = deque([
            'osm', 'osm-cycle', 'stamen-terrain', 'stamen-toner-lite', 'stamen-toner',
            'stamen-watercolor', 'ms-aerial', 'ms-hybrid', 'ms-road', 'bluemarble',
        ])

        self.refresh_map = asyncio.Event()

        scene = QGraphicsScene()
        self.scene = scene
        self.setScene(scene)
        self.item = QGraphicsPixmapItem()
        scene.addItem(self.item)

        self.circle = QGraphicsEllipseItem(0, 0, 20, 20)
        pen = QPen(QColor(255, 0, 0, 128))
        pen.setWidth(2)
        self.circle.setPen(pen)
        scene.addItem(self.circle)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)


    def keyPressEvent(self, event):
        """
        Handle key press events

        - '-' to zoom out
        - '+'/'=' to zoom in
        - 'n' to use next map provider
        - 'p' to use previous map provider
        - 'q' to quit

        """
        key = event.key()
        if key == QtCore.Qt.Key_Minus:
            self.map.zoom -= 1
        elif key == QtCore.Qt.Key_Plus or key == QtCore.Qt.Key_Equal:
            self.map.zoom += 1
        elif key == QtCore.Qt.Key_Q:
            loop.stop()
        elif key == QtCore.Qt.Key_N:
            self.providers.rotate(-1)
            p = self.providers[0]
            self.map.provider = geotiler.find_provider(p)
        elif key == QtCore.Qt.Key_P:
            self.providers.rotate(1)
            p = self.providers[0]
            self.map.provider = geotiler.find_provider(p)
        scroll_map(self, self.position)
        self.refresh_map.set()


    def resizeEvent(self, event):
        """
        On resize event redraw the map.
        """
        w = self.width()
        h = self.height()
        self.circle.setRect(w / 2 - 10, h / 2 - 10, 20, 20)
        scroll_map(self, self.position)



# bind Qt application with Python asyncio loop
app = QApplication(sys.argv)
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

g = app.desktop().screenGeometry()
size = g.width() + 256 * 2, g.height() + 256 * 2
provider = geotiler.find_provider('osm')
mm = geotiler.Map(size=size, center=(0, 0), zoom=18, provider=provider)

window = MapWindow(mm)
window.show()

queue = asyncio.Queue()
t1 = read_gps(queue)
t2 = locate(window, queue)
t3 = refresh_map(window)
task = asyncio.gather(t1, t2, t3)

loop.run_until_complete(task)

# vim: sw=4:et:ai