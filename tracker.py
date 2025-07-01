from flask import Flask, render_template,flash,request
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
app.secret_key='your_secret_key_here'

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0)"
]

check_interval_seconds = 21600 #  Check every 6 hours (21600 seconds)

email_sent = False
products = []  # List of dicts: {url, target_price, email, last_checked_price, etc.}

update_list=""
@app.route('/updates')
def live_updates():
    global update_list
    return update_list


@app.route('/',methods=['GET','POST'])
def home():
    global update_list

    if request.method=='POST':
        url = request.form.get('URL')
        email=request.form.get('email')
        target_price = float(request.form.get('price'))

        products.append({
            "url": url,
            "email": email,
            "target_price": target_price,
            "history": []  # For graph
        })

        flash("✅ Tracking started. You'll be notified here if price drops.")

        update_list = f"✅ Tracking started at {time.strftime('%H:%M:%S')} on {time.strftime('%Y-%m-%d')}. You'll be notified below."
        
        safe_email = email.replace('@', '_at_').replace('.', '_')
        graph_path = f"{safe_email}_price_graph.png"
        
        return render_template('index.html', graph=graph_path)


    return render_template('index.html')

def send_email(email,message):
    port = 465
    smtp_server = "smtp.gmail.com"
    sender_email = "meetmourya04@gmail.com"
    load_dotenv()
    password = os.getenv("Email_password")

    # Email body with UTF-8
    msg = MIMEMultipart()
    msg['Subject'] = "🔔 Price Alert"
    msg['From'] = sender_email
    msg['To'] = email

    # Add UTF-8 encoded message
    msg.attach(MIMEText(message, 'plain', _charset='utf-8'))

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, email, msg.as_string())


    print(f"✅ Email sent to {email}")

price_history=[]
def check_price(product):
    global update_list, email_sent
    
    url = product["url"]
    target_price = product["target_price"]
    email=product["email"]
    

    headers = {
        "User-Agent": random.choice(user_agents),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Connection": "keep-alive"
        }

    for attempt in range(3):

        try:
            time.sleep(random.uniform(3, 6))  # Wait randomly before request between 3-6 seconds
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')

            price_az = soup.find("span", {"class": "a-offscreen"})# use as it can work even after the class changed of price tag on offical page of given url
            price_my = soup.find("span", {"class": "pdp-price"} and soup.find("span", {"class": "pdp-price"}).find("strong"))
            price_fl = soup.find("div", {"class": "Nx9bqj CxhGGd"})
            

            price_tag = price_az or price_fl or price_my

            if price_tag:
                price_text = price_tag.text.strip().replace('₹', '').replace(',', '')

                if not price_text:
                    print(f"⚠ Price text is empty at attempt {attempt + 1}. Retrying...")
                    time.sleep(2)
                    continue

                current_price = float(price_text)
                price_history.append((time.strftime('%H:%M:%S'), current_price))
                product["history"].append((time.strftime('%H:%M:%S'), current_price))
                update_price_chart(product["history"], email)  # Unique chart per user
                

                if current_price <= target_price:
                    update_list= f"\n✅ Checked at {time.strftime('%H:%M:%S')} — Current Price: ₹{current_price} \n 📢 Price has dropped! Time to buy! ✅\n"
                    message = f"""\
                        Subject:  Price Alert

                        Your product price has dropped to ₹{current_price} at {time.strftime('%H:%M:%S')} """
                    send_email(email,message)
                    email_sent=True
                    return f"✅ Email sent at {time.strftime('%H:%M:%S')} — Current Price: ₹{current_price}"

                else:
                    update_list= f"\n✅ Checked at {time.strftime('%H:%M:%S')} — Current Price: ₹{current_price} \n ⏳ Price is still high. Waiting for a better deal...\n"
                    return

            else:
                print(f"⚠ Attempt {attempt + 1}: Couldn't find price. Retrying...")
                time.sleep(2)

        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed with error:", e)
            time.sleep(2)

    print("❌ All attempts failed. Skipping this check.\n")


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

    #saving the png file in static folder
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
            time.sleep(5)

# Using daemon thread to not to kill the thread manually it will automatically shuts down when flask shuts
threading.Thread(target=price_check_loop,daemon=True).start() 

if __name__=='__main__':
    app.run(debug=True)
