# groot-credits-service :moneybag:

Groot core development:

[![Join the chat at https://gitter.im/acm-uiuc/groot-development](https://badges.gitter.im/acm-uiuc/groot-development.svg)](https://gitter.im/acm-uiuc/groot-development?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Questions on how to add your app to Groot or use the Groot API:

[![Join the chat at https://gitter.im/acm-uiuc/groot-users](https://badges.gitter.im/acm-uiuc/groot-users.svg)](https://gitter.im/acm-uiuc/groot-users?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)


## Install / Setup
1. Clone repo:

    ```
    git clone https://github.com/acm-uiuc/groot-credits-service
    cd groot-credits-service
    ```

2. Install dependencies:

    ```
    pip install -r requirements.txt
    ```

3. Copy settings template:

    ```
    cd groot_credits_service
    cp settings.template.py settings.py
    ```

4. Add your DB credentials to settings.py.

## Run Application
```
python app.py
```

## Routes

#### POST /payment

Performs a payment charge through the Stripe API.

*Body Params:*

* `netid` - NetID of the user being charged
    * Required
* `amount` - The amount of money being charged. Expressed as an integer in cents. (i.e. $12.34 -> 1234)
    * Required
* `token` - The Stripe.js token for the transaction.
    * Required
* `description` - Description of the charge to be used in the Stripe charge, and in the Credits Transaction (if applicable)
    * Required
* `adjust_balance` - Whether or not credits service should credit the user with the amount being charged. 
    * Default: True
    * Note: Should be `True` for balance refills, and `False` for purchases, like buying membership

#### GET /credits/users

Gets the balance of all users.
Returns user balances with the following schema:
```
    [
        {
            "netid": jdoe2
            "balance": 123.45
        },
        {
            "netid": sjobs2
            "balance": 999.99
        },
        ...
    ]
```

#### GET /credits/users/{netid}

Gets the details of a user's credits account.
Returns a user with the following schema:
```
    {
        "netid": jdoe2
        "balance": 123.45
    }
```

#### GET /credits/transactions

Endpoint for getting a user's transaction history. Returns transactions in reverse chronologial order

*Params:*
* `netid` - NetID of the user.
    * Required

Returns a user transaction history with the following schema:
```
    {
        "transactions": [
            {
                "id": 1
                "created_at": "2017-02-13T11:58:39Z"
                "description": "Balance Refill"
                "amount": 12.34
            }
            ...
        ]
        "balance": 123.45
    }
```

#### POST /credits/transactions

Endpoint for creating a new transaction. Creates a new Transaction record and updates the associated User record's balance.

*Body Params:*
* `netid` - NetID of the user.
    * Required
* `amount` - The transaction amount as a float
    * Required
    * Note: If you want the transaction to be a charge (i.e. lower the user's balance), the amount should be negative.
* `description` Description of the transaction
    * Required

#### DELETE /credits/transactions/{id}

Endpoint for deleting a transaction. Deletes the given Transaction and updates the associated User record's balance.

*Headers*
* `Credits-Token` - The session token of the user making the request
    * Required
    * Used to authenticate route

## Contributing

Contributions to `groot-credits-service` are welcomed!

1. Fork the repo.
2. Create a new feature branch.
3. Add your feature / make your changes.
4. Install [pep8](https://pypi.python.org/pypi/pep8) and run `pep8 *.py` in the root project directory to lint your changes. Fix any linting errors.
5. Create a PR.
6. ???
7. Profit.
