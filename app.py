import os

from flask import (
    Flask,render_template,flash, redirect,url_for,session,logging,request
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import func, ForeignKey
from werkzeug.utils import secure_filename
from currency_conversion import RealTimeCurrencyConverter
from sqlalchemy import or_

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
db = SQLAlchemy(app)

converter = RealTimeCurrencyConverter(app.config['EXCHANGE_RATE_URL'])

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255) , nullable=False)
    avtar = db.Column(db.Text , nullable=True)
    default_currency = db.Column(db.String(10),  nullable=False, default='USD')
    mail_id = db.Column(db.String(120),  nullable=False)
    password = db.Column(db.String(80),  nullable=False)
    created_at = db.Column(db.DateTime(), default=func.now())

class Wallet(db.Model):
    __tablename__ = 'wallet'
    id = db.Column(db.Integer, primary_key=True)
    debited_to_user_id = db.Column(db.Integer, ForeignKey("user.id"))
    created_by_user_id = db.Column(db.Integer, ForeignKey("user.id"))

    currency_type = db.Column(db.String(10),  nullable=False, default='USD')
    amount = db.Column(db.Numeric(precision=8, asdecimal=False, decimal_return_scale=None))
    created_at = db.Column(db.DateTime(), default=func.now())

    debited_to_user = relationship("User", foreign_keys=[debited_to_user_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

@app.route("/")
def index():
    return render_template("index.html", is_index=True)

@app.route("/login",methods=["GET", "POST"])
def login():
    if request.method == "POST":        
        login = User.query.filter_by(
                mail_id=request.form["mail_id"], 
                password=request.form["password"]
            ).first()

        if login is not None:
            return redirect(url_for("wallet", user_id=login.id))
            # return render_template("wallet.html")
    return render_template("login.html")


@app.route("/wallet/<user_id>", methods=["GET"])
def wallet(user_id):
    currency_type = request.args.get('currency_type')

    user = User.query.filter_by(id=user_id).first()
    wallet = Wallet.query.filter(
                or_(
                    Wallet.debited_to_user_id == user_id,
                    Wallet.created_by_user_id == user_id
                    )
                ).all()
    
    if currency_type is None:
        currency_type = user.default_currency
    
    wallets = []

    for wall in wallet:
        converted_currency = converter.convert(wall.currency_type, currency_type,  wall.amount)

        debited_money, debited_to_user = '', ''
        credited_money, credited_by_user = '', ''

        if wall.created_by_user_id == int(user_id):
            debited_money = wall.amount
            debited_to_user = f"{wall.debited_to_user.first_name} {wall.debited_to_user.last_name}"

        if wall.debited_to_user_id == int(user_id):
            credited_money = wall.amount
            credited_by_user = f"{wall.created_by_user.first_name} {wall.created_by_user.last_name}"

        wallets.append(dict(
            debited_to_user = debited_to_user,
            credited_by_user = credited_by_user, 

            currency_type = wall.currency_type,
            converted_currency = converted_currency,

            credited_amount = credited_money,
            debited_money = debited_money,
            created_at = wall.created_at
        ))
    return render_template("wallet.html",
                user=user, 
                wallet=wallets,
                currency_type=currency_type,
                currencies=converter.currencies
            )


@app.route("/user_profile/<user_id>", methods=["GET"])
def user_profile(user_id):
    usr_obj = User.query.filter_by(id=user_id)    
    return render_template("profile.html",
                user=usr_obj.first(),
                currencies=converter.currencies
            )


def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/edit_profile", methods=["POST"])
def edit_profile():  
    usr_obj = User.query.filter_by(id= request.form.get('id'))
    if request.method == "POST":
        user_profile = {}
        
        if request.files['avtar'] is not None:
            avtar = request.files['avtar']
            if avtar and allowed_file(avtar.filename):
                filename = secure_filename(avtar.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                avtar.save(path)
                user_profile['avtar'] = str(request.url_root)+ str(path)

        else:
            flash('Allowed image types are -> png, jpg, jpeg, gif')
            return redirect(request.url)

        for name in ['first_name', 'last_name', 'mail_id', 'password', 'default_currency']:
            if request.form.get(name) is not None:
                user_profile[name] = request.form.get(name)
        data = usr_obj.update(user_profile)
        db.session.commit()
        user = usr_obj.first()
        return redirect(url_for("user_profile", user_id=user.id))
    
    return redirect(url_for("login"))



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User.query.filter_by(
                mail_id=request.form["mail_id"], 
            ).first()
        
        if user is not None:
            return redirect(url_for("login"))

        register = User(
            first_name = request.form.get('first_name'),
            last_name = request.form.get('last_name'),
            mail_id = request.form.get('mail_id'), 
            password = request.form.get('password'), 
        )
        db.session.add(register)
        db.session.commit()

        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/send_money/<user_id>", methods=["GET"])
def send_money(user_id):
    user_list = User.query.filter(User.id != user_id).all()
    user = User.query.filter_by(id=user_id).first()
    return render_template("send_money.html",
             user=user, 
             user_list=user_list, currencies=converter.currencies)

@app.route("/send_money_to_user", methods=["POST"])
def send_money_to_user():
    if request.method == "POST":
        wallet = Wallet(
            debited_to_user_id = request.form.get('send_to'),
            created_by_user_id = request.form.get('id'),
            currency_type = request.form.get('currency_type'), 
            amount = request.form.get('amount'), 
        )
        db.session.add(wallet)
        db.session.commit()

        return redirect(url_for("wallet", user_id=request.form.get('id')))
    return redirect(url_for("login"))


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)