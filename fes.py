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

import serial
import argparse
import sys
import time
import os
import logging
from fes_common import FESMessages,FESResponses


VER = sys.version_info
if VER[0]<3:
    raise Exception("at least python version 3 is needed")

########################################################################

STDOUT=sys.stdout
STDERR=sys.stderr

########################################################################

class FES(object):
    messages=FESMessages()
    BEGIN_CHAR=b'0x55'
    END_CHAR=b'0xaa'

    def __init__(self, device, speed):
        self.device=device
        self.speed=speed
        self.ser=None
        self.opened=False
        self.connected=False
        self.identifier="unknown"
        self.passwd="unknown"
        
    def open(self):
        logging.debug("opening device %s\n",self.device)
        if self.opened:
            logging.error("cannot open device %s more than once!\n",self.device)
            return
        try:
            self.ser=serial.Serial(self.device, self.speed,timeout=30)
            self.opened=True
        except Exception as ex:
            logging.fatal("%s\n",ex)

    def isOpened(self):
        return self.opened

    def isConnected(self):
        logging.debug("isConnected:%s\n",self.connected)
        return self.connected
    
    def close(self):
        if self.opened:
            self.ser.close()
            self.opened=False
        else:
            self.warn("could not close device; %s iss not open\n",self.device)

    def send(self,data,exp=None):
        if self.ser.in_waiting>0:
            stale=self.ser.read_all()
            self.warn("read stale bytes from device: %s\n",stale)
        logging.debug("sending:%s\n",data)
        self.ser.write(bytes(data))
        if exp!=None:
            ack=self.ser.read(len(exp))
            if ack==exp:
                logging.debug("got acknowledge\n")
            else:
                logging.fatal("didn't got acknowledge; got:%s\n",ack)
        else:
            logging.debug("no acknowledge expected!\n")

    def _check(self):
        if not self.connected:
            logging.fatal("connection failed! Could not detect FES battery!")

    def decodeMessage(self,data,id=0):
#        logging.info("Type of data %s\n", type(data))

#        if data[0] != BEGIN_CHAR
#            logging.error("Message does not start with 0x55")

        ptr=0
        startpos=0
        len=data[startpos+3]
        while ptr < id:
            startpos=4+len+2+1
            len=data[startpos+3]
            ptr=ptr+1

        decoded = data[startpos+4:startpos+4+len]

        return decoded
        
    def connect(self):
        logging.debug("connecting...\n")
        self.send(self.messages.MESSAGES['IDN?'])
        logging.debug("reading serial\n")
        time.sleep(0.1)
        resp=self.ser.read_all()
        logging.debug("response read:%s\n",resp)

        self.identifier=self.decodeMessage(resp)

        self.connected=True
        self._check()
        logging.debug("...connected!\n")
        logging.info("Identifier detected:%s\n",self.identifier)
        
    def password(self):
        self.send(self.messages.MESSAGES['PASS'])
        time.sleep(0.1)
        resp=self.ser.read_all()
        logging.debug("pass response read:%s",resp)
        self.passwd=self.decodeMessage(resp)
        logging.info("Received password :%s\n",self.passwd)

    def requestForRaw(self, requestStr, debugMessage, lenpos):
        self.send(requestStr)
        time.sleep(0.1)
        resp=self.ser.read_all()
        fragmentCount = 10
        logging.debug("%s from %s %s\n", debugMessage, self.ser, resp)
        while (len(resp) < lenpos and fragmentCount>=0):
            time.sleep(0.2)
            newresp=self.ser.read_all()
            logging.debug("newresp %s from %s: %s at step %s\n", debugMessage, self.ser, resp, fragmentCount)
            resp1=b''.join([resp, newresp])
            resp=resp1
            logging.debug("%s: %s\n", debugMessage, resp)
            fragmentCount=fragmentCount-1

        fragmentCount = 10
        if (len(resp) > lenpos):
            msglen=resp[lenpos]
        else:
            return resp

        logging.info("message len: %s\n", msglen)
        totallen=lenpos+msglen+3
        logging.info("total len message len: %s\n", totallen)

        while (len(resp) < totallen and fragmentCount>=0):
            time.sleep(0.1)
            newresp=self.ser.read_all()
            logging.debug("newresp %s from %s: %s at step %s\n", debugMessage, self.ser, resp, fragmentCount)
            resp1=b''.join([resp, newresp])
            resp=resp1
