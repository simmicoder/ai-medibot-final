import os, sqlite3, threading, requests, logging
from flask import Flask, render_template, request, jsonify
from random import uniform, randint, choice
from datetime import datetime
import pyttsx3

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "databases", "meds.db")

# TextBee credentials (updated)
TEXTBEE_API = "https://api.textbee.dev/api/v1"
API_KEY = "e1735361-5065-49d0-849f-863ccbe135de"
DEVICE_ID = "685c0d24279700d071eeaa09"
RECIPIENT_NUM = "+919321830156"

def send_doctor_sms():
    resp = requests.post(
        f"{TEXTBEE_API}/gateway/devices/{DEVICE_ID}/send-sms",
        headers={'x-api-key': API_KEY},
        json={'recipients': [RECIPIENT_NUM],
              'message': 'MediBot Alert: Please consult this patient.'}
    )
    data = resp.json()
    logging.info("TextBee response: %s", data)
    nested = data.get('data') or {}
    return nested.get('success', False), nested.get('message', '')

def speak(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def speak_async(text):
    threading.Thread(target=speak, args=(text,), daemon=True).start()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            temperature REAL,
            heart_rate INTEGER,
            systolic INTEGER,
            diastolic INTEGER,
            spo2 INTEGER,
            symptoms TEXT,
            suggested_med TEXT
        )
    """)
    conn.commit()
    conn.close()

def generate_vitals():
    return {
        "temperature": round(uniform(36.0,39.0),1),
        "heart_rate": randint(50,120),
        "systolic": randint(85,150),
        "diastolic": randint(55,95),
        "spo2": randint(90,100),
        "timestamp": datetime.utcnow().isoformat()
    }

def suggest_med(symptoms, vitals):
    s = symptoms.lower()
    t = vitals["temperature"]; h = vitals["heart_rate"]
    sbp = vitals["systolic"]; dbp = vitals["diastolic"]; spo2 = vitals["spo2"]
    alerts = []
    if t > 37.5: alerts.append("High temperature")
    if h > 100: alerts.append("High heart rate")
    if sbp > 140 or dbp > 90: alerts.append("High blood pressure")
    if spo2 < 94: alerts.append("Low SpO₂")

    # Expanded: 20+ symptom checks
    if "fever" in s and "cough" in s:
        med = "Paracetamol and cough syrup"
    elif "headache" in s:
        med = "Ibuprofen"
    elif "cold" in s or "sneezing" in s:
        med = "Cetrizine"
    elif "nausea" in s or "vomit" in s:
        med = "Ondem"
    elif "stomach" in s or "ache" in s:
        med = "Antacid"
    elif "constipation" in s:
        med = "Stool softener"
    elif "diarrhea" in s or "loose motion" in s:
        med = "ORS + Loperamide"
    elif "heartburn" in s or "acid reflux" in s:
        med = "Omeprazole"
    elif "dizziness" in s or "vertigo" in s:
        med = "Meclizine"
    elif "fatigue" in s or "tired" in s:
        med = "Multivitamin + rest"
    elif "insomnia" in s or "sleep" in s:
        med = "Mild sleep aid"
    elif "anxiety" in s or "nervous" in s:
        med = "Chamomile tea"
    elif "rash" in s or "itch" in s:
        med = "Hydrocortisone cream"
    elif "hives" in s or "allergy" in s:
        med = "Cetirizine"
    elif "ear pain" in s or "earache" in s:
        med = "Ear drops"
    elif "toothache" in s:
        med = "Ibuprofen + dentist"
    elif "sore throat" in s or "throat" in s:
        med = "Lozenges or gargle"
    elif "sinus" in s or "congestion" in s:
        med = "Decongestant + saline spray"
    elif "back pain" in s or "muscle" in s:
        med = "Muscle relaxant spray"
    elif "joint pain" in s:
        med = "NSAID cream"
    elif "eye pain" in s or "vision" in s:
        med = "Eye drops"
    elif alerts:
        med = "Consult a doctor"
    else:
        med = "Rest and monitor"

    return med, alerts

def check_stock(med):
    return choice([True,False]), "https://www.example.com/order"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vitals')
def vitals():
    return jsonify(generate_vitals())

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    vit = data['vitals']; sym = data['symptoms']
    med, alerts = suggest_med(sym, vit)
    in_stock, order_url = check_stock(med)

    if med == "Consult a doctor":
        ok,msg = send_doctor_sms()
        alerts.append("Doctor SMS sent ✔️" if ok else f"Doctor SMS failed: {msg}")

    speak_async(f"Medicine: {med}. " + ("In stock." if in_stock else "Out of stock."))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO entries
        (timestamp,temperature,heart_rate,systolic,diastolic,spo2,symptoms,suggested_med)
        VALUES (?,?,?,?,?,?,?,?)""", (
        datetime.utcnow().isoformat(), vit["temperature"], vit["heart_rate"],
        vit["systolic"], vit["diastolic"], vit["spo2"], sym, med))
    conn.commit(); conn.close()

    return jsonify({
        "suggested_med": med,
        "alerts": alerts,
        "in_stock": in_stock,
        "order_url": order_url
    })

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
