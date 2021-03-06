# -*- coding: utf-8 -*-
"""
@author: Kimon Tsitsikas

Copyright © 2015 Kimon Tsitsikas, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License version 2 as published by the Free Software
Foundation.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Odemis. If not, see http://www.gnu.org/licenses/.
"""

# Test module for model.Stream classes
from __future__ import division

import logging
from odemis import model
import odemis
from odemis.acq import path, stream
from odemis.util import test
import os
import unittest
from unittest.case import skip


logging.getLogger().setLevel(logging.DEBUG)

# FIXME: the test fail to pass due to too many threads running.
# That's mostly because the optical path managers don't get deref'd, which in
# turn keep all the callback Pyro daemons active (=16 threads per daemon)
# The reason it doesn't get deref'd is that the executor keeps reference to
# the method (which contains reference to the manager). This is fixed in
# concurrent.futures v3.0 .
# pyrolog = logging.getLogger("Pyro4")
# pyrolog.setLevel(min(pyrolog.getEffectiveLevel(), logging.DEBUG))


CONFIG_PATH = os.path.dirname(odemis.__file__) + "/../../install/linux/usr/share/odemis/"
# Test for the different configurations
SPARC_CONFIG = CONFIG_PATH + "sim/sparc-sim.odm.yaml"
MONASH_CONFIG = CONFIG_PATH + "sim/sparc-pmts-sim.odm.yaml"
SPEC_CONFIG = CONFIG_PATH + "sim/sparc-sim-spec.odm.yaml"
SPARC2_CONFIG = CONFIG_PATH + "sim/sparc2-sim.odm.yaml"
SPARC2_EXT_SPEC_CONFIG = CONFIG_PATH + "sim/sparc2-ext-spec-sim.odm.yaml"


# @skip("faster")
class SimPathTestCase(unittest.TestCase):
    """
    Tests to be run with a (simulated) simple SPARC (like in Chalmers)
    """
    backend_was_running = False

    @classmethod
    def setUpClass(cls):
        try:
            test.start_backend(SPARC_CONFIG)
        except LookupError:
            logging.info("A running backend is already found, skipping tests")
            cls.backend_was_running = True
            return
        except IOError as exp:
            logging.error(str(exp))
            raise

        # Microscope component
        cls.microscope = model.getComponent(role="sparc")
        # Find CCD & SEM components
        cls.ccd = model.getComponent(role="ccd")
        cls.spec = model.getComponent(role="spectrometer")
        cls.ebeam = model.getComponent(role="e-beam")
        cls.sed = model.getComponent(role="se-detector")
        cls.lenswitch = model.getComponent(role="lens-switch")
        cls.optmngr = path.OpticalPathManager(cls.microscope)

    @classmethod
    def tearDownClass(cls):
        if cls.backend_was_running:
            return

#        print gc.get_referrers(cls.optmngr)
        del cls.optmngr  # To garbage collect it
#         logging.debug("Current number of threads: %d", threading.active_count())
#         for t in threading.enumerate():
#             print "Thread %d: %s" % (t.ident, t.name)
        test.stop_backend()

    def setUp(self):
        if self.backend_was_running:
            self.skipTest("Running backend found")

#    @skip("simple")
    def test_wrong_mode(self):
        """
        Test setting mode that does not exist
        """
        with self.assertRaises(ValueError):
            self.optmngr.setPath("ErrorMode").result()

#     @skip("simple")
    def test_set_path(self):
        """
        Test setting modes that do exist. We expect ar, spectral and mirror-align
        modes to be available
        """
        # setting ar
        self.optmngr.setPath("ar").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["ar"][1]["lens-switch"])

        # setting spectral
        self.optmngr.setPath("spectral").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["spectral"][1]["lens-switch"])

        # setting mirror-align
        self.optmngr.setPath("mirror-align").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["mirror-align"][1]["lens-switch"])

        self.optmngr.setPath("chamber-view").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["chamber-view"][1]["lens-switch"])

        # setting cli
        with self.assertRaises(ValueError):
            self.optmngr.setPath("cli").result()

        # setting monochromator
        with self.assertRaises(ValueError):
            self.optmngr.setPath("monochromator").result()

