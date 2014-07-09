# -*- coding: utf-8 -*-
"""
Created on 11 Apr 2014

@author: Kimon Tsitsikas

Copyright © 2013-2014 Kimon Tsitsikas, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the
terms  of the GNU General Public License version 2 as published by the Free
Software  Foundation.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY;  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR  PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Odemis. If not, see http://www.gnu.org/licenses/.
"""

from __future__ import division

from concurrent.futures._base import CancelledError, CANCELLED, FINISHED, \
    RUNNING
import logging
import numpy
from odemis import model
from odemis.acq._futures import executeTask
import threading
import time
from scipy import ndimage

FINE_SPOTMODE_ACCURACY = 5e-6  # fine focus accuracy in spot mode #m
ROUGH_SPOTMODE_ACCURACY = 10e-6  # rough focus accuracy in spot mode #m
INIT_THRES_FACTOR = 4e-3  # initial autofocus threshold factor

MAX_STEPS_NUMBER = 40  # Max steps to perform autofocus


def MeasureFocus(image):
    """
    Given an image, focus measure is calculated using the standard deviation of
    the raw data.
    image (model.DataArray): Optical image
    returns (float):    The focus level of the optical image
    """
    # Handle RGB image
    if len(image.shape) == 3:
        # TODO find faster solution
        r, g, b = image[:, :, 0], image[:, :, 1], image[:, :, 2]
        gray = numpy.empty(image.shape[0:2], dtype="uint16")
        gray[...] = r
        gray += g
        gray += b
    else:
        gray = image
    return ndimage.standard_deviation(image)


def _DoAutoFocus(future, detector, max_step, thres_factor, et, focus, accuracy):
    """
    Iteratively acquires an optical image, measures its focus level and adjusts 
    the optical focus with respect to the focus level.
    future (model.ProgressiveFuture): Progressive future provided by the wrapper 
    detector: model.DigitalCamera or model.Detector
    max_step: step used in case we are completely out of focus
    thres_factor: threshold factor depending on type of detector and binning
    et: exposure time if detector is a ccd, 
        dwellTime*prod(resolution) if detector is an SEM
    focus (model.CombinedActuator): The optical focus
    accuracy (float): Focus precision #m
    returns (float):    Focus position #m
                        Focus level
    raises:    
            CancelledError if cancelled
            IOError if procedure failed
    """
    logging.debug("Starting Autofocus...")

    try:
        # Clip accuracy within reasonable limits
        accuracy = numpy.clip(accuracy, max_step / 5, max_step)
        rng = focus.axes["z"].range

        # Keep the initial focus position
        init_pos = focus.position.value.get('z')
        step = accuracy
        cur_pos = focus.position.value.get('z')
        image = detector.data.get(asap=False)
        fm_cur = MeasureFocus(image)
        init_fm = fm_cur
        f = focus.moveRel({"z": step})
        f.result()
        image = detector.data.get(asap=False)
        fm_test = MeasureFocus(image)

        if future._autofocus_state == CANCELLED:
            raise CancelledError()
        cur_pos = focus.position.value.get('z')

        # Check if we our completely out of focus
        if abs(fm_cur - fm_test) < (thres_factor * fm_cur):
            logging.warning("Completely out of focus, retrying...")
            step = max_step
            fm_new = 0
            sign = 1
            factor = 1
            new_step = step
            cur_pos = focus.position.value.get('z')

            steps = 0
            count_fails = 0
            while fm_new - fm_test < (thres_factor * 2) * fm_test:
                if steps >= MAX_STEPS_NUMBER:
                    break
                sign = -sign
                cur_pos = cur_pos + sign * new_step
                if sign == 1:
                    factor += 1
                new_step += factor * step
                if rng[0] <= cur_pos <= rng[1]:
                    pos = focus.position.value.get('z')
                    shift = cur_pos - pos
                    f = focus.moveRel({"z":shift})
                    f.result()
                    image = detector.data.get(asap=False)
                    fm_new = MeasureFocus(image)
                    if fm_test - fm_new > (thres_factor / 2) * fm_new:
                        count_fails+=1
                        if (steps == 1) and (count_fails == 2):
                            # Return to initial position
                            logging.info("Binary search does not improve focus.")
                            pos = focus.position.value.get('z')
                            shift = init_pos - pos
                            f = focus.moveRel({"z":shift})
                            f.result()
                            break
                    if future._autofocus_state == CANCELLED:
                        raise CancelledError()
                steps += 1

            image = detector.data.get(asap=False)
            fm_cur = MeasureFocus(image)
            f = focus.moveRel({"z": step})
            f.result()
            image = detector.data.get(asap=False)
            fm_test = MeasureFocus(image)
            if future._autofocus_state == CANCELLED:
                raise CancelledError()

        # Update progress of the future
        future.set_end_time(time.time() +
                            estimateAutoFocusTime(et, MAX_STEPS_NUMBER / 2))
        # Determine focus direction
        if fm_cur > fm_test:
            sign = -1
            f = focus.moveRel({"z":-step})
            f.result()
            if future._autofocus_state == CANCELLED:
                raise CancelledError()
            fm_test = fm_cur
        else:
            sign = 1

        # Move the lens in the correct direction until focus measure is decreased
        step = accuracy
        fm_old, fm_new = fm_test, fm_test
        steps = 0
        while fm_old - fm_new <= thres_factor * fm_old:
            if steps >= MAX_STEPS_NUMBER:
                break
            fm_old = fm_new
            f = focus.moveRel({"z":sign * step})
            f.result()
            image = detector.data.get(asap=False)
            fm_new = MeasureFocus(image)
            if future._autofocus_state == CANCELLED:
                raise CancelledError()
            steps += 1

        f = focus.moveRel({"z":-sign * step})
        f.result()

        if future._autofocus_state == CANCELLED:
            raise CancelledError()
        fm_final = fm_old
        if steps == 1:
            logging.info("Already well focused.")
            return focus.position.value.get('z'), fm_final

        if init_fm - fm_final < -thres_factor * fm_final:
            return focus.position.value.get('z'), fm_final
        else:
            # Return to initial position
            pos = focus.position.value.get('z')
            shift = init_pos - pos
            f = focus.moveRel({"z":shift})
            f.result()
            raise IOError("Autofocus failure")

        return focus.position.value.get('z'), fm_final
    finally:
        with future._autofocus_lock:
            if future._autofocus_state == CANCELLED:
                raise CancelledError()
            future._autofocus_state = FINISHED

