# fes-battery-control
Battery Controller for FES

## Environment Setup
Install
- VirtualBox: https://www.virtualbox.org/wiki/Downloads
- LinuxMint: https://www.linuxmint.com/download.php

Clone Git Repo
- ```git clone https://github.com/esanya/fes-battery-control.git```

Setup Python VEenv
- ```python3 -mvenv fes-battery-control``` (the same folder as the checked out repository)

Install Dependencies
- ```./bin/pip3 install crccheck```
- ```./bin/pip3 install telemetrix```

## Start the SW without HW
- ```socat -d -d pty,raw,echo=0 tcp-listen:8083```
- ```./bin/python3 ./dummybattery.py -p 8083 -lo=25```
- ```socat -d -d pty,raw,echo=0 tcp-listen:8084```
- ```./bin/python3 ./dummybattery.py -p 8084 -lo=25```
- ```mkfifo /tmp/bttrymngr_ctrl.fifo```
- ```./bin/python3 ./battery_ctrl.py -mt True -bu1 /dev/pts/X -bu2 /dev/pts/Y``` (/dev/pts/X,Y from the socat command output)

Read the logs
- ```tail -f /tmp/bttrymngr_report.log```

Controll the SW
- ```echo "bat=all target_soc=70" > /tmp/bttrymngr_ctrl.fifo```
- ```echo "bat=all charge" > /tmp/bttrymngr_ctrl.fifo```
- ```echo "bat=all shutdown" > /tmp/bttrymngr_ctrl.fifo```
- ```echo "bat=all target_soc=60" > /tmp/bttrymngr_ctrl.fifo```
- ```echo "bat=all discharge" > /tmp/bttrymngr_ctrl.fifo```
- ```echo "bat=all shutdown" > /tmp/bttrymngr_ctrl.fifo```




