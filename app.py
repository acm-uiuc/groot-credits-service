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
from utils import (send_error, send_success, is_admin, validate_netid,
                   netid_from_token)
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


@scheduler.scheduled_job('interval', minutes=60, next_run_time=datetime.now())
def verify_balance_integrity():
    '''
    Verifies integrity of User.balance for all users

    Checks to make sure that the sum of transaction amounts associated with a
    user is equal to the balance stored on the user object
    '''
    with app.app_context():
        for user in User.query.all():
            bal = db.session.query(func.sum(Transaction.amount)).filter_by(
                netid=user.netid).scalar()
            if user.balance != bal:
                user.balance = bal
                db.session.add(user)
                db.session.commit()


def create_user_account(netid):
    '''
    Creates a user account for the given netid.
    Initializes the user's balance with the default amount of credits.
    Creates a transaction corrosponding to the default credits ammount.

    Params:
    * netid: A valid netid (NOTE: Does not check for validity)

    Returns:
    * The user object
    '''
    if User.query.filter_by(netid=netid).first():
        return  # User already exists
    user = User(netid=netid, balance=DEFAULT_CREDITS_BALANCE)
    initial_transaction = Transaction(netid=netid,
                                      amount=DEFAULT_CREDITS_BALANCE,
                                      description="Initial balance")
    db.session.add(user)
    db.session.add(initial_transaction)
    db.session.commit()
    return user


def get_user(netid):
    '''
    Returns or creates a user object with the given netid.

    Params:
    * netid: A valid netid (NOTE: Does not check for validity)

    Returns:
    * The user object
    '''
    user = User.query.filter_by(netid=netid).first()
    if not user:
        user = create_user_account(netid)
    return user


@app.route('/payment', methods=['POST'])
def make_payment():
    '''
    Endpoint for executing Stripe payments

    Params:
    * netid: NetID of user making payment
    * amount: Payment amount in cents
    * token: Stipe.js payment token
    * description: Description of payment
    '''
    parser = reqparse.RequestParser()
    parser.add_argument('netid', location='json',
                        required=True, type=validate_netid)
    parser.add_argument('amount', location='json',
                        required=True, type=int)
    parser.add_argument('token', location='json',
                        required=True)
    parser.add_argument('description', location='json',
                        required=True)
    parser.add_argument('adjust_balance', location='json',
                        default=True, type=bool)
    args = parser.parse_args()

    if (args.amount < 500) or (args.amount > 5000):
        return send_error('Invalid transaction amount.')

    try:
        customer = stripe.Customer.create(
            description=args.netid,
            source=args.token
        )

        stripe.Charge.create(
            customer=customer.id,
            amount=args.amount,
            currency='usd',
            description=args.description
        )
        float_amount = (args.amount / 100.0)  # Convert from cents to dollars

        if args.adjust_balance:
            # Create transaction for payment
            refill = Transaction(
                netid=args.netid,
                amount=float_amount,
                description=args.description
            )

            # Update User balance
            user = get_user(args.netid)
            user.balance += float_amount

            db.session.add(refill)
            db.session.add(user)
            db.session.commit()
        return jsonify({'successful': True})
    except Exception as e:
        print e
        return jsonify({'successful': False})


class UserCreditsResource(Resource):
    def get(self, netid=None):
        ''' Endpoint for checking a user's balance '''
        if netid:  # Find single user's balance
            try:
                validate_netid(netid)
            except:
                return send_error('Unrecognized user', 404)
            user = get_user(netid)
            return jsonify(user.serialize())
        else:  # Find all users' balances
            users = User.query.all()
            return jsonify([u.serialize() for u in users])


class TransactionResource(Resource):
    def get(self, id=None):
        '''
        Endpoint for getting a user's transaction history

        Returns transactions in reverse chronologial order
        '''
        parser = reqparse.RequestParser()
        parser.add_argument('netid', location='args',
                            required=True, type=validate_netid)
        args = parser.parse_args()

        transactions = (Transaction.query
                        .filter_by(netid=args.netid)
                        .order_by(Transaction.created_at.desc()))

        balance = get_user(args.netid).balance

        payload = {
            'transactions': [t.serialize() for t in transactions],
            'balance': balance
        }
        return jsonify(payload)

    def post(self, id=None):
        '''
        Endpoint for creating a new transaction

        Creates a new Transaction record and updates the associated User
        record's balance
        '''
        parser = reqparse.RequestParser()
        parser.add_argument('netid', location='json',
                            required=True, type=validate_netid)
        parser.add_argument('amount', location='json',
                            required=True, type=float)
        parser.add_argument('description', location='json', default='')

        args = parser.parse_args()

        transaction = Transaction(
            netid=args.netid,
            amount=args.amount,
            description=args.description
        )
        user = get_user(args.netid)
        user.balance += args.amount

        db.session.add(user)
        db.session.add(transaction)
        db.session.commit()
        return jsonify(transaction.serialize())

    def delete(self, transaction_id):
        '''
        Endpoint for deleting a transaction

        Deletes the given Transaction and updates the associated User record's
        balance
        '''
        parser = reqparse.RequestParser()
        parser.add_argument('Credits-Token', location='headers',
                            required=True, type=netid_from_token,
                            dest='admin_netid')
        args = parser.parse_args()

        # Require an admin session token to delete transactions
        if not is_admin(args.admin_netid):
            return send_error("Must be admin to delete transaction", 403)

        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if transaction:
            transaction.user.balance -= transaction.amount
            db.session.add(transaction.user)
            db.session.delete(transaction)
            db.session.commit()
            return send_success("Deleted transaction: %s" % transaction_id)
        else:
            return send_error("Unknown transaction")


api.add_resource(UserCreditsResource, '/credits/users',
                 '/credits/users/<netid>')
api.add_resource(TransactionResource, '/credits/transactions',
                 '/credits/transactions/<int:transaction_id>')
db.init_app(app)
db.create_all(app=app)
scheduler.start()

if __name__ == "__main__":
    app.run(port=PORT, debug=DEBUG)