#            msglen=resp[3]
            logging.debug("%s: %s\n", debugMessage, resp)
            fragmentCount=fragmentCount-1


        return resp

    def requestFor(self, requestStr, debugMessage):
        resp=self.requestForRaw(requestStr, debugMessage, 3)

        value=self.decodeMessage(resp)
        logging.info("%s: %s\n", debugMessage, value)

        return value

    def tmin(self):
        return self.requestFor(self.messages.MESSAGES['TMIN'], "tmin response read")

    def tmax(self):
        return self.requestFor(self.messages.MESSAGES['TMAX'], "tmax response read")

    def cmin(self):
        return self.requestFor(self.messages.MESSAGES['CMIN'], "cmin response read")

    def cmax(self):
        return self.requestFor(self.messages.MESSAGES['CMAX'], "cmax response read")

    def minh(self):
        return self.requestFor(self.messages.MESSAGES['MINH'], "minh response read")

    def maxh(self):
        return self.requestFor(self.messages.MESSAGES['MAXH'], "maxh response read")
        
    def lcd1(self):
        debugMessage="lcd1 response read"
        try:
            self.requestFor(self.messages.MESSAGES['LCD1'], debugMessage)
        except IndexError:
            logging.error("%s: invalid read\n", debugMessage)
        except Exception:
            logging.error("%s: invalid read\n", debugMessage)
        
    def soc(self):
        debugMessage="soc response read"
        resp=self.requestForRaw(self.messages.MESSAGES['LCD1'], debugMessage, 12)

        try:
            compl=self.decodeMessage(resp, 1)
            value=0
            if ((compl[23]&0x01) > 0):
                value=50+(50*compl[22])/127
            else:
                value=(50*compl[21])/127


        
            logging.info("%s: %s\n", debugMessage, value)

            return value

        except IndexError:
            logging.error("%s: invalid read (IndexError)\n", debugMessage)
            raise
        except Exception:
            logging.error("%s: invalid read (Exception)\n", debugMessage)
            raise

        
    def cell(self):
        return self.requestFor(self.messages.MESSAGES['CELL'], "cell response read")
        
    def tbal(self):
        return self.requestFor(self.messages.MESSAGES['TBAL'], "cell response read")



########################################################################
        
    
VERSION="0.10"    
    

DESCRIPTION="""
FES control program for FES battery
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under certain conditions; See COPYING for details.
""".format(VERSION)

if __name__ == '__main__':
    
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=format, level=logging.DEBUG)
    parser = argparse.ArgumentParser(description=DESCRIPTION,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     epilog='''FES battery control''')
    parser.add_argument('-d', '--device',metavar="device",help='the serial device',default="/dev/ttyUSB0")
    parser.add_argument('-s', '--speed',metavar="speed",help='the speed of the serial device',type=int,default=115200)
    parser.add_argument('-v', '--verbosity',help='increase verbosity level ',action='count',default=0)
    parser.add_argument('-l', '--loop',metavar="loop",help='the loop type of the application',type=int,default=1)
    parser.add_argument('-lc', '--loopcount',metavar="loopcount",help='the loop count of the application',type=int,default=10)
    
    args = parser.parse_args()

    battery=FES(args.device, args.speed)
    battery.open()

    if (args.loop == 1):
        battery.connect()
        battery.password()
        battery.tmax()
        battery.tmin()
    elif (args.loop == 2):
        battery.connect()
        while (not(battery.isConnected())):
            battery.connect()
        battery.password()
        battery.tmax()
        battery.tmin()
    elif (args.loop == 3):
        battery.connect()

        while (not(battery.isConnected())):
            battery.connect()

        battery.password()
        battery.tmin()
        battery.tmax()
        battery.cmin()
        battery.cmax()
        battery.minh()
        battery.maxh()

        loopvar=0
        while (loopvar < args.loopcount):
            battery.lcd1()
            battery.soc()
#            battery.cell()

            loopvar=loopvar+1
            time.sleep(1)
    elif (args.loop == 4):
        battery.connect()

        while (not(battery.isConnected())):
            battery.connect()

        battery.password()

        while (True):
            battery.soc()
            input("Press any key to continue")

    battery.close()

    if not (args.verbosity or args.device or args.speed or args.loop):
        parser.print_help()


