from enum import Enum
from telemetrix import telemetrix
from fes import FES
import logging

CtrlState = Enum('CtrlState', 'off statecheck charging discharging ')
BtryMainSwitchState = Enum('BtryMainSwitchState', 'off on conn_failed')

#off:           the battery controller is switched off
#statecheck:    
#charging       
#discharging    

class BatteryControl(object):
    def __init__(self, name, board, chargerPin, disChargerPin, mainSwitchServoPin, localMqttClient, localMqttTopicRoot, usbCtrlCable, usbCableSpeed, mockBattery=False):
        self.name=name
        self.batteryId=None
        self.chargerPin=chargerPin
        self.disChargerPin=disChargerPin
        self.mainSwitchServoPin=mainSwitchServoPin
        self.ctrlstate=CtrlState.off
        self.btrystate=BtryMainSwitchState.off
        self.switchServoPos=0
        self.targetSOC=50
        self.currentSOC=-1
        self.socFailCount=0
        self.currentValue={}
        self.valueReadFailCount={}
        self.operationExceptions={}
        self.mockBattery=mockBattery
        self.usbCtrlCable=usbCtrlCable
        self.usbCableSpeed=usbCableSpeed

        self.board=board
        self.localMqttClient=localMqttClient
        self.localMqttTopicRoot=localMqttTopicRoot
        self.battery=None
        self.initPin()
        self.initBoard()


    def __repr__(self):
        return f"BatteryControl: name: {self.name}, ctrlstate: {self.ctrlstate}, btrystate: {self.btrystate}, targetSOC: {self.targetSOC}, currentSOC: {self.currentSOC}"

    def getState(self):
        state={'ctrlstate': str(self.ctrlstate), 'btrystate': str(self.btrystate), 'targetSOC': self.targetSOC, 'currentSOC': self.currentSOC, 'socFailCount': self.socFailCount, 'valueReadFailCount': self.valueReadFailCount, 'operationExceptions': self.operationExceptions}
        return state

    def getTelemetric(self):
        if (self.btrystate == BtryMainSwitchState.on and self.battery != None):
            self.getCurrentTmin(True)
            self.getCurrentTmax(True)
            self.getCurrentCmin(True)
            self.getCurrentCmax(True)
            self.getCurrentMinh(True)
            self.getCurrentMaxh(True)

        if (self.battery != None):
            telemetric={
                'name': str(self.batteryId),
                'tmin': str(self.currentValue.get(self.battery.tmin.__name__)), 
                'tmax': str(self.currentValue.get(self.battery.tmax.__name__)), 
                'cmin': str(self.currentValue.get(self.battery.cmin.__name__)), 
                'cmax': str(self.currentValue.get(self.battery.cmax.__name__)), 
                'minh': str(self.currentValue.get(self.battery.minh.__name__)), 
                'maxh': str(self.currentValue.get(self.battery.maxh.__name__)), 
                'tbal': str(self.currentValue.get(self.battery.tbal.__name__))}
        else:
            telemetric={}

        return telemetric

    def shortInfo(self):
        return f"{self.name} "+("off" if (self.btrystate==BtryMainSwitchState.off) else f"t:{self.targetSOC}, c:{self.currentSOC}")

    def initPin(self):
        self.board.set_pin_mode_digital_output(self.chargerPin)
        self.board.set_pin_mode_digital_output(self.disChargerPin)
        self.board.set_pin_mode_servo(self.mainSwitchServoPin)
        if (self.localMqttClient != None):
            self.localMqttClient.publish(self.localMqttTopicRoot+"/switches/"+self.name, "OFF", qos=1, retain=True)

    def initBoard(self):
        self.board.digital_write(self.chargerPin, 1)
        self.board.digital_write(self.disChargerPin, 1)
        self.board.servo_write(self.mainSwitchServoPin, 0)
        if (self.localMqttClient != None):
            self.localMqttClient.publish(self.localMqttTopicRoot+"/switches/"+self.name, "OFF", qos=1, retain=True)

        self.ctrlstate=CtrlState.off
        self.btrystate=BtryMainSwitchState.off
        self.switchServoPos=0

    def setTargetSoc(self,targetSOC=50):
        self.targetSOC=targetSOC

    def getCurrentTmin(self, refresh=False):
        return self.getValueByName(self.battery.tmin, refresh, float)

    def getCurrentTmax(self, refresh=False):
        return self.getValueByName(self.battery.tmax, refresh, float)

    def getCurrentCmin(self, refresh=False):
        return self.getValueByName(self.battery.cmin, refresh, float)

    def getCurrentCmax(self, refresh=False):
        return self.getValueByName(self.battery.cmax, refresh, float)

    def getCurrentMinh(self, refresh=False):
        return self.getValueByName(self.battery.minh, refresh, float)

    def getCurrentMaxh(self, refresh=False):
        return self.getValueByName(self.battery.maxh, refresh, float)
