# Setlist: Step-up two-factor authentication with Django and Vonage Verify

A small Django app that demonstrates **step-up authentication**: a password gets you
into the account, but moving something of value out of it takes a code sent to your
phone by the [Vonage Verify API](https://developer.vonage.com/en/verify/overview).

Setlist holds concert tickets. You can browse shows and look at your own tickets with
nothing but a session cookie. Transferring a ticket to someone else is irreversible,
so that one view, and only that view, asks you to prove you still have the phone.

Companion code for the blog post *Add Two-Factor Authentication to Your Django App
With Vonage Verify*.

## What it demonstrates

- Verify v2 through the Vonage Python SDK v4, with Basic authentication.
- Verification scoped to a **session** and given a **time limit**, not a permanent
  flag on the user.
- A reusable `VerificationRequiredMixin` you can drop onto any class-based view.
- Every Verify failure mode mapped to something a person can act on: wrong code,
  expired request, too many attempts, rate limit, concurrent request.
- 47 tests, none of which touch the network or send an SMS.

## Requirements

- Python 3.12 or newer
- A [Vonage API account](https://developer.vonage.com/sign-up), for the API key and
  secret from the [dashboard](https://dashboard.vonage.com/settings)
- A phone that can receive SMS

## Setup

Clone the repository and create a virtual environment:

```bash
python -m venv .venv && source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Copy the example environment file and fill in your Vonage credentials:

```bash
cp .env.example .env
```

Create the database and load the demo shows and accounts:

```bash
python manage.py migrate && python manage.py seed_demo
```

Start the server:

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000>, sign in as `ada` with the password `setlist-demo`, and
transfer a ticket to `grace`. You will be asked for a phone number, then for the code
that arrives by SMS.

> **Trial accounts:** while your Vonage account is in trial, you can only send to
> numbers you have added as test numbers in the dashboard. Add your own number under
> [Your numbers](https://dashboard.nexmo.com/your-numbers) before you try this.

## Running the tests

```bash
python manage.py test
```

## How it fits together

The file structure is as follows:

```
blog-django-2fa-vonage-verify/
├── setlist/                    # Main Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── stepup/                     # Two-factor authentication app
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── client.py              # Vonage API integration
│   ├── mixins.py              # VerificationRequiredMixin for views
│   ├── models.py              # VerifiedPhone model
│   ├── session.py             # Verification session management
│   ├── tests.py               # 47 tests (no network/SMS calls)
│   ├── urls.py
│   └── views.py               # Verification flow views
│
├── tickets/                    # Demo app for ticket transfers
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py               # TicketTransferView (uses mixin)
│
├── templates/                  # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── ticket_list.html
│   ├── ticket_transfer.html
│   ├── verify_code.html        # Enter SMS code
│   └── verify_phone.html       # Choose phone number
│
├── manage.py                  # Django management script
├── requirements.txt           # Python dependencies
├── .env.example              # Example environment variables
├── .gitignore                # Git ignore rules
└── README.md                 # Documentation
```

The following files specifically are responsible for the following:

| File | What it does |
| --- | --- |
| `stepup/client.py` | The only module that knows about Vonage. Starts and checks verifications, turns API failures into user-facing messages. |
| `stepup/session.py` | Where a verification lives between requests, and when it expires. Also validates `?next=`. |
| `stepup/mixins.py` | `VerificationRequiredMixin`, the guard you put on sensitive views. |
| `stepup/views.py` | The two-step flow: choose a number, then enter the code. |
| `stepup/models.py` | `VerifiedPhone`, a one-to-one with the user. |
| `tickets/views.py` | The demo app. `TicketTransferView` is the one view behind the mixin. |



## Configuration

| Variable | Purpose |
| --- | --- |
| `VONAGE_API_KEY` | From the Vonage dashboard. |
| `VONAGE_API_SECRET` | From the Vonage dashboard. |
| `VONAGE_BRAND_NAME` | Sender name in the SMS. Maximum 16 characters. |
| `STEP_UP_TTL_SECONDS` | How long a verification stays valid. Defaults to 300. |
| `DJANGO_SECRET_KEY` | Standard Django setting. |
| `DJANGO_DEBUG` | `True` locally. |

## Not included

This is a tutorial app, not a product. Before anything like it goes near real users
you would also want: rate limiting on the verification endpoints themselves, a
recovery path for a lost phone, and a decision about which other actions belong
behind the same mixin: changing a password, changing the phone number, or adding a
payout method.
