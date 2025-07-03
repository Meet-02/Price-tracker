from flask import Flask, render_template, flash, request
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

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0)"
]

check_interval_seconds = 14400  # 4 hours
products = []
user_updates = {}  # Dictionary to store updates per user


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        url = request.form.get('URL')
        email = request.form.get('email')
        target_price = float(request.form.get('price'))

        # Validate supported URL
        if not ('amazon.in' in url or 'flipkart.com' in url):
            flash("❌ This website is not supported yet. Please enter an Amazon or Flipkart URL.")
            return render_template('index.html')  # Clean form again

        # Add product for tracking
        products.append({
            "url": url,
            "email": email,
            "target_price": target_price,
            "history": []
        })

        flash("✅ Tracking started. You'll be notified here if price drops.")

        # Show user's own chart path
        safe_email = email.replace('@', '_at_').replace('.', '_')
        graph_path = f"{safe_email}_price_graph.png"
        return render_template('index.html', graph=graph_path)

    # For GET request (fresh user): always show a clean page
    return render_template('index.html', graph=None)


def send_email(email, message):
    port = 465
    smtp_server = "smtp.gmail.com"
    sender_email = "meetmourya04@gmail.com"
    load_dotenv()
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

            if not price_tag:
                user_updates[email] = "⚠ This site is not supported. Please use an Amazon or Flipkart link."
                return

            price_text = price_tag.text.strip().replace('₹', '').replace(',', '')
            if not price_text:
                print(f"⚠ Attempt {attempt + 1}: Empty price text.")
                continue

            current_price = float(price_text)
            product["history"].append((time.strftime('%H:%M:%S'), current_price))
            update_price_chart(product["history"], email)

            if current_price <= target_price:
                message = f"Your product price has dropped to ₹{current_price} at {time.strftime('%H:%M:%S')}"
                user_updates[email] = f"✅ Price dropped to ₹{current_price}! Email sent. ✅"
                send_email(email, message)
            else:
                user_updates[email] = f"⏳ ₹{current_price} is still above target. Will recheck later."

            return
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed:", e)
            time.sleep(2)

    user_updates[email] = "❌ All attempts to check price failed."

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
    filepath = f'static/{safe_email}_price_graph.png'
    plt.savefig(filepath)
    plt.close()

def price_check_loop():
    while True:
        if products:
            for product in products:
                check_price(product)
            time.sleep(check_interval_seconds)
        else:
            time.sleep(10)

threading.Thread(target=price_check_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
