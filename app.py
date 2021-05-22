# Python standard libraries
import json
import os
import sqlite3
from dotenv import dotenv_values
from flask import render_template
# Third party libraries
from flask import Flask, redirect, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests

# Internal imports
from db import init_db_command
from user import User
from flask_sqlalchemy import SQLAlchemy

# to viz in plotly
import pandas as pd
import json
import plotly
import plotly.express as px
import plotly.graph_objects as go

# Configuration
config = dotenv_values(".env")

GOOGLE_CLIENT_ID = "868588184946-klp2u5umbbmujhqp8pio7vfp28jtofoh.apps.googleusercontent.com" #config["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = "zV5LssPwqjv7ksjnm6tbhdpW" #config["GOOGLE_CLIENT_SECRET"]
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)


# Adding the connection to the MySQL database
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="carloodq",
    password="1996Stud",
    hostname="carloodq.mysql.pythonanywhere-services.com",
    databasename="carloodq$students",
)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

#setting up the attendances table
class Comment(db.Model):

    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    student_email = db.Column(db.String(4096), nullable=False)
    student_position = db.Column(db.String(4096), nullable=False)



# User session management setup
# https://flask-login.readthedocs.io/en/latest
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.unauthorized_handler
def unauthorized():
    return "You must be logged in to access this content.", 403


# Naive database setup
try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)


# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html")
        # return (
        #     "<p>Hello, {}! You're logged in! Email: {}</p>"
        #     "<div><p>Google Profile Picture:</p>"
        #     '<img src="{}" alt="Google profile pic"></img></div>'
        #     '<a class="button" href="/logout">Logout</a>'.format(
        #         current_user.name, current_user.email, current_user.profile_pic
        #     )
        # )
    else:
        return render_template("bootstrap.html") #'<a class="button" href="/login">Google Login</a>'


# adding the thanks route
@app.route("/thanks", methods=["POST"])
def thanks():
    student_position = request.form.get("form-input") # take the request the user made, access the form,
                                    # and store the field called `name` in a Python variable also called `name`
    student = Comment(student_email=current_user.email, student_position=student_position)
    db.session.add(student)
    db.session.commit()
    return render_template("thanks.html", name = current_user.name)


# adding the prof route
@app.route("/prof", methods=["POST", "GET"])
def prof():

    students = [Comment.query.get(x+1).student_email for x in range(Comment.query.count())]
    positions = [Comment.query.get(x+1).student_position for x in range(Comment.query.count())]
    df = pd.DataFrame({'Student':students,'Position':positions})
    #pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/2014_usa_states.csv')

    def get_coords_x(x):
        try:
            coords = [float(i) for i in x.split(' ')]
            return (coords[0]+10)/20*100
        except:
            return None

    def get_coords_y(x):
        try:
            coords = [float(i) for i in x.split(' ')]
            return coords[1]/10*100
        except:
            return None

    df['positions_x'] = df['Position'].apply(lambda x: get_coords_x(x))
    df['positions_y'] = df['Position'].apply(lambda x: get_coords_y(x))

    df = df.dropna()
    df_returned = df[['Student','Position']]

    fig = go.Figure(data=[go.Table(
        header=dict(values=list(df_returned.columns),
                    fill_color='paleturquoise',
                    align='left'),
        cells=dict(values=[df_returned.Student, df_returned.Position],
                   fill_color='lavender',
                   align='left'))
    ])
    fig.update_layout(title='Registered students')

    #data= pd.read_csv("https://raw.githubusercontent.com/plotly/datasets/master/2014_usa_states.csv")

    fig_scatter = go.Figure(data=go.Scatter(x=df['positions_x'],
                                    y=df['positions_y'],
                                    mode='markers',
                                    #marker_color=df['Population'], #Ican add it has time of exposure
                                    text=df['Student'])) # hover text goes here

    fig_scatter.update_layout(title='Students Position')


    #fig.show()
    #if post:
        # query the class and return the respective details

    #else:
        # ask to select a class
    #df = pd.DataFrame({
    #  "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
    #  "Amount": [4, 1, 2, 2, 4, 5],
    #  "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"]})

    #fig = px.bar(df, x="Fruit", y="Amount", color="City",    barmode="group")
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    scatter = json.dumps(fig_scatter, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template('notdash.html', graphJSON=graphJSON, scatter = scatter)


@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)




@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    # Create a user in our db with the information provided
    # by Google
    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )

    # Doesn't exist? Add to database
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)

    # Begin user session by logging the user in
    login_user(user)

    # Send user back to homepage
    return redirect(url_for("index"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


if __name__ == "__main__":
    app.run(ssl_context="adhoc")
