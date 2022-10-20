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
#
#
#
#
########################################################################

import socket
import sys
import time
import argparse
from fes_common import FESMessages,FESResponses
from crccheck.crc import Crc16Arc

parser = argparse.ArgumentParser(description="Dummy Battery Emulator",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                 epilog='''FES Dummy Battery''')

parser.add_argument('-p', '--port',metavar="port",help='the tcp port where the serial port is mapped to',type=int,default=10000)
parser.add_argument('-w', '--password',metavar="password",help='the password for the applecatien',default=None)
parser.add_argument('-i', '--identifier',metavar="identifier",help='the identifier the application',default=None)
parser.add_argument('-tmn', '--tmininit',metavar="tmininit",help='the initial value of TMIN',type=float,default=None)
parser.add_argument('-tmx', '--tmaxinit',metavar="tmaxinit",help='the initial value of TMAX',type=float,default=None)
parser.add_argument('-cmn', '--cmininit',metavar="cmininit",help='the initial value of CMIN',type=float,default=None)
parser.add_argument('-cmx', '--cmaxinit',metavar="cmaxinit",help='the initial value of CMAX',type=float,default=None)
parser.add_argument('-mnh', '--minhinit',metavar="minhinit",help='the initial value of MINH',type=float,default=None)
parser.add_argument('-mxh', '--maxhinit',metavar="maxhinit",help='the initial value of MAXH',type=float,default=None)
parser.add_argument('-lc', '--lcd1init',metavar="lcd1init",help='the initial value of LCD1',default=None)
parser.add_argument('-lo', '--lcd1cont',metavar="lcd1cont",help='the continue change value of LCD1 at this index',default=None)
parser.add_argument('-li', '--lcd1incr',metavar="lcd1incr",help='the continue change value of LCD1 with this value',type=int,default=2)
parser.add_argument('-cl', '--cellinit',metavar="cellinit",help='the initial value of CELL',type=float,default=None)
parser.add_argument('-tb', '--tbalinit',metavar="tbalinit",help='the initial value of TBAL',type=float,default=None)
parser.add_argument('-cm', '--cheminit',metavar="cheminit",help='the initial value of CHEM',type=float,default=None)
parser.add_argument('-cp', '--capainit',metavar="capainit",help='the initial value of CAPA',type=float,default=None)
parser.add_argument('-cy', '--cyclinit',metavar="cyclinit",help='the initial value of CYCL',type=float,default=None)
parser.add_argument('-pr', '--parvinit',metavar="parvinit",help='the initial value of PARV',type=float,default=None)
parser.add_argument('-bv', '--bvolinit',metavar="bvolinit",help='the initial value of BVOL',type=float,default=None)
parser.add_argument('-bm', '--bmininit',metavar="bmininit",help='the initial value of BMIN',type=float,default=None)
parser.add_argument('-cr', '--charinit',metavar="charinit",help='the initial value of CHAR',type=float,default=None)
parser.add_argument('-fr', '--fragment',metavar="fragment",help='to send fragmented messages',type=bool,default=False)

args = parser.parse_args()
    
# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect the socket to the port where the server is listening
server_address = ('localhost', args.port)
print(sys.stderr, 'connecting to %s port %s' % server_address)
sock.connect(server_address)

incrementalLcd=0
messages=FESMessages()
responses=FESResponses()

def sendSimpleLcd():
    if (args.lcd1init!= None):
        sock.sendall(args.lcd1init.encode('utf-8'))
    else:
        if (args.fragment):
            len=int(len(responses.RESPONSES['LCD1'])/2)
            part1=responses.RESPONSES['LCD1'][:len]
            part2=responses.RESPONSES['LCD1'][len:]
            sock.sendall(bytes(part1))
            time.sleep(0.1)
            sock.sendall(bytes(part2))
        else:
            sock.sendall(bytes(responses.RESPONSES['LCD1']))

def sendIncrementalLcd():
    global incrementalLcd
    initialLCD=responses.RESPONSES['LCD1']
    initialLCD1stMsg=initialLCD[0:10]
    initialLCD2ndMsg=initialLCD[10:41]

    bytestosend=[]
    bytestosend.extend(initialLCD1stMsg)


    initialLCD2ndMsg[int(args.lcd1cont)] = int.from_bytes((incrementalLcd).to_bytes(1, byteorder='big'), byteorder='big')

    incrementalLcd=incrementalLcd+args.lcd1incr
    if (incrementalLcd > 255):
        incrementalLcd = 0

