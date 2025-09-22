from flask import Flask, request, jsonify
import requests
import json
import os
import csv
from datetime import datetime
from twilio.rest import Client

app = Flask(__name__)
CALL_SUMMARY_FILE = "call_Summary.json"
DEALS_FILE = "deals.json"
NUMBERS_CSV = "numbers.csv"
GEMINI_API_KEY = "AIzaSyA4UV8P9Xg25uOTH2ozEHJimGy_qVO7VN4"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# VAPI Configuration
VAPI_API_KEY = os.getenv("VAPI_API_KEY")

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

def save_call_summary(summary):
    if os.path.exists(CALL_SUMMARY_FILE):
        with open(CALL_SUMMARY_FILE, 'r') as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    else:
        data = []
    data.append(summary)
    with open(CALL_SUMMARY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def save_deal_summary(deal_data):
    if os.path.exists(DEALS_FILE):
        with open(DEALS_FILE, 'r') as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    else:
        data = []
    data.append(deal_data)
    with open(DEALS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def mark_phone_as_done(phone_number):
    if not os.path.exists(NUMBERS_CSV):
        return False
    
    rows = []
    updated = False
    with open(NUMBERS_CSV, 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['phone'].strip() == phone_number.strip():
                row['status'] = 'done'
                updated = True
            rows.append(row)
    
    if updated:
        with open(NUMBERS_CSV, 'w', newline='') as file:
            fieldnames = ['phone', 'name', 'status']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return True
    return False

def detect_deal_in_summary(summary):
    deal_keywords = [
        "deal closed", "sale made", "purchase confirmed", "agreement reached",
        "signed up", "bought", "committed", "order placed", "transaction complete"
    ]
    summary_lower = summary.lower()
    for keyword in deal_keywords:
        if keyword in summary_lower:
            return True
    return False




@app.route('/vapi-webhook', methods=['POST'])
def vapi_webhook():
    req_data = request.get_json()

    # For outbound calls only, assume voice_call type
    conversation_type = 'voice_call'  # Force voice_call for outbound

    # Handle voice call summary
    prompt = f"Summarize this outbound sales call report: {req_data}. Include key topics discussed, customer name, phone number, email if mentioned, deal status (if deal was closed, mention explicitly), and important details."

    gemini_payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    gemini_response = requests.post(
            GEMINI_API_URL,
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": GEMINI_API_KEY
            },
            json=gemini_payload
        )
    print("Gemini API response status:", gemini_response.status_code)
    print("Gemini API response body:", gemini_response.text)
    if gemini_response.status_code == 200:
        gemini_data = gemini_response.json()
        # Try to extract summary text robustly
        summary = None
        # Gemini REST API returns 'candidates' -> [0] -> 'content' -> 'parts' -> [0] -> 'text'
        try:
            summary = gemini_data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            summary = gemini_data.get("text") or gemini_data.get("output") or "No summary generated."
    else:
        summary = f"Gemini API error: {gemini_response.text}"

    # Get phone number from request
    user_phone = req_data.get('customer', {}).get('number', 'N/A')

    # Detect if deal was done
    deal_done = detect_deal_in_summary(summary)

    # Store summary
    summary_record = {
        "timestamp": datetime.now().isoformat(),
        "type": "voice_call",
        "summary": summary,
        "conversation_id": req_data.get('callId', 'N/A'),
        "user_phone": user_phone,
        "assistant_id": req_data.get('assistantId', 'N/A'),
        "duration": req_data.get('duration', 'N/A'),
        "status": req_data.get('status', 'N/A'),
        "deal_done": deal_done,
        "raw": req_data
    }
    save_call_summary(summary_record)

    # If deal done, mark in CSV and save deal summary
    if deal_done and user_phone != 'N/A':
        mark_phone_as_done(user_phone)
        deal_record = {
            "timestamp": datetime.now().isoformat(),
            "phone": user_phone,
            "summary": summary,
            "deal_details": req_data
        }
        save_deal_summary(deal_record)
        print(f"Deal closed for {user_phone}, marked as done in CSV")

    return jsonify({"summary": summary, "type": "voice_call", "deal_done": deal_done})
       

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
