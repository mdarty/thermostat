#!/usr/bin/python2
import RPi.GPIO as GPIO
from time import sleep
import datetime, sys, os, signal, threading, os.path, pywapi
import Adafruit_DHT
import ConfigParser
import psycopg2
import picamera, numpy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import redis

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
Database = False

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
        sleep(1)
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
        global Debug
        global Database
        threading.Thread.__init__(self)
        self.relay = relay()
        self.thermo = thermo()
        self.loop = True
        self.log_int = 15
        self.log_time = datetime.datetime.now() - datetime.timedelta(minutes = self.log_int)
        self.run_int = 15
        self.run_time = datetime.datetime.now() - datetime.timedelta(minutes = self.run_int)
        self.pic_int = 5
        self.pic_time = datetime.datetime.now() - datetime.timedelta(minutes = self.pic_int)
        self.hostname = ["192.168.1.27", "192.168.1.3"]
        if Debug or Database:
            print "Connecting to Redis"
        self.red = redis.Redis(unix_socket_path = '/var/run/redis/redis.sock')
        self.pipe = self.red.pipeline(transaction = False)
        folder = "/tmp/thermo"
        if not os.path.exists(folder):
            os.makedirs(folder)
        self.pipe.set('set_away_temp', self.thermo.set_away_temp)
        self.pipe.set('set_temp', self.thermo.set_temp)
        self.pipe.execute()
        self.dev_type = Adafruit_DHT.DHT22
        self.dhtpin = int(4)

    def run(self):
        global Debug
        global Database
        while(self.loop):
            if Debug:
                print "Starting Loop"
            self.pipe.get('mode')
            self.pipe.get('set_temp')
            self.pipe.get('state')
            self.pipe.get('set_away_temp')
            self.pipe.get('set_away')
            self.pipe.get('garage')

            self.thermo.mode, self.thermo.set_temp, self.thermo.state, self.thermo.set_away_temp, self.thermo.set_away, garage = self.pipe.execute()

            if Debug:
                print "Garage: "+garage
            if garage == "on":
                if Debug:
                    print "Opening Garage"
                self.relay.garage()
                garage = "off"
                self.red.set('garage', garage)
            else:
                sleep(.5)
            if Debug:
                print "Relay"
            self.thermo.run = self.relay.run
            if Debug:
                print "CPU Temp"
            self.read_cpu_temp()
            self.thermo.cpu_temp = self.cpu_temp
            if Debug:
                print "Sensor Read"
            self.thermo.RH, self.thermo.T = Adafruit_DHT.read_retry(self.dev_type, self.dhtpin)
            #self.THI = round(t-0.55*(1-h/100)*(t-58),1)
            self.thermo.THI = self.thermo.T
            if datetime.datetime.now() - self.run_time >= datetime.timedelta(minutes = self.run_int):
                self.thermo.Tout, self.thermo.RHout = outdoor()
            else:
                sleep(0.5)

            if datetime.datetime.now() - self.pic_time >= datetime.timedelta(minutes = self.pic_int):
                with picamera.PiCamera() as camera:
                    if Debug:
                        print "Taking Picture"
                    camera.led = False
                    camera.start_preview()
                    camera.vflip = True
                    camera.hflip = True
                    sleep(2)
                    camera.capture('/tmp/thermo/image.jpg')
                    self.pic_time = datetime.datetime.now()
            else:
                sleep(0.5)
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

            if Debug:
                print "Home/Away"
            if self.thermo.active == "auto":
                self.home()
            else:
                sleep(0.5)

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

            if Debug:
                print "Cool/Heat/Fan"
            if self.thermo.mode == "cool":
                if self.thermo.THI > self.desired_temp + self.hist and self.relay.run != "cool":
                    self.relay.cool()
                    self.run_time = datetime.datetime.now()
                    self.log()
                elif self.thermo.THI < self.desired_temp and self.relay.run == "cool" and datetime.datetime.now() - self.run_time >= datetime.timedelta(minutes = self.run_int):
                    self.relay.fan()#spin down
                    self.wait(30)
                    self.relay.off()
                    self.log()
            elif self.thermo.mode == "heat":
                if self.thermo.THI < self.desired_temp - self.hist and self.relay.run != "heat":
                    self.relay.heat()
                    self.run_time = datetime.datetime.now()
                    self.log()
                elif self.thermo.THI > self.desired_temp and self.relay.run == "heat" and datetime.datetime.now() - self.run_time >= datetime.timedelta(minutes = self.run_int):
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
                sleep(0.1)
            if Debug:
                print "Log Int"
            if (datetime.datetime.now() - self.log_time >= datetime.timedelta(minutes = self.log_int)):
                self.log()
            else:
                sleep(0.5)
        del self.relay
        self.sensor.stop()
        self.sensor.join()

    def stop(self):
        self.loop = False

    def __del__(self):
        self.loop = False

    def log(self):
        global Debug
        global Database
        if Debug:
            print "Log"
        self.conn = psycopg2.connect("dbname = 'thermo' user = 'thermo' host = 'localhost' password = 'chaaCoh9' options = '-c statement_timeout=1000'")
        self.cur = self.conn.cursor()
        datetime.datetime.now()
        print "desired_temp" + str(self.desired_temp)
        self.desired_temp = int(0)

        self.cur.execute("""INSERT INTO thermo_log (Time, T, RH, Tout, RHout, THI, hist, desired_temp, state, mode, relay) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",(datetime.datetime.now(), self.thermo.T, self.thermo.RH, self.thermo.Tout, self.thermo.RHout, self.thermo.THI, self.hist, self.desired_temp, self.thermo.state, self.thermo.mode, self.relay.run))
        self.conn.commit()

        self.log_time = datetime.datetime.now()

        entrys = 150

        self.cur.execute("""SELECT Time, T, desired_temp, Tout FROM thermo_log WHERE Time >= NOW() - '1 day'::INTERVAL ORDER BY Time LIMIT %s;""", (entrys, ))
        data = self.cur.fetchall()

        entrys = len(data)

        Time = numpy.empty(entrys)
        T = numpy.empty(entrys)
        desired_temp = numpy.empty(entrys)
        Tout = numpy.empty(entrys)

        if Debug:
            print "Generate Graph"

        for i, row in enumerate(data):
           Time[i] = (row[0]-data[0][0]).total_seconds()/3600
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

        self.cur.close()
        self.conn.close()

    def home(self):
        self.state = "away"
        for h in self.hostname:
                response = os.system("ping -c 1 " + h)
                if response == 0:
                        self.state = "here"
                        break

    def wait(self, time):
        for i in range(time):
            sleep(1)
            if not self.loop:
                del self.relay
                del self.sensor
                break

    def read_cpu_temp(self):
        temp_file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        self.cpu_temp = int(temp_file.read()) * 9 / 5000 + 32
        temp_file.close()
        if self.cpu_temp > 185:
            print "I'm burning up"

def main():
    global Debug
    global Database
    print "PID: " + str(os.getpid())
    if Debug:
        print "Debug"
    if Database:
        print "Database"
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
    if sys.argv[1] == 'Debug':
        Debug = True
    if sys.argv[1] == 'Database':
        Database = True
    main()