#     @skip("simple")
    def test_guess_mode(self):
        # test guess mode for ar
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        ars = stream.ARSettingsStream("test ar", self.ccd, self.ccd.data, self.ebeam)
        sas = stream.SEMARMDStream("test sem-ar", sems, ars)

        guess = self.optmngr.guessMode(ars)
        self.assertEqual(guess, "ar")

        guess = self.optmngr.guessMode(sas)
        self.assertEqual(guess, "ar")

        # test guess mode for spectral
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        guess = self.optmngr.guessMode(specs)
        self.assertEqual(guess, "spectral")

        guess = self.optmngr.guessMode(sps)
        self.assertEqual(guess, "spectral")


# @skip("faster")
class MonashPathTestCase(unittest.TestCase):
    """
    Tests to be run with a (simulated) full SPARC (like in Monash)
    """
    backend_was_running = False

    @classmethod
    def setUpClass(cls):
        try:
            test.start_backend(MONASH_CONFIG)
        except LookupError:
            logging.info("A running backend is already found, skipping tests")
            cls.backend_was_running = True
            return
        except IOError as exp:
            logging.error(str(exp))
            raise

        # Microscope component
        cls.microscope = model.getComponent(role="sparc")
        # Find CCD & SEM components
        cls.ccd = model.getComponent(role="ccd")
        cls.spec = model.getComponent(role="spectrometer")
        cls.specgraph = model.getComponent(role="spectrograph")
        cls.cld = model.getComponent(role="cl-detector")
        cls.ebeam = model.getComponent(role="e-beam")
        cls.sed = model.getComponent(role="se-detector")
        cls.lenswitch = model.getComponent(role="lens-switch")
        cls.filter = model.getComponent(role="filter")
        cls.spec_det_sel = model.getComponent(role="spec-det-selector")
        cls.optmngr = path.OpticalPathManager(cls.microscope)

    @classmethod
    def tearDownClass(cls):
        if cls.backend_was_running:
            return
        del cls.optmngr  # To garbage collect it
        test.stop_backend()

    def setUp(self):
        if self.backend_was_running:
            self.skipTest("Running backend found")

#    @skip("simple")
    def test_wrong_mode(self):
        """
        Test setting mode that does not exist
        """
        with self.assertRaises(ValueError):
            self.optmngr.setPath("ErrorMode").result()

#    @skip("simple")
    def test_set_path(self):
        """
        Test setting modes that do exist. We expect all modes to be available
        """
        fbands = self.filter.axes["band"].choices
        # setting ar
        self.optmngr.setPath("ar").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["ar"][1]["lens-switch"])

        # setting spectral
        self.optmngr.setPath("spectral").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["spectral"][1]["lens-switch"])

        # setting mirror-align
        self.optmngr.setPath("mirror-align").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["mirror-align"][1]["lens-switch"])
        # Check the filter wheel is in "pass-through"
        self.assertEqual(fbands[self.filter.position.value["band"]], "pass-through")

        # setting fiber-align
        self.optmngr.setPath("fiber-align").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["fiber-align"][1]["lens-switch"])
        # Check the filter wheel is in "pass-through", and the slit is opened
        self.assertEqual(fbands[self.filter.position.value["band"]], "pass-through")
        self.assertEqual(self.specgraph.position.value['slit-in'], path.SPARC_MODES["fiber-align"][1]["spectrograph"]['slit-in'])

        # setting cli
        self.optmngr.setPath("cli").result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.lenswitch.position.value, path.SPARC_MODES["cli"][1]["lens-switch"])

        # setting monochromator
        self.optmngr.setPath("monochromator").result()
        self.assertEqual(self.spec_det_sel.position.value,
                         path.SPARC_MODES["monochromator"][1]["spec-det-selector"])

