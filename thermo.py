#!/usr/bin/python2
import RPi.GPIO as GPIO
from time import sleep
import datetime
import sys
import dhtreader
import os
import os.path
import pywapi
import threading

def outdoor():
    try:
        w=pywapi.get_weather_from_noaa('KCLL')
        t=round(float(w[u'temp_f']),1)
        h=round(float(w[u'relative_humidity']),1)
        return t, h
    except:
        try:
            w=pyapi.get_weather_from_weather_com('')
            t=round(float(w[u'current_conditions'][u'temperature']),1)
            h=round(float(w[u'current_conditions'][u'humidity']),1)
            return t, h
        except:
            try:
                w=pyapi.get_weather_from_yahoo('')
                t=round(float(w[u'condition'][u'temp']),1)
                h=round(float(w[u'atmosphere'][u'humidity']),1)
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
        self.Garage_Pin=22

        GPIO.setup(self.Cool_Pin, GPIO.OUT)
        GPIO.setup(self.Heat_Pin, GPIO.OUT)
        GPIO.setup(self.Fan_Pin, GPIO.OUT)
        GPIO.setup(self.Garage_Pin, GPIO.OUT)
        GPIO.output(self.Garage_Pin, GPIO.HIGH) #Off
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
        print "GPIO clean"

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
                    self.wait(5)
            self.t=round(t*9/5+32,1)
            self.h=round(h,1)
            #self.THI=round(t-0.55*(1-h/100)*(t-58),1)
            self.THI=self.t
            self.wait(60)
        print "Sensor died"

    def wait(self, time):
        for i in range(time):
            sleep(1)
            if self.loop == False:
                break

    def __del__(self):
        self.loop=False
        sleep(2)

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
        self.log_time=datetime.datetime.now()-datetime.timedelta(minutes=self.log_int)
        self.run_int=1#5
        self.run_time=datetime.datetime.now()-datetime.timedelta(minutes=self.run_int)
        self.hostname = ["192.168.1.27", "192.168.1.3"]
        self.T=0
        self.RH=0
        self.THI=0
        self.RHout=0
        self.Tout=0

    def garage(self):
        GPIO.output(self.Garage_Pin, GPIO.LOW)
        sleep(1)
        GPIO.output(self.Garage_Pin, GPIO.HIGH)


    def run(self):
        while(self.loop):
            self.read_cpu_temp()
            self.T, self.RH, self.THI=self.sensor.read()
            if datetime.datetime.now()-self.run_time>=datetime.timedelta(minutes=self.run_int):
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
                    self.run_time=datetime.datetime.now()
                    self.log()
                elif self.THI < self.desired_temp and self.relay.run == "cool" and datetime.datetime.now()-self.run_time>=datetime.timedelta(minutes=self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
                    self.log()
            elif self.mode=="heat":
                if self.THI < self.desired_temp - self.hist and self.relay.run != "heat":
                    self.relay.heat()
                    self.run_time=datetime.datetime.now()
                    self.log()
                elif self.THI > self.desired_temp and self.relay.run == "heat" and datetime.datetime.now()-self.run_time>=datetime.timedelta(minutes=self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
                    self.log()
            elif self.mode=="off" and self.relay.run != "off":
                self.relay.off()
            elif self.mode=="fan" and self.relay.run != "fan":
                self.relay.fan()
            if (datetime.datetime.now()-self.log_time>=datetime.timedelta(minutes=self.log_int)):
                self.log()
            sleep(1)
        del self.relay
        del self.sensor
        sleep(1)
        print "Exit"
        #sys.exit(0)

    def stop(self):
        self.loop=False

    def __del__(self):
        self.loop=False

    def log(self):
            
        if not os.path.isfile('./therm.log'): 
            log_text='Time,'
            log_text+='T,RH,THI'
            log_text+=',hist'
            log_text+=',desired_temp'
            log_text+=',state'
            log_text+=',mode'
            log_text+=',relay'
            log_text+='\n'
            log_text+=str(datetime.datetime.now())+','
            log_text+=str(self.T)+','+str(self.RH)+','+str(self.THI)
            log_text+=','+str(self.hist)
            log_text+=','+str(self.desired_temp)
            log_text+=','+str(self.state)
            log_text+=','+str(self.mode)
            log_text+=','+str(self.relay.run)
            log_text+='\n'
            self.log_time=datetime.datetime.now()
            log_file=open('./therm.log','w')
            log_file.write(log_text)
            log_file.close()

 
        else:
            log_text=str(datetime.datetime.now())+','
            log_text+=str(self.T)+','+str(self.RH)+','+str(self.THI)
            log_text+=','+str(self.hist)
            log_text+=','+str(self.desired_temp)
            log_text+=','+str(self.state)
            log_text+=','+str(self.mode)
            log_text+=','+str(self.relay.run)
            log_text+='\n'
            self.log_time=datetime.datetime.now()
            log_file=open('./therm.log','a')
            log_file.write(log_text)
            log_file.close()

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