def _CancelAutoFocus(future):
    """
    Canceller of _DoAutoFocus task.
    """
    logging.debug("Cancelling autofocus...")

    with future._autofocus_lock:
        if future._autofocus_state == FINISHED:
            return False
        future._autofocus_state = CANCELLED
        logging.debug("Autofocus cancelled.")

    return True

def estimateAutoFocusTime(exposure_time, steps=MAX_STEPS_NUMBER):
    """
    Estimates overlay procedure duration
    """
    return steps * exposure_time


def AutoFocus(detector, scanner, focus, accuracy):
    """
    Wrapper for DoAutoFocus. It provides the ability to check the progress of autofocus 
    procedure or even cancel it.
    detector (model.DigitalCamera or model.Detector): Type of detector
    scanner (None or model.Scanner): In case of a SED this is the scanner used
    focus (model.CombinedActuator): The optical focus
    accuracy (float): Focus precision #m
    returns (model.ProgressiveFuture):    Progress of DoAutoFocus, whose result() will return:
            Focus position #m
            Focus level
    """
    # Create ProgressiveFuture and update its state to RUNNING
    est_start = time.time() + 0.1
    # Check if you focus the SEM or a digital camera
    if scanner is not None:
        et = scanner.dwellTime.value * numpy.prod(scanner.resolution.value)
    else:
        et = detector.exposureTime.value

    # Set proper step and thres factor according to detector type
    thres_factor = INIT_THRES_FACTOR
    role = detector.role
    if role == "ccd":  # CCD
        max_step = 3 * detector.pixelSize.value[0]
        if detector.binning.value[0] > 2:
            thres_factor = 10 * thres_factor  # better snr
        else:
            thres_factor = 5 * thres_factor
    elif role == "overview-ccd":  # NAVCAM
        max_step = 100 * detector.pixelSize.value[0]
    elif role == "se-detector":  # SEM
        thres_factor = 5 * thres_factor
        max_step = 15e03 * scanner.pixelSize.value[0]

    f = model.ProgressiveFuture(start=est_start,
                                end=est_start + estimateAutoFocusTime(et))
    f._autofocus_state = RUNNING
    f._autofocus_lock = threading.Lock()

    # Task to run
    doAutoFocus = _DoAutoFocus
    f.task_canceller = _CancelAutoFocus

    # Run in separate thread
    autofocus_thread = threading.Thread(target=executeTask,
                  name="Autofocus",
                  args=(f, doAutoFocus, f, detector, max_step, thres_factor, et, focus, accuracy))

    autofocus_thread.start()
    return f