#     @skip("simple")
    def test_guess_mode(self):
        # test guess mode for ar
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        ars = stream.ARSettingsStream("test ar", self.ccd, self.ccd.data, self.ebeam)
        sas = stream.SEMARMDStream("test sem-ar", sems, ars)

        guess = self.optmngr.guessMode(ars)
        self.assertEqual(guess, "ar")

        guess = self.optmngr.guessMode(sas)
        self.assertEqual(guess, "ar")

        # test guess mode for spectral
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        guess = self.optmngr.guessMode(specs)
        self.assertEqual(guess, "spectral")

        guess = self.optmngr.guessMode(sps)
        self.assertEqual(guess, "spectral")

        # test guess mode for cli
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        cls = stream.SpectrumSettingsStream("test cl", self.cld, self.cld.data, self.ebeam)
        sls = stream.SEMSpectrumMDStream("test sem-cl", sems, cls)

        guess = self.optmngr.guessMode(cls)
        self.assertEqual(guess, "cli")

        guess = self.optmngr.guessMode(sls)
        self.assertEqual(guess, "cli")


# @skip("faster")
class SpecPathTestCase(unittest.TestCase):
    """
    Tests to be run with a (simulated) SPARC with just a spectrometer (like in AMOLF)
    """
    backend_was_running = False

    @classmethod
    def setUpClass(cls):
        try:
            test.start_backend(SPEC_CONFIG)
        except LookupError:
            logging.info("A running backend is already found, skipping tests")
            cls.backend_was_running = True
            return
        except IOError as exp:
            logging.error(str(exp))
            raise

        # Microscope component
        cls.microscope = model.getComponent(role="sparc")
        # Find CCD & SEM components
        cls.spec = model.getComponent(role="spectrometer")
        cls.ebeam = model.getComponent(role="e-beam")
        cls.sed = model.getComponent(role="se-detector")
        cls.optmngr = path.OpticalPathManager(cls.microscope)

    @classmethod
    def tearDownClass(cls):
        if cls.backend_was_running:
            return
        del cls.optmngr  # To garbage collect it
        test.stop_backend()

    def setUp(self):
        if self.backend_was_running:
            self.skipTest("Running backend found")

#     @skip("simple")
    def test_wrong_mode(self):
        """
        Test setting mode that does not exist
        """
        with self.assertRaises(ValueError):
            self.optmngr.setPath("ErrorMode").result()

#     @skip("simple")
    def test_set_path(self):
        """
        Test setting modes that do exist, but not available.
        We expect only spectral mode to be available
        """
        # setting ar
        with self.assertRaises(ValueError):
            self.optmngr.setPath("ar").result()

        # setting spectral
        self.optmngr.setPath("spectral").result()

        # setting mirror-align
        with self.assertRaises(ValueError):
            self.optmngr.setPath("mirror-align").result()

        # setting cli
        with self.assertRaises(ValueError):
            self.optmngr.setPath("cli").result()

        # setting monochromator
        with self.assertRaises(ValueError):
            self.optmngr.setPath("monochromator").result()

#     @skip("simple")
    def test_guess_mode(self):
        # test guess mode for spectral
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        guess = self.optmngr.guessMode(specs)
        self.assertEqual(guess, "spectral")

        guess = self.optmngr.guessMode(sps)
        self.assertEqual(guess, "spectral")

        with self.assertRaises(LookupError):
            guess = self.optmngr.guessMode(sems)


