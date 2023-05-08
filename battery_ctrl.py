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
import logging
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
parser.add_argument('-mqs', '--mqttServer',metavar="mqttServer",
        help='Mqtt server Address',default=None)
parser.add_argument('-mqp', '--mqttPort',metavar="mqttPort",
        help='Mqtt server Port',type=int,default=1883)
parser.add_argument('-mqu', '--mqttUser',metavar="mqttUser",
        help='Mqtt server User',default=None)
parser.add_argument('-mqw', '--mqttPassword',metavar="mqttPassword",
        help='Mqtt server Password',default=None)
parser.add_argument('-mqtr', '--mqttTopicRoot',metavar="mqttTopicRoot",
        help='Mqtt Topic Root',default="acbs/fes")
parser.add_argument('-loglevel', '--loglevel',metavar="loglevel",
        help='LogLevel: DEBUG, ERROR, FATAL, INFO, WARNING',default=logging.INFO)

args = parser.parse_args()

bm = BatteryManager(args.arduino,
        args.battery1,args.batteryspeed1,
        args.battery2,args.batteryspeed2,
        mocktelemetrix=args.mocktelemetrix,mockBattery=args.mockbatteryusb,
        mqttServer=args.mqttServer, mqttPort=args.mqttPort, mqttUser=args.mqttUser, 
        mqttPassword=args.mqttPassword, mqttTopicRoot=args.mqttTopicRoot, loglevel=args.loglevel)

try:
    bm.startUp()
except KeyboardInterrupt:
    bm.shutdown()
except Exception as e:
    print(e)
    bm.shutdown()

