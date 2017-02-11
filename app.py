# -*- coding: utf-8 -*-
'''
Copyright © 2017, ACM@UIUC
This file is part of the Groot Project.
The Groot Project is open source software, released under the University of
Illinois/NCSA Open Source License.  You should have received a copy of
this license in a file with the distribution.
'''

from flask import Flask, jsonify
from flask_restful import Resource, Api, reqparse
from sqlalchemy import func
from apscheduler.schedulers.background import BackgroundScheduler
import os
from datetime import datetime
from models import db, User, Transaction
from utils import send_error, send_success
import stripe
import logging
from settings import MYSQL, GROOT_ACCESS_TOKEN, STRIPE_SECRET_KEY
stripe.api_key = STRIPE_SECRET_KEY
logger = logging.getLogger('groot_credits_service')
logging.basicConfig(level="INFO")

# Check to see that Stripe can make API calls
# I got bitten by an openSSL version error, so make sure to double check
try:
    stripe.Charge.all()
    logger.info("TLS 1.2 supported, no action required.")
except stripe.error.APIConnectionError:
    logger.error("TLS 1.2 is not supported. Strip WILL NOT function.")



app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://{}:{}@{}/{}'.format(
    MYSQL['user'],
    MYSQL['password'],
    MYSQL['host'],
    MYSQL['dbname']
)
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=UTF-8'

PORT = 8765
DEBUG = os.environ.get('CREDITS_DEBUG', False)
DEFAULT_CREDITS_BALANCE = 5.0

api = Api(app)
scheduler = BackgroundScheduler()


def validate_netid(netid):
    # TODO: Ask user service to validate netid
    return netid


@scheduler.scheduled_job('interval', minutes=60, next_run_time=datetime.now())
def verify_balance_integrity():
    with app.app_context():
        for user in User.query.all():
            bal = db.session.query(func.sum(Transaction.amount)).filter_by(
                netid=user.netid).scalar()
            if user.balance != bal:
                user.balance = bal
                db.session.add(user)
                db.session.commit()


@app.route('/payment', methods=['POST'])
def make_payment():
    parser = reqparse.RequestParser()
    parser.add_argument('netid', location='json',
                        required=True, type=validate_netid)
    parser.add_argument('amount', location='json',
                        required=True, type=int)
    parser.add_argument('token', location='json',
                        required=True)
    parser.add_argument('description', location='json',
                        required=True)
    args = parser.parse_args()

    customer = stripe.Customer.create(
        description=args.netid,
        source=args.token
    )

    try:
        stripe.Charge.create(
            customer=customer.id,
            amount=args.amount,
            currency='usd',
            description=args.description
        )
        # TODO: Create User if necessary
        # TODO: Update User balance
        refill = Transaction(
            netid=args.netid,
            amount=(args.amount / 100.0),
            description=args.description
        )
        db.session.add(refill)
        db.session.commit()
        return jsonify({'successful': True})
    except Exception as e:
        print e
        return jsonify({'successful': False})


class UserCreditsResource(Resource):
    def get(self, netid):
        ''' Endpoint for checking a user's balance '''
        user = User.query.filter_by(netid=netid).first()
        if not user:
            return send_error('Unrecognized user', 404)
        return jsonify(user.serialize())

    def post(self, netid):
        '''
        Endpoint for creating a user account

        Sets balance to DEFAULT_CREDITS_BALANCE and creates a corrosponding
        transaction to initialize the user's balance.
        '''
        if User.query.filter_by(netid=netid).first():
            return send_error('User already exists')
        user = User(netid=netid, balance=DEFAULT_CREDITS_BALANCE)
        initial_transaction = Transaction(netid=netid,
                                          amount=DEFAULT_CREDITS_BALANCE)
        db.session.add(user)
        db.session.add(initial_transaction)
        db.session.commit()
        return jsonify(user.serialize())


class TransactionResource(Resource):
    def get(self, id=None):
        ''' Endpoint for getting a user's transaction history '''
        parser = reqparse.RequestParser()
        parser.add_argument('netid', required=True, type=validate_netid)
        args = parser.parse_args()

        transactions = Transaction.query.filter_by(netid=args.netid)
        balance = User.query.filter_by(netid=args.netid).first().balance

        # TODO: Sort Transactins in reverse chronological order
        payload = {
            'transactions': [t.serialize() for t in transactions],
            'balance': balance
        }
        return jsonify(payload)

    def post(self, id=None):
        ''' Endpoint for creating a new transaction '''
        parser = reqparse.RequestParser()
        parser.add_argument('netid', location='json',
                            required=True, type=validate_netid)
        parser.add_argument('amount', location='json',
                            required=True, type=float)
        parser.add_argument('description', location='json', default='')
        args = parser.parse_args()

        user = User.query.filter_by(netid=args.netid).first()
        if not user:
            return send_error('Unrecognized user')

        transaction = Transaction(
            netid=args.netid,
            amount=args.amount,
            description=args.description
        )
        user.balance += args.amount

        db.session.add(user)
        db.session.add(transaction)
        db.session.commit()
        return jsonify(transaction.serialize())

    def delete(self, transaction_id):
        ''' Endpoint for deleting a transaction '''
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if transaction:
            transaction.user.balance -= transaction.amount
            db.session.add(transaction.user)
            db.session.delete(transaction)
            db.session.commit()
            return send_success("Deleted transaction: %s" % transaction_id)
        else:
            return send_error("Unknown transaction")


api.add_resource(UserCreditsResource, '/credits/users/<netid>')
api.add_resource(TransactionResource, '/credits/transactions',
                 '/credits/transactions/<int:transaction_id>')
db.init_app(app)
db.create_all(app=app)
scheduler.start()

if __name__ == "__main__":
    app.run(port=PORT, debug=DEBUG)