#    print(sys.stderr, 'to crc "%s"' % (initialLCD2ndMsg))
    lcdcrc=Crc16Arc.calcbytes(initialLCD2ndMsg)

    bytestosend.extend(initialLCD2ndMsg)
    bytestosend.extend(lcdcrc)
    bytestosend.extend([170])

    print(sys.stderr, 'to send back "%s"' % (bytestosend))

    sock.sendall(bytes(bytestosend))


def sendLcd():
    if (args.lcd1cont!= None):
        sendIncrementalLcd()
    else:
        sendSimpleLcd()


try:
    # Send data
    message = 'This is the message.  It will be repeated.'
#    print(sys.stderr, 'sending "%s"' % message)
#    sock.sendall(message.encode('utf-8'))

    # Look for the response
    amount_received = 0
    amount_expected = len(message)
    while True:
        data = sock.recv(12)
        amount_received += len(data)

        command=None
        for i in messages.MESSAGES:
            if (data.find(i.encode()) >=0):
                command = i
                break

        print(sys.stderr, 'received "%s"' % command)

        if (command == 'IDN?'):
            if (args.identifier != None):
                encodeddata=args.identifier.encode('utf-8')
                idcrc=Crc16Arc.calchex(encodeddata)
                bytestosend=[0x55, 0x00, 0x09]
                bytestosend.append(args.identifier)
                bytestosend.append(idcrc)
                bytestosend.append(0xaa)

                print(sys.stderr, 'to send back "%s"' % (bytestosend))

                sock.sendall(bytes(bytestosend))
            else:
                sock.sendall(bytes(responses.RESPONSES['IDN?']))
        elif (command == 'PASS'):
            if (args.password!= None):
                sock.sendall(args.password.encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['PASS']))
        elif (command == 'TMIN'):
            if (args.tmininit!= None):
                sock.sendall('xwr{}sdf'.format(args.tmininit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['TMIN']))
        elif (command == 'TMAX'):
            if (args.tmaxinit!= None):
                sock.sendall('xwr{}sdf'.format(args.tmaxinit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['TMAX']))
        elif (command == 'CMIN'):
            if (args.cmininit!= None):
                sock.sendall('xwr{}sdf'.format(args.cmininit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['CMIN']))
        elif (command == 'CMAX'):
            if (args.cmaxinit!= None):
                sock.sendall('xwr{}sdf'.format(args.cmaxinit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['CMAX']))
        elif (command == 'MINH'):
            if (args.minhinit!= None):
                sock.sendall('xwr{}sdf'.format(args.minhinit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['MINH']))
        elif (command == 'MAXH'):
            if (args.maxhinit!= None):
                sock.sendall('xwr{}sdf'.format(args.maxhinit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['MAXH']))
        elif (command == 'LCD1'):
            sendLcd()
        elif (command == 'CELL'):
            if (args.cellinit!= None):
                sock.sendall('xwr{}sdf'.format(args.cellinit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['CELL']))
        elif (command == 'TBAL'):
            if (args.tbalinit!= None):
                sock.sendall('xwr{}sdf'.format(args.tbalinit).encode('utf-8'))
            else:
                sock.sendall(bytes(responses.RESPONSES['TBAL']))
        elif (command == 'CHEM'):
            sock.sendall('xwr{}sdf'.format(args.cheminit).encode('utf-8'))
        elif (command == 'CAPA'):
            sock.sendall('xwr{}sdf'.format(args.capainit).encode('utf-8'))
        elif (command == 'CYCL'):
            sock.sendall('xwr{}sdf'.format(args.cyclinit).encode('utf-8'))
        elif (command == 'PARV'):
            sock.sendall('xwr{}sdf'.format(args.parvinit).encode('utf-8'))

        elif (command == 'BVOL'):
            sock.sendall('xwr{}sdf'.format(args.bvolinit).encode('utf-8'))
        elif (command == 'BMIN'):
            sock.sendall('xwr{}sdf'.format(args.bmininit).encode('utf-8'))
        elif (command == 'CHAR'):
            sock.sendall('xwr{}sdf'.format(args.charinit).encode('utf-8'))
        else:
            print(sys.stderr, 'received "%s"\n' % data)


finally:
    print(sys.stderr, 'closing socket')
    sock.close()