#
#    def getCurrentSOC(self, refresh=False):
#        return self.getValueByName(self.battery.soc, refresh)

    def getValueByName(self, method, refresh, conversion=None):
        if (refresh and self.mockBattery == False):
            try:
                if (not(method.__name__ in self.valueReadFailCount)):
                    self.valueReadFailCount[method.__name__]=0

                value=method()

                if (conversion != None):
                    self.currentValue[method.__name__]=conversion(value)
                else:
                    self.currentValue[method.__name__]=value

                self.valueReadFailCount[method.__name__]=0
            except IndexError as e:
                self.valueReadFailCount[method.__name__]=self.valueReadFailCount[method.__name__]+1
                logging.warn('%s could not read %s, keeping the previous state %s, failCount %s', self.name,
                        method.__name__, self.currentValue.get(method.__name__), self.valueReadFailCount.get(method.__name__))
                self.storeExceptions(method.__name__, e)
            except Exception as e:
                self.valueReadFailCount[method.__name__]=self.valueReadFailCount[method.__name__]+1
                logging.warn('%s could not read %s, keeping the previous state %s, failCount %s', self.name,
                        method.__name__, self.currentValue.get(method.__name__), self.valueReadFailCount.get(method.__name__))
                self.storeExceptions(method.__name__, e)
        elif (refresh and self.mockBattery == True):
            self.currentValue[method.__name__]=self.currentValue[method.__name__]+1

        return self.currentValue.get(method.__name__)

    def getCurrentSOC(self, refresh=False):
        if (refresh and self.mockBattery == False):
            try:
                self.currentSOC=round(self.battery.soc(), 2)
                self.socFailCount=0
            except IndexError as e:
                logging.info('%s could not read soc, keeping the previous state %s, failCount %s', self.name, self.currentSOC, self.socFailCount)
                self.socFailCount=self.socFailCount+1
                self.storeExceptions('soc', e)
            except Exception as e:
                logging.info('%s could not read soc, keeping the previous state %s, failCount %s', self.name, self.currentSOC, self.socFailCount)
                self.socFailCount=self.socFailCount+1
                self.storeExceptions('soc', e)
        elif (refresh and self.mockBattery == True):
            self.currentSOC=self.currentSOC+1

        return self.currentSOC

    def switchBatteryOn(self):
        if (self.btrystate != BtryMainSwitchState.on):
            self.board.servo_write(self.mainSwitchServoPin, 90)
            if (self.mockBattery == False):
                logging.info('%s opening battery %s with speed %s', self.name, self.usbCtrlCable, self.usbCableSpeed)
                try:
                    self.battery=FES(self.usbCtrlCable, self.usbCableSpeed)
                    self.battery.open()
                    self.batteryId=self.battery.connect()

