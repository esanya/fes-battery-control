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
        self.mockBattery=mockBattery
        self.usbCtrlCable=usbCtrlCable
        self.usbCableSpeed=usbCableSpeed
#        sel

        self.board=board
        self.initPin()
        self.initBoard()


    def __repr__(self):
        return f"BatteryControl: name: {self.name}, ctrlstate: {self.ctrlstate}, btrystate: {self.btrystate}, targetSOC: {self.targetSOC}, currentSOC: {self.currentSOC}"

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
        


