#!/usr/bin/python2
import RPi.GPIO as GPIO
from time import sleep
import datetime
import sys
import dhtreader
import os
import os.path
from pywapi import get_weather_from_noaa
import threading

def outdoor():
    try:
        w=get_weather_from_noaa('KCLL')
        t=round(float(w[u'temp_f']),1)
        h=round(float(w[u'relative_humidity']),1)
        return t, h
    except:
        return 0, 0

class relay:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)

        self.mode="cool"

        self.Cool_Pin=17
        self.Heat_Pin=18
        self.Fan_Pin=27

        GPIO.setup(self.Cool_Pin, GPIO.OUT)
        GPIO.setup(self.Heat_Pin, GPIO.OUT)
        GPIO.setup(self.Fan_Pin, GPIO.OUT)
        self.run="off"

    def cool(self):
        GPIO.output(self.Heat_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Cool_Pin, GPIO.LOW) #On
        self.run="cool"

    def heat(self):
        GPIO.output(self.Cool_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Heat_Pin, GPIO.LOW) #On
        self.run="heat"

    def fan(self):
        GPIO.output(self.Cool_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Heat_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.LOW) #On
        self.run="fan"

    def off(self):
        GPIO.output(self.Cool_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Heat_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.HIGH) #Off
        self.run="off"

    def __del__(self):
        self.off()
        GPIO.cleanup()

class DHT(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        dhtreader.init()
        self.dev_type = int(22)
        self.dhtpin = int(4)
        self.loop=True
        self.t=0
        self.h=0
        self.THI=0

    def read(self):
        return self.t, self.h, self.THI

    def run(self):
        while(self.loop):
            while(self.loop):
                try:
                    t, h = dhtreader.read(self.dev_type, self.dhtpin)
                    break
                except TypeError:
                    sleep(3)
            self.t=round(t*9/5+32,1)
            self.h=round(h,1)
            self.THI=round(t-0.55*(1-h/100)*(t-58),1)
            sleep(60)

    def __del__(self):
        self.loop=False

class temp(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.relay=relay()
        self.sensor=DHT()
        self.sensor.start()
        sleep(1)
        self.active_hist=1
        self.inactive_hist=5
        self.set_temp=70
        self.set_away_temp=75
        self.set_away="off"#auto
        self.active="manual"
        self.state="home"
        self.mode="off"
        self.loop=True
        self.log_int=15
        self.run_int=15
        self.hostname = ["192.168.1.27", "192.168.1.3"]
        self.T=0
        self.RH=0
        self.THI=0
        self.RHout=0
        self.Tout=0

    def run(self):
        while(self.loop):
            run_time=datetime.datetime.now()
            self.read_cpu_temp()
            self.T, self.RH, self.THI=self.sensor.read()
            self.Tout, self.RHout=outdoor()
            if self.active=="auto":
                self.home()
            if self.state=="home":
                self.hist=self.active_hist
                self.desired_temp=self.set_temp
            elif self.state=="away":
                self.hist=self.inactive_hist
                self.desired_temp=self.set_away_temp
            else:
                sys.exit("self.state broke")

            if self.mode=="cool":
                if self.THI > self.desired_temp + self.hist and self.relay.run != "cool":
                    self.relay.cool()
                    run_time=datetime.datetime.now()
                elif self.THI < self.desired_temp and datetime.datetime.now()-run_time>=datetime.timedelta(minutes=self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
            elif self.mode=="heat":
                if self.THI < heat_set - self.hist and self.relay.run != "heat":
                    self.relay.heat()
                    run_time=datetime.datetime.now()
                elif self.THI > heat_set and self.relay.run != "off" and datetime.datetime.now()-run_time>=datetime.timedelta(minutes=self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
            elif self.mode=="off" and self.relay.run != "off":
                self.relay.off()
            elif self.mode=="fan" and self.relay.run != "fan":
                self.relay.fan()
            self.log()
            sleep(1)
        del self.relay
        del self.sensor
        print "Exit"
        sys.exit(0)

    def stop(self):
        self.loop=False

    def log(self):
        self.log_time=datetime.datetime.now()
        if not os.path.isfile('./therm.log'): 
            log_text='T,RH,THI'
            log_text+=',hist'
            log_text+=',desired_temp'
            log_text+=',state'
            log_text+=',mode'
            log_text+='\n'
            log_text+=str(self.T)+','+str(self.RH)+','+str(self.THI)
            log_text+=','+str(self.hist)
            log_text+=','+str(self.desired_temp)
            log_text+=','+str(self.state)
            log_text+=','+str(self.mode)
            log_text+='\n'
            self.log_file=open('./therm.log','w')
            self.log_file.write(log_text)
 
        elif (datetime.datetime.now()-self.log_time>=datetime.timedelta(minutes=self.log_int)):
            log_text=str(self.T)+','+str(self.RH)+','+str(self.THI)
            log_text+=','+str(self.hist)
            log_text+=','+str(self.desired_temp)
            log_text+=','+str(self.state)
            log_text+=','+str(self.mode)
            log_text+='\n'
            self.log_time=datetime.datetime.now()
            self.log_file.write(log_text)

    def home(self):
        self.state="away"
        for h in self.hostname:
                response = os.system("ping -c 1 " + h)
                if response == 0:
                        self.state="here"
                        break

    def wait(self, time):
        for i in range(time):
            sleep(1)
            if not self.loop:
                del self.relay
                del self.sensor
                sys.exit(0)

    def read_cpu_temp(self):
        temp_file=open('/sys/class/thermal/thermal_zone0/temp','r')
        self.cpu_temp=int(temp_file.read())*9/5000+32
        temp_file.close()
        if self.cpu_temp>130:
            print "I'm burning up"