#                    while (not(self.battery.isConnected())):
#                        self.battery.connect()

                    self.battery.password()
                    self.btrystate=BtryMainSwitchState.on
                except Exception as e:
                    self.btrystate=BtryMainSwitchState.conn_failed
                    logging.error('%s battery switch on failed: %s', self.name, str(e))
                    self.storeExceptions('connect', e)
            else:
                self.btrystate=BtryMainSwitchState.on
            logging.info('%s battery switched on', self.name)
        else:
            logging.warn('%s the battery is in %s state, can not switch on again', self.name, self.btrystate)

    def switchBatteryOff(self):
        if (self.btrystate == BtryMainSwitchState.on):
            self.btrystate=BtryMainSwitchState.off
            self.board.servo_write(self.mainSwitchServoPin, 0)
            logging.info('%s battery switched off', self.name)
        else:
            logging.warn('%s the battery is in %s state, can not switch off again', self.name, self.btrystate)

    def switchOffChargeDisCharge(self):
        if (self.ctrlstate != CtrlState.off):
            self.board.digital_write(self.chargerPin, 1)
            self.board.digital_write(self.disChargerPin, 1)
            if (self.localMqttClient != None):
                self.localMqttClient.publish(self.localMqttTopicRoot+"/switches/"+self.name+'/cmnd/POWER', "OFF", qos=1, retain=True)
            self.ctrlstate = CtrlState.off
            logging.info('%s controller switched off', self.name)
        else:
            logging.warn('%s the controller is in %s state, please switch on it before', self.name, self.ctrlstate)

    def shutdown(self):
        self.switchOffChargeDisCharge()
        self.switchBatteryOff()

    def charge(self):
        self.switchBatteryOn()
        if (self.btrystate != BtryMainSwitchState.on):
            logging.warn('%s the battery is in %s state, please switch on it before', self.name, self.btrystate)
            return

        if (self.ctrlstate == CtrlState.off):
            self.board.digital_write(self.chargerPin, 0)
            if (self.localMqttClient != None):
                self.localMqttClient.publish(self.localMqttTopicRoot+"/switches/"+self.name+'/cmnd/POWER', "ON", qos=1, retain=True)
            self.ctrlstate = CtrlState.charging
            logging.info('%s charging', self.name)
        else:
            logging.warn('%s the controller is in %s state, please switch off it before', self.name, self.ctrlstate)

    def disCharge(self):
        self.switchBatteryOn()
        if (self.btrystate != BtryMainSwitchState.on):
            logging.warn('%s the battery is in %s state, please switch on it before', self.name, self.btrystate)
            return

        if (self.ctrlstate == CtrlState.off):
            self.board.digital_write(self.disChargerPin, 0)
            if (self.localMqttClient != None):
                self.localMqttClient.publish(self.localMqttTopicRoot+"/switches/"+self.name, "ON", qos=1, retain=True)
            self.ctrlstate = CtrlState.discharging
            logging.info('%s discharging', self.name)
        else:
            logging.warn('%s the controller is in %s state, please switch off it before', self.name, self.ctrlstate)

    def doManagement(self):
        if (self.btrystate != BtryMainSwitchState.on):
            #            logging.debug('%s the battery is in %s state, please switch on it before', self.name, self.btrystate)
            return False

        if (self.ctrlstate == CtrlState.off):
            #            logging.debug('%s the controller is in %s state, please switch off it before', self.name, self.ctrlstate)
            return False
        
        #get current SOC
        self.getCurrentSOC(True)

        if (self.ctrlstate == CtrlState.charging and self.currentSOC >= self.targetSOC):
            logging.info('%s target SOC %s reached, curr: %s during %s', self.name, self.targetSOC, self.currentSOC, self.ctrlstate)
            self.switchOffChargeDisCharge()
            return True
        elif (self.ctrlstate == CtrlState.discharging and self.currentSOC <= self.targetSOC):
            logging.info('%s target SOC %s reached, curr: %s during %s', self.name, self.targetSOC, self.currentSOC, self.ctrlstate)
            self.switchOffChargeDisCharge()
            return True
        else:
            logging.info('%s target SOC %s not reached, curr: %s during %s', self.name, self.targetSOC, self.currentSOC, self.ctrlstate)
        return False

    def storeExceptions(self, operation, e):
        if (not(operation in self.operationExceptions)):
            self.operationExceptions[operation]=[]
        self.operationExceptions[operation].append(str(e))


#    def doStateCheck(self):
        


