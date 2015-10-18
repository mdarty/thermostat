#!/usr/bin/python2
import redis
import ConfigParser
from flask.ext.wtf import Form
from flask_bootstrap import Bootstrap
from wtforms.validators import Required
from wtforms import TextField, BooleanField
from flask import Flask, render_template, flash, redirect, request, send_file

red = redis.Redis(unix_socket_path='/var/run/redis/redis.sock')
pipe = red.pipeline(transaction=False)

Config = ConfigParser.ConfigParser()
Config.read('/root/thermostat/config.ini')

app = Flask(__name__)
Bootstrap(app)
app.config.from_object('config')
app.debug = True


class LoginForm(Form):
    openid = TextField('openid', validators=[Required()])
    remember_me = BooleanField('remember_me', default=False)


@app.route('/')
@app.route('/index')
def index():
    pipe.get('mode')
    pipe.get('set_temp')
    pipe.get('state')
    pipe.get('set_away_temp')
    pipe.get('set_away')
    mode, set_temp, state, set_away_temp, set_away = pipe.execute()
    return render_template("index.html",
                           title="Thermostat",
                           mode=mode,
                           set_temp=set_temp,
                           state=state,
                           set_away_temp=set_away_temp,
                           set_away=set_away)


@app.route('/index', methods=['POST'])
def index_post():
    if request.form['submit'] == "Garage":
        pipe.set('garage', 'on')
    else:
        pipe.set('garage', 'off')
    print(request)
    mode = request.form['mode']
    set_temp = request.form['set_temp']
    state = request.form['state']
    set_away_temp = request.form['set_away_temp']
    set_away = request.form['set_away']
    pipe.set('mode', mode)
    pipe.set('set_temp', set_temp)
    pipe.set('state', state)
    pipe.set('set_away_temp', set_away_temp)
    pipe.set('set_away', set_away)
    pipe.execute()
    return render_template("index.html",
                           title="Thermostat",
                           mode=mode,
                           set_temp=set_temp,
                           state=state,
                           set_away_temp=set_away_temp,
                           set_away=set_away)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        flash('Login requested for ' +
              'OpenID="{}", remember_me={}'.format(form.openid.data,
                                                   form.remember_me.data))
        return redirect('/index')
    return render_template('login.html',
                           title='Sign In',
                           form=form,
                           providers=app.config['OPENID_PROVIDERS'])


@app.route('/run_AC', methods=['Get'])
def run_AC():
    return red.get('run')


@app.route('/updatetemp', methods=['Get'])
def updatetemp():
    return red.get('T')


@app.route('/updateRH', methods=['Get'])
def updateRH():
    return red.get('RH')


@app.route('/updateOuttemp', methods=['Get'])
def updateOuttemp():
    return red.get('Tout')


@app.route('/updateOutRH', methods=['Get'])
def updateOutRH():
    return red.get('RHout')


@app.route('/cputemp', methods=['Get'])
def cputemp():
    return red.get('cpu_temp')


@app.route('/stop', methods=['Get'])
def stop():
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return 'stopped'

if __name__ == "__main__":
    # app.run("0.0.0.0", port=80)
    app.run()