# @skip("faster")
class Sparc2PathTestCase(unittest.TestCase):
    """
    Tests to be run with a (simulated) SPARC2 (like in Oslo)
    """
    backend_was_running = False

    @classmethod
    def setUpClass(cls):
        try:
            test.start_backend(SPARC2_CONFIG)
        except LookupError:
            logging.info("A running backend is already found, skipping tests")
            cls.backend_was_running = True
            return
        except IOError as exp:
            logging.error(str(exp))
            raise

        # Microscope component
        cls.microscope = model.getComponent(role="sparc2")
        # Find CCD & SEM components
        cls.ccd = model.getComponent(role="ccd")
        cls.spec = model.getComponent(role="spectrometer")
        cls.spec_integrated = model.getComponent(role="spectrometer-integrated")
        cls.specgraph = model.getComponent(role="spectrograph")
        cls.cld = model.getComponent(role="cl-detector")
        cls.ebeam = model.getComponent(role="e-beam")
        cls.sed = model.getComponent(role="se-detector")
        cls.lensmover = model.getComponent(role="lens-mover")
        cls.lenswitch = model.getComponent(role="lens-switch")
        cls.filter = model.getComponent(role="filter")
        cls.slit = model.getComponent(role="slit-in-big")
        cls.focus = model.getComponent(role="focus")
        cls.spec_det_sel = model.getComponent(role="spec-det-selector")
        cls.cl_det_sel = model.getComponent(role="cl-det-selector")
        cls.optmngr = path.OpticalPathManager(cls.microscope)

    @classmethod
    def tearDownClass(cls):
        if cls.backend_was_running:
            return
        del cls.optmngr  # To garbage collect it
        test.stop_backend()

    def setUp(self):
        if self.backend_was_running:
            self.skipTest("Running backend found")

    def assert_pos_as_in_mode(self, comp, mode):
        """
        Check the position of the given component is as defined for the
        specified mode (for all the axes defined in the specified mode)
        comp (Component): component for which
        mode (str): name of one of the modes
        raises AssertionError if not equal
        """
        positions = path.SPARC2_MODES[mode][1][comp.role]
        for axis, pos in positions.items():
            axis_def = comp.axes[axis]
            # If "not mirror", just check it's different from "mirror"
            if pos == path.GRATING_NOT_MIRROR:
                choices = axis_def.choices
                for key, value in choices.items():
                    if value == "mirror":
                        self.assertNotEqual(comp.position.value[axis], key,
                                            "Position of %s.%s is %s == mirror, but shouldn't be" %
                                            (comp.name, axis, comp.position.value[axis]))
                        break
                # If no "mirror" pos => it's all fine anyway
                continue

            # If the position is a name => convert it
            if hasattr(axis_def, "choices"):
                for key, value in axis_def.choices.items():
                    if value == pos:
                        pos = key
                        break

            # TODO: if grating == mirror and no mirror choice, check wavelength == 0
            self.assertAlmostEqual(comp.position.value[axis], pos,
                                   msg="Position of %s.%s is %s != %s" %
                                       (comp.name, axis, comp.position.value[axis], pos))

    def test_wrong_mode(self):
        """
        Test setting mode that does not exist
        """
        with self.assertRaises(ValueError):
            self.optmngr.setPath("ErrorMode").result()

    # @skip("simple")
    def test_set_path(self):
        """
        Test setting modes that do exist. We expect all modes to be available
        """
        fbands = self.filter.axes["band"].choices

        # setting ar
        self.optmngr.setPath("ar").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "ar")
        self.assert_pos_as_in_mode(self.slit, "ar")
        self.assert_pos_as_in_mode(self.specgraph, "ar")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

        # CL intensity mode
        self.optmngr.setPath("cli").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "cli")
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.003})

        # setting spectral
        self.optmngr.setPath("spectral").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral")
        self.assert_pos_as_in_mode(self.slit, "spectral")
        self.assert_pos_as_in_mode(self.specgraph, "spectral")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 1.5707963267948966})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

#         self.optmngr.setPath("spectral-dedicated").result()
#         # Assert that actuator was moved according to mode given
#         self.assertEqual(self.lenswitch.position.value,
#                          self.find_dict_key(self.lenswitch, sparc2_modes["spectral-dedicated"]))

