"""
This script will read messages from an IMAP mailbox,
and add the email as a new ticket in Taiga.
"""

import os
import shutil
import environ
import taiga
import imaplib
import email
import re
import uuid
import traceback
from email.header import decode_header
from taiga import TaigaAPI


env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

# Set the project base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# False if not in os.environ because of casting above
DEBUG = env('DEBUG')

imap = imaplib.IMAP4_SSL(env('IMAP_HOST'))
imap.login(env('IMAP_USER'), env('IMAP_PWD'))


def camel_case_to_slug(name):
    slug = re.sub('(?!^)([A-Z]+)', r'-\1',name).lower()
    return slug


def attach_file(path, issue, filename, content, description):
    if type(content) == str:
      newFile = open(os.path.join(path, filename), "w")
      newFile.write(content)
      newFile.close()
    else:
      newFile = open(os.path.join(path, filename), "wb")
      newFile.write(content)
      newFile.close()

    issue.attach(os.path.join(path, filename), description=description)


def create_ticket(api, project_slug, message):

    try:
        project = api.projects.get_by_slug(project_slug)
    except:
        project = None
    if project is None:
        projects = api.projects.list()
        for p in projects:
            if camel_case_to_slug(p.name) == project_slug:
                project = api.projects.get_by_slug(p.slug)
    if project is None:
        print(f"cannot find project with slug {project_slug}")
        return False

    body = message['text']
    #if message['html'] is not None:
    #    body = message['html'].replace('<meta http-equiv="content-type" content="text/html; charset=UTF-8">', '')

    body = f"From: {message['from']}\nDate: {message['date']}\n\n" + body

    # TODO: do we have this ticket already, and this is a reply?
    #search_result = api.search(project.id, 'NEW')
    #issue = api.issues.list(project=project.id, name=message['subject'])
    #print(issue)
    #return False


    #if message['subject'] == 'Test Ticket mit Bild':
    #    newissue = project.get_issue_by_ref(5)
    #    newissue.description = body
    #    newissue.update()
    #else:
    if True:
        newissue = project.add_issue(
            message['subject'],
            project.priorities.get(name='High').id,
            project.issue_statuses.get(name='New').id,
            project.issue_types.get(name='Bug').id,
            project.severities.get(name='Minor').id,
            description=body,
            assigned_to=env('TAIGA_ASSIGN_TO'),
        )

    # attach the original message, as .eml file to be opened in eg. Thunderbird
    path = os.path.join(BASE_DIR, message['message_id'])
    os.makedirs(path)

    try:
        attach_file(path, newissue, 'message.eml', str(message['msg']), description='The original mail message')

        # attach attachments
        for att in message['attachments']:
            attach_file(path, newissue, att['filename'], att['content'], description="Attachment")
    except taiga.exceptions.TaigaRestException as ex:
        print(f"while uploading attachments into project {project_slug}: ")
        print(message['from'])
        print(message['to'])
        print(ex)
        return False

    finally:
        shutil.rmtree(path)
    
    imap.store(message["e_id"], '+FLAGS', '\Seen')

    
def create_tickets(messages):
    api = TaigaAPI(host=env('TAIGA_HOST'))
    api.auth(username=env('TAIGA_USER'), password=env('TAIGA_PWD'))

    for message in messages:
        toAddress = message['to']
        if '<' in toAddress:
            toAddress = toAddress[toAddress.index('<') + 1:]
            toAddress = toAddress[:toAddress.index('>')]
        project_slug = camel_case_to_slug(toAddress[:toAddress.index('@')])

        create_ticket(api, project_slug, message)


def decode_email(msg, tag):
    if not msg[tag]:
        return None
    val, encoding = decode_header(msg[tag])[0]
    if encoding is None:
        encoding = "utf-8"
    if isinstance(val, bytes):
        # if it's a bytes, decode to str
        val = val.decode(encoding)
    return val

def collect_emails():
    # get all new messages
    messages = []

    imap.select("INBOX")

    status, response = imap.search(None, '(UNSEEN)')
    unread_messages = response[0].split()

    for e_id in unread_messages:
      # fetch the email message by ID; BODY.PEEK: do not mark as seen
      res, msg = imap.fetch(e_id, "(BODY.PEEK[])")
      for response in msg:
        if isinstance(response, tuple):
          try:
            # parse a bytes email into a message object
            msg = email.message_from_bytes(response[1])

            post = {}
            post['e_id'] = e_id
            post['to'] = decode_email(msg, "To")
            post['from'] = decode_email(msg, "From")
            post['subject'] = decode_email(msg, "Subject")
            post['date'] = decode_email(msg, "Date")
            post['message_id'] = decode_email(msg, "Message-ID")
            post['msg'] = msg

            if not post['message_id']:
                post['message_id'] = str(uuid.uuid4())

            post['text'] = ""
            post['html'] = ""
            post['attachments'] = []
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    try:
                        body = part.get_payload(decode=True).decode()
                    except:
                        pass
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        post['text'] = body
                    elif content_type == "text/html":
                        post['html'] = body
                    elif part.get_filename() is not None:
                        att = {}
                        att['filename'] = part.get_filename()
                        att['content'] = part.get_payload(decode=True)
                        post['attachments'].append(att)
            else:
                # extract content type of email
                content_type = msg.get_content_type()
                # get the email body
                body = msg.get_payload(decode=True).decode()
                if content_type == "text/plain":
                    post['text'] = body
                elif content_type == "text/html":
                    post['html'] = body

            messages.append(post)
          except Exception as ex:
            # TODO send error notification?
            print(post['to'])
            print(ex)
            traceback.print_exc()


    return messages


messages = collect_emails()
create_tickets(messages)


