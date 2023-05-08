
from telemetrix import telemetrix
from unittest.mock import Mock
from batterycontrol import BatteryControl
from i2c_lcd_pcf8574 import LCD_I2C
import time
import logging
import threading
import re
import paho.mqtt.client as mqttClient
from paho import mqtt
import json
import os
import os.path
import subprocess

report_log='/bttrymngr_report.log'

class BatteryManager(object):
    def __init__(self, telemetrixPort, btt1CtrlCable, btt1CableSpeed, btt2CtrlCable, btt2CableSpeed, mqttTopicRoot, arduino_instance_id=1, mocktelemetrix=False, mockBattery=False, control_fifo='/tmp/bttrymngr_ctrl.fifo', mqttServer=None, mqttPort=1883, mqttUser=None, mqttPassword=None, initStateIteration=6, initTelemetricIteration=12, loglevel=logging.DEBUG):
        if (telemetrixPort != 'auto'):
            self.telemetrixPort=telemetrixPort
        else:
            self.telemetrixPort=self.findTelemetrixPort()

        self.control_fifo=control_fifo
        self.arduino_instance_id=arduino_instance_id
        self.mocktelemetrix=mocktelemetrix
        self.mockBattery=mockBattery
        
        if (btt1CtrlCable!= 'auto'):
            self.btt1CtrlCable=btt1CtrlCable
        else:
            self.btt1CtrlCable=self.findBttCtrlCable(0)
        self.btt1CableSpeed=btt1CableSpeed

        if (btt2CtrlCable!= 'auto'):
            self.btt2CtrlCable=btt2CtrlCable
        else:
            self.btt2CtrlCable=self.findBttCtrlCable(1)
        self.btt2CableSpeed=btt2CableSpeed

        self.mqttServer=mqttServer
        self.mqttPort=mqttPort
        self.mqttTopicRoot=mqttTopicRoot
        self.mqttUser=mqttUser
        self.mqttPassword=mqttPassword

        self.initStateIteration=initStateIteration
        self.initTelemetricIteration=initTelemetricIteration
        self.stateIteration=self.initStateIteration
        self.telemetricIteration=self.initTelemetricIteration
        log_prefix=''
        if (mocktelemetrix):
            log_prefix='/tmp/'
        else:
            log_prefix='/tmp/'
#            log_prefix='/var/log'
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.reportFile=log_prefix+report_log
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s - %(message)s', filename=self.reportFile, level=loglevel)

    def findBttCtrlCable(self, cableId):
        return findUsbPortIntern('ptx24235', '4', cableId)

    def findTelemetrixPort(self):
        return findUsbPortIntern('ch341', '2', 0)

    def findUsbPortIntern(self, pattern, lastEntries, portId):
        last_usb=subprocess.getoutput('dmesg |grep -i ttyusb|grep -i '+pattern+'|tail -'+lastEntries).split('\n')
        if (len(last_usb) == 0):
            raise Exception(pattern+" not connected")
        elif ('disconnected' in last_usb[len(last_usb)-1]):
            raise Exception(pattern+" was disconnected")
        elif ('attached' in last_usb[len(last_usb)-1]):
            index_oftty = last_usb[len(last_usb)-1].find('ttyUSB')
            return '/dev/' + last_usb[len(last_usb)-1][index_oftty:]
        else:
            raise Exception(pattern+" was disconnected")

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

#        self.mqttClient = None
        if (self.mqttServer != None):
            self.mqttClient = mqttClient.Client(client_id="", userdata=None, protocol=mqttClient.MQTTv5)
            if (self.mqttUser != None):
                self.mqttClient.username_pw_set(self.mqttUser, self.mqttPassword)
            self.mqttClient.on_connect = self.on_mqtt_connect
            self.mqttClient.on_message = self.on_mqtt_message
#            self.mqttClient.on_log= self.on_mqtt_log
    
            if (self.mqttPort == 8883):
                self.mqttClient.tls_set(tls_version=mqttClient.ssl.PROTOCOL_TLS)
            self.mqttClient.connect(self.mqttServer, self.mqttPort)
            self.mqttClient.loop_start()

    def getState(self):
        state={'batt1': self.batt1.getState(), 'batt2': self.batt2.getState()}
        return state

    def getTelemetric(self):
        telemetric={'batt1': self.batt1.getTelemetric(), 'batt2': self.batt2.getTelemetric()}
        return telemetric

    def initCtrlFifo(self):
        if (os.path.exists(self.control_fifo)):
            os.remove(self.control_fifo)
        os.mkfifo(self.control_fifo)
        os.system('echo dummy > ' + self.control_fifo + ' &')
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
            time.sleep(5)

    def mngrInnerLoop(self, line, immediateNotification=False):
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
        self.publishMqttState(immediateNotification)

    def publishMqttState(self, immediateNotification):
        if (self.mqttServer != None and self.mqttClient != None):
            if (self.stateIteration<0 or immediateNotification):
                self.mqttClient.publish(self.mqttTopicRoot+"/state", json.dumps(self.getState()), qos=1)
                self.stateIteration=self.initStateIteration
            else:
                self.stateIteration=self.stateIteration-1

            if (self.telemetricIteration<0 or immediateNotification):
                self.mqttClient.publish(self.mqttTopicRoot+"/telemetric", json.dumps(self.getTelemetric()), qos=1)
                self.telemetricIteration=self.initTelemetricIteration
            else:
                self.telemetricIteration=self.telemetricIteration-1

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
    def on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        logging.debug("Connected with result code "+str(rc))
        logging.debug("Connected with client "+str(client))
        logging.debug("Connected with userdata "+str(userdata))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(self.mqttTopicRoot+"/command", qos=1)
    
    # The callback for when a PUBLISH message is received from the server.
    def on_mqtt_message(self, client, userdata, msg):
        logging.debug('on_message: %s, %s', msg.topic, msg.payload)
        pl=json.loads(msg.payload)
        self.mngrInnerLoop(pl['command'], True)
    
    def on_mqtt_log(self, client, userdata, level, msg):
        logging.debug("log with client "+str(client))
        logging.debug("log with userdata "+str(userdata))
        logging.debug('on_log: %s', msg)
    
