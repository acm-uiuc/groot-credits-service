# -*- coding: utf-8 -*-
'''
Copyright © 2017, ACM@UIUC
This file is part of the Groot Project.
The Groot Project is open source software, released under the University of
Illinois/NCSA Open Source License.  You should have received a copy of
this license in a file with the distribution.
'''

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
db = SQLAlchemy()


class User(db.Model):
    netid = db.Column(db.String(200), primary_key=True)
    balance = db.Column(db.Float())
    transactions = db.relationship('Transaction', backref='user',
                                   lazy='dynamic')

    def serialize(self):
        return {
            "netid": self.netid,
            "balance": self.balance or 0
        }


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    netid = db.Column(db.String(200), db.ForeignKey('user.netid'))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    description = db.Column(db.String(200))
    amount = db.Column(db.Integer)

    def serialize(self):
        return {
            "id": self.id,
            "user": self.netid,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "amount": self.amount or 0
        }
