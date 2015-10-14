#!/usr/bin/python2
import RPi.GPIO as GPIO
import cPickle as pickle
from time import sleep
from datetime import datetime, timedelta
import sys, os, signal, threading, os.path, pywapi, redis, picamera, numpy, Adafruit_DHT, ConfigParser
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

Config = ConfigParser.ConfigParser()
Config.read('/root/thermostat/config.ini')
ZIP = Config.get('thermo', 'ZIP')
NOAA = Config.get('thermo','NOAA')
directory = Config.get('thermo', 'directory')
directory = "/tmp/thermo"
log = Config.get('thermo', 'log')
Cool_Pin = int(Config.get('thermo', 'Cool_Pin'))
Heat_Pin = int(Config.get('thermo', 'Heat_Pin'))
Fan_Pin = int(Config.get('thermo', 'Fan_Pin'))
Garage_Pin = int(Config.get('thermo', 'Garage_Pin'))

Stop = False

Debug = False

def sig_handler(signum, frame):
    global Stop
    Stop = True

signal.signal(signal.SIGTERM, sig_handler)
signal.signal(signal.SIGINT, sig_handler)

def outdoor():
    global NOAA
    global ZIP
    try:
        w = pywapi.get_weather_from_noaa(NOAA)
        t = round(float(w[u'temp_f']), 1)
        h = round(float(w[u'relative_humidity']), 1)
        return t, h
    except:
        try:
            w = pywapi.get_weather_from_weather_com(ZIP)
            t = round(float(w[u'current_conditions'][u'temperature']), 1)
            h = round(float(w[u'current_conditions'][u'humidity']), 1)
            return t, h
        except:
            try:
                w = pywapi.get_weather_from_yahoo(ZIP)
                t = round(float(w[u'condition'][u'temp']), 1)
                h = round(float(w[u'atmosphere'][u'humidity']), 1)
                return t, h
            except:
                return 0, 0

class relay:
    def __init__(self):
        global Cool_Pin
        global Heat_Pin
        global Fan_Pin
        GPIO.setmode(GPIO.BCM)

        self.mode = "cool"

        self.Cool_Pin = Cool_Pin
        self.Heat_Pin = Heat_Pin
        self.Fan_Pin = Fan_Pin
        self.Garage_Pin = Garage_Pin

        GPIO.setup(self.Cool_Pin, GPIO.OUT)
        GPIO.setup(self.Heat_Pin, GPIO.OUT)
        GPIO.setup(self.Fan_Pin, GPIO.OUT)
        self.off()
        GPIO.setup(self.Garage_Pin, GPIO.OUT)
        GPIO.output(self.Garage_Pin, GPIO.HIGH) #Off
        self.run = "off"

    def garage(self):
        GPIO.output(self.Garage_Pin, GPIO.LOW)
        sleep(0.5)
        GPIO.output(self.Garage_Pin, GPIO.HIGH)

    def cool(self):
        GPIO.output(self.Heat_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Cool_Pin, GPIO.LOW) #On
        self.run = "cool"

    def heat(self):
        GPIO.output(self.Cool_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Heat_Pin, GPIO.LOW) #On
        self.run = "heat"

    def fan(self):
        GPIO.output(self.Cool_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Heat_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.LOW) #On
        self.run = "fan"

    def off(self):
        GPIO.output(self.Cool_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Heat_Pin, GPIO.HIGH) #Off
        GPIO.output(self.Fan_Pin, GPIO.HIGH) #Off
        self.run = "off"

    def __del__(self):
        self.off()
        GPIO.cleanup()
        print "GPIO clean"

class thermo:
    def __init__(self):
        self.active_hist = 1
        self.inactive_hist = 5
        self.set_temp = 70
        self.set_away_temp = 75
        self.set_away = "off"
        self.active = "manual"
        self.state = "home"
        self.mode = "off"
        self.T = 0
        self.RH = 0
        self.THI = 0
        self.RHout = 0
        self.Tout = 0
        self.run = "off"
        self.cpu_temp = 0

