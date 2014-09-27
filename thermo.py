#!/usr/bin/python2
import RPi.GPIO as GPIO
from time import sleep
from lockfile import FileLock
import datetime, sys, os, signal, pickle, threading, pywapi, os.path, pywapi, dhtreader, ConfigParser

Config = ConfigParser.ConfigParser()
Config.read('config.ini')
ZIP=Config.get('thermo', 'ZIP')
NOAA=Config.get('thermo','NOAA')
directory=Config.get('thermo', 'directory')
log=Config.get('thermo', 'log')
Cool_Pin=int(Config.get('thermo', 'Cool_Pin'))
Heat_Pin=int(Config.get('thermo', 'Heat_Pin'))
Fan_Pin=int(Config.get('thermo', 'Fan_Pin'))
Garage_Pin=int(Config.get('thermo', 'Garage_Pin'))


Stop=False
def sig_handler(signum, frame):
    global Stop
    Stop=True

signal.signal(signal.SIGTERM, sig_handler)
signal.signal(signal.SIGINT, sig_handler)

def outdoor():
    global NOAA
    global ZIP
    try:
        w=pywapi.get_weather_from_noaa(NOAA)
        t=round(float(w[u'temp_f']),1)
        h=round(float(w[u'relative_humidity']),1)
        return t, h
    except:
        try:
            w=pywapi.get_weather_from_weather_com(ZIP)
            t=round(float(w[u'current_conditions'][u'temperature']),1)
            h=round(float(w[u'current_conditions'][u'humidity']),1)
            return t, h
        except:
            try:
                w=pywapi.get_weather_from_yahoo(ZIP)
                t=round(float(w[u'condition'][u'temp']),1)
                h=round(float(w[u'atmosphere'][u'humidity']),1)
                return t, h
            except:
                return 0, 0

class relay:
    def __init__(self):
        global Cool_Pin
        global Heat_Pin
        global Fan_Pin
        GPIO.setmode(GPIO.BCM)

        self.mode="cool"

        self.Cool_Pin=Cool_Pin
        self.Heat_Pin=Heat_Pin
        self.Fan_Pin=Fan_Pin
        self.Garage_Pin=Garage_Pin

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
        t=0
        h=0
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

    def stop(self):
        self.loop=False

    def __del__(self):
        self.loop=False

class thermo:
    def __init__(self):
        self.active_hist=1
        self.inactive_hist=5
        self.set_temp=70
        self.set_away_temp=75
        self.set_away="off"
        self.active="manual"
        self.state="home"
        self.mode="off"
        self.T=0
        self.RH=0
        self.THI=0
        self.RHout=0
        self.Tout=0
        self.run="off"
        self.cpu_temp=0

class temp(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.relay=relay()
        self.sensor=DHT()
        self.sensor.start()
        self.thermo=thermo()
        self.loop=True
        self.log_int=15
        self.log_time=datetime.datetime.now()-datetime.timedelta(minutes=self.log_int)
        self.run_int=15
        self.run_time=datetime.datetime.now()-datetime.timedelta(minutes=self.run_int)
        self.hostname = ["192.168.1.27", "192.168.1.3"]
        
        global directory
        #self.directory="/tmp/thermo"
        self.directory=directory
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

    def garage(self):
        GPIO.output(self.Garage_Pin, GPIO.LOW)
        sleep(1)
        GPIO.output(self.Garage_Pin, GPIO.HIGH)


    def run(self):
        while(self.loop):
            file_view=self.directory+"/view.obj"
            if os.path.isfile(file_view):
                with FileLock(file_view):
                    file=open(file_view, 'rb')
                    self.views=pickle.load(file)
                    file.close()
                    self.thermo.mode=self.views.mode
                    self.thermo.set_temp=self.views.set_temp
                    self.thermo.state=self.views.state
                    self.thermo.set_away_temp=self.views.set_away_temp
                    self.thermo.set_away=self.views.set_away
            self.thermo.run=self.relay.run
            file_thermo=self.directory+"/thermo.obj"
            self.read_cpu_temp()
            self.thermo.cpu_temp=self.cpu_temp
            self.thermo.T, self.thermo.RH, self.thermo.THI=self.sensor.read()
            if datetime.datetime.now()-self.run_time>=datetime.timedelta(minutes=self.run_int):
                self.thermo.Tout, self.thermo.RHout=outdoor()
            with FileLock(file_thermo):
                file=open(file_thermo, 'wb')
                pickle.dump(self.thermo, file)
                file.close()
            if self.thermo.active=="auto":
                self.home()

            if self.thermo.state=="here" or self.thermo.state=="home":
                self.hist=self.thermo.active_hist
                self.desired_temp=self.thermo.set_temp
            elif self.thermo.state=="away":
                self.hist=self.thermo.inactive_hist
                self.desired_temp=self.thermo.set_away_temp
            else:
                print "State broke"

            if self.thermo.mode=="cool":
                if self.thermo.THI > self.desired_temp + self.hist and self.relay.run != "cool":
                    self.relay.cool()
                    self.run_time=datetime.datetime.now()
                    self.log()
                elif self.thermo.THI < self.desired_temp and self.relay.run == "cool" and datetime.datetime.now()-self.run_time>=datetime.timedelta(minutes=self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
                    self.log()
            elif self.thermo.mode=="heat":
                if self.thermo.THI < self.desired_temp - self.hist and self.relay.run != "heat":
                    self.relay.heat()
                    self.run_time=datetime.datetime.now()
                    self.log()
                elif self.thermo.THI > self.desired_temp and self.relay.run == "heat" and datetime.datetime.now()-self.run_time>=datetime.timedelta(minutes=self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
                    self.log()
            elif self.thermo.mode=="off" and self.relay.run != "off":
                self.relay.off()
            elif self.thermo.mode=="fan" and self.relay.run != "fan":
                self.relay.fan()
            if (datetime.datetime.now()-self.log_time>=datetime.timedelta(minutes=self.log_int)):
                self.log()
            if self.loop:
                sleep(.5)
        del self.relay
        self.sensor.stop()
        self.sensor.join()

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
            log_text+=str(self.thermo.T)+','+str(self.thermo.RH)+','+str(self.thermo.THI)
            log_text+=','+str(self.hist)
            log_text+=','+str(self.desired_temp)
            log_text+=','+str(self.thermo.state)
            log_text+=','+str(self.thermo.mode)
            log_text+=','+str(self.relay.run)
            log_text+='\n'
            self.log_time=datetime.datetime.now()
            log_file=open('./therm.log','w')
            log_file.write(log_text)
            log_file.close()

 
        else:
            log_text=str(datetime.datetime.now())+','
            log_text+=str(self.thermo.T)+','+str(self.thermo.RH)+','+str(self.thermo.THI)
            log_text+=','+str(self.hist)
            log_text+=','+str(self.desired_temp)
            log_text+=','+str(self.thermo.state)
            log_text+=','+str(self.thermo.mode)
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

    def read_cpu_temp(self):
        temp_file=open('/sys/class/thermal/thermal_zone0/temp','r')
        self.cpu_temp=int(temp_file.read())*9/5000+32
        temp_file.close()
        if self.cpu_temp>130:
            print "I'm burning up"

def main():
    print "PID: "+str(os.getpid())
    t=temp()
    t.start()
    while True:
        sleep(1)
        if Stop:
            print "Interrupt Please wait for program to exit cleanly"
            t.stop()
            t.join()
            break
        if not t.isAlive():
            print "The thread is Dead"
    sys.exit(0)

if __name__=="__main__":
    main()
