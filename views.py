#!/usr/bin/python2
from flask import Flask, render_template, flash, redirect, request
from flask.ext.wtf import Form
from wtforms import TextField, BooleanField
from wtforms.validators import Required
from flask_wtf.csrf import CsrfProtect
from thermo import temp
import sys
temp=temp()
temp.start()

app=Flask(__name__)
#CsrfProtect(app)
app.config.from_object('config')

class LoginForm(Form):
    openid = TextField('openid', validators = [Required()])
    remember_me = BooleanField('remember_me', default = False)

@app.route('/')
@app.route('/index')
def index():
    return render_template("index.html", title="Thermostat", mode=temp.mode, set_temp=temp.set_temp, state=temp.state, set_away_temp=temp.set_away_temp, set_away=temp.set_away)

@app.route('/index', methods = ['POST'])
def index_post():
    print request.form
    if request.method['submit'] == 'temp':
        temp.mode=request.form['mode']
        temp.set_temp=request.form['set_temp']
        temp.state=request.form['state']
        temp.set_away_temp=request.form['set_away_temp']
        temp.set_away=request.form['set_away']
    elif request.method['sumbit'] == 'Garage':
        temp.garage()
    else:
        print 'Something Broke on post'
    return render_template("index.html", title="Thermostat", mode=temp.mode, set_temp=temp.set_temp, state=temp.state, set_away_temp=temp.set_away_temp, set_away=temp.set_away)

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

@app.route('/run_AC', methods = ['Get'])
def run_AC():
    return str(temp.relay.run)

@app.route('/updatetemp', methods = ['Get'])
def updatetemp():
    return str(temp.T)

@app.route('/updateRH', methods = ['Get'])
def updateRH():
    return str(temp.RH)

@app.route('/updateOuttemp', methods = ['Get'])
def updateOuttemp():
    return str(temp.Tout)

@app.route('/updateOutRH', methods = ['Get'])
def updateOutRH():
    return str(temp.RHout)

@app.route('/stop', methods = ['Get'])
def stop():
    temp.stop()
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
