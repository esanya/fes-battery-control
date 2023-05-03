from enum import Enum
from telemetrix import telemetrix
from fes import FES
import logging

CtrlState = Enum('CtrlState', 'off statecheck charging discharging ')
BtryMainSwitchState = Enum('BtryMainSwitchState', 'off on')

#off:           the battery controller is switched off
#statecheck:    
#charging       
#discharging    

diffEpsSOC=1

class BatteryControl(object):
    def __init__(self, name, board, chargerPin, disChargerPin, mainSwitchServoPin, usbCtrlCable, usbCableSpeed, mockBattery=False):
        self.name=name
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
        self.mockBattery=mockBattery
        self.usbCtrlCable=usbCtrlCable
        self.usbCableSpeed=usbCableSpeed
#        sel

        self.board=board
        self.battery=None
        self.initPin()
        self.initBoard()


    def __repr__(self):
        return f"BatteryControl: name: {self.name}, ctrlstate: {self.ctrlstate}, btrystate: {self.btrystate}, targetSOC: {self.targetSOC}, currentSOC: {self.currentSOC}"

    def getState(self):
        state={'ctrlstate': str(self.ctrlstate), 'btrystate': str(self.btrystate), 'targetSOC': self.targetSOC, 'currentSOC': self.currentSOC, 'socFailCount': self.socFailCount}
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

    def initBoard(self):
        self.board.digital_write(self.chargerPin, 1)
        self.board.digital_write(self.disChargerPin, 1)
        self.board.servo_write(self.mainSwitchServoPin, 0)

        self.ctrlstate=CtrlState.off
        self.btrystate=BtryMainSwitchState.off
        self.switchServoPos=0

    def setTargetSoc(self,targetSOC=50):
        self.targetSOC=targetSOC

    def getCurrentTmin(self, refresh=False):
        return self.getValueByName(self.battery.tmin, refresh)

    def getCurrentTmax(self, refresh=False):
        return self.getValueByName(self.battery.tmax, refresh)

    def getCurrentCmin(self, refresh=False):
        return self.getValueByName(self.battery.cmin, refresh)

    def getCurrentCmax(self, refresh=False):
        return self.getValueByName(self.battery.cmax, refresh)

    def getCurrentMinh(self, refresh=False):
        return self.getValueByName(self.battery.minh, refresh)

    def getCurrentMaxh(self, refresh=False):
        return self.getValueByName(self.battery.maxh, refresh)

    def getValueByName(self, method, refresh):
        if (refresh and self.mockBattery == False):
            try:
                self.currentValue[method.__name__]=method()
                self.valueReadFailCount[method.__name__]=0
            except IndexError:
                logging.info('could not read %s, keeping the previous state %s, failCount %s', 
                        method.__name__, self.currentValue[method.__name__], self.self.valueReadFailCount[method.__name__])
                self.valueReadFailCount[method.__name__]=self.valueReadFailCount[method.__name__]+1
            except Exception:
                logging.info('could not read %s, keeping the previous state %s, failCount %s', 
                        method.__name__, self.currentValue[method.__name__], self.self.valueReadFailCount[method.__name__])
                self.valueReadFailCount[method.__name__]=self.valueReadFailCount[method.__name__]+1
        elif (refresh and self.mockBattery == True):
            self.currentValue[method.__name__]=self.currentValue[method.__name__]+1

        return self.currentValue.get(method.__name__)

    def getCurrentSOC(self, refresh=False):
        if (refresh and self.mockBattery == False):
            try:
                self.currentSOC=self.battery.soc()
                self.socFailCount=0
            except IndexError:
                logging.info('could not read soc, keeping the previous state %s, failCount %s', self.currentSOC, self.socFailCount)
                self.socFailCount=self.socFailCount+1
            except Exception:
                logging.info('could not read soc, keeping the previous state %s, failCount %s', self.currentSOC, self.socFailCount)
                self.socFailCount=self.socFailCount+1
        elif (refresh and self.mockBattery == True):
            self.currentSOC=self.currentSOC+1

        return self.currentSOC

    def switchBatteryOn(self):
        if (self.btrystate == BtryMainSwitchState.off):
            self.btrystate=BtryMainSwitchState.on
            self.board.servo_write(self.mainSwitchServoPin, 90)
            if (self.mockBattery == False):
                logging.info('opening battery %s with speed %s', self.usbCtrlCable, self.usbCableSpeed)
                self.battery=FES(self.usbCtrlCable, self.usbCableSpeed)
                self.battery.open()
                self.battery.connect()

                while (not(self.battery.isConnected())):
                    self.battery.connect()

                self.battery.password()
            logging.info('battery switched on')
        else:
            logging.warn('the battery is in %s state, can not switch on again', self.btrystate)

    def switchBatteryOff(self):
        if (self.btrystate == BtryMainSwitchState.on):
            self.btrystate=BtryMainSwitchState.off
            self.board.servo_write(self.mainSwitchServoPin, 0)
            logging.info('battery switched off')
        else:
            logging.warn('the battery is in %s state, can not switch off again', self.btrystate)

    def switchOffChargeDisCharge(self):
        if (self.ctrlstate != CtrlState.off):
            self.board.digital_write(self.chargerPin, 1)
            self.board.digital_write(self.disChargerPin, 1)
            self.ctrlstate = CtrlState.off
            logging.info('controller switched off')
        else:
            logging.warn('the controller is in %s state, please switch on it before', self.ctrlstate)

    def shutdown(self):
        self.switchOffChargeDisCharge()
        self.switchBatteryOff()

    def charge(self):
        self.switchBatteryOn()
        if (self.ctrlstate == CtrlState.off):
            self.board.digital_write(self.chargerPin, 0)
            self.ctrlstate = CtrlState.charging
            logging.info('charging')
        else:
            logging.warn('the controller is in %s state, please switch off it before', self.ctrlstate)

    def disCharge(self):
        self.switchBatteryOn()
        if (self.ctrlstate == CtrlState.off):
            self.board.digital_write(self.disChargerPin, 0)
            self.ctrlstate = CtrlState.discharging
            logging.info('discharging')
        else:
            logging.warn('the controller is in %s state, please switch off it before', self.ctrlstate)

    def doManagement(self):
        if (self.ctrlstate == CtrlState.off):
            return
        
        #get current SOC
        self.getCurrentSOC(True)

        if (self.ctrlstate == CtrlState.charging and self.currentSOC >= self.targetSOC):
            logging.info('target SOC %s reached %s', self.targetSOC, self.currentSOC)
            self.switchOffChargeDisCharge()
        elif (self.ctrlstate == CtrlState.discharging and self.currentSOC <= self.targetSOC):
            logging.info('target SOC %s reached %s', self.targetSOC, self.currentSOC)
            self.switchOffChargeDisCharge()
        else:
            logging.debug('target SOC %s not reached %s', self.targetSOC, self.currentSOC)



#    def doStateCheck(self):
        


