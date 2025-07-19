from flask import Flask, render_template, flash, request, send_file,session
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import random
import threading
import tempfile
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

user_agents = [
    # Chrome - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",

    # Chrome - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.91 Safari/537.36",

    # Chrome - Android
    "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.136 Mobile Safari/537.36",

    # Firefox - Linux
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:117.0) Gecko/20100101 Firefox/117.0",

    # Firefox - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",

    # Edge - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.62 Safari/537.36 Edg/117.0.2045.31",

    # Safari - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Safari/605.1.15",

    # Safari - iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1",

    # Brave - Android
    "Mozilla/5.0 (Linux; Android 10; SM-A205F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Mobile Safari/537.36",

    # Samsung Browser
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36 SamsungBrowser/16.0"
]

check_interval_seconds = 14400  # 4 hours
products = []
user_updates = {}

@app.route('/graph/<email>')
def serve_graph(email):
    safe_email = email.replace('@', '_at_').replace('.', '_')
    path = f"/tmp/{safe_email}_price_graph.png"
    if not os.path.exists(path):
        print(f"❌ Graph file not found at: {path}")
        return "Graph not found", 404
    return send_file(path, mimetype='image/png')

@app.route('/updates/<email>')
def live_updates(email):
    return user_updates.get(email, '')

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        url = request.form.get('URL')
        email = request.form.get('email')
        target_price = float(request.form.get('price'))

        if not ('amazon.in' in url or 'flipkart.com' in url):
            flash("❌ This website is not supported yet. Please enter an Amazon or Flipkart URL.")
            return render_template('index.html')

        product = {
            "url": url,
            "email": email,
            "target_price": target_price,
            "history": []
        }

        products.append(product)
        user_updates[email] = f"✅ Tracking started at {time.strftime('%H:%M:%S')} on {time.strftime('%Y-%m-%d')}."
        check_price(product)

        flash("✅ Tracking started. You'll be notified here if price drops.")
        return render_template('index.html', email=email, graph=True)

    return render_template('index.html')



def send_email(email, message):
    load_dotenv()
    port = 465
    smtp_server = "smtp.gmail.com"
    sender_email = "meetmourya04@gmail.com"
    password = os.getenv("Email_password")

    msg = MIMEMultipart()
    msg['Subject'] = "🔔 Price Alert"
    msg['From'] = sender_email
    msg['To'] = email
    msg.attach(MIMEText(message, 'plain', _charset='utf-8'))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, email, msg.as_string())
    print(f"✅ Email sent to {email}")

def check_price(product):

    url = product["url"]
    target_price = product["target_price"]
    email = product["email"]

    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Connection": "keep-alive"
    }

    for attempt in range(3):
        try:
            time.sleep(random.uniform(3, 6))
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')

            price_az = soup.find("span", {"class": "a-offscreen"})
            price_fl = soup.find("div", {"class": "Nx9bqj CxhGGd"})

            price_tag = price_az or price_fl

            if price_tag:
                price_text = price_tag.text.strip().replace('₹', '').replace(',', '')
                if not price_text:
                    print(f"⚠ Price text is empty at attempt {attempt + 1}. Retrying...")
                    time.sleep(2)
                    continue

                current_price = float(price_text)
                timestamp = time.strftime('%H:%M:%S')
                product["history"].append((timestamp, current_price))
                print(f"✅ Saving graph for {email}")
                update_price_chart(product["history"], email)

                if current_price <= target_price:
                    user_updates[email] = f"✅ Checked at {timestamp} — ₹{current_price}. Price dropped! ✅"
                    message = f"Your product price dropped to ₹{current_price} at {timestamp}"
                    send_email(email, message)
                else:
                    user_updates[email] = f"✅ Checked at {timestamp} — ₹{current_price}. Still waiting ⏳"
                return
            else:
                print(f"⚠ Attempt {attempt + 1}: Couldn't find price. Retrying...")
                time.sleep(2)

        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed with error:", e)
            time.sleep(2)

    print("❌ All attempts failed.")



def update_price_chart(price_history, email):
    if not price_history:
        return

    times, prices = zip(*price_history)
    plt.figure(figsize=(8, 4))
    plt.plot(times, prices, marker='o')
    plt.title('Price History')
    plt.xlabel('Time')
    plt.ylabel('Price (₹)')
    plt.grid(True)
    plt.tight_layout()

    safe_email = email.replace('@', '_at_').replace('.', '_')

    # Ensure tmp directory exists
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    filepath = os.path.join(tmp_dir, f"{safe_email}_price_graph.png")
    print(f"✅ Saving graph to: {filepath}")
    print("✅ Saved chart:", os.path.exists(filepath))

    plt.savefig(filepath)
    plt.close()


def price_check_loop():
    while True:
        if products:
            for product in products:
                check_price(product)
                time.sleep(check_interval_seconds)
        else:
            time.sleep(5)

threading.Thread(target=price_check_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
