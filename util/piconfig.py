#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Allows to read/write the configuration in non-volatile memory of Physik
# Instrumente controllers.
# The file to represent the memory is a tab-separated value with the following format:
# axis  parameter  value    # comment
# axis must be A1->A16
#       parameter is hexdecimal 32 bit unsigned int
#                  value is a string (actual allowed values depend on the parameter)
# The recommend file extension is '.pi.tsv'

'''
Created on November 2014

@author: Éric Piel

Copyright © 2014 Éric Piel, Delmic

piconfig is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License version 2 as published by the Free Software
Foundation.

piconfig is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
piconfig. If not, see http://www.gnu.org/licenses/.
'''
# To test:
# ./util/piconfig.py --log-level 2 --write test.pi.tsv --port /dev/fake --controller 1

import argparse
import logging
import re
import sys
from odemis.driver import pigcs


# The functions available to the user
def read_param(cont, f):
    # Write the controller, for reference
    idn = cont.GetIdentification()
    if cont.address is None:
        f.write("# Parameters from controller %s\n" % (idn,))
    else:
        f.write("# Parameters from controller %d - %s\n" % (cont.address, idn))
    f.write("# Axis\tParam\tAddress\tDescription\n")

    params_desc = cont.GetAvailableParameters()
    ap = cont.GetParameters()

    for a, p in sorted(ap.keys()):
        # v = cont.GetParameter(a, p)
        v = ap[(a, p)]
        try:
            desc = params_desc[p]
            f.write("A%d\t0x%x\t%s\t# %s\n" % (a, p, v, desc))
        except KeyError:
            f.write("A%d\t0x%x\t%s\n" % (a, p, v))

    f.close()


def write_param(cont, f):
    params = {} # int -> str = param num -> value

    # We could use SPE to directly write to flash memory but:
    # * As you need to put the "password", the command is longer and so can more
    #   often reach the limit
    # * Some parameters (GEMAC) cannot be written this way
    # * In case of error, we could end up with half the parameters written

    # read the parameters "database" from stdin
    axes = set()
    for l in f:
        # comment or empty line?
        mc = re.match(r"\s*(#|$)", l)
        if mc:
            logging.debug("Comment line skipped: '%s'", l.rstrip("\n\r"))
            continue
        m = re.match(r"A(?P<axis>\d+)\t0x(?P<param>[0-9A-Fa-f]+)\t(?P<value>(\S+))\s*(#.*)?$", l)
        if m:
            axis, param, value = int(m.group("axis")), int(m.group("param"), 16), m.group("value")
            params[(axis, param)] = value
            axes.add(axis)
        else:
            # Format used to support only one axis (1) => fallback to this if the
            # first column doesn't start with A.
            m = re.match(r"0x(?P<param>[0-9A-Fa-f]+)\t(?P<value>(\S+))\s*(#.*)?$", l)
            if not m:
                logging.debug("Line skipped: '%s'", l)
                continue
            param, value = int(m.group("param"), 16), m.group("value")
            params[(1, param)] = value

    logging.debug("Parsed parameters as:\n%s", params)

    avail_cmds = cont.GetAvailableCommands()
    if "CCL" in avail_cmds:
        # Some controllers need to have changed "command level" before it's
        # possible to write the parameters. 1/advanced is for E-725.
        cont.SetCommandLevel(1, "advanced")

    axes = set(a for a, p in params.keys())

    # Write unit parameters first, as updating them will change the rest of the
    # values.
    def nd_first_order(e):
        a, p = e
        if p in (0xe, 0xf):
            return a, -p
        else:
            return e

    # Write each parameters (in order, to be clearer in case of error)
    for a, p in sorted(params.keys(), key=nd_first_order):
        v = params[a, p]
        try:
            cont.SetParameter(a, p, v)
        except ValueError:
            logging.error("Failed to write axis %d parameter 0x%x to %s", a, p, v)
            # still continue
        except Exception:
            logging.exception("Failed to write axis %d parameter 0x%x", a, p)
            raise

    # save to flash
    cont._sendOrderCommand("WPA 100\n")


def reboot(cont):
    cont.Reboot()

    # make sure it's fully rebooted and recovered
    cont.GetErrorNum()


def main(args):
    """
    Handles the command line arguments
    args is the list of arguments passed
    return (int): value to return to the OS as program exit code
    """

    # arguments handling
    parser = argparse.ArgumentParser(prog="piconfig",
                                     description="Read/write parameters in a PI controller")

    parser.add_argument("--log-level", dest="loglev", metavar="<level>", type=int,
                        default=1, help="set verbosity level (0-2, default = 1)")

    parser.add_argument('--read', dest="read", type=argparse.FileType('w'),
                        help="Will read all the parameters and save them in a file (use - for stdout)")
    parser.add_argument('--write', dest="write", type=argparse.FileType('r'),
                        help="Will write all the parameters as read from the file (use - for stdin)")
    parser.add_argument('--reboot', dest="reboot", action='store_true',
                        help="Reboot the controller")

    parser.add_argument('--port', dest="port", required=True,
                        help="Port name (ex: /dev/ttyUSB0, autoip, or 192.168.95.5)")
    parser.add_argument('--controller', dest="addr", type=int,
                        help="Controller address (if controller needs it)")

    # TODO: allow to reconfigure the IP settings on the network controller via USB
    # TODO: add way to turn on/off the error light (ex, send \x18 "STOP" and ERR?)

    options = parser.parse_args(args[1:])

    # Set up logging before everything else
    if options.loglev < 0:
        logging.error("Log-level must be positive.")
        return 127
    loglev_names = (logging.WARNING, logging.INFO, logging.DEBUG)
    loglev = loglev_names[min(len(loglev_names) - 1, options.loglev)]
    logging.getLogger().setLevel(loglev)

    try:
        kwargs = {}
        if options.addr is None:
            # If no address, there is also no master (for IP)
            kwargs["master"] = None

        if options.port == "/dev/fake":
            kwargs["_addresses"] = {options.addr: False}
            acc = pigcs.FakeBus._openPort(options.port, **kwargs)
        else:
            acc = pigcs.Bus._openPort(options.port, **kwargs)

        cont = pigcs.Controller(acc, address=options.addr, _stem=True)
        cont.GetErrorNum()

        if options.read:
            read_param(cont, options.read)
        elif options.write:
            write_param(cont, options.write)
        elif options.reboot:
            reboot(cont)
        else:
            raise ValueError("Need to specify either read, write, or reboot")

        cont.terminate()
        acc.terminate()
    except ValueError as exp:
        logging.error("%s", exp)
        return 127
    except IOError as exp:
        logging.error("%s", exp)
        return 129
    except Exception:
        logging.exception("Unexpected error while performing action.")
        return 130

    return 0


if __name__ == '__main__':
    ret = main(sys.argv)
    exit(ret)
