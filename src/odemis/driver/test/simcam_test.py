#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on 20 Jun 2014

@author: Éric Piel

Copyright © 2014 Éric Piel, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 2 as published by the Free Software Foundation.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with Odemis. If not, see http://www.gnu.org/licenses/.
'''

from __future__ import division

import logging
from odemis import model
from odemis.driver import simcam
import time
import unittest
from unittest.case import skip


logging.getLogger().setLevel(logging.DEBUG)

CLASS = simcam.Camera
CONFIG_FOCUS = {"name": "focus", "role": "overview-focus"}
KWARGS = dict(name="camera", role="overview", image="simcam-fake-overview.h5",
              children={"focus": CONFIG_FOCUS})

# TODO focus

class TestSimCam(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.camera = CLASS(**KWARGS)
        for child in cls.camera.children:
            if child.name == CONFIG_FOCUS["name"]:
                cls.focus = child

    @classmethod
    def tearDownClass(cls):
        cls.camera.terminate()

    def setUp(self):
        size = self.camera.shape[:-1]
        self.is_rgb = (len(size) >= 3 and size[-1] in {3, 4})
        # image shape is inverted order of size
        if self.is_rgb:
            self.imshp = size[-2::-1] + size[-1:] # RGB dim at the end
        else:
            self.imshp = size[::-1]
        self.camera.resolution.value = self.camera.resolution.range[1]
        self.acq_dates = (set(), set()) # 2 sets of dates, one for each receiver

    def tearDown(self):
        pass

    def _ensureExp(self, exp):
        """
        Ensure the camera has picked up the new exposure time
        """
        old_exp = self.camera.exposureTime.value
        self.camera.exposureTime.value = exp
        time.sleep(old_exp) # wait for the last frame (worst case)

#    @unittest.skip("simple")
    def test_acquire(self):
        self.assertGreaterEqual(len(self.camera.shape), 3)
        exposure = 0.1
        self._ensureExp(exposure)

        im = self.camera.data.get()
        start = im.metadata[model.MD_ACQ_DATE]
        duration = time.time() - start

        self.assertEqual(im.shape, self.imshp)
        self.assertGreaterEqual(duration, exposure, "Error execution took %f s, less than exposure time %f." % (duration, exposure))
        self.assertIn(model.MD_EXP_TIME, im.metadata)

    def test_metadata(self):
        im = self.camera.data.get()
        md = im.metadata
        self.assertAlmostEqual(self.camera.exposureTime.value, md[model.MD_EXP_TIME])
        self.assertGreater(time.time(), md[model.MD_ACQ_DATE])

        if self.is_rgb:
            self.assertEqual(md[model.MD_DIMS], "YXC")

        spxs = self.camera.pixelSize.value
        self.assertEqual(spxs, md[model.MD_SENSOR_PIXEL_SIZE])
        mag = md.get(model.MD_LENS_MAG, 1)
        pxs = tuple(s / mag for s in spxs)
        self.assertAlmostEqual(pxs, md[model.MD_PIXEL_SIZE])


#    @unittest.skip("simple")
    def test_two_acquire(self):
        exposure = 0.1
        self._ensureExp(exposure)

        im = self.camera.data.get()
        start = im.metadata[model.MD_ACQ_DATE]
        duration = time.time() - start

        self.assertEqual(im.shape, self.imshp)
        self.assertGreaterEqual(duration, exposure, "Error execution took %f s, less than exposure time %f." % (duration, exposure))
        self.assertIn(model.MD_EXP_TIME, im.metadata)

        im = self.camera.data.get()
        start = im.metadata[model.MD_ACQ_DATE]
        duration = time.time() - start

        self.assertEqual(im.shape, self.imshp)
        self.assertGreaterEqual(duration, exposure, "Error execution took %f s, less than exposure time %f." % (duration, exposure))
        self.assertIn(model.MD_EXP_TIME, im.metadata)

#    @unittest.skip("simple")
    def test_acquire_flow(self):
        exposure = 0.1
        self._ensureExp(exposure)

        number = 5
        self.left = number
        self.camera.data.subscribe(self.receive_image)
        for i in range(number):
            # end early if it's already finished
            if self.left == 0:
                break
            time.sleep(2 + exposure) # 2s per image should be more than enough in any case

        self.assertEqual(self.left, 0)

#    @unittest.skip("simple")
    def test_data_flow_with_va(self):
        exposure = 1.0 # long enough to be sure we can change VAs before the end
        self._ensureExp(exposure)

        number = 3
        self.left = number
        self.camera.data.subscribe(self.receive_image)

        # change the attribute
        time.sleep(exposure)
        self.camera.exposureTime.value = exposure / 2
        # should just not raise any exception

        for i in range(number):
            # end early if it's already finished
            if self.left == 0:
                break
            time.sleep(2 + exposure) # 2s per image should be more than enough in any case

        self.assertEqual(self.left, 0)

#    @unittest.skip("not implemented")
    def test_df_subscribe_get(self):
        exposure = 1.0 # long enough to be sure we can do a get before the end
        self._ensureExp(exposure)

        number = 3
        self.left = number
        self.camera.data.subscribe(self.receive_image)

        # change the attribute
        self.camera.exposureTime.value = exposure / 2
        # should just not raise any exception

        # get one image: probably the first one from the subscribe (without new exposure)
        im = self.camera.data.get()

        # get a second image (this one must be generated with the new settings)
        start = time.time()
        im = self.camera.data.get()
        duration = time.time() - start

        self.assertEqual(im.shape, self.imshp)
        self.assertGreaterEqual(duration, exposure / 2, "Error execution took %f s, less than exposure time %f." % (duration, exposure))
        self.assertIn(model.MD_EXP_TIME, im.metadata)

        for i in range(number):
            # end early if it's already finished
            if self.left == 0:
                break
            time.sleep(2 + exposure) # 2s per image should be more than enough in any case

        self.assertEqual(self.left, 0)

#    @unittest.skip("simple")
    def test_df_double_subscribe(self):
        exposure = 1.0 # long enough to be sure we can do a get before the end
        number, number2 = 3, 5
        self._ensureExp(exposure)

        self.left = number
        self.camera.data.subscribe(self.receive_image)

        time.sleep(exposure)
        self.left2 = number2
        self.camera.data.subscribe(self.receive_image2)

        for i in range(number + number2):
            # end early if it's already finished
            if self.left == 0 and self.left2 == 0:
                break
            time.sleep(2 + exposure) # 2s per image should be more than enough in any case

        # check that at least some images are shared?
        common_dates = self.acq_dates[0] & self.acq_dates[1]
        self.assertGreater(len(common_dates), 0, "No common dates between %r and %r" %
                           (self.acq_dates[0], self.acq_dates[1]))

        self.assertEqual(self.left, 0)
        self.assertEqual(self.left2, 0)

    def receive_image(self, dataflow, image):
        """
        callback for df of test_acquire_flow()
        """
        self.assertEqual(image.shape, self.imshp)
        self.assertIn(model.MD_EXP_TIME, image.metadata)
        self.acq_dates[0].add(image.metadata[model.MD_ACQ_DATE])
#        print "Received an image"
        self.left -= 1
        if self.left <= 0:
            dataflow.unsubscribe(self.receive_image)


    def receive_image2(self, dataflow, image):
        """
        callback for df of test_acquire_flow()
        """
        self.assertEqual(image.shape, self.imshp)
        self.assertIn(model.MD_EXP_TIME, image.metadata)
        self.acq_dates[1].add(image.metadata[model.MD_ACQ_DATE])
#        print "Received an image in 2"
        self.left2 -= 1
        if self.left2 <= 0:
            dataflow.unsubscribe(self.receive_image2)

    def test_focus(self):
        """
        Check it's possible to change the focus
        """
        pos = self.focus.position.value
        f = self.focus.moveRel({"z": 1e-3}) # 1 mm
        f.result()
        self.assertNotEqual(self.focus.position.value, pos)
        self.camera.data.get()

        f = self.focus.moveRel({"z":-10e-3}) # 10 mm
        f.result()
        self.assertNotEqual(self.focus.position.value, pos)
        self.camera.data.get()

        # restore original position
        f = self.focus.moveAbs(pos)
        f.result()
        self.assertEqual(self.focus.position.value, pos)

if __name__ == '__main__':
    unittest.main()