class temp(threading.Thread):
    def __init__(self):
        pid=str(os.getpid())
        print "PID: " + pid
        with open("/var/run/thermo.pid", "w") as f:
            f.write(pid)
        global Debug
        threading.Thread.__init__(self)
        self.relay = relay()
        self.thermo = thermo()
        self.loop = True
        self.log_int = 15
        self.log_time = datetime.now() - timedelta(minutes = self.log_int)
        self.run_int = 15
        self.run_time = datetime.now() - timedelta(minutes = self.run_int)
        self.pic_int = 3
        self.pic_time = datetime.now() - timedelta(minutes = self.pic_int)
        self.sensor_int = 5
        self.sensor_time = datetime.now() - timedelta(minutes = self.sensor_int)
        self.hostname = ["192.168.1.27", "192.168.1.3"]
        if Debug:
            print "Connecting to Redis"
        self.red = redis.Redis(unix_socket_path = '/var/run/redis/redis.sock')
        self.pipe = self.red.pipeline(transaction = False)
        folder = "/tmp/thermo"
        if not os.path.exists(folder):
            os.makedirs(folder)
        #self.pipe.set('set_away_temp', self.thermo.set_away_temp)
        #self.pipe.set('set_temp', self.thermo.set_temp)
        #self.pipe.execute()
        self.dev_type = Adafruit_DHT.DHT22
        self.dhtpin = int(4)
        self.log_list=[]

        self.snooze=0.3

    def run(self):
        global Debug
        while(self.loop):
            if Debug:
                print "Starting Loop"
            self.pipe.get('mode')
            self.pipe.get('set_temp')
            self.pipe.get('state')
            self.pipe.get('set_away_temp')
            self.pipe.get('set_away')
            self.pipe.get('garage')
            self.thermo.mode, self.thermo.set_temp, self.thermo.state, self.thermo.set_away_temp, self.thermo.set_away, self.garage = self.pipe.execute()

            sleep(self.snooze)

            self.garage_action()

            if Debug:
                print "Relay"
            self.thermo.run = self.relay.run

            if (datetime.now() - self.sensor_time >= timedelta(minutes = self.sensor_int)):
                self.read_cpu_temp()
                self.sensor()
            elif (datetime.now() - self.pic_time >= timedelta(minutes = self.pic_int)):
                self.take_pic()
            else:
                sleep(self.snooze)

            if Debug:
                print "Updating Redis"
            self.pipe.set('cpu_temp', self.thermo.cpu_temp)
            self.pipe.set('T', self.thermo.T)
            self.pipe.set('RH', self.thermo.RH)
            self.pipe.set('THI', self.thermo.THI)
            self.pipe.set('Tout', self.thermo.Tout)
            self.pipe.set('RHout', self.thermo.RHout)
            self.pipe.set('run', self.thermo.run)
            self.pipe.execute()

            sleep(self.snooze)

            if Debug:
                print "Home/Away"
            if self.thermo.active == "auto":
                self.home()
            else:
                sleep(self.snooze)

            self.away_home()

            self.HVAC()

            if Debug:
                print "Log Int"
            if (datetime.now() - self.log_time >= timedelta(minutes = self.log_int)):
                self.log()
            else:
                sleep(self.snooze)
        del self.relay

    def garage_action(self):
        if Debug:
            print "Garage: "+self.garage
        if self.garage == "on":
            if Debug:
                print "Opening Garage"
            self.relay.garage()
            self.garage = "off"
            self.red.set('garage', self.garage)
        else:
            sleep(self.snooze)

    def sensor(self):
        if Debug:
            print "Read outdoor"
        self.thermo.Tout, self.thermo.RHout = outdoor()
        if Debug:
            print "Sensor Read"
        RH, T = Adafruit_DHT.read_retry(self.dev_type, self.dhtpin)
        try:
            self.thermo.RH=round(RH, 2)
            self.thermo.T=round(T*9/5+32, 2)
            #self.thermo.THI = round(t-0.55*(1-h/100)*(t-58),1)
            self.thermo.THI = self.thermo.T
            self.sensor_time=datetime.now()
        except:
            print "Reading sensor failed"

    def take_pic(self):
        with picamera.PiCamera() as camera:
            if Debug:
                print "Taking Picture"
            camera.led = False
            camera.start_preview()
            camera.vflip = True
            camera.hflip = True
            sleep(2)
            camera.capture('/tmp/thermo/image.jpg')
            self.pic_time = datetime.now()

    def away_home(self):
        if self.thermo.state == "here" or self.thermo.state == "home":
            self.hist = self.thermo.active_hist
            self.desired_temp = self.thermo.set_temp
        elif self.thermo.state == "away":
            self.hist = self.thermo.inactive_hist
            self.desired_temp = self.thermo.set_away_temp
        else:
            print "State broke"
            self.thermo.state == "away"
            self.hist = self.thermo.inactive_hist
            self.desired_temp = self.thermo.set_away_temp

    def HVAC(self):
        if Debug:
            print "Cool/Heat/Fan"
        if self.thermo.mode == "cool":
            if self.thermo.THI > self.desired_temp + self.hist and self.relay.run != "cool":
                self.relay.cool()
                self.run_time = datetime.now()
                self.log()
            elif self.thermo.THI < self.desired_temp and self.relay.run == "cool" and datetime.now() - self.run_time >= timedelta(minutes = self.run_int):
                self.relay.fan()#spin down
                self.wait(30)
                self.relay.off()
                self.log()
        elif self.thermo.mode == "heat":
            if self.thermo.THI < self.desired_temp - self.hist and self.relay.run != "heat":
                self.relay.heat()
                self.run_time = datetime.now()
                self.log()
            elif self.thermo.THI > self.desired_temp and self.relay.run == "heat" and datetime.now() - self.run_time >= timedelta(minutes = self.run_int):
                self.relay.fan()#spin down
                self.wait(30)
                self.relay.off()
                self.log()
        elif self.thermo.mode == "off" and self.relay.run != "off":
            self.relay.off()
            self.log()
        elif self.thermo.mode == "fan" and self.relay.run != "fan":
            self.relay.fan()
            self.log()
        else:
            sleep(self.snooze)

    def log(self):
        global Debug
        if Debug:
            print "Log"

        print "desired_temp" + str(self.desired_temp)
        self.desired_temp = int(0)
        if len(self.log_list) == 0 and os.path.isfile("/root/.thermo/log.pickle"):
            self.log_list=pickle.load(open("/root/.thermo/log.pickle", "rb"))

        self.log_list.append([datetime.now(), self.thermo.T, self.thermo.RH, self.thermo.Tout, self.thermo.RHout, self.thermo.THI, self.hist, self.desired_temp, self.thermo.state, self.thermo.mode, self.relay.run])

        with open("/root/.thermo/thermo.log", "a") as myfile:
            string=''
            for i in self.log_list[-1]:
                string+=str(i)+'\t'
            string[:-1]
            string+='\n'
            myfile.write(string)

        if len(self.log_list)>60*24/15:
            print self.log_list.pop(0)
        else:
            print "{}/{}".format(len(self.log_list), 60*24/15)

        self.log_time = datetime.now()

        entrys = len(self.log_list)

        Time = numpy.empty(entrys)
        T = numpy.empty(entrys)
        desired_temp = numpy.empty(entrys)
        Tout = numpy.empty(entrys)

        if Debug:
            print "Generate Graph"

        for i, row in enumerate(self.log_list):
           Time[i] = (row[0]-self.log_list[0][0]).total_seconds()/3600
           T[i] = row[1]
           desired_temp[i] = row[2]
           Tout[i] = row[3]

        plt.figure()
        plt.plot(Time, T, Time, desired_temp, Time, Tout)
        plt.title('History')
        plt.xlabel('Time')
        plt.ylabel('Temp (f)')
        plt.savefig('/tmp/thermo/graph.png')
        plt.close()

    def home(self):
        self.state = "away"
        for h in self.hostname:
            response = os.system("ping -c 1 " + h)
            if response == 0:
                self.state = "here"
                break

    def read_cpu_temp(self):
        if Debug:
            print "CPU Temp"

        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as temp_file:
            self.cpu_temp = int(temp_file.read()) * 9 / 5000 + 32
        if self.cpu_temp > 185:
            print "I'm burning up"
        self.thermo.cpu_temp = self.cpu_temp

    def wait(self, time):
        for i in range(time):
            sleep(1)
            if not self.loop:
                del self.relay
                break

    def stop(self):
        self.loop = False

    def __del__(self):
        pickle.dump(self.log_list, open("/root/.thermo/log.pickle", "wb"))
        self.loop = False


def main():
    global Debug
    pid=str(os.getpid())
    print "PID: " + pid
    if Debug:
        print "Debug"
    t = temp()
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
            break
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv)>1:
        if sys.argv[1] == 'Debug':
            Debug = True
    main()