#         # spectral should be a shortcut to spectral-dedicated
#         self.optmngr.setPath("spectral").result()
#         # Assert that actuator was moved according to mode given
#         self.assertEqual(self.lenswitch.position.value,
#                          self.find_dict_key(self.lenswitch, sparc2_modes["spectral-dedicated"]))
#         self.assertTrue(self.specgraph.position.value['grating'] != 'mirror')

        # setting mirror-align
        self.optmngr.setPath("mirror-align").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "mirror-align")
        self.assert_pos_as_in_mode(self.slit, "mirror-align")
        self.assert_pos_as_in_mode(self.specgraph, "mirror-align")
        # Check the filter wheel is in "pass-through"
        self.assertEqual(fbands[self.filter.position.value["band"]], "pass-through")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

        # Check the focus is remembered before going to chamber-view
        orig_focus = self.focus.position.value
        # Move to a different filter band
        for b in fbands.keys():
            if b != self.filter.position.value["band"]:
                self.filter.moveAbsSync({"band": b})
                break

        # setting chamber-view
        self.optmngr.setPath("chamber-view").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "chamber-view")
        self.assert_pos_as_in_mode(self.slit, "chamber-view")
        self.assert_pos_as_in_mode(self.specgraph, "chamber-view")
        # Check the filter wheel is in "pass-through"
        self.assertEqual(fbands[self.filter.position.value["band"]], "pass-through")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})
        self.focus.moveRel({"z": 1e-3}).result()
        chamber_focus = self.focus.position.value

        # Check the focus is back after changing to previous mode
        self.optmngr.setPath("mirror-align").result()
        self.assertEqual(self.focus.position.value, orig_focus)

        # setting spec-focus
        self.optmngr.setPath("spec-focus").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spec-focus")
        self.assert_pos_as_in_mode(self.slit, "spec-focus")
        self.assert_pos_as_in_mode(self.specgraph, "spec-focus")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

        # Check the focus in chamber is back
        self.optmngr.setPath("chamber-view").result()
        self.assertEqual(self.focus.position.value, chamber_focus)

    # @skip("simple")
    def test_guess_mode(self):
        # test guess mode for ar
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        ars = stream.ARSettingsStream("test ar", self.ccd, self.ccd.data, self.ebeam)
        sas = stream.SEMARMDStream("test sem-ar", sems, ars)

        guess = self.optmngr.guessMode(ars)
        self.assertEqual(guess, "ar")

        guess = self.optmngr.guessMode(sas)
        self.assertEqual(guess, "ar")

        # test guess mode for spectral-dedicated
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        guess = self.optmngr.guessMode(specs)
        self.assertIn(guess, ("spectral", "spectral-dedicated"))

        guess = self.optmngr.guessMode(sps)
        self.assertIn(guess, ("spectral", "spectral-dedicated"))

    # @skip("simple")
    def test_set_path_stream(self):
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        ars = stream.ARSettingsStream("test ar", self.ccd, self.ccd.data, self.ebeam)
        sas = stream.SEMARMDStream("test sem-ar", sems, ars)

        self.optmngr.setPath(ars).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "ar")
        self.assert_pos_as_in_mode(self.slit, "ar")
        self.assert_pos_as_in_mode(self.specgraph, "ar")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})

        # Change positions back
        self.optmngr.setPath("mirror-align").result()

        self.optmngr.setPath(sas).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "ar")
        self.assert_pos_as_in_mode(self.slit, "ar")
        self.assert_pos_as_in_mode(self.specgraph, "ar")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})

        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        self.optmngr.setPath(specs).result()
        # Assert that actuator was moved according to mode given
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 1.5707963267948966})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

        # Change positions back
        self.optmngr.setPath("chamber-view").result()

        self.optmngr.setPath(sps).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral")
        self.assert_pos_as_in_mode(self.slit, "spectral")
        self.assert_pos_as_in_mode(self.specgraph, "spectral")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 1.5707963267948966})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec_integrated, self.spec_integrated.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        # Change positions back
        self.optmngr.setPath("chamber-view").result()

        self.optmngr.setPath(specs).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral-integrated")
        self.assert_pos_as_in_mode(self.slit, "spectral-integrated")
        self.assert_pos_as_in_mode(self.specgraph, "spectral-integrated")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})

        # Check the focus is remembered before going to chamber-view
        orig_focus = self.focus.position.value

        # Change positions back
        self.optmngr.setPath("chamber-view").result()
        self.focus.moveRel({"z": 1e-3}).result()

        self.optmngr.setPath(sps).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral")
        self.assert_pos_as_in_mode(self.slit, "spectral")
        self.assert_pos_as_in_mode(self.specgraph, "spectral")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertEqual(self.cl_det_sel.position.value, {'x': 0.01})
        self.assertEqual(self.focus.position.value, orig_focus)


