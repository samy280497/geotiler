#
# GeoTiler - library to create maps using tiles from a map provider
#
# Copyright (C) 2014-2016 by Artur Wroblewski <wrobell@pld-linux.org>
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
Create an object containing a GeoTiler object and convert the resulting
image to an OpenCV image in order to show it. Also contains functions to
plot points on the resulting map.

Zooming is possible with the mousewheel and `+` and `-` keys.

Requirements

- geotiler
- opencv
- numpy (also required by OpenCV)

Example provided by `https://github.com/matthijs876`.
"""

import geotiler
import cv2
import numpy as np


RED = (0, 0, 255)


class MapObject:
    """
    OpenCV compatible map image.

    After creating the object the map can be displayed with:

        cv2.imShow('window name', MapObject.img)
        cv2.waitKey(10)

    """
    def __init__(self, center: tuple=(0.0, 51.47879),
                 zoom: int=15, size: tuple=(1900, 1000)):
        """
        Create OpenCV compatible map image.

        :param center: Center of the map (longitude and latitude).
        :param zoom: Zoom level of the map.
        :param size: Resolution of the resulting image.
        """
        self.mm = geotiler.Map(center=center, zoom=zoom, size=size)
        self.map_markers = []
        self.update_map()


    def update_map(self):
        """
        Download new map tiles and redraw everyting on the map.
        """
        self.pil_image = geotiler.render_map(self.mm)
        self.draw_map()


    def draw_map(self):
        """
        Fetch map tiles and draw the map.

        The map markers are being plotted as well.

        Any additional drawing operations should be performed here.
        """
        data = np.array(self.pil_image)[:, :, :3]
        self.img = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
        self.plot_markers(self.map_markers)


    def zoom_in(self):
        """
        Zoom in.

        Calling this function might fetch new tiles.
        """
        if self.mm.zoom < 19:
            self.mm.zoom += 1
        self.update_map()


    def zoom_out(self):
        """
        Zoom out.

        Calling this function might fetch new tiles.
        """
        if self.mm.zoom > 3:
            self.mm.zoom -= 1
        self.update_map()


    def plot_markers(self, markers):
        """
        Draws all markers on the map.

        :param markers: Collection of map markers.
        """
        for lon, lat in markers:
            x, y = self.mm.rev_geocode((lon, lat))
            cv2.circle(self.img, center=(int(x), int(y)), radius=5,
                       color=RED, thickness=-1)


    def mouse_callback(self, event, x, y, flag=0, param=None):
        """
        Mouse events callback.

        Events handled

        left-click
            add map marker
        right-click
            remove map marker
        scroll
            zoom in or out at the location of the mouse pointer
        """
        if event == cv2.EVENT_MOUSEWHEEL:
            if flag > 0:  # Scroll up
                self.mm.center = self.mm.geocode((x, y))
                self.zoom_in()
            elif flag < 0:    # Scroll down
                self.mm.center = self.mm.geocode((x, y))
                self.zoom_out()
        elif event == cv2.EVENT_LBUTTONUP:
            self.map_markers.append(self.mm.geocode((x, y)))
            self.draw_map()
        elif event == cv2.EVENT_RBUTTONUP:
            if self.map_markers:
                del self.map_markers[-1]
                self.draw_map()
            else:
                print('Nothing to delete')



# Create the map object and call it "kaart" (dutch for map)
kaart = MapObject()
# Create a window called window and have it adjust in size automatically
cv2.namedWindow('window', cv2.WINDOW_AUTOSIZE)
# Create the mousecallback in the window called "window"
cv2.setMouseCallback('window', kaart.mouse_callback)

while 1:
    # Show the image in "window"
    cv2.imshow('window', kaart.img)
    # OpenCV doesn't show anything untill the waitKey function is called
    key = cv2.waitKey(20)
    # when Esc is pressed: close all opencv windows and break
    if (key == 27):
        cv2.destroyAllWindows()
        break
    elif key == 43:  # "+" key
        kaart.zoom_in()
    elif key == 45:   # "-" key
        kaart.zoom_out()

# vim: sw=4:et:ai
