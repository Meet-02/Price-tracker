from flask import Flask, render_template, flash, request, send_file
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
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

load_dotenv()
EMAIL_PASSWORD = os.getenv("Email_password")

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0)"
]

check_interval_seconds = 14400  # 4 hours
products = []  # List of dicts
update_list = ""

@app.route('/updates')
def live_updates():
    return update_list

@app.route('/graph/<email>')
def get_graph(email):
    safe_email = email.replace('@', '_at_').replace('.', '_')
    filepath = f'/tmp/{safe_email}_price_graph.png'
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    else:
        return "Graph not found", 404

@app.route('/', methods=['GET', 'POST'])
def home():
    global update_list

    if request.method == 'POST':
        url = request.form.get('URL')
        email = request.form.get('email')
        price = request.form.get('price')

        if not url or not email or not price:
            flash("❌ All fields are required.")
            return render_template('index.html')

        if not ('amazon.in' in url or 'flipkart.com' in url):
            flash("❌ Only Amazon and Flipkart URLs are supported.")
            return render_template('index.html')

        target_price = float(price)

        products.append({
            "url": url,
            "email": email,
            "target_price": target_price,
            "history": []
        })

        flash("✅ Tracking started. You'll be notified here if price drops.")
        update_list = f"✅ Tracking started at {time.strftime('%H:%M:%S')} on {time.strftime('%Y-%m-%d')}."

        return render_template('index.html', email=email)

    # GET request — fresh form
    return render_template('index.html')

def send_email(email, message):
    sender_email = "meetmourya04@gmail.com"
    port = 465
    smtp_server = "smtp.gmail.com"

    msg = MIMEMultipart()
    msg['Subject'] = "🔔 Price Alert"
    msg['From'] = sender_email
    msg['To'] = email
    msg.attach(MIMEText(message, 'plain', _charset='utf-8'))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, EMAIL_PASSWORD)
        server.sendmail(sender_email, email, msg.as_string())

    print(f"✅ Email sent to {email}")

def check_price(product):
    global update_list
    url = product["url"]
    target_price = product["target_price"]
    email = product["email"]

    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Connection": "keep-alive"
    }

    for attempt in range(3):
        try:
            time.sleep(random.uniform(2, 4))
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')

            price_az = soup.find("span", {"class": "a-offscreen"})
            price_fl = soup.find("div", {"class": "Nx9bqj CxhGGd"})

            price_tag = price_az or price_fl

            if price_tag:
                price_text = price_tag.text.strip().replace('₹', '').replace(',', '')
                if not price_text:
                    continue
                current_price = float(price_text)

                timestamp = time.strftime('%H:%M:%S')
                product["history"].append((timestamp, current_price))
                update_price_chart(product["history"], email)

                update_list = f"✅ Checked at {timestamp} — ₹{current_price}"

                if current_price <= target_price:
                    message = f"Your product has dropped to ₹{current_price} at {timestamp}."
                    send_email(email, message)
                return
            else:
                print(f"⚠ Attempt {attempt + 1}: Price tag not found. Retrying...")
                time.sleep(1)

        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            time.sleep(1)

    print("❌ All attempts failed. Skipping this check.")

def update_price_chart(history, email):
    if not history:
        return
    times, prices = zip(*history)
    plt.figure(figsize=(8, 4))
    plt.plot(times, prices, marker='o')
    plt.title('Price History')
    plt.xlabel('Time')
    plt.ylabel('Price (₹)')
    plt.grid(True)
    plt.tight_layout()

    safe_email = email.replace('@', '_at_').replace('.', '_')
    filepath = f'/tmp/{safe_email}_price_graph.png'
    plt.savefig(filepath)
    plt.close()
    print(f"📈 Graph saved to {filepath}")

def price_check_loop():
    while True:
        if products:
            for product in products:
                check_price(product)
                time.sleep(check_interval_seconds)
        else:
            time.sleep(5)

# Start background checker
threading.Thread(target=price_check_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