# @skip("faster")
class Sparc2ExtSpecPathTestCase(unittest.TestCase):
    """
    Tests to be run with a (simulated) SPARC2 (like in EMPA)
    """
    backend_was_running = False

    @classmethod
    def setUpClass(cls):
        try:
            test.start_backend(SPARC2_EXT_SPEC_CONFIG)
        except LookupError:
            logging.info("A running backend is already found, skipping tests")
            cls.backend_was_running = True
            return
        except IOError as exp:
            logging.error(str(exp))
            raise

        # Microscope component
        cls.microscope = model.getComponent(role="sparc2")
        # Find CCD & SEM components
        cls.ccd = model.getComponent(role="ccd")
        cls.spec = model.getComponent(role="spectrometer")
        cls.specgraph = model.getComponent(role="spectrograph")
        cls.specgraph_dedicated = model.getComponent(role="spectrograph-dedicated")
        cls.ebeam = model.getComponent(role="e-beam")
        cls.sed = model.getComponent(role="se-detector")
        cls.lensmover = model.getComponent(role="lens-mover")
        cls.lenswitch = model.getComponent(role="lens-switch")
        cls.spec_sel = model.getComponent(role="spec-selector")
        cls.slit = model.getComponent(role="slit-in-big")
        cls.spec_det_sel = model.getComponent(role="spec-det-selector")
        cls.optmngr = path.OpticalPathManager(cls.microscope)

    @classmethod
    def tearDownClass(cls):
        if cls.backend_was_running:
            return
        del cls.optmngr  # To garbage collect it
        test.stop_backend()

    def setUp(self):
        if self.backend_was_running:
            self.skipTest("Running backend found")

    def assert_pos_as_in_mode(self, comp, mode):
        """
        Check the position of the given component is as defined for the
        specified mode (for all the axes defined in the specified mode)
        comp (Component): component for which
        mode (str): name of one of the modes
        raises AssertionError if not equal
        """
        positions = path.SPARC2_MODES[mode][1][comp.role]
        for axis, pos in positions.items():
            axis_def = comp.axes[axis]
            # If "not mirror", just check it's different from "mirror"
            if pos == path.GRATING_NOT_MIRROR:
                choices = axis_def.choices
                for key, value in choices.items():
                    if value == "mirror":
                        self.assertNotEqual(comp.position.value[axis], key,
                                            "Position of %s.%s is %s == mirror, but shouldn't be" %
                                            (comp.name, axis, comp.position.value[axis]))
                        break
                # If no "mirror" pos => it's all fine anyway
                continue

            # If the position is a name => convert it
            if hasattr(axis_def, "choices"):
                for key, value in axis_def.choices.items():
                    if value == pos:
                        pos = key
                        break

            # TODO: if grating == mirror and no mirror choice, check wavelength == 0
            self.assertAlmostEqual(comp.position.value[axis], pos,
                                   msg="Position of %s.%s is %s != %s" %
                                       (comp.name, axis, comp.position.value[axis], pos))

    # @skip("simple")
    def test_wrong_mode(self):
        """
        Test setting mode that does not exist
        """
        with self.assertRaises(ValueError):
            self.optmngr.setPath("ErrorMode").result()

    # @skip("simple")
    def test_set_path(self):
        """
        Test setting modes that do exist. We expect all modes to be available
        """
        # setting ar
        self.optmngr.setPath("ar").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "ar")
        self.assert_pos_as_in_mode(self.slit, "ar")
        self.assert_pos_as_in_mode(self.specgraph, "ar")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

        # setting spectral
        spgph_pos = self.specgraph.position.value
        self.optmngr.setPath("spectral").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral")
        # No slit check, as slit-in-big does _not_ affects the (external) spectrometer
        # No specgraph_dedicated check, as any position is fine
        # Check that specgraph (not -dedicated) should _not_ move (as it's not
        # affecting the spectrometer)
        self.assertEqual(spgph_pos, self.specgraph.position.value)
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.026112848)

        self.optmngr.setPath("spectral-integrated").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral-integrated")
        self.assert_pos_as_in_mode(self.slit, "spectral-integrated")
        self.assert_pos_as_in_mode(self.specgraph, "spectral-integrated")
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

