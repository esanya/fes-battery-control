
from telemetrix import telemetrix
from unittest.mock import Mock
from batterycontrol import BatteryControl
from i2c_lcd_pcf8574 import LCD_I2C
import time
import logging
import threading
import re
import paho.mqtt.client as mqtt
import json

report_log='/bttrymngr_report.log'

class BatteryManager(object):
    def __init__(self, telemetrixPort, btt1CtrlCable, btt1CableSpeed, btt2CtrlCable, btt2CableSpeed, arduino_instance_id=1, mocktelemetrix=False, mockBattery=False, control_fifo='/tmp/bttrymngr_ctrl.fifo', mqttServer=None, mqttTopicRoot= '/fes'):
        self.telemetrixPort=telemetrixPort
        self.control_fifo=control_fifo
        self.arduino_instance_id=arduino_instance_id
        self.mocktelemetrix=mocktelemetrix
        self.mockBattery=mockBattery
        self.btt1CtrlCable=btt1CtrlCable
        self.btt1CableSpeed=btt1CableSpeed
        self.btt2CtrlCable=btt2CtrlCable
        self.btt2CableSpeed=btt2CableSpeed
        self.mqttServer=mqttServer
        self.mqttTopicRoot=mqttTopicRoot

        log_prefix=''
        if (mocktelemetrix):
            log_prefix='/tmp/'
        else:
            log_prefix='/tmp/'
#            log_prefix='/var/log'
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.reportFile=log_prefix+report_log
        logging.basicConfig(format=format, filename=self.reportFile, level=logging.DEBUG)


    def startUp(self):
        if (self.mocktelemetrix):
            self.board = Mock()
        else:
            self.board = telemetrix.Telemetrix(arduino_instance_id=self.arduino_instance_id, com_port=self.telemetrixPort, sleep_tune=1e-04)

        self.lcd = LCD_I2C(self.board)
        self.lcd.begin()
        self.lcd.clear()
        self.lcd.backlight()

        self.batt1 = BatteryControl('batt1', self.board, 4, 6, 3, self.btt1CtrlCable, self.btt1CableSpeed, self.mockBattery);
        self.batt2 = BatteryControl('batt2', self.board, 7, 8, 5, self.btt2CtrlCable, self.btt2CableSpeed, self.mockBattery);
        self.printCurrentStateToLcd()

        self.mngrLoopEnabled=True
        self.initCtrlFifo()

        loopThread = threading.Thread(target=self.mngrLoop)
        loopThread.start()

        self.mqttClient = None
        if (self.mqttServer != None):
            self.mqttClient = mqtt.Client()
            self.mqttClient.on_connect = self.on_connect
            self.mqttClient.on_message = self.on_message
    
            self.mqttClient.connect(self.mqttServer, 1883, 60)
            self.mqttClient.loop_start()

    def getState(self):
        state={'batt1': self.batt1.getState(), 'batt2': self.batt2.getState()}
#        logging.debug('state: %s', state)
        return state

    def initCtrlFifo(self):
        self.ctrlFifo=open(self.control_fifo, 'r')

    def __repr__(self):
        return f"BatteryManager:\n\tboard: {self.board}\n\tctrlFifo: {self.ctrlFifo}\n\treportFile: {self.reportFile}\n\tmngrLoopEnabled: {self.mngrLoopEnabled}\n\tbtt1: {self.batt1}\n\tbtt2: {self.batt2}"

    def shutdown(self):
        self.batt1.shutdown()
        self.batt2.shutdown()

        #stop loop
        self.mngrLoopEnabled=False

        #close files/fifos
        self.ctrlFifo.close()

        #shutdown telemetrix
        self.board.shutdown()

        if (self.mqttServer != None and self.mqttClient != None):
            self.mqttClient.disconnect()

    #start in separate thread
    def mngrLoop(self):
        while(self.mngrLoopEnabled):
            line=self.ctrlFifo.readline()

            self.mngrInnerLoop(line)
            if (self.mqttServer != None and self.mqttClient != None):
                self.mqttClient.publish(self.mqttTopicRoot+'/state', json.dumps(self.getState()))

            time.sleep(5)

    def mngrInnerLoop(self, line):
        if (line != ''):
            logging.debug('command received: %s', line.replace('\n',''))

            match=re.search('bat=(\d+|all)\s+(\w+)(=(\d+))?', line)
            if (match):
                batteryId=match.group(1)
                command=match.group(2)
                argument=match.group(4)


                self.processCommand(batteryId, command, argument)
            else:
                logging.debug('no match.')
                

        self.batt1.doManagement()
        self.batt2.doManagement()

        self.printCurrentStateToLcd()



    def printCurrentStateToLcd(self):
        self.lcd.clear()
        self.lcd.setCursor(0,0)
        self.lcd.print(self.batt1.shortInfo())
        self.lcd.setCursor(0,1)
        self.lcd.print(self.batt2.shortInfo())


    def processCommand(self, batteryId, command, argument):
        batToUpdate=[]
        logging.debug('batteryId: %s', batteryId)
        if (batteryId == '1'):
            batToUpdate.append(self.batt1)
        elif (batteryId == '2'):
            batToUpdate.append(self.batt2)
        elif (batteryId == 'all'):
            batToUpdate.append(self.batt1)
            batToUpdate.append(self.batt2)
        else:
            logging.warning('invalid batteryId: %s', batteryId)
            return

        logging.debug('command: %s', command)
        if (command == 'target_soc'):
            [x.setTargetSoc(int(argument)) for x in batToUpdate]
        elif (command == 'charge'):
            [x.charge() for x in batToUpdate]
        elif (command == 'discharge'):
            [x.disCharge() for x in batToUpdate]
        elif (command == 'switchoff_charge'):
            [x.switchOffChargeDisCharge() for x in batToUpdate]
        elif (command == 'switch_on'):
            [x.switchBatteryOn() for x in batToUpdate]
        elif (command == 'switch_off'):
            [x.switchBatteryOff() for x in batToUpdate]
        elif (command == 'shutdown'):
            [x.shutdown() for x in batToUpdate]
        else:
            logging.warning('invalid command: %s', command)
            return
    
    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(self.mqttTopicRoot+"/command")
    
    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        logging.info('on_message: %s, %s', msg.topic, str(msg.payload))
        self.mngrInnerLoop(msg.payload)
    
