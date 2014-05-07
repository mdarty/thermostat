#!/usr/bin/python2
from flask import Flask, render_template, flash, redirect, request
from flask.ext.wtf import Form
from wtforms import TextField, BooleanField
from wtforms.validators import Required
from flask_wtf.csrf import CsrfProtect

app=Flask(__name__)
#CsrfProtect(app)
app.config.from_object('config')

class LoginForm(Form):
    openid = TextField('openid', validators = [Required()])
    remember_me = BooleanField('remember_me', default = False)

@app.route('/')
@app.route('/index')
def index():
    mode="off"
    set_temp="70"
    state="here"
    set_away="off"
    return render_template("index.html", title="Home", mode=mode, set_temp=set_temp, state=state, set_away=set_away)

@app.route('/index', methods = ['POST'])
def index_post():
    print request.form
    mode=request.form['mode']
    set_temp=request.form['set_temp']
    state=request.form['state']
    set_away=request.form['set_away']
    return render_template("index.html", title="Home", mode=mode, set_temp=set_temp, state=state, set_away=set_away)

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

@app.route('/updatetemp', methods = ['Get'])
def updatetemp():
    return str(70)

@app.route('/updateRH', methods = ['Get'])
def updateRH():
    return str(50)

if __name__=="__main__":
    app.run("0.0.0.0", port=80, debug=True)
