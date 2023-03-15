Creating tickets in Taiga via E-Mail
====================================

Purpose
-------

Your clients send their requests to a specified mailbox. 

This script will collect the emails and add them as a ticket to specified projects.


Setup
-----

You must copy the `.env.sample` file, and call it `.env`.

    cp .env.sample .env

Then you edit the file and add the credentials for your IMAP folder, and for a Taiga user.

It is recommended that you create a specific user, eg. called `TaigaEmail`, and make this part of the projects you want to be served with this script.

The name before the @ character in the email address must be the name or slug of the project.

You can forward e-mails from multiple addresses to one single mailbox, and the recipient address will still send the tickets to separate projects.

For the setup of this script, follow these steps:

    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt


You must configure a cronjob for this script to be run regularly (every 2 minutes):

    */2 * * * * cd $HOME/taiga-email-tickets && ./.venv/bin/python3 import_tickets.py >/dev/null 2>&1


References
----------

We are using `python-taiga`: https://python-taiga.readthedocs.io/en/latest/

See also the Taiga API: https://docs.taiga.io/api.html
