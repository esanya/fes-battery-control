#!/usr/bin/env python3
########################################################################
#
#
#
#
#
#
#
#
#
#
########################################################################

import argparse
import sys
from batterymanager import BatteryManager

VERSION="0.10"    
DESCRIPTION="""
FES control program for FES battery
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under certain conditions; See COPYING for details.
""".format(VERSION)

parser = argparse.ArgumentParser(description=DESCRIPTION,
         formatter_class=argparse.ArgumentDefaultsHelpFormatter,
         epilog='''FES battery control service''')
parser.add_argument('-bu1', '--battery1',metavar="battery1",
        help='the USB serial device',default="/dev/ttyUSB0")
parser.add_argument('-bs1', '--batteryspeed1',metavar="batteryspeed1",
        help='the speed of the serial device',type=int,default=115200)
parser.add_argument('-bu2', '--battery2',metavar="battery2",
        help='the USB serial device',default="/dev/ttyUSB1")
parser.add_argument('-bs2', '--batteryspeed2',metavar="batteryspeed2",
        help='the speed of the serial device',type=int,default=115200)
parser.add_argument('-ar', '--arduino',metavar="arduino",
        help='the serial device',default="/dev/ttyUSB2")
parser.add_argument('-mt', '--mocktelemetrix',metavar="mocktelemetrix",
        help='to mock the telemetrix HW device',default=False)
parser.add_argument('-mb', '--mockbatteryusb',metavar="mockbatteryusb",
        help='to mock the battery USB-HW device',default=False)
parser.add_argument('-mq', '--mqttServer',metavar="mqttServer",
        help='Mqtt server Address',default=None)

args = parser.parse_args()

bm = BatteryManager(args.arduino,
        args.battery1,args.batteryspeed1,
        args.battery2,args.batteryspeed2,
        mocktelemetrix=args.mocktelemetrix,mockBattery=args.mockbatteryusb,
        mqttServer=args.mqttServer)

try:
    bm.startUp()
except KeyboardInterrupt:
    bm.shutdown()
except Exception:
    bm.shutdown()

