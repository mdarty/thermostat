#!/usr/bin/python2
from flask import Flask, render_template, flash, redirect, request, send_file
from flask.ext.wtf import Form
from wtforms import TextField, BooleanField
from wtforms.validators import Required
from flask_wtf.csrf import CsrfProtect
from thermo import temp, thermo
#import cPickle as pickle
import pickle, pprint
import sys, os, ConfigParser
from lockfile import FileLock
#import picamera
#camera = picamera.PiCamera()
#camera.hflip=True
#camera.vflip=True
#camera.resolution = (1024, 768)

Config = ConfigParser.ConfigParser()
Config.read('/root/thermostat/config.ini')
directory=Config.get('thermo', 'directory')
directory="/tmp/thermo"

app=Flask(__name__)
#CsrfProtect(app)
app.config.from_object('config')

class LoginForm(Form):
    openid = TextField('openid', validators = [Required()])
    remember_me = BooleanField('remember_me', default = False)

@app.route('/')
@app.route('/index')
def index():
    global directory
    print directory
    if not os.path.exists(directory):
        os.makedirs(directory)
    file_thermo=directory+"/thermo.obj"
    file_view=directory+"/view.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
            return render_template("index.html", title="Thermostat", mode=thermo.mode, set_temp=thermo.set_temp, state=thermo.state, set_away_temp=thermo.set_away_temp, set_away=thermo.set_away)
    elif os.path.isfile(file_view):
        with FileLock(file_views):
            file=open(file_views, 'rb')
            views=pickle.load(file)
            file.close()
    else:
        views=thermo()
    return render_template("index.html", title="Thermostat", mode=views.mode, set_temp=views.set_temp, state=views.state, set_away_temp=views.set_away_temp, set_away=views.set_away)

@app.route('/index', methods = ['POST'])
def index_post():
    global directory
    #directory="/tmp/thermo"
    file_view=directory+"/view.obj"
    file_thermo=directory+"/thermo.obj"
    file_garage=directory+"/garage"
    print request.form
    if request.form['submit'] == "Garage":
        print "I'm here"
        open(file_garage, 'a').close()
    if not os.path.exists(directory):
        os.makedirs(directory)
    if os.path.isfile(file_view):
        with FileLock(file_view):
            file=open(file_view, 'rb')
            views=pickle.load(file)
            file.close()
    elif os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            views=pickle.load(file)
            file.close()
    else:
        views=thermo()
    views.mode=str(request.form['mode'])
    views.set_temp=float(str(request.form['set_temp']))
    views.state=str(request.form['state'])
    views.set_away_temp=float(str(request.form['set_away_temp']))
    views.set_away=str(request.form['set_away'])
    if not os.path.exists(directory):
        os.makedirs(directory)
    #file_view=directory+"/view.obj"
    #file_view="/tmp/thermostat/view.obj"
    with FileLock(file_view):
        file=open(file_view, 'wb')
        pprint.pprint(views)
        pickle.dump(views, file)
        file.close()
   
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
            return render_template("index.html", title="Thermostat", mode=thermo.mode, set_temp=thermo.set_temp, state=thermo.state, set_away_temp=thermo.set_away_temp, set_away=thermo.set_away)
    return render_template("index.html", title="Thermostat", mode=views.mode, set_temp=views.set_temp, state=views.state, set_away_temp=views.set_away_temp, set_away=views.set_away)

@app.route('/login', methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        flash('Login requested for OpenID="' + form.openid.data + '", remember_me=' + str(form.remember_me.data))
        return redirect('/index')
    return render_template('login.html', 
        title = 'Sign In',
        form = form,
        providers = app.config['OPENID_PROVIDERS'])

@app.route('/get_image')
def get_image():
    os.system('/opt/vc/bin/raspistill -vf -hf -w 800 -h 600 -o /tmp/thermo/image.jpg')
    filename='/tmp/thermo/image.jpg'
    #camera.capture(filename)
    return send_file(filename, mimetype='image/jpg')

@app.route('/run_AC', methods = ['Get'])
def run_AC():
    #directory="/tmp/thermo"
    global directory
    file_thermo=directory+"/thermo.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
    return str(thermo.run)

@app.route('/updatetemp', methods = ['Get'])
def updatetemp():
    #directory="/tmp/thermo"
    global directory
    file_thermo=directory+"/thermo.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
    return str(thermo.T)

@app.route('/updateRH', methods = ['Get'])
def updateRH():
    #directory="/tmp/thermo"
    global directory
    file_thermo=directory+"/thermo.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
    return str(thermo.RH)

@app.route('/updateOuttemp', methods = ['Get'])
def updateOuttemp():
    #directory="/tmp/thermo"
    global directory
    file_thermo=directory+"/thermo.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
    return str(thermo.Tout)

@app.route('/updateOutRH', methods = ['Get'])
def updateOutRH():
    #directory="/tmp/thermo"
    global directory
    file_thermo=directory+"/thermo.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
    return str(thermo.RHout)

@app.route('/cputemp', methods = ['Get'])
def cputemp():
    #directory="/tmp/thermo"
    global directory
    file_thermo=directory+"/thermo.obj"
    if os.path.isfile(file_thermo):
        with FileLock(file_thermo):
            file=open(file_thermo, 'rb')
            thermo=pickle.load(file)
            file.close()
    return str(thermo.cpu_temp)

@app.route('/stop', methods = ['Get'])
def stop():
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return 'stopped'

@app.route('/restart', methods = ['Get'])
def restart():
    temp.stop()
    temp.start()
    return 'restart'

if __name__=="__main__":
    app.run("0.0.0.0", port=80, debug=True)
    #app.run("0.0.0.0", port=80)