#         # spectral should be a shortcut to spectral-dedicated
#         self.optmngr.setPath("spectral-dedicated").result()
#         # Assert that actuator was moved according to mode given
#         self.assertEqual(self.lenswitch.position.value,
#                          self.find_dict_key(self.lenswitch, sparc2_modes["spectral-dedicated"]))

        # setting mirror-align
        self.optmngr.setPath("mirror-align").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "mirror-align")
        self.assert_pos_as_in_mode(self.slit, "mirror-align")
        self.assert_pos_as_in_mode(self.specgraph, "mirror-align")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

        # setting chamber-view
        self.optmngr.setPath("chamber-view").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "chamber-view")
        self.assert_pos_as_in_mode(self.slit, "chamber-view")
        self.assert_pos_as_in_mode(self.specgraph, "chamber-view")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

        # setting spec-focus
        self.optmngr.setPath("spec-focus").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spec-focus")
        self.assert_pos_as_in_mode(self.slit, "spec-focus")
        self.assert_pos_as_in_mode(self.specgraph, "spec-focus")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

        # setting fiber-align
        self.optmngr.setPath("fiber-align").result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "fiber-align")
        self.assert_pos_as_in_mode(self.specgraph_dedicated, "fiber-align")
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.026112848)

    # @skip("simple")
    def test_guess_mode(self):
        # test guess mode for ar
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        ars = stream.ARSettingsStream("test ar", self.ccd, self.ccd.data, self.ebeam)
        sas = stream.SEMARMDStream("test sem-ar", sems, ars)

        guess = self.optmngr.guessMode(ars)
        self.assertEqual(guess, "ar")

        guess = self.optmngr.guessMode(sas)
        self.assertEqual(guess, "ar")

        # test guess mode for spectral-dedicated
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        guess = self.optmngr.guessMode(specs)
        self.assertIn(guess, ("spectral", "spectral-dedicated"))

        guess = self.optmngr.guessMode(sps)
        self.assertIn(guess, ("spectral", "spectral-dedicated"))

    # @skip("simple")
    def test_set_path_stream(self):
        # test guess mode for ar
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        ars = stream.ARSettingsStream("test ar", self.ccd, self.ccd.data, self.ebeam)
        sas = stream.SEMARMDStream("test sem-ar", sems, ars)

        self.optmngr.setPath(ars).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "ar")
        self.assert_pos_as_in_mode(self.slit, "ar")
        self.assert_pos_as_in_mode(self.specgraph, "ar")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

        # Change positions back
        self.optmngr.setPath("mirror-align").result()

        self.optmngr.setPath(sas).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "ar")
        self.assert_pos_as_in_mode(self.slit, "ar")
        self.assert_pos_as_in_mode(self.specgraph, "ar")
        self.assertEqual(self.spec_det_sel.position.value, {'rx': 0})
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.022)

        # test guess mode for spectral-dedicated
        sems = stream.SEMStream("test sem", self.sed, self.sed.data, self.ebeam)
        specs = stream.SpectrumSettingsStream("test spec", self.spec, self.spec.data, self.ebeam)
        sps = stream.SEMSpectrumMDStream("test sem-spec", sems, specs)

        self.optmngr.setPath(specs).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral")
        # No slit/spectrograph as they are not affecting the detector
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.026112848)

        # Change positions back
        self.optmngr.setPath("chamber-view").result()

        self.optmngr.setPath(sps).result()
        # Assert that actuator was moved according to mode given
        self.assert_pos_as_in_mode(self.lenswitch, "spectral")
        self.assertAlmostEqual(self.spec_sel.position.value["x"], 0.026112848)


if __name__ == "__main__":
    unittest.main()
